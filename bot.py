import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz
import json
import os
import re

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1301417363991826504

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"

MY_GANG = "[DR] Dragons Breath"
tz = pytz.timezone("Asia/Ho_Chi_Minh")

# ================== LOAD / SAVE ==================
def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

config = load_json(CONFIG_FILE, {
    "diemdanh_channel": None,
    "tinhdiem_channel": None
})

# ================== BOT ==================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
guild = discord.Object(id=GUILD_ID)

# ================== DAILY CHECK ==================
sent_today = {
    "date": datetime.now(tz).date(),
    "noon": False,
    "evening": False
}

def reset_if_new_day():
    today = datetime.now(tz).date()
    if sent_today["date"] != today:
        sent_today["date"] = today
        sent_today["noon"] = False
        sent_today["evening"] = False

# ================== AUTO MESSAGE ==================
async def send_noon_message():
    reset_if_new_day()
    if sent_today["noon"] or not config["diemdanh_channel"]:
        return

    channel = bot.get_channel(config["diemdanh_channel"])
    if channel:
        await channel.send("@everyone\n# Điểm Danh Sự Kiện Xịt Sơn Lúc 13h00")
        sent_today["noon"] = True

async def send_evening_message():
    reset_if_new_day()
    if sent_today["evening"] or not config["diemdanh_channel"]:
        return

    channel = bot.get_channel(config["diemdanh_channel"])
    if channel:
        await channel.send("@everyone\n# Điểm Danh Sự Kiện Xịt Sơn Lúc 19h00")
        sent_today["evening"] = True

# ================== SLASH COMMAND ==================
@tree.command(name="diemdanhroom", description="Set kênh điểm danh", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
async def diemdanhroom(interaction: discord.Interaction, channel: discord.TextChannel):

    await interaction.response.defer(ephemeral=True)

    config["diemdanh_channel"] = channel.id
    save_json(CONFIG_FILE, config)

    await interaction.followup.send(
        f"✅ Kênh điểm danh: {channel.mention}",
        ephemeral=True
    )

@tree.command(name="tinhdiemroom", description="Set kênh tính điểm", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
async def tinhdiemroom(interaction: discord.Interaction, channel: discord.TextChannel):

    await interaction.response.defer(ephemeral=True)

    config["tinhdiem_channel"] = channel.id
    save_json(CONFIG_FILE, config)

    await interaction.followup.send(
        f"✅ Kênh tính điểm: {channel.mention}",
        ephemeral=True
    )

@tree.command(name="tinhdiem", description="Cộng điểm từ bảng xếp hạng", guild=guild)
@app_commands.describe(text="Dán bảng điểm vào đây")
async def tinhdiem(interaction: discord.Interaction, text: str):

    await interaction.response.defer(ephemeral=True)

    if config["tinhdiem_channel"] and interaction.channel.id != config["tinhdiem_channel"]:
        await interaction.followup.send(
            "❌ Lệnh chỉ dùng trong kênh tính điểm",
            ephemeral=True
        )
        return

    data = load_json(DATA_FILE, {})
    updated = False

    matches = re.findall(
        r"\d+\s+(\[[^\]]+\]\s+.+?)\s+([\d,]+)",
        text
    )

    for gang, score in matches:
        score = int(score.replace(",", ""))
        data[gang] = data.get(gang, 0) + score
        updated = True

    if not updated:
        await interaction.followup.send("❌ Không đọc được dữ liệu", ephemeral=True)
        return

    save_json(DATA_FILE, data)
    await send_week_embed(interaction.channel, data)

    await interaction.followup.send("✅ Đã cộng điểm thành công", ephemeral=True)

@tree.command(name="week", description="Xem bảng xếp hạng TOP TUẦN", guild=guild)
async def week(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await send_week_embed(interaction.channel, load_json(DATA_FILE, {}))

# ================== EMBED ==================
async def send_week_embed(channel, data):
    if not data:
        await channel.send("📭 Chưa có dữ liệu")
        return

    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 TOP TUẦN – CREW",
        color=discord.Color.gold()
    )

    embed.description = "\n".join(
        f"🔥 **{i}. {name}** — `{score:,}` điểm" if name == MY_GANG
        else f"**{i}. {name}** — `{score:,}` điểm"
        for i, (name, score) in enumerate(sorted_data, 1)
    )

    await channel.send(embed=embed)

# ================== READY ==================
@bot.event
async def on_ready():
    await tree.sync(guild=guild)
    print(f"✅ Bot online: {bot.user}")

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(send_noon_message, "cron", hour=12, minute=0)
    scheduler.add_job(send_evening_message, "cron", hour=18, minute=0)
    scheduler.start()

# ================== RUN ==================
bot.run(TOKEN)
