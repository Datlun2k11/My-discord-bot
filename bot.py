import os, asyncio, aiohttp, discord
from flask import Flask
from threading import Thread
from discord.ext import commands
from groq import Groq

# --- WEB MỒI ---
app = Flask('')
@app.route('/')
def home(): return "Bot Backrooms đang 'thở' cực mạnh 💀"

def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- CONFIG ---
TOKEN = os.getenv('DISCORD_TOKEN')
client_groq = Groq(api_key=os.getenv('GROQ_API_KEY'))
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# --- HÀM HÚT DATA "VÉT CẠN" (OPENSEARCH) ---
async def get_backrooms_data(session, query):
    api_url = "https://backrooms.fandom.com/api.php"
    
    # Bước 1: Thử tìm trực tiếp Level {n} nếu m chỉ gõ số
    search_query = f"Level {query}" if query.isdigit() else query
    
    # Bước 2: Dùng opensearch để lấy title chuẩn nhất
    search_params = {
        "action": "opensearch", "search": search_query, "limit": 1, "format": "json"
    }
    async with session.get(api_url, params=search_params) as r:
        s_data = await r.json()
        if not s_data[1]: 
            # Nếu vẫn k thấy, thử search chay lần cuối
            search_params["search"] = query
            async with session.get(api_url, params=search_params) as r2:
                s_data = await r2.json()
        
        if not s_data[1]: return None
        best_title = s_data[1][0] # Đây là tiêu đề chuẩn nhất 🎯

    # Bước 3: Lấy text sạch từ tiêu đề đó
    content_params = {
        "action": "query", "prop": "extracts", "titles": best_title,
        "explaintext": 1, "format": "json", "redirects": 1
    }
    async with session.get(api_url, params=content_params) as r:
        c_data = await r.json()
        pages = c_data.get("query", {}).get("pages", {})
        for k, v in pages.items():
            if k == "-1": return None
            return v.get("extract")
    return None

@bot.event
async def on_message(msg):
    if msg.author.bot: return
    
    # Check mention hoặc prefix
    if bot.user.mentioned_in(msg) or msg.content.startswith('!tomtat'):
        q = msg.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').replace('!tomtat', '').strip()
        if not q: return await msg.reply("Gõ tên level vào bradar, t k biết bói đâu 💀")

        async with msg.channel.typing():
            async with aiohttp.ClientSession() as session:
                txt = await get_backrooms_data(session, q)
                if not txt or len(txt) < 100: 
                    return await msg.reply(f"Wiki nó viết cụt lủn hoặc t đ tìm thấy cái '{q}' này 💔")

                # Đút cho con 120B múa quạt
                try:
                    res = client_groq.chat.completions.create(
                        model="gpt-oss-120b",
                        messages=[
                            {"role": "system", "content": "M là bot Backrooms GenZ. Tóm tắt lore sau cực ngắn, nhây, cà khịa, dùng teencode và emoji 💀."},
                            {"role": "user", "content": f"Data: {txt[:2800]}"}
                        ]
                    )
                    await msg.reply(f"{res.choices[0].message.content} 🥀")
                except Exception:
                    await msg.reply("Con AI 120B đang 'đột tử', thử lại sau thx ☠️")

@bot.event
async def on_ready(): print(f"Hú! {bot.user} online r nhé bradar (¬‿¬)")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
