import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import pytz
import requests
from PIL import Image
from io import BytesIO
import json
import os

TOKEN = os.getenv("TOKEN")  # 🔥 lấy từ Railway ENV

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "points.json"
CONFIG_FILE = "config.json"
tz = pytz.timezone("Asia/Ho_Chi_Minh")

# ================= LOAD / SAVE =================
def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# ================= WEEK =================
def get_week_key():
    now = datetime.now(tz)
    return f"{now.year}-W{now.isocalendar()[1]}"

# ================= CHECK ẢNH =================
def check_image(image):
    return True

# ================= CHỌN FORUM =================
@bot.tree.command(name="chude")
@app_commands.checks.has_permissions(administrator=True)
async def chude(interaction: discord.Interaction, forum: discord.ForumChannel):
    config = load_json(CONFIG_FILE)
    config[str(interaction.guild.id)] = forum.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message(
        f"✅ Đã chọn forum: {forum.name}",
        ephemeral=True
    )

# ================= RESET =================
@bot.tree.command(name="resetdiem")
@app_commands.checks.has_permissions(administrator=True)
async def resetdiem(interaction: discord.Interaction, forum: discord.ForumChannel):
    data = load_json(DATA_FILE)
    week = get_week_key()

    if week in data:
        del data[week]

    save_json(DATA_FILE, data)

    deleted = 0
    for thread in forum.threads:
        try:
            await thread.delete()
            deleted += 1
        except:
            pass

    await interaction.response.send_message(
        f"🔄 Reset + xoá {deleted} bài",
        ephemeral=True
    )

# ================= TỔNG ĐIỂM =================
@bot.tree.command(name="tongdiem")
async def tongdiem(interaction: discord.Interaction, forum: discord.ForumChannel):
    data = load_json(DATA_FILE)
    week = get_week_key()

    msg = f"🏆 TỔNG ĐIỂM XỊT SƠN - {forum.name}\n\n"
    found = False

    threads = data.get(week, {})

    for thread_id, users in threads.items():
        try:
            thread = await bot.fetch_channel(int(thread_id))
        except:
            continue

        for user_id, score in users.items():
            if score > 0:
                user = await bot.fetch_user(int(user_id))
                msg += f"{thread.name} - {user.name} : {score} điểm\n"
                found = True

    if not found:
        msg += "❌ Chưa có dữ liệu"

    await interaction.response.send_message(msg)

# ================= THREAD =================
@bot.event
async def on_thread_create(thread):
    config = load_json(CONFIG_FILE)
    forum_id = config.get(str(thread.guild.id))

    if thread.parent_id != forum_id:
        return

    try:
        starter = await thread.fetch_message(thread.id)
        owner = starter.author

        try:
            await owner.send(
                f"📌 Bạn đã tạo phiếu thi đua xịt sơn\n🔗 {thread.jump_url}"
            )
        except:
            await thread.send(f"{owner.mention} 📌 Bạn đã tạo phiếu thi đua xịt sơn")

    except Exception as e:
        print(e)

# ================= NHẬN ẢNH =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.Thread):
        return

    config = load_json(CONFIG_FILE)
    forum_id = config.get(str(message.guild.id))

    if message.channel.parent_id != forum_id:
        return

    if message.attachments:
        attachment = message.attachments[0]

        if attachment.filename.lower().endswith(("png", "jpg", "jpeg")):
            try:
                response = requests.get(attachment.url)
                img = Image.open(BytesIO(response.content)).convert("RGB")
            except:
                return

            if check_image(img):
                await message.add_reaction("✅")

                data = load_json(DATA_FILE)
                week = get_week_key()
                thread_id = str(message.channel.id)
                user_id = str(message.author.id)

                if week not in data:
                    data[week] = {}

                if thread_id not in data[week]:
                    data[week][thread_id] = {}

                if user_id not in data[week][thread_id]:
                    data[week][thread_id][user_id] = 0

                data[week][thread_id][user_id] += 1
                total = data[week][thread_id][user_id]

                save_json(DATA_FILE, data)

                await message.reply(
                    f" +1 điểm xịt sơn\n Tổng: **{total}**"
                )
            else:
                await message.add_reaction("❌")

    await bot.process_commands(message)

# ================= READY =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

bot.run(TOKEN)
