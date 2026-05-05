import os
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from discord.ext import commands
import discord
from groq import Groq

# --- CONFIG ---
app = Flask('')
@app.route('/')
def home(): return "Bot vẫn đang sống nhăn răng nhé bradar 💀"

def run_flask(): app.run(host='0.0.0.0', port=8080)

client_groq = Groq(api_key="API_GROQ_CUA_M")
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# --- HELPER ---
async def get_fandom_text(session, title):
    url = f"https://backrooms.fandom.com/api.php"
    params = {
        "action": "query", "prop": "extracts", "titles": title,
        "explaintext": 1, "format": "json"
    }
    async with session.get(url, params=params) as r:
        data = await r.json()
        pages = data.get("query", {}).get("pages", {})
        for k, v in pages.items():
            return v.get("extract", "Đếch thấy level này bradar ơi 💔")

# --- COMMANDS ---
@bot.command()
async def tom_tat(ctx, *, level: str):
    async with aiohttp.ClientSession() as session:
        content = await get_fandom_text(session, level)
        
        # Đút vào 120B tóm tắt kiểu báo thủ
        chat = client_groq.chat.completions.create(
            model="gpt-oss-120b",
            messages=[
                {"role": "system", "content": "M là bot Backrooms GenZ. Tóm tắt lore sau cực ngắn, nhây, cà khịa, dùng teencode và emoji 💀."},
                {"role": "user", "content": f"Level: {level}\nContent: {content[:2000]}"}
            ]
        )
        await ctx.send(f"{chat.choices[0].message.content} 🥀")

@bot.event
async def on_ready(): print(f"Thằng master {bot.user} dậy r nè (¬‿¬)")

# --- RUN ---
Thread(target=run_flask).start()
bot.run("TOKEN_DISCORD_CUA_M")
