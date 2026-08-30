import discord
from discord import app_commands
from discord.ext import commands
import os
import word

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

games = {}

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

        lines.append(f"{''.join(res)}  {g}")

    while len(lines) < 6:
        lines.append("⬛⬛⬛⬛⬛")

    return "\n".join(lines)

# 1. Ô nhập từ (Modal)
class GuessModal(discord.ui.Modal, title="Đoán từ Wordle"):
    guess_input = discord.ui.TextInput(
        label="Nhập từ 5 chữ cái",
        placeholder="VD: APPLE",
        min_length=5,
        max_length=5,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        game = games.get(user_id)

        if not game:
            await interaction.response.send_message("Không tìm thấy ván chơi!", ephemeral=True)
            return

        user_guess = self.guess_input.value.strip().upper()

        if not word.check(user_guess):
            await interaction.response.send_message(f"Từ `{user_guess}` không hợp lệ!", ephemeral=True)
            return

        game["guesses"].append(user_guess)
        game["attempts"] += 1

        new_board = render_board(game["guesses"], game["answer"])

        if user_guess == game["answer"]:
            content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n🎉 **Chúc mừng! Bạn đã thắng! Đáp án: `{game['answer']}`**"
            await interaction.response.edit_message(content=content, view=None)
            del games[user_id]
        elif game["attempts"] >= 6:
            content = f"<@{user_id}> is playing\n```\n{new_board}\n```\n💀 **Bạn đã thua! Đáp án: `{game['answer']}`**"
            await interaction.response.edit_message(content=content, view=None)
            del games[user_id]
        else:
            content = f"<@{user_id}> is playing\n```\n{new_board}\n```"
            await interaction.response.edit_message(content=content)

# 2. Nút bấm kèm theo tin nhắn
class WordleView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    @discord.ui.button(label="Nhập từ đoán 📝", style=discord.ButtonStyle.primary)
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # DETECT CHỈ ĐÚNG THẰNG ĐANG CHƠI MỚI ĐƯỢC DÙNG
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Đây không phải ván chơi của bạn!", ephemeral=True)
            return

        await interaction.response.send_modal(GuessModal())

# 3. Lệnh Play
@bot.tree.command(name="play", description="Chơi Wordle")
async def play(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id in games:
        await interaction.response.send_message("Bạn đang trong ván chơi rồi!", ephemeral=True)
        return

    secret = word.choose_answer()
    games[user_id] = {
        "answer": secret,
        "guesses": [],
        "attempts": 0
    }

    board_text = render_board([], secret)
    content = f"<@{user_id}> is playing\n```\n{board_text}\n```"

    # Gửi tin nhắn có gắn Nút Bấm
    await interaction.response.send_message(content=content, view=WordleView(owner_id=user_id))

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot {bot.user} ready!")

if TOKEN:
    bot.run(TOKEN)
