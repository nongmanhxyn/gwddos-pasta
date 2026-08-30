import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import word

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Bộ lưu trữ ván chơi
games = {}

def render_board(guesses, target):
    lines = []
    for g in guesses:
        res = ["⬛"] * 5
        t_list = list(target)
        g_list = list(g)

        # Lần 1: Check chữ đúng vị trí (Xanh)
        for i in range(5):
            if g_list[i] == t_list[i]:
                res[i] = "🟩"
                t_list[i] = None  # Loại bỏ chữ đã xanh để không trùng với check vàng

        # Lần 2: Check chữ có trong từ nhưng sai vị trí (Vàng)
        for i in range(5):
            # CHỈ check những ô chưa thành màu xanh
            if res[i] != "🟩" and g_list[i] in t_list and g_list[i] is not None:
                res[i] = "🟨"
                t_list[t_list.index(g_list[i])] = None

        lines.append(f"{''.join(res)}  {g}")

    # Đệm ô trống cho đủ 6 dòng
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
    main_msg = await interaction.original_response()

    games[user_id] = {
        "answer": secret,
        "guesses": [],
        "attempts": 0,
        "message_id": main_msg.id
    }

    def check_user(m):
        return m.author.id == user_id and m.channel.id == interaction.channel_id

    while games.get(user_id) and games[user_id]["attempts"] < 6:
        try:
            guess_msg = await bot.wait_for("message", check=check_user, timeout=180.0)
            user_guess = guess_msg.content.strip().upper()

            try:
                await guess_msg.delete()
            except:
                pass

            if len(user_guess) != 5 or not word.check(user_guess):
                continue

            game = games[user_id]
            game["guesses"].append(user_guess)
            game["attempts"] += 1

            new_board = render_board(game["guesses"], game["answer"])

            if user_guess == game["answer"]:
                updated_content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n🎉 **Chúc mừng! Bạn đã đoán đúng từ: `{game['answer']}`**"
                await main_msg.edit(content=updated_content)
                del games[user_id]
                break

            elif game["attempts"] >= 6:
                updated_content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n💀 **Bạn đã hết lượt! Đáp án là: `{game['answer']}`**"
                await main_msg.edit(content=updated_content)
                del games[user_id]
                break

            else:
                updated_content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n👉 *Nhập từ tiếp theo...*"
                await main_msg.edit(content=updated_content)

        except asyncio.TimeoutError:
            if user_id in games:
                await main_msg.edit(content=f"<@{user_id}> is playing\n```\n{render_board(games[user_id]['guesses'], games[user_id]['answer'])}\n```\n⏰ **Hết thời gian chờ!**")
                del games[user_id]
            break

@bot.event
async def on_ready():
    print(f"Bot {bot.user} da dang nhap thanh cong!")
    try:
        synced = await bot.tree.sync()
        print(f"Da sync {len(synced)} lenh Slash!")
    except Exception as e:
        print(f"Loi sync lenh: {e}")

if TOKEN:
    bot.run(TOKEN)
else:
    print("Loi: Chua thiet lap BOT_TOKEN trong bien moi truong!")
