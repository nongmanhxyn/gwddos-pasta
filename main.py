import discord
from discord import app_commands
from discord.ext import commands
import os
import word

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Bộ lưu trữ ván chơi
games = {}

def render_board(guesses, target):
    lines = []
    for g in guesses:
        res = ["⬛"] * 5
        t_list = list(target)
        g_list = list(g)

        # Check chữ đúng vị trí (Xanh)
        for i in range(5):
            if g_list[i] == t_list[i]:
                res[i] = "🟩"
                t_list[i] = None

        # Check chữ có trong từ nhưng sai vị trí (Vàng)
        for i in range(5):
            if res[i] != "🟩" and g_list[i] in t_list and g_list[i] is not None:
                res[i] = "🟨"
                t_list[t_list.index(g_list[i])] = None

        lines.append(f"{''.join(res)}  {g}")

    # Đệm ô trống cho đủ 6 dòng
    while len(lines) < 6:
        lines.append("⬛⬛⬛⬛⬛")

    return "\n".join(lines)


# 1. Lệnh bắt đầu chơi
@bot.tree.command(name="play", description="Bắt đầu ván chơi Wordle")
async def play(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id in games:
        await interaction.response.send_message("Bro đang trong ván chơi rồi! Dùng `/guess` để đoán tiếp.", ephemeral=True)
        return

    # Trả lời tạm thời để tránh bị timeout interaction 3s
    await interaction.response.defer()

    secret = word.choose_answer()
    board_text = render_board([], secret)
    content = f"<@{user_id}> is playing\n```\n{board_text}\n```\n👉 *Dùng lệnh `/guess <từ>` để đoán!*"

    # Gửi tin nhắn chứa bàn chơi
    main_msg = await interaction.followup.send(content=content)

    games[user_id] = {
        "answer": secret,
        "guesses": [],
        "attempts": 0,
        "message_id": main_msg.id,
        "channel_id": interaction.channel_id
    }


# 2. Lệnh đoán từ
@bot.tree.command(name="guess", description="Đoán từ trong ván chơi Wordle")
@app_commands.describe(dudoan="Từ 5 chữ cái muốn đoán")
async def guess(interaction: discord.Interaction, dudoan: str):
    user_id = interaction.user.id
    game = games.get(user_id)

    # Detect chỉ người đang trong game mới đoán được
    if not game:
        await interaction.response.send_message("Bro chưa tạo ván chơi! Hãy gõ `/play` để bắt đầu.", ephemeral=True)
        return

    user_guess = dudoan.strip().upper()

    # Kiểm tra từ hợp lệ
    if len(user_guess) != 5 or not word.check(user_guess):
        await interaction.response.send_message(f"Từ `{user_guess}` không hợp lệ hoặc không có trong từ điển!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    game["guesses"].append(user_guess)
    game["attempts"] += 1

    new_board = render_board(game["guesses"], game["answer"])

    # Lấy lại tin nhắn bàn chơi để EDIT
    try:
        channel = bot.get_channel(game["channel_id"])
        main_msg = await channel.fetch_message(game["message_id"])

        if user_guess == game["answer"]:
            content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n🎉 **Chúc mừng! Bạn đã thắng! Đáp án: `{game['answer']}`**"
            await main_msg.edit(content=content)
            await interaction.followup.send("Đoán chính xác!", ephemeral=True)
            del games[user_id]

        elif game["attempts"] >= 6:
            content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n💀 **Bạn đã hết lượt! Đáp án đúng là: `{game['answer']}`**"
            await main_msg.edit(content=content)
            await interaction.followup.send("Rất tiếc, bạn đã thua!", ephemeral=True)
            del games[user_id]

        else:
            content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n👉 *Dùng lệnh `/guess <từ>` tiếp theo...*"
            await main_msg.edit(content=content)
            await interaction.followup.send(f"Đã cập nhật lượt đoán `{user_guess}`!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Lỗi cập nhật bàn chơi: {e}", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Bot {bot.user} da online!")
    try:
        synced = await bot.tree.sync()
        print(f"Da sync {len(synced)} lenh Slash!")
    except Exception as e:
        print(f"Loi sync lenh: {e}")

if TOKEN:
    bot.run(TOKEN)
