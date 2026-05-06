import discord
from discord.ext import commands
import aiohttp, asyncio, json, random, os, threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
TOKEN, GROQ_KEY = os.getenv('DISCORD_TOKEN'), os.getenv('GROQ_API_KEY')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())
app = Flask(__name__)

# Database "cùi bắp" nhưng có võ
DATA_FILE = "user_data.json"
def load_db():
    try: return json.load(open(DATA_FILE, "r"))
    except: return {}
def save_db(): json.dump(user_data, open(DATA_FILE, "w"), indent=4)

user_data = load_db()
cooldowns = {}

@app.route('/')
def home(): return "AI nhây đang chạy... 🥀"

async def call_groq_ai(outcome, context=""):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    prompt = f"Bạn là game master siêu nhây, khịa người chơi vừa {'THẮNG' if outcome == 'win' else 'THUA'}. Dùng tiếng Việt GenZ, lầy lội, 1 câu duy nhất. Bối cảnh: {context}"
    payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.9}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROQ_URL, headers=headers, json=payload, timeout=5) as resp:
                data = await resp.json()
                return data['choices'][0]['message']['content'].strip()
        except: return "Quái thấy m xấu quá nên nó tự xỉu, m nhận được tiền vì... quá xấu! 💀"

def init_user(uid):
    if str(uid) not in user_data:
        user_data[str(uid)] = {"gold": 100, "weapon": "kiếm gỉ", "armor": "áo rách", "last_daily": None, "hunts": 0}
        save_db()

@bot.command(name='go_hunt')
async def go_hunt(ctx):
    uid = str(ctx.author.id)
    init_user(uid)
    
    if uid in cooldowns and datetime.now() < cooldowns[uid]:
        return await ctx.send(f"Đợi tí bro, quái đang đi vệ sinh, còn {(cooldowns[uid]-datetime.now()).seconds}s! ⌛")
    
    cooldowns[uid] = datetime.now() + timedelta(seconds=15)
    win = random.random() < (0.5 + (0.2 if user_data[uid]['weapon'] == "kiếm sắt" else 0))
    story = await call_groq_ai("win" if win else "lose", f"đồ: {user_data[uid]['weapon']}")

    if win:
        reward = random.randint(20, 60)
        user_data[uid]["gold"] += reward
        color = discord.Color.green()
    else:
        loss = random.randint(10, 30) if user_data[uid]['armor'] != "áo da" else random.randint(5, 15)
        user_data[uid]["gold"] = max(0, user_data[uid]["gold"] - loss)
        color = discord.Color.red()
    
    user_data[uid]["hunts"] += 1
    save_db()
    
    emb = discord.Embed(title="KẾT QUẢ ĐI SĂN", description=story, color=color)
    emb.set_footer(text=f"Ví: {user_data[uid]['gold']} xu | Săn: {user_data[uid]['hunts']}")
    await ctx.send(embed=emb)

@bot.command(name='shop')
async def shop(ctx):
    emb = discord.Embed(title="TIỆM ĐỒ CŨ", description="`/buy [tên]` để hốt", color=discord.Color.blue())
    emb.add_field(name="kiếm sắt (100)", value="+20% tỉ lệ thắng", inline=False)
    emb.add_field(name="áo da (80)", value="Giảm lỗ khi thua", inline=False)
    await ctx.send(embed=emb)

@bot.command(name='buy')
async def buy(ctx, *, item: str):
    uid = str(ctx.author.id)
    init_user(uid)
    prices = {"kiếm sắt": 100, "áo da": 80}
    item = item.lower()
    if item in prices and user_data[uid]["gold"] >= prices[item]:
        user_data[uid]["gold"] -= prices[item]
        user_data[uid]["weapon" if "kiếm" in item else "armor"] = item
        save_db()
        await ctx.send(f"Hốt thành công {item}, giờ thì đi báo quái đi! ⚔️")
    else: await ctx.send("Nghèo mà còn đòi mua đồ hiệu hả bradar? 💸")

@bot.command(name='top')
async def top(ctx):
    top_list = sorted(user_data.items(), key=lambda x: x[1]['gold'], reverse=True)[:5]
    txt = "\n".join([f"#{i+1} <@{u[0]}>: {u[1]['gold']} xu" for i, u in enumerate(top_list)])
    await ctx.send(embed=discord.Embed(title="BẢNG VÀNG ĐẠI GIA", description=txt or "Chưa ai giàu 💀"))

threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
bot.run(TOKEN)
