import discord
import json
import os
import re

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN")

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"

MY_GANG = "[DR] Dragons Breath"

# ================== JSON ==================
def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
            return json.loads(text) if text else {}
    except:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ================== DISCORD ==================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Bot online: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    data = load_json(DATA_FILE)
    config = load_json(CONFIG_FILE)

    # chỉ hoạt động trong channel đã set (nếu có)
    if config.get("channel_id") and message.channel.id != config["channel_id"]:
        return

    # -------- !addchannel <id> --------
    if message.content.startswith("!addchannel"):
        parts = message.content.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.channel.send("❌ Dùng: `!addchannel <channel_id>`")
            return

        config["channel_id"] = int(parts[1])
        save_json(CONFIG_FILE, config)
        await message.channel.send("✅ Đã set channel cố định cho bot")
        return

    # -------- !clear --------
    if message.content == "!clear":
        data.clear()
        save_json(DATA_FILE, data)
        await message.channel.send("♻️ Đã reset bảng điểm TOP TUẦN")
        return

    # -------- !week --------
    if message.content == "!week":
        await send_week_embed(message.channel, data)
        return

    # ================== !tinhdiem ==================
    if not message.content.startswith("!tinhdiem"):
        return

    lines = message.content.split("\n")[1:]
    if not lines:
        await message.channel.send("❌ Bạn chưa dán bảng điểm")
        return

    updated = False

    for line in lines:
        # FORMAT:
        # 1 [FG] Fearless Gang 1,238
        m = re.match(
            r"^\s*\d+\s+(\[[^\]]+\]\s+.+?)\s+([\d,]+)\s*$",
            line
        )
        if not m:
            continue

        gang = m.group(1).strip()
        score = int(m.group(2).replace(",", ""))

        # ✅ CỘNG DỒN – KHÔNG BAO GIỜ GHI ĐÈ
        data[gang] = data.get(gang, 0) + score
        updated = True

    if not updated:
        await message.channel.send("❌ Không đọc được dữ liệu")
        return

    save_json(DATA_FILE, data)
    await send_week_embed(message.channel, data)

# ================== EMBED ==================
async def send_week_embed(channel, data):
    if not data:
        await channel.send("📭 Chưa có dữ liệu")
        return

    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    top10 = sorted_data[:10]
    names_top10 = [n for n, _ in top10]

    embed = discord.Embed(
        title="🏆 TOP TUẦN – CREW",
        color=discord.Color.gold()
    )

    desc = ""

    for i, (name, score) in enumerate(top10, 1):
        if name == MY_GANG:
            desc += f"🔥 **{i}. {name}** — `{score:,}` điểm\n"
        else:
            desc += f"**{i}. {name}** — `{score:,}` điểm\n"

    # DR không trong top 10 → hiển thị riêng (KHÔNG ĐỤNG ĐIỂM)
    if MY_GANG in data and MY_GANG not in names_top10:
        desc += "\n─────────────\n"
        desc += f"🔥 **{MY_GANG}** — `{data[MY_GANG]:,}` điểm"

    embed.description = desc
    await channel.send(embed=embed)

# ================== RUN ==================
client.run(TOKEN)
