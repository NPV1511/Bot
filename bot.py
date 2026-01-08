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
intents.guilds = True
intents.message_content = True  # 🔥 BẮT BUỘC cho forum + history

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================== DAILY STATE ==================
sent_today = {}

def reset_if_new_day(gid: str):
    today = datetime.now(tz).date()
    if gid not in sent_today or sent_today[gid]["date"] != today:
        sent_today[gid] = {
            "date": today,
            "noon": False,
            "evening": False
        }

# ================== DIEM DANH CORE ==================
async def send_diemdanh(hour: int, force: bool = False):
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

        text = (
            "@everyone\n# 📌 ĐIỂM DANH SỰ KIỆN XỊT SƠN TRƯA"
            if hour == 12
            else "@everyone\n# 📌 ĐIỂM DANH SỰ KIỆN XỊT SƠN TỐI"
        )

        await channel.send(text)

        if not force:
            sent_today[gid][key] = True

# ================== AUTO JOB ==================
async def noon_job():
    await send_diemdanh(12)

async def evening_job():
    await send_diemdanh(18)

# ================== PERMISSION ==================
def admin_only():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

# ================== SLASH COMMAND ==================
@tree.command(name="diemdanhroom", description="Set kênh điểm danh")
@admin_only()
async def diemdanhroom(interaction: discord.Interaction, channel: discord.TextChannel):
    gid = str(interaction.guild.id)
    config.setdefault(gid, {})
    config[gid]["diemdanh_channel"] = channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message(
        f"✅ Đã set kênh điểm danh: {channel.mention}",
        ephemeral=True
    )

@tree.command(name="testdiemdanh", description="Test điểm danh ngay")
@admin_only()
@app_commands.choices(
    time=[
        app_commands.Choice(name="Trưa (12:00)", value=12),
        app_commands.Choice(name="Tối (18:00)", value=18),
    ]
)
async def testdiemdanh(
    interaction: discord.Interaction,
    time: app_commands.Choice[int]
):
    await interaction.response.defer(ephemeral=True)
    await send_diemdanh(time.value, force=True)
    await interaction.followup.send(
        f"✅ Đã test điểm danh {time.name}",
        ephemeral=True
    )

@tree.command(name="tinhdiem", description="Cộng điểm từ bảng xếp hạng")
@app_commands.describe(text="Dán bảng điểm")
async def tinhdiem(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)

    matches = re.findall(r"\d+\s+(\[[^\]]+\]\s+.+?)\s+([\d,]+)", text)
    if not matches:
        await interaction.followup.send("❌ Không đọc được dữ liệu", ephemeral=True)
        return

    for gang, score in matches:
        scores[gang] = scores.get(gang, 0) + int(score.replace(",", ""))

    save_json(DATA_FILE, scores)
    await send_week_embed(interaction.channel, scores)
    await interaction.followup.send("✅ Đã cộng điểm", ephemeral=True)

@tree.command(name="week", description="Xem TOP TUẦN")
async def week(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await send_week_embed(interaction.channel, scores)

@tree.command(name="clear", description="Xóa toàn bộ điểm")
@admin_only()
async def clear(interaction: discord.Interaction):
    scores.clear()
    save_json(DATA_FILE, scores)
    await interaction.response.send_message("🧹 Đã xóa toàn bộ điểm", ephemeral=True)

# ================== ĐẾM ẢNH FORUM ==================
@tree.command(
    name="demanhforum",
    description="Đếm ảnh trong từng mục Forum (đọc bên trong, không sai số)"
)
@admin_only()
@app_commands.describe(forum="Forum cần đếm ảnh")
async def demanhforum(
    interaction: discord.Interaction,
    forum: discord.ForumChannel
):
    await interaction.response.defer(ephemeral=True)

    ket_qua = []

    # Thread đang mở
    tat_ca_threads = list(forum.threads)

    # Thread đã archive
    async for t in forum.archived_threads(limit=None):
        tat_ca_threads.append(t)

    for thread in tat_ca_threads:
        so_anh = 0

        async for msg in thread.history(limit=None):
            if not msg.attachments:
                continue

            for att in msg.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    so_anh += 1

        ket_qua.append(f"🧵 **{thread.name}**: {so_anh} ảnh")

    if not ket_qua:
        await interaction.followup.send("📭 Không có bài đăng", ephemeral=True)
        return

    text = "\n".join(ket_qua)
    if len(text) > 1900:
        text = text[:1900] + "\n..."

    await interaction.followup.send(text, ephemeral=True)

# ================== EMBED ==================
async def send_week_embed(channel, data):
    if not data:
        await channel.send("📭 Chưa có dữ liệu")
        return

    top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 TOP TUẦN – CREW", color=discord.Color.gold())

    embed.description = "\n".join(
        f"🔥 **{i}. {name}** — `{score:,}` điểm"
        if name == MY_GANG else
        f"**{i}. {name}** — `{score:,}` điểm"
        for i, (name, score) in enumerate(top, 1)
    )

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
