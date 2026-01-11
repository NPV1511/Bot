import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz
import json
import os
import re
import colorsys

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
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================== DAILY STATE ==================
sent_today = {}

def reset_if_new_day(gid):
    today = datetime.now(tz).date()
    if gid not in sent_today or sent_today[gid]["date"] != today:
        sent_today[gid] = {"date": today, "noon": False, "evening": False}

# ================== DIEM DANH ==================
async def send_diemdanh(hour, force=False):
    for gid, cfg in config.items():
        reset_if_new_day(gid)
        if not isinstance(cfg, dict):
            continue

        channel_id = cfg.get("diemdanh_channel")
        if not channel_id:
            continue

        key = "noon" if hour == 12 else "evening"
        if sent_today[gid][key] and not force:
            continue

        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        text = "@everyone\n# 📌 ĐIỂM DANH TRƯA" if hour == 12 else "@everyone\n# 📌 ĐIỂM DANH TỐI"
        await channel.send(text)

        if not force:
            sent_today[gid][key] = True

async def noon_job():
    await send_diemdanh(12)

async def evening_job():
    await send_diemdanh(18)

# ================== 🌈 RAINBOW ROLE (FAST) ==================
hue = 0.0

async def rainbow_role_job():
    global hue
    hue = (hue + 0.04) % 1.0  # 🔥 tăng nhanh hơn

    r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)
    color = discord.Color.from_rgb(
        int(r * 255),
        int(g * 255),
        int(b * 255)
    )

    for gid, cfg in config.items():
        if not cfg.get("rainbow_enable"):
            continue

        guild = bot.get_guild(int(gid))
        if not guild:
            continue

        role = guild.get_role(cfg.get("rainbow_role", 0))
        if not role:
            continue

        try:
            await role.edit(color=color, reason="Rainbow role auto")
        except discord.Forbidden:
            print("❌ Không đủ quyền đổi màu role")
        except discord.HTTPException:
            pass  # tránh spam lỗi rate limit

# ================== PERMISSION ==================
def admin_only():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

# ================== SLASH COMMAND ==================

@tree.command(name="setrainbowrole", description="Set role rainbow")
@admin_only()
async def setrainbowrole(interaction: discord.Interaction, role: discord.Role):
    gid = str(interaction.guild.id)
    config.setdefault(gid, {})
    config[gid]["rainbow_role"] = role.id
    config[gid]["rainbow_enable"] = True
    save_json(CONFIG_FILE, config)
    await interaction.response.send_message(
        f"🌈 Set role rainbow: {role.mention}", ephemeral=True
    )

@tree.command(name="rainbow", description="Bật / Tắt rainbow role")
@admin_only()
@app_commands.choices(mode=[
    app_commands.Choice(name="Bật", value=1),
    app_commands.Choice(name="Tắt", value=0),
])
async def rainbow(interaction: discord.Interaction, mode: app_commands.Choice[int]):
    gid = str(interaction.guild.id)
    config.setdefault(gid, {})
    config[gid]["rainbow_enable"] = bool(mode.value)
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message(
        "🌈 Đã bật rainbow" if mode.value else "⛔ Đã tắt rainbow",
        ephemeral=True
    )

@tree.command(name="rainbowstatus", description="Xem trạng thái rainbow")
@admin_only()
async def rainbowstatus(interaction: discord.Interaction):
    cfg = config.get(str(interaction.guild.id), {})
    role = interaction.guild.get_role(cfg.get("rainbow_role", 0))

    await interaction.response.send_message(
        f"""🌈 **RAINBOW STATUS**
• Role: {role.mention if role else '❌ Chưa set'}
• Trạng thái: {'✅ BẬT' if cfg.get('rainbow_enable') else '⛔ TẮT'}""",
        ephemeral=True
    )

# ================== READY ==================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online: {bot.user}")

    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(noon_job, "cron", hour=12, minute=12)
    scheduler.add_job(evening_job, "cron", hour=18, minute=0)

    # 🔥 RAINBOW NHANH
    scheduler.add_job(rainbow_role_job, "interval", seconds=2)

    scheduler.start()

bot.run(TOKEN)
