import os
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
from groq import Groq

# --- CẤU HÌNH WEB MỒI (FLASK) ---
app = Flask('')
@app.route('/')
def home(): return "Bot Backrooms đang thở nhé bradar (¬‿¬)"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# --- CẤU HÌNH BOT ---
# Lấy API từ Environment Variables cho nó pro[span_0](start_span)[span_0](end_span)
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_KEY = os.getenv('GROQ_API_KEY')

client_groq = Groq(api_key=GROQ_KEY)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- HÀM LẤY DATA (BUG FIX: THÊM TRY-EXCEPT) ---
async def get_fandom_text(session, title):
    url = "https://backrooms.fandom.com/api.php"
    params = {
        "action": "query", "prop": "extracts", "titles": title,
        "explaintext": 1, "format": "json"
    }
    try:
        async with session.get(url, params=params, timeout=10) as r:
            data = await r.json()
            pages = data.get("query", {}).get("pages", {})
            for k, v in pages.items():
                if "extract" in v:
                    return v["extract"]
            return None
    except Exception as e:
        print(f"Lỗi hút data: {e}")
        return None

# --- LOGIC MENTION & TÓM TẮT ---
@bot.event
async def on_message(message):
    if message.author.bot: return

    # Nếu được mention hoặc dùng lệnh !tomtat
    if bot.user.mentioned_in(message) or message.content.startswith('!tomtat'):
        # Lấy tên level (bỏ mention hoặc bỏ lệnh)
        level_name = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').replace('!tomtat', '').strip()
        
        if not level_name:
            await message.channel.send("M định tóm tắt cái nịt à? Gõ tên level vào bradar 💀")
            return

        async with message.channel.typing():
            async with aiohttp.ClientSession() as session:
                content = await get_fandom_text(session, level_name)
                
                if not content:
                    await message.channel.send(f"Đếch tìm thấy cái level {level_name} này trên Fandom, m bịp t à? 💔")
                    return

                try:
                    # Gọi GPT-OSS-120B qua Groq
                    chat = client_groq.chat.completions.create(
                        model="gpt-oss-120b",
                        messages=[
                            {"role": "system", "content": "M là bot Backrooms GenZ. Tóm tắt lore sau cực ngắn, nhây, cà khịa, dùng teencode (nx, th, cx, k, j...) và emoji 💀."},
                            {"role": "user", "content": f"Level: {level_name}\nData: {content[:2500]}"}
                        ]
                    )
                    await message.reply(f"{chat.choices[0].message.content} 🥀")
                except Exception as e:
                    await message.channel.send(f"Con AI 120B đang bị ngáo, m đợi tí ☠️ (Lỗi: {e})")

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"Bot {bot.user} đã lên sàn! Ready to báo 💀")

# --- KHỞI CHẠY ---
if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
