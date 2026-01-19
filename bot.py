import discord
from discord.ext import commands
from discord import app_commands
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
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================== PERMISSION ==================
def admin_only():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

# ================== SCORE ==================
@tree.command(name="tinhdiem", description="Cộng điểm từ bảng")
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

@tree.command(name="week", description="Xem top tuần")
async def week(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await send_week_embed(interaction.channel, scores)

@tree.command(name="clear", description="Xóa toàn bộ điểm")
@admin_only()
async def clear(interaction: discord.Interaction):
    scores.clear()
    save_json(DATA_FILE, scores)
    await interaction.response.send_message("🧹 Đã xóa điểm", ephemeral=True)

# ================== FORUM ==================
@tree.command(name="demanhforum", description="Đếm ảnh trong forum")
@admin_only()
async def demanhforum(interaction: discord.Interaction, forum: discord.ForumChannel):
    await interaction.response.defer(ephemeral=True)

    result = []
    threads = list(forum.threads)
    async for t in forum.archived_threads(limit=None):
        threads.append(t)

    for thread in threads:
        count = 0
        async for msg in thread.history(limit=None):
            for att in msg.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    count += 1
        result.append(f"🎇 **{thread.name}**: {count} Bình")

    await interaction.followup.send("\n".join(result)[:1900] or "📭 Không có bài", ephemeral=True)

# ================== ACCEPT ROLE ==================
@tree.command(name="selectrole", description="Set role accept + kênh thông báo")
@admin_only()
async def selectrole(interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel):
    gid = str(interaction.guild.id)
    config.setdefault(gid, {})
    config[gid]["accept_role"] = role.id
    config[gid]["accept_channel"] = channel.id
    save_json(CONFIG_FILE, config)

    await interaction.response.send_message(
        f"✅ Role accept: {role.mention}\n📢 Kênh: {channel.mention}",
        ephemeral=True
    )

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    gid = str(after.guild.id)
    cfg = config.get(gid, {})

    role_id = cfg.get("accept_role")
    channel_id = cfg.get("accept_channel")
    if not role_id or not channel_id:
        return

    before_roles = {r.id for r in before.roles}
    after_roles = {r.id for r in after.roles}

    if role_id not in before_roles and role_id in after_roles:
        channel = after.guild.get_channel(channel_id)
        if channel:
            await channel.send(
                f"🎉 Chúc Mừng {after.mention} Đã Được Accept Vào Server\n"
                f"Vui Lòng Đọc Hết Nội Dung Ở <#1461276993126662299> Và Làm Theo"
            )

# ================== EMBED ==================
async def send_week_embed(channel, data):
    if not data:
        await channel.send("📭 Chưa có dữ liệu")
        return

    top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 TOP TUẦN", color=discord.Color.gold())
    embed.description = "\n".join(
        f"🔥 **{i}. {name}** — `{score:,}`" if name == MY_GANG
        else f"**{i}. {name}** — `{score:,}`"
        for i, (name, score) in enumerate(top, 1)
    )
    await channel.send(embed=embed)

# ================== READY ==================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online: {bot.user}")

bot.run(TOKEN)
