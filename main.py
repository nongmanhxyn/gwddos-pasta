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

# Bộ lưu trữ ván chơi: { user_id: {data} }
games = {}

# Lưu mốc thời gian chơi gần nhất của từng user để check cooldown (1 tiếng): { user_id: timestamp }
cooldowns = {}

def render_board(guesses, target):
    lines = []
    for g in guesses:
        res = ["⬛"] * 5
        t_list = list(target)
        g_list = list(g)

        # Check xanh
        for i in range(5):
            if g_list[i] == t_list[i]:
                res[i] = "🟩"
                t_list[i] = None

        # Check vàng
        for i in range(5):
            if res[i] != "🟩" and g_list[i] in t_list and g_list[i] is not None:
                res[i] = "🟨"
                t_list[t_list.index(g_list[i])] = None

        lines.append(f"{' '.join(res)}   **{g}**")

    while len(lines) < 6:
        lines.append("⬛ ⬛ ⬛ ⬛ ⬛")

    return "\n".join(lines)


# task định kỳ --> tránh nặng ram
@tasks.loop(hours=1.0)
async def clean_cooldowns():
    current_time = time.time()
    expired_users = [uid for uid, t in cooldowns.items() if current_time - t >= 3600]
    for uid in expired_users:
        del cooldowns[uid]


# 1. Lệnh Ping check độ trễ
@bot.tree.command(name="ping", description="ping pong🏓")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 (`{latency}ms`)", ephemeral=True)


# 2. Lệnh Play (Có check Cooldown 1 tiếng & Timeout 5 phút tự động hủy)
@bot.tree.command(name="play", description="Start wordle?")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def play(interaction: discord.Interaction):
    user_id = interaction.user.id
    current_time = time.time()

    # Kiểm tra Cooldown 1 tiếng
    if user_id in cooldowns:
        elapsed = current_time - cooldowns[user_id]
        if elapsed < 3600:
            remaining_min = math.ceil((3600 - elapsed) / 60)
            await interaction.response.send_message(f"⏳ Bro đang trong thời gian chờ cooldown! Vui lòng đợi khoảng **{remaining_min} phút** nữa để chơi ván mới.", ephemeral=True)
            return

    if user_id in games:
        await interaction.response.send_message("Bro đang có ván chơi dở dang! Dùng `/guess` để tiếp tục.", ephemeral=True)
        return

    await interaction.response.defer()

    secret = word.choose_answer()
    board_text = render_board([], secret)
    
    # Tạo Embed cho ván mới
    embed = discord.Embed(
        title="🎮 WORDLE GAME",
        description=f"<@{user_id}> is playing\n\n{board_text}",
        color=discord.Color.blue()
    )
    embed.set_footer(text="👉 Dùng lệnh /guess <từ> để đoán!")

    main_msg = await interaction.followup.send(embed=embed)

    # Ghi nhận thời gian chơi vào cooldown
    cooldowns[user_id] = current_time

    # Lưu ván chơi vào games trước khi tạo task timeout
    games[user_id] = {
        "answer": secret,
        "guesses": [],
        "attempts": 0,
        "message_obj": main_msg,
        "timeout_task": None
    }

    # Tạo đối tượng quản lý timeout ván đấu (5 phút = 300 giây)
    async def timeout_task():
        await asyncio.sleep(300)
        if user_id in games and games[user_id]["message_obj"].id == main_msg.id:
            expired_board = render_board(games[user_id]["guesses"], games[user_id]["answer"])
            
            timeout_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{expired_board}",
                color=discord.Color.red()
            )
            timeout_embed.set_footer(text=f"⏰ Timed out! Đáp án là: {games[user_id]['answer']}")
            
            try:
                await main_msg.edit(embed=timeout_embed)
            except:
                pass
            del games[user_id]

    games[user_id]["timeout_task"] = asyncio.create_task(timeout_task())


# 3. Lệnh Đoán từ
@bot.tree.command(name="guess", description="Guess word")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(dudoan="Từ 5 chữ cái muốn đoán")
async def guess(interaction: discord.Interaction, dudoan: str):
    user_id = interaction.user.id
    game = games.get(user_id)

    if not game:
        await interaction.response.send_message("Bro chưa bắt đầu ván chơi nào! Gõ `/play` để chơi.", ephemeral=True)
        return

    user_guess = dudoan.strip().upper()

    if len(user_guess) != 5 or not word.check(user_guess):
        await interaction.response.send_message(f"Từ `{user_guess}` không hợp lệ hoặc không có trong từ điển!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    game["guesses"].append(user_guess)
    game["attempts"] += 1

    new_board = render_board(game["guesses"], game["answer"])

    try:
        main_msg = game["message_obj"]

        if user_guess == game["answer"]:
            game["timeout_task"].cancel()
            
            win_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{new_board}",
                color=discord.Color.green()
            )
            win_embed.set_footer(text=f"🎉 Chúc mừng! Bạn đã thắng! Đáp án: {game['answer']}")
            
            await main_msg.edit(embed=win_embed)
            await interaction.followup.send("Đoán chính xác!", ephemeral=True)
            del games[user_id]

        elif game["attempts"] >= 6:
            game["timeout_task"].cancel()
            
            lose_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{new_board}",
                color=discord.Color.red()
            )
            lose_embed.set_footer(text=f"💀 Hết lượt! Đáp án đúng là: {game['answer']}")
            
            await main_msg.edit(embed=lose_embed)
            await interaction.followup.send("Rất tiếc, bạn đã thua!", ephemeral=True)
            del games[user_id]

        else:
            play_embed = discord.Embed(
                title="🎮 WORDLE GAME",
                description=f"<@{user_id}> is playing\n\n{new_board}",
                color=discord.Color.blue()
            )
            play_embed.set_footer(text="👉 Dùng lệnh /guess <từ> tiếp theo...")
            
            await main_msg.edit(embed=play_embed)
            await interaction.followup.send(f"Đã nhận từ `{user_guess}`!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Lỗi: {e}", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Bot {bot.user} da online và sẵn sàng!")
    if not clean_cooldowns.is_running():
        clean_cooldowns.start()
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} lệnh Slash!")
    except Exception as e:
        print(f"Lỗi sync: {e}")

if TOKEN:
    bot.run(TOKEN)
