import os, asyncio, aiohttp, discord
from flask import Flask
from threading import Thread
from discord.ext import commands
from groq import Groq

# --- CẤU HÌNH WEB MỒI ---
app = Flask('')
@app.route('/')
def home(): return "Bot Backrooms vẫn đang 'thở' trên Render nhé bradar (¬‿¬)"

def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- CẤU HÌNH BOT ---
TOKEN = os.getenv('DISCORD_TOKEN')
client_groq = Groq(api_key=os.getenv('GROQ_API_KEY'))
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# --- HÀM SEARCH & GET DATA PRO ---
async def get_backrooms_data(session, query):
    api_url = "https://backrooms.fandom.com/api.php"
    
    # Bước 1: Search cái title chuẩn nhất (để tránh lỗi gõ '0' k ra 'Level 0')
    search_params = {
        "action": "query", "list": "search", "srsearch": query, "format": "json"
    }
    async with session.get(api_url, params=search_params) as r:
        s_data = await r.json()
        search_results = s_data.get("query", {}).get("search", [])
        if not search_results: return None
        best_title = search_results[0]["title"] # Lấy cái tên trang khớp nhất 🎯

    # Bước 2: Hút nội dung từ cái title vừa tìm đc
    content_params = {
        "action": "query", "prop": "extracts", "titles": best_title,
        "explaintext": 1, "format": "json", "redirects": 1
    }
    async with session.get(api_url, params=content_params) as r:
        c_data = await r.json()
        pages = c_data.get("query", {}).get("pages", {})
        for k, v in pages.items():
            return v.get("extract")
    return None

@bot.event
async def on_message(msg):
    if msg.author.bot: return
    if bot.user.mentioned_in(msg) or msg.content.startswith('!tomtat'):
        q = msg.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').replace('!tomtat', '').strip()
        if not q: return await msg.reply("Gõ tên level vào cái thằng báo này 💀")

        async with msg.channel.typing():
            async with aiohttp.ClientSession() as session:
                txt = await get_backrooms_data(session, q)
                if not txt: return await msg.reply(f"Đếch thấy lore cho '{q}' nx, m bịp t à? 💔")

                # Đút vào GPT-120B múa quạt
                res = client_groq.chat.completions.create(
                    model="gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": "M là bot Backrooms GenZ nhây lầy. Tóm tắt lore sau cực ngắn, cà khịa, dùng teencode (nx, th, cx, k, j...) và emoji 💀."},
                        {"role": "user", "content": f"Data: {txt[:2500]}"}
                    ]
                )
                await msg.reply(f"{res.choices[0].message.content} 🥀")

@bot.event
async def on_ready(): print(f"Master {bot.user} online r nhé bradar (¬‿¬)")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
