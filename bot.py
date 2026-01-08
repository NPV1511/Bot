import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz
import json
import os
import re

# ================== ENV ==================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Thiếu TOKEN")

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"
MY_GANG = "[DR] Dragons Breath"
tz = pytz.timezone("Asia/Ho_Chi_Minh")

# ================== LOAD / SAVE ==================
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

config = load_json(CONFIG_FILE, {})
scores = load_json(DATA_FILE, {})

# ================== BOT ==================
intents = discord.Intents.default()
intents.guilds = True   # ⭐ FIX QUAN TRỌNG
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================== DAILY STATE ==================
sent_today = {}

def reset_if_new_day(guild_id):
    today = datetime.now(tz).date()
    if guild_id not in sent_today or sent_today[guild_id]["date"] != today:
        sent_today[guild_id] = {
            "date": today,
            "noon": False,
            "evening": False
        }

# ================== AUTO MESSAGE ==================
async def send_auto(guild_id, key, text):
    reset_if_new_day(guild_id)

    if sent_today[guild_id][key]:
        return

    cfg = config.get(str(guild_id))
    if not cfg or not cfg.get("diemdanh_channel"):
        return

    channel = bot.get_channel(cfg["diemdanh_channel"])
    if channel:
        await channel.send(text)
        sent_today[guild_id][key] = True

async def noon_job():
    for gid in config:
        await send_auto(
            int(gid),
            "noon",
            "@everyone\n# 📌 Điểm Danh Sự Kiện Xịt Sơn Lúc 13h00"
        )

async def evening_job():
    for gid in config:
        await send_auto(
            int(gid),
            "evening",
            "@everyone\n# 📌 Điểm Danh Sự Kiện Xịt Sơn Lúc 19h00"
        )

# ================== SLASH COMMAND ==================
@tree.command(name="diemdanhroom", description="Set kênh điểm danh")
@app_commands.checks.has_permissions(administrator=True)
async def diemdanhroom(interaction: discord.Interaction, channel: discord.TextChannel):
    gid = str(interaction.guild.id)
    config.setdefault(gid, {})
    config[gid]["diemdanh_channel"] = channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message(
        f"✅ Kênh điểm danh: {channel.mention}",
        ephemeral=True
    )

@tree.command(name="tinhdiemroom", description="Set kênh tính điểm")
@app_commands.checks.has_permissions(administrator=True)
async def tinhdiemroom(interaction: discord.Interaction, channel: discord.TextChannel):
    gid = str(interaction.guild.id)
    config.setdefault(gid, {})
    config[gid]["tinhdiem_channel"] = channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message(
        f"✅ Kênh tính điểm: {channel.mention}",
        ephemeral=True
    )

@tree.command(name="tinhdiem", description="Cộng điểm từ bảng xếp hạng")
@app_commands.describe(text="Dán bảng điểm")
async def tinhdiem(interaction: discord.Interaction, text: str):
    await interaction.response.send_message("⏳ Đang xử lý...", ephemeral=True)

    gid = str(interaction.guild.id)
    cfg = config.get(gid)

    if cfg and cfg.get("tinhdiem_channel") and interaction.channel.id != cfg["tinhdiem_channel"]:
        await interaction.followup.send("❌ Sai kênh tính điểm", ephemeral=True)
        return

    matches = re.findall(r"\d+\s+(\[[^\]]+\]\s+.+?)\s+([\d,]+)", text)
    if not matches:
        await interaction.followup.send("❌ Không đọc được dữ liệu", ephemeral=True)
        return

    for gang, score in matches:
        score = int(score.replace(",", ""))
        scores[gang] = scores.get(gang, 0) + score

    save_json(DATA_FILE, scores)
    await send_week_embed(interaction.channel, scores)

    await interaction.followup.send("✅ Đã cộng điểm", ephemeral=True)

@tree.command(name="week", description="Xem TOP TUẦN")
async def week(interaction: discord.Interaction):
    await interaction.response.send_message("📊 Đang tải bảng xếp hạng...", ephemeral=True)
    await send_week_embed(interaction.channel, scores)

# ================== EMBED ==================
async def send_week_embed(channel, data):
    if not data:
        await channel.send("📭 Chưa có dữ liệu")
        return

    top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 TOP TUẦN – CREW",
        color=discord.Color.gold()
    )

    lines = []
    for i, (name, score) in enumerate(top, 1):
        if name == MY_GANG:
            lines.append(f"🔥 **{i}. {name}** — `{score:,}` điểm")
        else:
            lines.append(f"**{i}. {name}** — `{score:,}` điểm")

    embed.description = "\n".join(lines)
    await channel.send(embed=embed)

# ================== READY ==================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online: {bot.user}")

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(noon_job, "cron", hour=12, minute=0)
    scheduler.add_job(evening_job, "cron", hour=18, minute=0)
    scheduler.start()

bot.run(TOKEN)
