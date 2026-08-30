import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import os
import math
import time
import word

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Game storage: { user_id: {data} }
games = {}

# Cooldown storage (30 minutes): { user_id: timestamp }
cooldowns = {}

def render_board(guesses, target):
    lines = []
    for g in guesses:
        res = ["⬛"] * 5
        t_list = list(target)
        g_list = list(g)

        # Check green
        for i in range(5):
            if g_list[i] == t_list[i]:
                res[i] = "🟩"
                t_list[i] = None

        # Check yellow
        for i in range(5):
            if res[i] != "🟩" and g_list[i] in t_list and g_list[i] is not None:
                res[i] = "🟨"
                t_list[t_list.index(g_list[i])] = None

        lines.append(f"{' '.join(res)}   **{g}**")

    while len(lines) < 6:
        lines.append("⬛ ⬛ ⬛ ⬛ ⬛")

    return "\n".join(lines)


# Periodic task to clear expired cooldowns (every 30 mins)
@tasks.loop(minutes=30.0)
async def clean_cooldowns():
    current_time = time.time()
    expired_users = [uid for uid, t in cooldowns.items() if current_time - t >= 1800]
    for uid in expired_users:
        del cooldowns[uid]


# 1. Ping Command
@bot.tree.command(name="ping", description="Check latency 🏓")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 (`{latency}ms`)", ephemeral=True)


# 2. Play Command (30-min Cooldown & 10-min Timeout)
@bot.tree.command(name="play", description="Start a Wordle game")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def play(interaction: discord.Interaction):
    user_id = interaction.user.id
    current_time = time.time()

    # Check 30-minute Cooldown
    if user_id in cooldowns:
        elapsed = current_time - cooldowns[user_id]
        if elapsed < 1800:
            remaining_min = math.ceil((1800 - elapsed) / 60)
            await interaction.response.send_message(f"⏳ You are on cooldown! Please wait **{remaining_min} minute(s)** before starting a new game.", ephemeral=True)
            return

    if user_id in games:
        await interaction.response.send_message("You already have an active game! Use `/guess` to continue.", ephemeral=True)
        return

    await interaction.response.defer()

    secret = word.choose_answer()
    board_text = render_board([], secret)
    
    # New Game Embed
    embed = discord.Embed(
        title="🎮 WORDLE GAME",
        description=f"<@{user_id}> is playing\n\n{board_text}",
        color=discord.Color.blue()
    )
    embed.set_footer(text="👉 Use /guess <word> to place your guess!")

    main_msg = await interaction.followup.send(embed=embed)

    # Save cooldown timestamp
    cooldowns[user_id] = current_time

    # Timeout task (10 minutes = 600 seconds)
    async def timeout_task():
        await asyncio.sleep(600)
        if user_id in games and games[user_id]["message_obj"].id == main_msg.id:
            expired_board = render_board(games[user_id]["guesses"], games[user_id]["answer"])
            
            timeout_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{expired_board}",
                color=discord.Color.red()
            )
            timeout_embed.set_footer(text=f"⏰ Timed out! The answer was: {games[user_id]['answer']}")
            
            try:
                await main_msg.edit(embed=timeout_embed)
            except:
                pass
            games.pop(user_id, None)

    # Save active game to dictionary
    games[user_id] = {
        "answer": secret,
        "guesses": [],
        "attempts": 0,
        "message_obj": main_msg,
        "timeout_task": asyncio.create_task(timeout_task())
    }


# 3. Guess Command
@bot.tree.command(name="guess", description="Guess a 5-letter word")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(dudoan="Your 5-letter word guess")
async def guess(interaction: discord.Interaction, dudoan: str):
    user_id = interaction.user.id
    game = games.get(user_id)

    if not game:
        await interaction.response.send_message("You don't have an active game! Type `/play` to start one.", ephemeral=True)
        return

    user_guess = dudoan.strip().upper()

    if len(user_guess) != 5 or not word.check(user_guess):
        await interaction.response.send_message(f"The word `{user_guess}` is invalid or not in the dictionary!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    game["guesses"].append(user_guess)
    game["attempts"] += 1

    new_board = render_board(game["guesses"], game["answer"])

    try:
        main_msg = game["message_obj"]

        if user_guess == game["answer"]:
            if game["timeout_task"]:
                game["timeout_task"].cancel()
            
            win_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{new_board}",
                color=discord.Color.green()
            )
            win_embed.set_footer(text=f"🎉 Congratulations! You won! Answer: {game['answer']}")
            
            await main_msg.edit(embed=win_embed)
            await interaction.followup.send("Correct guess!", ephemeral=True)
            games.pop(user_id, None)

        elif game["attempts"] >= 6:
            if game["timeout_task"]:
                game["timeout_task"].cancel()
            
            lose_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{new_board}",
                color=discord.Color.red()
            )
            lose_embed.set_footer(text=f"💀 Out of attempts! The correct answer was: {game['answer']}")
            
            await main_msg.edit(embed=lose_embed)
            await interaction.followup.send("Game over! Better luck next time.", ephemeral=True)
            games.pop(user_id, None)

        else:
            play_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{new_board}",
                color=discord.Color.blue()
            )
            play_embed.set_footer(text="👉 Use /guess <word> for your next guess...")
            
            await main_msg.edit(embed=play_embed)
            await interaction.followup.send(f"Received word `{user_guess}`!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Bot {bot.user} is online and ready!")
    if not clean_cooldowns.is_running():
        clean_cooldowns.start()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)!")
    except Exception as e:
        print(f"Sync error: {e}")

if TOKEN:
    bot.run(TOKEN)
