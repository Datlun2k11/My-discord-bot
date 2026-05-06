import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from flask import Flask
import threading

load_dotenv()

# Khởi tạo intents - CÁCH ĐÚNG
intents = discord.Intents.all()  # Bật toàn bộ quyền
bot = commands.Bot(command_prefix=['!', '/'], intents=intents)

# ... phần còn lại giữ nguyên

# Discord bot setup
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Database đơn giản (dùng dict, nâng lên SQLite sau nếu muốn)
user_data = {}
cooldowns = {}

# Flask server để keep alive (cho free hosting)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

async def call_groq_ai(outcome, custom_context=""):
    """Gọi Groq AI để sinh câu chuyện hài hước"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    if outcome == "win":
        prompt = "Bạn là 1 game master hài hước. Người chơi vừa THẮNG trong săn quái. Hãy kể 1 câu kết cực kỳ hài hước, bất ngờ, dùng tiếng Việt street style, độ dài 1 câu. Ví dụ: 'Mày đạp trúng vỏ chuối, quái trượt chân đập đầu vào đá. Chúc mừng!' hoặc 'Mày đã biến quái thành cục cứt! Chúc mừng!'"
    else:
        prompt = "Bạn là 1 game master hài hước. Người chơi vừa THUA trong săn quái. Hãy kể 1 câu kết cực kỳ hài hước, hơi châm biếm, dùng tiếng Việt street style, độ dài 1 câu. Ví dụ: 'Quái biến kiếm của mày thành xúc xích, mày nhận được cái nịt!' hoặc 'Quái dùng chiêu nhìn mày xấu, mày mất 10HP và 5 xu vì tự ái'"
    
    if custom_context:
        prompt += f"\nBối cảnh thêm: {custom_context}"
    
    payload = {
        "model": "openai/gpt-oss-120b",  # GPT-OSS-120B không có sẵn, dùng model tốt nhất
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 150
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROQ_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content'].strip()
                else:
                    # Fallback nếu AI lỗi
                    return random.choice(win_messages) if outcome == "win" else random.choice(lose_messages)
        except:
            return random.choice(win_messages) if outcome == "win" else random.choice(lose_messages)

# Fallback messages (khi AI fail)
win_messages = [
    "Mày đã biến quái thành cục cứt! Chúc mừng 20 xu!",
    "Quái xin lỗi vì đã nhìn mày, nó đưa mày 30 xu chuộc tội!",
    "Mày đá quái bay 10 mét, nó rớt ra 50 xu và 1 trái cam!"
]

lose_messages = [
    "Quái biến kiếm của mày thành xúc xích, mày nhận được cái nịt!",
    "Quái cười vào mặt mày xong chạy mất, mày mất 10 xu tiền vé vườn thú!",
    "Mày bị quái húc văng 5 mét, rớt mất 5 xu, ai nhặt được người đó hên!"
]

def init_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "gold": 100,
            "weapon": "kiếm gỉ",
            "armor": "áo rách",
            "last_daily": None,
            "total_hunts": 0
        }

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} đã sẵn sàng!")

@bot.command(name='go_hunt')
async def go_hunt(ctx):
    user_id = str(ctx.author.id)
    init_user(user_id)
    
    cooldown_key = f"{user_id}_hunt"
    if cooldown_key in cooldowns:
        time_left = (cooldowns[cooldown_key] - datetime.now()).total_seconds()
        if time_left > 0:
            await ctx.send(f"🐉 {ctx.author.mention} Chậm thôi, đợi {int(time_left)} giây nữa quái mới mọc!")
            return
    
    cooldowns[cooldown_key] = datetime.now() + timedelta(seconds=10)
    
    is_win = random.choice([True, False])
    
    async with ctx.typing():
        story = await call_groq_ai("win" if is_win else "lose", f"user có {user_data[user_id]['weapon']} và {user_data[user_id]['armor']}")
    
    if is_win:
        reward = random.randint(15, 50)
        user_data[user_id]["gold"] += reward
        user_data[user_id]["total_hunts"] += 1
        embed = discord.Embed(
            title="🏆 CHIẾN THẮNG! 🏆",
            description=f"{story}\n\n✨ Nhận được **{reward} xu**!",
            color=discord.Color.green()
        )
    else:
        penalty = random.randint(5, 20)
        user_data[user_id]["gold"] = max(0, user_data[user_id]["gold"] - penalty)
        user_data[user_id]["total_hunts"] += 1
        embed = discord.Embed(
            title="💀 THẤT BẠI! 💀",
            description=f"{story}\n\n💸 Mất **{penalty} xu**!",
            color=discord.Color.red()
        )
    
    embed.add_field(name="💰 Xu hiện tại", value=f"{user_data[user_id]['gold']}", inline=True)
    embed.add_field(name="⚔️ Vũ khí", value=user_data[user_id]['weapon'], inline=True)
    embed.add_field(name="🛡️ Giáp", value=user_data[user_id]['armor'], inline=True)
    embed.set_footer(text="Dùng /shop để mua đồ mới!")
    
    await ctx.send(embed=embed)

@bot.command(name='shop')
async def shop(ctx):
    embed = discord.Embed(
        title="🛒 CỬA HÀNG",
        description="Dùng `/buy [món]` để mua",
        color=discord.Color.blue()
    )
    embed.add_field(name="Kiếm sắt (100 xu)", value="Tăng 20% cơ hội thắng", inline=False)
    embed.add_field(name="Áo da (80 xu)", value="Giảm 50% tiền phạt khi thua", inline=False)
    embed.add_field(name="Thuốc hồi máu (30 xu)", value="+10 xu mỗi lần dùng", inline=False)
    
    user_id = str(ctx.author.id)
    init_user(user_id)
    embed.set_footer(text=f"💰 Xu của bạn: {user_data[user_id]['gold']}")
    
    await ctx.send(embed=embed)

@bot.command(name='buy')
async def buy(ctx, *, item: str):
    user_id = str(ctx.author.id)
    init_user(user_id)
    gold = user_data[user_id]["gold"]
    
    if "kiếm sắt" in item.lower() and gold >= 100:
        user_data[user_id]["gold"] -= 100
        user_data[user_id]["weapon"] = "kiếm sắt"
        await ctx.send(f"⚔️ {ctx.author.mention} Đã mua **Kiếm sắt**! Còn {user_data[user_id]['gold']} xu")
    elif "áo da" in item.lower() and gold >= 80:
        user_data[user_id]["gold"] -= 80
        user_data[user_id]["armor"] = "áo da"
        await ctx.send(f"🛡️ {ctx.author.mention} Đã mua **Áo da**! Còn {user_data[user_id]['gold']} xu")
    elif "thuốc" in item.lower() and gold >= 30:
        user_data[user_id]["gold"] -= 30
        user_data[user_id]["gold"] += 10
        await ctx.send(f"💊 {ctx.author.mention} Dùng thuốc! Nhận 10 xu, tổng: {user_data[user_id]['gold']} xu")
    else:
        await ctx.send(f"❌ Không đủ xu hoặc không có món `{item}` trong shop!")

@bot.command(name='inv')
async def inventory(ctx):
    user_id = str(ctx.author.id)
    init_user(user_id)
    data = user_data[user_id]
    
    embed = discord.Embed(
        title=f"📦 {ctx.author.name}'s Inventory",
        color=discord.Color.gold()
    )
    embed.add_field(name="💰 Xu", value=data['gold'], inline=True)
    embed.add_field(name="⚔️ Vũ khí", value=data['weapon'], inline=True)
    embed.add_field(name="🛡️ Giáp", value=data['armor'], inline=True)
    embed.add_field(name="🎯 Tổng số lần săn", value=data['total_hunts'], inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='daily')
async def daily(ctx):
    user_id = str(ctx.author.id)
    init_user(user_id)
    
    today = datetime.now().date()
    if user_data[user_id]["last_daily"] == str(today):
        await ctx.send(f"⏰ {ctx.author.mention} Hôm nay nhận rồi! Quay lại mai nha!")
        return
    
    reward = 50
    user_data[user_id]["gold"] += reward
    user_data[user_id]["last_daily"] = str(today)
    await ctx.send(f"🎁 {ctx.author.mention} Nhận **{reward} xu** đây! Tổng: {user_data[user_id]['gold']} xu")

@bot.command(name='top')
async def top_rich(ctx):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]['gold'], reverse=True)[:5]
    if not sorted_users:
        await ctx.send("Chưa có ai săn quái cả!")
        return
    
    embed = discord.Embed(title="💰 Bảng xếp hạng giàu nhất 💰", color=discord.Color.gold())
    for i, (uid, data) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(uid))
            embed.add_field(name=f"#{i} {user.name}", value=f"{data['gold']} xu", inline=False)
        except:
            embed.add_field(name=f"#{i} Người lạ", value=f"{data['gold']} xu", inline=False)
    
    await ctx.send(embed=embed)

# Chạy bot
if __name__ == "__main__":
    bot.run(TOKEN)
