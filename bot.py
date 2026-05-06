import discord
from discord import app_commands
import aiohttp
import asyncio
import json
import random
import os
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_KEY = os.getenv('GROQ_API_KEY')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DATA_FILE = "user_data.json"

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Bot {self.user} đã sẵn sàng với slash command!")

bot = MyBot()
app = Flask(__name__)

# ==================== DATABASE ====================
def load_db():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=4)

user_data = load_db()
cooldowns = {}

# ==================== FLASK KEEP ALIVE ====================
@app.route('/')
def home():
    return "🐉 Bot săn quái đang chạy ngon lành!"

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# ==================== HELPER ====================
def init_user(uid):
    uid = str(uid)
    if uid not in user_data:
        user_data[uid] = {
            "gold": 100,
            "weapon": "kiếm gỉ",
            "armor": "áo rách",
            "hunts": 0,
            "wins": 0,
            "losses": 0,
            "boss_kills": 0,
            "last_daily": None,
            "last_weekly": None
        }
        save_db()

def check_cooldown(uid, cmd, seconds):
    key = f"{uid}_{cmd}"
    if key in cooldowns and datetime.now() < cooldowns[key]:
        remaining = int((cooldowns[key] - datetime.now()).total_seconds())
        return remaining
    cooldowns[key] = datetime.now() + timedelta(seconds=seconds)
    return 0

# ==================== AI CALL ====================
async def call_groq_ai(outcome, context=""):
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Bạn là game master hài hước, lầy lội, style GenZ. 
Người chơi vừa {'THẮNG' if outcome == 'win' else 'THUA'} trong săn quái. 
Hãy kể 1 câu cực kỳ hài hước, bất ngờ, dùng tiếng Việt street style, có thể chửi thề nhẹ.
Độ dài tối đa 20 từ.
Bối cảnh: {context}
Kết quả:"""
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": 60
    }
    
    fallback_win = ["Mày đập quái chết tươi! +random xu", "Quái thấy mặt mày xỉu luôn! 🥀", "Mày thắng á? AI sinh ra nói dối à?"]
    fallback_lose = ["Mày thua! Quái cười vào mặt mày! 🤣", "Mày biến kiếm thành xúc xích rồi! 🌭", "Quái đạp mày 10 cái, mất xu!"]
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROQ_URL, headers=headers, json=payload, timeout=6) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data['choices'][0]['message']['content'].strip()
                    return text[:150]
                return random.choice(fallback_win if outcome == "win" else fallback_lose)
        except:
            return random.choice(fallback_win if outcome == "win" else fallback_lose)

# ==================== SLASH COMMANDS ====================
@bot.tree.command(name='go_hunt', description="🐉 Săn quái – kiếm xu, hên xui")
async def go_hunt(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    cd = check_cooldown(uid, "hunt", 10)
    if cd > 0:
        return await interaction.response.send_message(f"⌛ Chậm thôi bro, còn {cd}s nữa quái mới mọc!", ephemeral=True)
    
    await interaction.response.defer()
    
    # Tính tỉ lệ thắng dựa trên vũ khí
    win_rate = 0.5
    if user_data[uid]['weapon'] == "kiếm sắt":
        win_rate = 0.65
    elif user_data[uid]['weapon'] == "kiếm thần":
        win_rate = 0.8
    
    is_win = random.random() < win_rate
    
    # Random sự kiện đặc biệt (5%)
    special = random.random() < 0.05
    
    story = await call_groq_ai("win" if is_win else "lose", f"vũ khí: {user_data[uid]['weapon']}, giáp: {user_data[uid]['armor']}")
    
    if special:
        story += "\n\n🎲 **SỰ KIỆN ĐẶC BIỆT!**"
    
    if is_win:
        reward = random.randint(20, 70)
        if special:
            reward *= 2
            story += f"\n✨ NHẬN X2! ✨"
        user_data[uid]['gold'] += reward
        user_data[uid]['wins'] += 1
        color = discord.Color.green()
        result_text = f"✨ +{reward} xu"
    else:
        penalty = random.randint(10, 35)
        if user_data[uid]['armor'] == "áo da":
            penalty = penalty // 2
        if special:
            penalty = penalty // 2
            story += f"\n🛡️ Giáp giảm sát thương!"
        user_data[uid]['gold'] = max(0, user_data[uid]['gold'] - penalty)
        user_data[uid]['losses'] += 1
        color = discord.Color.red()
        result_text = f"💸 -{penalty} xu"
    
    user_data[uid]['hunts'] += 1
    save_db()
    
    embed = discord.Embed(
        title="🏹 KẾT QUẢ SĂN QUÁI 🏹",
        description=f"```{story}```",
        color=color
    )
    embed.add_field(name="💰 Kết quả", value=result_text, inline=True)
    embed.add_field(name="📦 Ví hiện tại", value=f"{user_data[uid]['gold']} xu", inline=True)
    embed.add_field(name="⚔️ Trang bị", value=f"{user_data[uid]['weapon']} | {user_data[uid]['armor']}", inline=False)
    embed.set_footer(text=f"Tổng số lần săn: {user_data[uid]['hunts']} (Thắng: {user_data[uid]['wins']} | Thua: {user_data[uid]['losses']})")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='inv', description="📦 Xem túi đồ và số xu")
async def inventory(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    data = user_data[uid]
    
    embed = discord.Embed(title=f"📦 TÚI ĐỒ CỦA {interaction.user.display_name}", color=discord.Color.gold())
    embed.add_field(name="💰 Xu", value=f"`{data['gold']}`", inline=True)
    embed.add_field(name="⚔️ Vũ khí", value=f"`{data['weapon']}`", inline=True)
    embed.add_field(name="🛡️ Giáp", value=f"`{data['armor']}`", inline=True)
    embed.add_field(name="🏆 Boss đã giết", value=f"`{data['boss_kills']}`", inline=True)
    embed.add_field(name="📊 Tỉ lệ thắng", value=f"`{(data['wins']/data['hunts']*100) if data['hunts'] > 0 else 0:.1f}%`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='shop', description="🛒 Xem cửa hàng trang bị")
async def shop(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    embed = discord.Embed(title="🛒 CỬA HÀNG QUÁI THỦ", description="Dùng `/buy [món]` để mua", color=discord.Color.blue())
    embed.add_field(name="⚔️ Kiếm sắt", value="Giá: `100 xu`\n+15% tỉ lệ thắng", inline=False)
    embed.add_field(name="🛡️ Áo da", value="Giá: `80 xu`\nGiảm 50% tiền phạt khi thua", inline=False)
    embed.add_field(name="⚔️ Kiếm thần", value="Giá: `300 xu`\n+30% tỉ lệ thắng (cực phẩm)", inline=False)
    embed.set_footer(text=f"💰 Xu của bạn: {user_data[uid]['gold']}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='buy', description="💸 Mua trang bị từ shop")
@app_commands.describe(item="Tên món đồ: kiếm sắt, áo da, kiếm thần")
async def buy(interaction: discord.Interaction, item: str):
    uid = str(interaction.user.id)
    init_user(uid)
    
    items = {
        "kiếm sắt": {"price": 100, "type": "weapon", "value": "kiếm sắt"},
        "kiếm thần": {"price": 300, "type": "weapon", "value": "kiếm thần"},
        "áo da": {"price": 80, "type": "armor", "value": "áo da"}
    }
    
    item_lower = item.lower()
    if item_lower not in items:
        return await interaction.response.send_message("❌ Không có món này! Dùng `/shop` để xem danh sách.", ephemeral=True)
    
    item_info = items[item_lower]
    if user_data[uid]['gold'] >= item_info['price']:
        user_data[uid]['gold'] -= item_info['price']
        if item_info['type'] == "weapon":
            user_data[uid]['weapon'] = item_info['value']
        else:
            user_data[uid]['armor'] = item_info['value']
        save_db()
        
        embed = discord.Embed(title="✅ MUA THÀNH CÔNG!", description=f"Bạn đã mua **{item_info['value']}**", color=discord.Color.green())
        embed.add_field(name="💰 Xu còn lại", value=f"{user_data[uid]['gold']}", inline=True)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"💸 Bạn nghèo quá! Cần {item_info['price']} xu nhưng bạn chỉ có {user_data[uid]['gold']} xu.", ephemeral=True)

@bot.tree.command(name='daily', description="🎁 Nhận 50 xu mỗi ngày")
async def daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    today = datetime.now().date()
    last = user_data[uid].get('last_daily')
    
    if last and datetime.strptime(last, "%Y-%m-%d").date() == today:
        return await interaction.response.send_message("⏰ Hôm nay bạn đã nhận rồi! Quay lại mai nha!", ephemeral=True)
    
    reward = 50
    user_data[uid]['gold'] += reward
    user_data[uid]['last_daily'] = str(today)
    save_db()
    
    await interaction.response.send_message(f"🎁 {interaction.user.mention} nhận **{reward} xu**! Hiện có {user_data[uid]['gold']} xu.")

@bot.tree.command(name='weekly', description="📆 Nhận 200 xu mỗi tuần")
async def weekly(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    today = datetime.now().date()
    last = user_data[uid].get('last_weekly')
    
    if last:
        last_date = datetime.strptime(last, "%Y-%m-%d").date()
        if (today - last_date).days < 7:
            remaining = 7 - (today - last_date).days
            return await interaction.response.send_message(f"⏰ Còn {remaining} ngày nữa mới nhận được tuần tiếp theo!", ephemeral=True)
    
    reward = 200
    user_data[uid]['gold'] += reward
    user_data[uid]['last_weekly'] = str(today)
    save_db()
    
    await interaction.response.send_message(f"📆 {interaction.user.mention} nhận **{reward} xu** tuần này! Giờ có {user_data[uid]['gold']} xu.")

@bot.tree.command(name='top', description="🏆 Bảng xếp hạng đại gia")
async def top(interaction: discord.Interaction):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]['gold'], reverse=True)[:10]
    
    if not sorted_users:
        return await interaction.response.send_message("Chưa có ai chơi cả!")
    
    description = ""
    for i, (uid, data) in enumerate(sorted_users, 1):
        user = await bot.fetch_user(int(uid))
        name = user.display_name if user else f"Người lạ {uid[:6]}"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "💰"
        description += f"{medal} **#{i}** {name}: `{data['gold']}` xu (⚔️: {data['hunts']})\n"
    
    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG ĐẠI GIA 🏆", description=description, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='gift', description="🎁 Tặng xu cho bạn bè")
@app_commands.describe(nguoi_nhan="Tag người nhận", so_luong="Số xu muốn tặng")
async def gift(interaction: discord.Interaction, nguoi_nhan: discord.User, so_luong: int):
    if so_luong <= 0:
        return await interaction.response.send_message("Số xu phải lớn hơn 0!", ephemeral=True)
    
    uid_giver = str(interaction.user.id)
    uid_receiver = str(nguoi_nhan.id)
    
    if uid_giver == uid_receiver:
        return await interaction.response.send_message("Không thể tự tặng chính mình!", ephemeral=True)
    
    init_user(uid_giver)
    init_user(uid_receiver)
    
    if user_data[uid_giver]['gold'] < so_luong:
        return await interaction.response.send_message(f"Bạn chỉ có {user_data[uid_giver]['gold']} xu, không đủ để tặng {so_luong} xu!", ephemeral=True)
    
    user_data[uid_giver]['gold'] -= so_luong
    user_data[uid_receiver]['gold'] += so_luong
    save_db()
    
    embed = discord.Embed(title="🎁 QUÀ TẶNG", description=f"{interaction.user.mention} đã tặng **{so_luong} xu** cho {nguoi_nhan.mention}!", color=discord.Color.magenta())
    embed.add_field(name="💰 Người tặng còn", value=f"{user_data[uid_giver]['gold']} xu", inline=True)
    embed.add_field(name="💰 Người nhận có", value=f"{user_data[uid_receiver]['gold']} xu", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='rob', description="😈 Liều ăn nhiều – cướp xu người khác (rủi ro cao)")
@app_commands.describe(nguoi_cuop="Người muốn cướp")
async def rob(interaction: discord.Interaction, nguoi_cuop: discord.User):
    uid_robber = str(interaction.user.id)
    uid_target = str(nguoi_cuop.id)
    
    if uid_robber == uid_target:
        return await interaction.response.send_message("Muốn cướp chính mình à? Bị điên à?", ephemeral=True)
    
    init_user(uid_robber)
    init_user(uid_target)
    
    cd = check_cooldown(uid_robber, "rob", 300)  # 5 phút
    if cd > 0:
        return await interaction.response.send_message(f"⌛ Đợi {cd}s nữa mới đi cướp được! Cảnh sát đang rình.", ephemeral=True)
    
    success = random.random() < 0.4  # 40% thành công
    
    if success:
        stolen = random.randint(10, 50)
        stolen = min(stolen, user_data[uid_target]['gold'])
        if stolen == 0:
            return await interaction.response.send_message(f"🤡 {nguoi_cuop.mention} nghèo rớt mồng tơi, chả có gì để cướp!")
        user_data[uid_robber]['gold'] += stolen
        user_data[uid_target]['gold'] -= stolen
        save_db()
        await interaction.response.send_message(f"😈 {interaction.user.mention} cướp thành công **{stolen} xu** từ {nguoi_cuop.mention}! Liều thì ăn nhiều!")
    else:
        penalty = random.randint(20, 60)
        user_data[uid_robber]['gold'] = max(0, user_data[uid_robber]['gold'] - penalty)
        save_db()
        await interaction.response.send_message(f"🚔 {interaction.user.mention} bị bắt quả tang! Mất **{penalty} xu** tiền hối lộ công an. Khôn nên người đi!")
    
    save_db()

@bot.tree.command(name='hunt_stats', description="📊 Xem thống kê săn bắn của bạn")
async def hunt_stats(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    data = user_data[uid]
    
    win_rate = (data['wins'] / data['hunts'] * 100) if data['hunts'] > 0 else 0
    
    embed = discord.Embed(title=f"📊 THỐNG KÊ SĂN BẮN – {interaction.user.display_name}", color=discord.Color.teal())
    embed.add_field(name="🎯 Tổng số lần săn", value=data['hunts'], inline=True)
    embed.add_field(name="🏆 Số lần thắng", value=data['wins'], inline=True)
    embed.add_field(name="💀 Số lần thua", value=data['losses'], inline=True)
    embed.add_field(name="📈 Tỉ lệ thắng", value=f"{win_rate:.1f}%", inline=True)
    embed.add_field(name="💀 Boss đã giết", value=data['boss_kills'], inline=True)
    embed.set_footer(text="Hãy mua đồ ở shop để tăng tỉ lệ thắng!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='boss', description="👾 Săn boss đặc biệt – phần thưởng lớn!")
async def boss(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    cd = check_cooldown(uid, "boss", 3600)  # 1 tiếng
    if cd > 0:
        return await interaction.response.send_message(f"⌛ Boss mọc lại sau {cd//60} phút {cd%60} giây! Luyện tập thêm đi.", ephemeral=True)
    
    await interaction.response.defer()
    
    win_rate = 0.3
    if user_data[uid]['weapon'] == "kiếm sắt":
        win_rate = 0.45
    elif user_data[uid]['weapon'] == "kiếm thần":
        win_rate = 0.6
    
    is_win = random.random() < win_rate
    
    if is_win:
        reward = random.randint(150, 300)
        user_data[uid]['gold'] += reward
        user_data[uid]['boss_kills'] += 1
        user_data[uid]['wins'] += 1
        color = discord.Color.purple()
        result = f"🎉 BOSS CHẾT! Nhận {reward} xu! 🎉"
    else:
        penalty = random.randint(50, 100)
        if user_data[uid]['armor'] == "áo da":
            penalty = int(penalty * 0.6)
        user_data[uid]['gold'] = max(0, user_data[uid]['gold'] - penalty)
        user_data[uid]['losses'] += 1
        color = discord.Color.dark_red()
        result = f"💀 BOSS ĐÁNH MÀY BAY MÀU! Mất {penalty} xu 💀"
    
    user_data[uid]['hunts'] += 1
    save_db()
    
    embed = discord.Embed(title="👾 SĂN BOSS TỐI THƯỢNG 👾", description=result, color=color)
    embed.add_field(name="💰 Xu hiện tại", value=f"{user_data[uid]['gold']}", inline=True)
    embed.add_field(name="⚔️ Trang bị", value=f"{user_data[uid]['weapon']} + {user_data[uid]['armor']}", inline=True)
    embed.set_footer(text="Boss mọc lại sau 1 tiếng! Dùng /boss để quẩy tiếp")
    
    await interaction.followup.send(embed=embed)

# ==================== RUN ====================
threading.Thread(target=run_flask, daemon=True).start()
bot.run(TOKEN)
