import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import word

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # Bắt buộc bật Intent này trên Developer Portal
bot = commands.Bot(command_prefix="!", intents=intents)

# Bộ lưu trữ ván chơi
games = {}

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

        lines.append(f"{''.join(res)}  {g}")

    # Đệm ô trống
    while len(lines) < 6:
        lines.append("⬛⬛⬛⬛⬛")

    return "\n".join(lines)


@bot.tree.command(name="play", description="Chơi Wordle")
async def play(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id in games:
        await interaction.response.send_message("Bro đang trong ván chơi rồi! Hãy đoán tiếp ở tin nhắn cũ.", ephemeral=True)
        return

    secret = word.choose_answer()
    board_text = render_board([], secret)

    msg_content = f"<@{user_id}> is playing\n```\n{board_text}\n```\n👉 *Hãy gõ từ 5 chữ cái trực tiếp vào chat để đoán!*"
    
    await interaction.response.send_message(msg_content)
    # Lấy message object vừa gửi
    main_msg = await interaction.original_response()

    # Lưu dữ liệu ván chơi
    games[user_id] = {
        "answer": secret,
        "guesses": [],
        "attempts": 0,
        "message_id": main_msg.id
    }

    # Hàm filter: CHỈ nhận tin nhắn từ ĐÚNG NGƯỜI CHƠI + CÙNG CHANNEL
    def check_user(m):
        return m.author.id == user_id and m.channel.id == interaction.channel_id

    # Vòng lặp lắng nghe tối đa 6 lượt đoán
    while games.get(user_id) and games[user_id]["attempts"] < 6:
        try:
            # Chờ người chơi gõ từ vào chat (timeout 3 phút)
            guess_msg = await bot.wait_for("message", check=check_user, timeout=180.0)
            user_guess = guess_msg.content.strip().upper()

            # Tự động xóa tin nhắn đoán của người chơi cho sạch chat
            try:
                await guess_msg.delete()
            except:
                pass

            # Check từ hợp lệ
            if len(user_guess) != 5 or not word.check(user_guess):
                continue

            # Cập nhật lượt đoán
            game = games[user_id]
            game["guesses"].append(user_guess)
            game["attempts"] += 1

            new_board = render_board(game["guesses"], game["answer"])

            # Thắng
            if user_guess == game["answer"]:
                updated_content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n🎉 **Chúc mừng! Bạn đã đoán đúng từ: `{game['answer']}`**"
                await main_msg.edit(content=updated_content)
                del games[user_id]
                break

            # Thua (hết 6 lượt)
            elif game["attempts"] >= 6:
                updated_content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n💀 **Bạn đã hết lượt! Đáp án là: `{game['answer']}`**"
                await main_msg.edit(content=updated_content)
                del games[user_id]
                break

            # Chưa xong -> EDIT lại khung game
            else:
                updated_content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n👉 *Nhập từ tiếp theo...*"
                await main_msg.edit(content=updated_content)

        except asyncio.TimeoutError:
            # Quá 3p không gõ thì hủy ván
            if user_id in games:
                await main_msg.edit(content=f"<@{user_id}> is playing\n```\n{render_board(games[user_id]['guesses'], games[user_id]['answer'])}\n```\n⏰ **Hết thời gian chờ!**")
                del games[user_id]
            break

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ready!")

bot.run(TOKEN)
