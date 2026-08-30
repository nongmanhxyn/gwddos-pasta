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

games = {}
matches = {}
cooldowns = {}

def render_board(guesses, target):
    lines = []
    for g in guesses:
        res = ["⬛"] * 5
        t_list = list(target)
        g_list = list(g)

        for i in range(5):
            if g_list[i] == t_list[i]:
                res[i] = "🟩"
                t_list[i] = None

        for i in range(5):
            if res[i] != "🟩" and g_list[i] in t_list and g_list[i] is not None:
                res[i] = "🟨"
                t_list[t_list.index(g_list[i])] = None

        lines.append(f"{' '.join(res)}   **{g}**")

    while len(lines) < 6:
        lines.append("⬛ ⬛ ⬛ ⬛ ⬛")

    return "\n".join(lines)


def render_match_embed(match):
    p1_name = match["p1_name"]
    p2_name = match["p2_name"]
    
    p1_board = render_board(match["p1_guesses"], match["p1_answer"])
    p2_board = render_board(match["p2_guesses"], match["p2_answer"])
    
    status_text = "⚔️ **Match in progress...** Use `/guess <word>` to play!"
    color = discord.Color.blue()
    
    if match["status"] == "ended":
        color = discord.Color.gold() if match["winner_name"] else discord.Color.dark_grey()
        if match["winner_name"]:
            status_text = f"🏆 **{match['winner_name']} WON THE MATCH!**"
        else:
            status_text = "🤝 **DRAW! Both players ran out of attempts.**"
            
        p1_board += f"\n*Answer: `{match['p1_answer']}`*"
        p2_board += f"\n*Answer: `{match['p2_answer']}`*"

    # Layout xếp dọc toàn bộ trong description
    desc = (
        f"{status_text}\n\n"
        f"👤 **{p1_name}**\n"
        f"{p1_board}\n\n"
        f"───────────────\n\n"
        f"👤 **{p2_name}**\n"
        f"{p2_board}"
    )

    embed = discord.Embed(
        title="⚔️ WORDLE VERSUS DUEL ⚔️",
        description=desc,
        color=color
    )
    embed.set_footer(text="Both players have different secret words for fairness!")
    
    return embed


class ChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.User, opponent: discord.User):
        super().__init__(timeout=300)
        self.challenger = challenger
        self.opponent = opponent

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="⚔️")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can accept this duel!", ephemeral=True)
            return

        p1_id = self.challenger.id
        p2_id = self.opponent.id

        if p1_id in games or p2_id in games:
            await interaction.response.send_message("One of the players is currently in another match!", ephemeral=True)
            return

        self.stop()

        p1_ans = word.choose_answer()
        p2_ans = word.choose_answer()

        match_data = {
            "p1": p1_id,
            "p2": p2_id,
            "p1_name": self.challenger.display_name,
            "p2_name": self.opponent.display_name,
            "p1_answer": p1_ans,
            "p2_answer": p2_ans,
            "p1_guesses": [],
            "p2_guesses": [],
            "p1_done": False,
            "p2_done": False,
            "status": "playing",
            "winner_name": None,
            "message_obj": None
        }

        embed = render_match_embed(match_data)
        
        # Sửa trực tiếp message gốc (giữ tag @user ở content, xoá nút view)
        await interaction.response.edit_message(
            content=f"<@{p1_id}> <@{p2_id}> The duel has begun!", 
            embed=embed, 
            view=None
        )
        
        match_data["message_obj"] = await interaction.original_response()

        matches[p1_id] = match_data
        matches[p2_id] = match_data
        games[p1_id] = {"type": "versus"}
        games[p2_id] = {"type": "versus"}

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, emoji="✖️")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can decline this duel!", ephemeral=True)
            return

        self.stop()
        embed = discord.Embed(
            title="⚔️ VERSUS DUEL DECLINED",
            description=f"**{self.opponent.display_name}** declined the challenge from **{self.challenger.display_name}**.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    async def on_timeout(self):
        embed = discord.Embed(
            title="⚔️ VERSUS DUEL TIMED OUT",
            description=f"The challenge from **{self.challenger.display_name}** to **{self.opponent.display_name}** has expired.",
            color=discord.Color.dark_grey()
        )
        try:
            await self.message.edit(content=None, embed=embed, view=None)
        except:
            pass


@tasks.loop(minutes=30.0)
async def clean_cooldowns():
    current_time = time.time()
    expired_users = [uid for uid, t in cooldowns.items() if current_time - t >= 1800]
    for uid in expired_users:
        del cooldowns[uid]


@bot.tree.command(name="ping", description="Check latency 🏓")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 (`{latency}ms`)", ephemeral=True)


@bot.tree.command(name="match", description="Challenge another user to a Wordle Duel!")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(opponent="The user you want to challenge")
async def match(interaction: discord.Interaction, opponent: discord.User):
    if opponent.bot:
        await interaction.response.send_message("You cannot challenge a bot!", ephemeral=True)
        return
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You cannot challenge yourself!", ephemeral=True)
        return

    if interaction.user.id in games or opponent.id in games:
        await interaction.response.send_message("One of you is already in an active game!", ephemeral=True)
        return

    view = ChallengeView(challenger=interaction.user, opponent=opponent)
    
    embed = discord.Embed(
        title="⚔️ WORDLE VERSUS CHALLENGE",
        description=f"**{interaction.user.display_name}** has challenged **{opponent.display_name}** to a Versus Duel!\n\n"
                    f"**Rules:**\n"
                    f"• Both players get different secret words.\n"
                    f"• First player to guess their word correctly wins!\n"
                    f"• You have 5 minutes to accept this challenge.",
        color=discord.Color.gold()
    )
    
    await interaction.response.send_message(content=f"<@{opponent.id}>", embed=embed, view=view)
    view.message = await interaction.original_response()


@bot.tree.command(name="play", description="Start a solo Wordle game")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def play(interaction: discord.Interaction):
    user_id = interaction.user.id
    current_time = time.time()

    if user_id in cooldowns:
        elapsed = current_time - cooldowns[user_id]
        if elapsed < 1800:
            remaining_min = math.ceil((1800 - elapsed) / 60)
            await interaction.response.send_message(f"⏳ You are on cooldown! Please wait **{remaining_min} minute(s)**.", ephemeral=True)
            return

    if user_id in games:
        await interaction.response.send_message("You are already in an active game! Use `/guess` to play.", ephemeral=True)
        return

    await interaction.response.defer()

    secret = word.choose_answer()
    board_text = render_board([], secret)
    
    embed = discord.Embed(
        title="🎮 WORDLE GAME",
        description=f"**{interaction.user.display_name}** is playing\n\n{board_text}",
        color=discord.Color.blue()
    )
    embed.set_footer(text="👉 Use /guess <word> to place your guess!")

    main_msg = await interaction.followup.send(embed=embed)
    cooldowns[user_id] = current_time

    async def timeout_task():
        await asyncio.sleep(600)
        if user_id in games and games[user_id].get("message_obj") and games[user_id]["message_obj"].id == main_msg.id:
            expired_board = render_board(games[user_id]["guesses"], games[user_id]["answer"])
            
            timeout_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"**{interaction.user.display_name}** is playing\n\n{expired_board}",
                color=discord.Color.red()
            )
            timeout_embed.set_footer(text=f"⏰ Timed out! The answer was: {games[user_id]['answer']}")
            
            try:
                await main_msg.edit(embed=timeout_embed)
            except:
                pass
            games.pop(user_id, None)

    games[user_id] = {
        "type": "solo",
        "answer": secret,
        "guesses": [],
        "attempts": 0,
        "message_obj": main_msg,
        "timeout_task": asyncio.create_task(timeout_task())
    }


@bot.tree.command(name="guess", description="Guess a 5-letter word")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(dudoan="Your 5-letter word guess")
async def guess(interaction: discord.Interaction, dudoan: str):
    user_id = interaction.user.id
    game = games.get(user_id)

    if not game:
        await interaction.response.send_message("You don't have an active game! Type `/play` or `/match` to start.", ephemeral=True)
        return

    user_guess = dudoan.strip().upper()

    if len(user_guess) != 5 or not word.check(user_guess):
        await interaction.response.send_message(f"The word `{user_guess}` is invalid or not in the dictionary!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if game.get("type") == "versus":
        match_data = matches.get(user_id)
        if not match_data or match_data["status"] == "ended":
            await interaction.followup.send("This match has already ended!", ephemeral=True)
            return

        is_p1 = (user_id == match_data["p1"])
        guesses = match_data["p1_guesses"] if is_p1 else match_data["p2_guesses"]
        target = match_data["p1_answer"] if is_p1 else match_data["p2_answer"]
        is_done = match_data["p1_done"] if is_p1 else match_data["p2_done"]

        if is_done:
            await interaction.followup.send("You have already finished your attempts!", ephemeral=True)
            return

        guesses.append(user_guess)
        
        if user_guess == target:
            if is_p1:
                match_data["p1_done"] = True
            else:
                match_data["p2_done"] = True
            
            match_data["status"] = "ended"
            match_data["winner_name"] = match_data["p1_name"] if is_p1 else match_data["p2_name"]

        elif len(guesses) >= 6:
            if is_p1:
                match_data["p1_done"] = True
            else:
                match_data["p2_done"] = True

            if match_data["p1_done"] and match_data["p2_done"]:
                match_data["status"] = "ended"

        updated_embed = render_match_embed(match_data)
        try:
            await match_data["message_obj"].edit(embed=updated_embed)
        except:
            pass

        if match_data["status"] == "ended":
            games.pop(match_data["p1"], None)
            games.pop(match_data["p2"], None)
            matches.pop(match_data["p1"], None)
            matches.pop(match_data["p2"], None)

        await interaction.followup.send(f"Received word `{user_guess}`!", ephemeral=True)
        return

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
                description=f"**{interaction.user.display_name}** is playing\n\n{new_board}",
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
                description=f"**{interaction.user.display_name}** is playing\n\n{new_board}",
                color=discord.Color.red()
            )
            lose_embed.set_footer(text=f"💀 Out of attempts! The correct answer was: {game['answer']}")
            
            await main_msg.edit(embed=lose_embed)
            await interaction.followup.send("Game over! Better luck next time.", ephemeral=True)
            games.pop(user_id, None)

        else:
            play_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"**{interaction.user.display_name}** is playing\n\n{new_board}",
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
