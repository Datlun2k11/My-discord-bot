import discord
from discord import app_commands
import aiohttp, asyncio, json, random, os, threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
TOKEN, GROQ_KEY = os.getenv('DISCORD_TOKEN'), os.getenv('GROQ_API_KEY')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Đồng bộ lệnh với Discord
        await self.tree.sync()
        print(f"✅ Đã sync xong lệnh Slash cho {self.user}!")

bot = MyBot()
app = Flask(__name__)

# DB lưu file json cho chắc
DATA_FILE = "user_data.json"
def load_db():
    try: return json.load(open(DATA_FILE, "r"))
    except: return {}
def save_db(): json.dump(user_data, open(DATA_FILE, "w"), indent=4)

user_data = load_db()
cooldowns = {}

@app.route('/')
def home(): return "Bot nhây đang sống... 🥀"

async def call_groq_ai(outcome, context=""):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    prompt = f"Bạn là game master nhây, khịa người chơi vừa {'THẮNG' if outcome == 'win' else 'THUA'}. Dùng tiếng Việt GenZ, lầy lội, cực ngắn 1 câu. Bối cảnh: {context}"
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.9}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROQ_URL, headers=headers, json=payload, timeout=5) as resp:
                data = await resp.json()
                return data['choices'][0]['message']['content'].strip()
        except: return "Quái thấy m đẹp trai quá nên nó tự xỉu r! 💀"

def init_user(uid):
    if str(uid) not in user_data:
        user_data[str(uid)] = {"gold": 100, "weapon": "kiếm gỉ", "armor": "áo rách", "hunts": 0}
        save_db()

@bot.tree.command(name='go_hunt', description="Đi săn quái kiếm cơm")
async def go_hunt(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    if uid in cooldowns and datetime.now() < cooldowns[uid]:
        return await interaction.response.send_message(f"Đợi tí bro, quái đang đi tắm, còn {(cooldowns[uid]-datetime.now()).seconds}s! ⌛", ephemeral=True)
    
    await interaction.response.defer() # Tránh lỗi 3s timeout của Discord
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
    await interaction.followup.send(embed=emb)

@bot.tree.command(name='shop', description="Tiệm đồ cũ")
async def shop(interaction: discord.Interaction):
    emb = discord.Embed(title="TIỆM ĐỒ CŨ", description="Dùng `/buy` để hốt đồ", color=discord.Color.blue())
    emb.add_field(name="kiếm sắt (100)", value="+20% tỉ lệ thắng", inline=False)
    emb.add_field(name="áo da (80)", value="Giảm lỗ khi thua", inline=False)
    await interaction.response.send_message(embed=emb)

@bot.tree.command(name='buy', description="Mua đồ nâng cấp")
@app_commands.describe(item="Tên món đồ muốn mua")
async def buy(interaction: discord.Interaction, item: str):
    uid = str(interaction.user.id)
    init_user(uid)
    prices = {"kiếm sắt": 100, "áo da": 80}
    item = item.lower()
    if item in prices and user_data[uid]["gold"] >= prices[item]:
        user_data[uid]["gold"] -= prices[item]
        user_data[uid]["weapon" if "kiếm" in item else "armor"] = item
        save_db()
        await interaction.response.send_message(f"Hốt thành công {item}! Giờ thì đi báo quái thôi bradar! ⚔️")
    else: await interaction.response.send_message("Nghèo quá k đủ xu đâu m ơi! 💸", ephemeral=True)

@bot.tree.command(name='top', description="Bảng xếp hạng đại gia")
async def top(interaction: discord.Interaction):
    top_list = sorted(user_data.items(), key=lambda x: x[1]['gold'], reverse=True)[:5]
    txt = "\n".join([f"#{i+1} <@{u[0]}>: {u[1]['gold']} xu" for i, u in enumerate(top_list)])
    await interaction.response.send_message(embed=discord.Embed(title="BẢNG VÀNG ĐẠI GIA", description=txt or "Chưa ai giàu 💀"))

def run_flask(): app.run(host='0.0.0.0', port=8080)
threading.Thread(target=run_flask, daemon=True).start()
bot.run(TOKEN)
