import discord
from discord import app_commands
import aiohttp
import asyncio
import json
import random
import os
import threading
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_KEY = os.getenv('GROQ_API_KEY')
GIST_TOKEN = os.getenv('GIST_TOKEN')
GIST_ID = os.getenv('GIST_ID')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DATA_FILE = "user_data.json"

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
boss_cooldowns = {}

# ==================== FLASK KEEP ALIVE ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "🐉 Bot săn quái đang chạy!"

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# ==================== DISCORD BOT ====================
class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)
        self.active_battles = {}

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Bot {self.user} đã sẵn sàng!")

bot = MyBot()

# ==================== HỆ THỐNG CẤP ĐỘ QUÁI ====================
ENEMY_TYPES = {
    "beginner": {
        "name": "🐣 Beginner",
        "level_req": 0,
        "time_limit": 8.0,
        "reward_range": (10, 20),
        "hp_multiplier": 0.5,
        "damage_range": (5, 10),
        "exp_reward": 10
    },
    "very_easy": {
        "name": "😊 Very Easy",
        "level_req": 2,
        "time_limit": 7.5,
        "reward_range": (20, 30),
        "hp_multiplier": 0.6,
        "damage_range": (8, 14),
        "exp_reward": 15
    },
    "easy": {
        "name": "👍 Easy",
        "level_req": 4,
        "time_limit": 6.0,
        "reward_range": (40, 50),
        "hp_multiplier": 0.7,
        "damage_range": (10, 18),
        "exp_reward": 20
    },
    "quite_normal": {
        "name": "😐 Quite Normal",
        "level_req": 6,
        "time_limit": 5.5,
        "reward_range": (50, 70),
        "hp_multiplier": 0.8,
        "damage_range": (12, 22),
        "exp_reward": 25
    },
    "normal": {
        "name": "😑 Normal",
        "level_req": 8,
        "time_limit": 5.0,
        "reward_range": (70, 90),
        "hp_multiplier": 0.9,
        "damage_range": (14, 26),
        "exp_reward": 30
    },
    "quite_hard": {
        "name": "😤 Quite Hard",
        "level_req": 10,
        "time_limit": 4.5,
        "reward_range": (90, 110),
        "hp_multiplier": 1.0,
        "damage_range": (16, 30),
        "exp_reward": 35
    },
    "hard": {
        "name": "😈 Hard",
        "level_req": 12,
        "time_limit": 4.0,
        "reward_range": (120, 160),
        "hp_multiplier": 1.1,
        "damage_range": (18, 35),
        "exp_reward": 45
    },
    "elite": {
        "name": "💀 Elite",
        "level_req": 15,
        "time_limit": 3.0,
        "reward_range": (160, 300),
        "hp_multiplier": 1.3,
        "damage_range": (22, 45),
        "exp_reward": 60
    },
    "master": {
        "name": "👑 Master",
        "level_req": 20,
        "time_limit": 2.75,
        "reward_range": (300, 400),
        "hp_multiplier": 1.6,
        "damage_range": (30, 60),
        "exp_reward": 100
    }
}

# ==================== HELPER ====================
def init_user(uid):
    uid = str(uid)
    if uid not in user_data:
        user_data[uid] = {
            "gold": 100,
            "weapon": "kiếm gỉ",
            "armor": "áo rách",
            "level": 1,
            "exp": 0,
            "hp_max": 55,
            "hp_current": 55,
            "death_time": None,
            "total_hunts": 0,
            "total_wins": 0,
            "unlocked_maps": ["beginner"],
            "current_map": "beginner",
            "inventory": {},
            "active_buffs": []
        }
        save_db()

def get_weapon_bonus(weapon):
    bonus = {"kiếm gỉ": 0, "kiếm sắt": 25, "kiếm thép": 50, "rìu chiến": 80, "kiếm huyền thoại": 120}
    return bonus.get(weapon, 0)

def get_armor_reduce(armor):
    reduce = {"áo rách": 0, "áo da": 25, "áo giáp sắt": 45, "áo thần": 65}
    return reduce.get(armor, 0) / 100

def get_damage(user_id, is_monster=False, monster_type="normal"):
    uid = str(user_id)
    if is_monster:
        if monster_type == "boss":
            base = random.randint(25, 50)
        else:
            enemy = ENEMY_TYPES.get(user_data[uid].get("current_map", "beginner"), ENEMY_TYPES["beginner"])
            base = random.randint(*enemy["damage_range"])
        reduce = get_armor_reduce(user_data[uid]["armor"])
        return int(base * (1 - reduce))
    else:
        base = random.randint(10, 25) + user_data[uid]["level"] * 2
        bonus = get_weapon_bonus(user_data[uid]["weapon"])
        if "active_buffs" in user_data[uid]:
            for buff in user_data[uid]["active_buffs"]:
                if buff["type"] == "dame":
                    bonus += 10
        return int(base * (1 + bonus / 100))

def get_next_symbol():
    symbols = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", 
               "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
    return random.choice(symbols)

def format_reward(gold, player_count):
    if player_count == 0:
        return 0
    remainder = gold % player_count
    return gold - remainder

def check_map_unlock(uid):
    """Kiểm tra và mở khóa map mới dựa trên level"""
    level = user_data[uid]["level"]
    unlocked = user_data[uid]["unlocked_maps"]
    
    unlock_map = {
        2: "very_easy",
        4: "easy", 
        6: "quite_normal",
        8: "normal",
        10: "quite_hard",
        12: "hard",
        15: "elite",
        20: "master"
    }
    
    new_maps = []
    for req_level, map_name in unlock_map.items():
        if level >= req_level and map_name not in unlocked:
            unlocked.append(map_name)
            new_maps.append(ENEMY_TYPES[map_name]["name"])
    
    if new_maps:
        user_data[uid]["unlocked_maps"] = unlocked
        save_db()
        return new_maps
    return []

# ==================== AI FUNNY COMMENT ====================
async def get_funny_comment(win, monster_type="normal"):
    if not GROQ_KEY:
        return random.choice(["Quái thấy m đẹp trai quá nên tự xỉu!", "Thắng rồi, đi ăn mừng đi bro!"])
    
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    prompt = f"Hãy viết 1 câu cực kỳ hài hước, lầy lội, style GenZ khi người chơi {'THẮNG' if win else 'THUA'} một trận đấu với {monster_type} trong game Discord. Chỉ 1 câu ngắn gọn, tối đa 20 từ."
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.9, "max_tokens": 50}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROQ_URL, headers=headers, json=payload, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content'].strip()
                return random.choice(["Thắng đẹp!", "Xịn vãi chưởng!"])
        except:
            return random.choice(["Thắng rồi, quẩy lên!", "Thua thì cố gắng lần sau!"])

# ==================== BATTLE SYSTEM ====================
async def start_battle(interaction, players, is_boss=False):
    channel_id = interaction.channel_id
    uid = str(interaction.user.id)
    
    if not is_boss:
        current_map = user_data[uid].get("current_map", "beginner")
        enemy_data = ENEMY_TYPES[current_map]
    else:
        enemy_data = {
            "name": "👾 BOSS CỰC KỲ TO TƯỚNG 👾",
            "time_limit": 4.0,
            "hp_multiplier": 2.0,
            "damage_range": (30, 70),
            "reward_range": (200, 500),
            "exp_reward": 100
        }
    
    total_hp_players = sum(p["hp_max"] for p in players)
    monster_hp = int(total_hp_players * enemy_data["hp_multiplier"])
    
    battle_data = {
        "players": players,
        "monster_hp": monster_hp,
        "monster_hp_max": monster_hp,
        "current_turn": 0,
        "game_over": False,
        "is_boss": is_boss,
        "enemy_data": enemy_data,
        "channel_id": channel_id
    }
    bot.active_battles[channel_id] = battle_data
    
    channel = bot.get_channel(channel_id)
    monster_type = "🔥 BOSS 🔥" if is_boss else f"🐉 {enemy_data['name']} 🐉"
    await channel.send(f"⚔️ **TRẬN CHIẾN BẮT ĐẦU!** ⚔️\n{monster_type} có **{monster_hp} HP**!\n⏱️ Thời gian mỗi lượt: {enemy_data['time_limit']} giây")
    
    # Gọi process_turn và tạo task riêng để không bị treo
    asyncio.create_task(process_turn(channel_id))

async def process_turn(channel_id):
    import asyncio
    battle = bot.active_battles.get(channel_id)
    if not battle or battle["game_over"]:
        return
    
    channel = bot.get_channel(channel_id)
    alive_players = [p for p in battle["players"] if p["hp_current"] > 0]
    
    if not alive_players:
        await end_battle(channel_id, win=False)
        return
    
    if battle["monster_hp"] <= 0:
        await end_battle(channel_id, win=True)
        return
    
    current = battle["current_turn"] % len(alive_players)
    player = alive_players[current]
    battle["current_turn"] += 1
    
    symbol = get_next_symbol()
    time_limit = battle["enemy_data"]["time_limit"]
    
    await channel.send(f"🔤 **Đến lượt {player['user'].mention}** – hãy nói chữ: **{symbol}** trong {time_limit} giây!\n🐉 HP quái: {battle['monster_hp']}/{battle['monster_hp_max']} | 💚 HP bạn: {player['hp_current']}/{player['hp_max']}")
    
    def check(m):
        return m.author.id == player["user"].id and m.content.strip().upper() == symbol and m.channel.id == channel_id
    
    try:
        msg = await bot.wait_for('message', timeout=time_limit, check=check)
        dmg = get_damage(player["user"].id)
        battle["monster_hp"] = max(0, battle["monster_hp"] - dmg)
        await channel.send(f"✅ {player['user'].mention} **đánh trúng!** Gây {dmg} sát thương. Quái còn {battle['monster_hp']} HP.")
    except asyncio.TimeoutError:
        dmg = get_damage(player["user"].id, is_monster=True, monster_type="boss" if battle["is_boss"] else "normal")
        player["hp_current"] = max(0, player["hp_current"] - dmg)
        await channel.send(f"❌ {player['user'].mention} **không kịp!** Quái đánh {dmg} sát thương. Bạn còn {player['hp_current']} HP.")
        
        if player["hp_current"] == 0:
            uid = str(player["user"].id)
            user_data[uid]["death_time"] = datetime.now().isoformat()
            save_db()
            await channel.send(f"💀 {player['user'].mention} **đã ngã xuống!** Chờ 20 giây mới hồi sinh.")
    
    await asyncio.sleep(1.5)
    # Gọi lại chính nó để tiếp tục lượt tiếp theo
    asyncio.create_task(process_turn(channel_id))

# ==================== SLASH COMMANDS ====================
@bot.tree.command(name='go_hunt', description="🐉 Săn quái (rủ thêm 1-3 bạn)")
@app_commands.describe(nguoi1="Tag người chơi thứ 2", nguoi2="Tag người chơi thứ 3", nguoi3="Tag người chơi thứ 4")
async def go_hunt(interaction: discord.Interaction, nguoi1: discord.User = None, nguoi2: discord.User = None, nguoi3: discord.User = None):
    await interaction.response.defer()
    
    if interaction.channel_id in bot.active_battles:
        return await interaction.followup.send("⚠️ Đã có trận chiến trong kênh này! Kết thúc rồi hãy săn tiếp.")
    
    players = [interaction.user]
    for p in [nguoi1, nguoi2, nguoi3]:
        if p:
            players.append(p)
    players = list(dict.fromkeys(players))
    
    # Check cooldown
    for p in players:
        uid = str(p.id)
        init_user(uid)
        
        cd_key = f"{uid}_hunt"
        if cd_key in cooldowns and datetime.now() < cooldowns[cd_key]:
            remaining = int((cooldowns[cd_key] - datetime.now()).seconds)
            return await interaction.followup.send(f"⏰ {p.mention} đang trong thời gian chờ! Còn {remaining}s nữa.")
        
        death = user_data[uid].get("death_time")
        if death:
            dt = datetime.fromisoformat(death)
            if datetime.now() - dt < timedelta(seconds=20):
                remaining = 20 - int((datetime.now() - dt).seconds)
                return await interaction.followup.send(f"💀 {p.mention} đang chết! Còn {remaining}s mới hồi sinh.")
    
    mention = " ".join([p.mention for p in players])
    await interaction.followup.send(f"🔥 {mention} có muốn tham gia săn quái không? Gõ **ok** trong 30 giây!")
    
    confirmed = {interaction.user.id}
    start_time = datetime.now()
    
    def check_join(m):
        return m.author.id in [p.id for p in players] and m.content.strip().lower() == "ok" and m.channel.id == interaction.channel_id
    
    while len(confirmed) < len(players) and (datetime.now() - start_time).seconds < 30:
        try:
            msg = await bot.wait_for('message', timeout=10, check=check_join)
            confirmed.add(msg.author.id)
            await interaction.followup.send(f"✅ {msg.author.mention} đã tham gia!")
        except:
            break
    
    final_players = [p for p in players if p.id in confirmed]
    if len(final_players) == 0:
        return await interaction.followup.send("❌ Không ai tham gia, hủy săn...")
    
    # Set cooldown
    battle_players = []
    for p in final_players:
        uid = str(p.id)
        cooldowns[f"{uid}_hunt"] = datetime.now() + timedelta(seconds=10)
        battle_players.append({
            "user": p,
            "hp_current": user_data[uid]["hp_current"],
            "hp_max": user_data[uid]["hp_max"],
            "uid": uid
        })
    
    await start_battle(interaction, battle_players, is_boss=False)

@bot.tree.command(name='boss', description="👾 Săn BOSS (khó hơn, thưởng xịn hơn)")
@app_commands.describe(nguoi1="Tag người chơi thứ 2", nguoi2="Tag người chơi thứ 3", nguoi3="Tag người chơi thứ 4")
async def boss_hunt(interaction: discord.Interaction, nguoi1: discord.User = None, nguoi2: discord.User = None, nguoi3: discord.User = None):
    await interaction.response.defer()
    
    if interaction.channel_id in bot.active_battles:
        return await interaction.followup.send("⚠️ Đã có trận chiến trong kênh này!")
    
    players = [interaction.user]
    for p in [nguoi1, nguoi2, nguoi3]:
        if p:
            players.append(p)
    players = list(dict.fromkeys(players))
    
    # Check boss cooldown (3 phút)
    if interaction.channel_id in boss_cooldowns:
        remaining = int((boss_cooldowns[interaction.channel_id] - datetime.now()).seconds)
        if remaining > 0:
            return await interaction.followup.send(f"👾 BOSS đang hồi sinh! Còn {remaining} giây nữa mới xuất hiện lại.")
    
    for p in players:
        uid = str(p.id)
        init_user(uid)
        
        cd_key = f"{uid}_boss"
        if cd_key in cooldowns and datetime.now() < cooldowns[cd_key]:
            remaining = int((cooldowns[cd_key] - datetime.now()).seconds)
            return await interaction.followup.send(f"⏰ {p.mention} chưa sẵn sàng săn boss! Còn {remaining}s.")
        
        death = user_data[uid].get("death_time")
        if death:
            dt = datetime.fromisoformat(death)
            if datetime.now() - dt < timedelta(seconds=20):
                remaining = 20 - int((datetime.now() - dt).seconds)
                return await interaction.followup.send(f"💀 {p.mention} đang chết! Còn {remaining}s mới hồi sinh.")
    
    mention = " ".join([p.mention for p in players])
    await interaction.followup.send(f"👾 **BOSS XUẤT HIỆN!** 👾\n{mention} có muốn tham gia săn BOSS không? Gõ **ok** trong 30 giây!")
    
    confirmed = {interaction.user.id}
    start_time = datetime.now()
    
    def check_join(m):
        return m.author.id in [p.id for p in players] and m.content.strip().lower() == "ok" and m.channel.id == interaction.channel_id
    
    while len(confirmed) < len(players) and (datetime.now() - start_time).seconds < 30:
        try:
            msg = await bot.wait_for('message', timeout=10, check=check_join)
            confirmed.add(msg.author.id)
            await interaction.followup.send(f"✅ {msg.author.mention} đã tham gia!")
        except:
            break
    
    final_players = [p for p in players if p.id in confirmed]
    if len(final_players) == 0:
        return await interaction.followup.send("❌ Không ai tham gia, boss bỏ đi...")
    
    boss_cooldowns[interaction.channel_id] = datetime.now() + timedelta(seconds=180)  # 3 phút
    battle_players = []
    for p in final_players:
        uid = str(p.id)
        cooldowns[f"{uid}_boss"] = datetime.now() + timedelta(seconds=60)
        battle_players.append({
            "user": p,
            "hp_current": user_data[uid]["hp_current"],
            "hp_max": user_data[uid]["hp_max"],
            "uid": uid
        })
    
    await start_battle(interaction, battle_players, is_boss=True)

@bot.tree.command(name='pass', description="🗺️ Xem và vượt ải mở khóa map mới")
async def pass_map(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    current_map = user_data[uid].get("current_map", "beginner")
    current_data = ENEMY_TYPES[current_map]
    unlocked = user_data[uid]["unlocked_maps"]
    
    # Tìm map tiếp theo
    map_order = ["beginner", "very_easy", "easy", "quite_normal", "normal", "quite_hard", "hard", "elite", "master"]
    current_index = map_order.index(current_map) if current_map in map_order else 0
    
    msg = f"**🗺️ HỆ THỐNG VƯỢT ẢI**\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📍 **Map hiện tại:** {current_data['name']}\n"
    msg += f"📊 **Level yêu cầu map tiếp theo:** {2 + current_index * 2}\n\n"
    
    if current_index + 1 < len(map_order):
        next_map = map_order[current_index + 1]
        next_data = ENEMY_TYPES[next_map]
        req_level = 2 + current_index * 2
        
        if user_data[uid]["level"] >= req_level:
            if next_map not in unlocked:
                user_data[uid]["unlocked_maps"].append(next_map)
                msg += f"✅ **ĐÃ MỞ KHÓA:** {next_data['name']}!\n"
                msg += f"   Dùng `/change_map {next_map}` để chuyển sang map mới.\n"
                save_db()
            else:
                msg += f"🔓 **Map đã mở khóa:** {next_data['name']}\n"
                msg += f"   Dùng `/change_map {next_map}` để chuyển map.\n"
        else:
            msg += f"🔒 **Cần level {req_level} để mở {next_data['name']}**\n"
    else:
        msg += f"🏆 **Bạn đã đạt map cao nhất!** 🏆\n"
    
    # Hiển thị các map đã mở khóa
    msg += f"\n**🗺️ Các map đã mở khóa:**\n"
    for map_name in unlocked:
        map_data = ENEMY_TYPES[map_name]
        check = "✅" if map_name == current_map else "  "
        msg += f"{check} {map_data['name']} (level {map_data['level_req']}+)\n"
    
    msg += f"\n💡 Dùng `/change_map [tên]` để đổi map săn!"
    await interaction.response.send_message(msg)

@bot.tree.command(name='change_map', description="🗺️ Đổi map săn quái")
@app_commands.describe(map_name="Tên map: beginner, very_easy, easy, quite_normal, normal, quite_hard, hard, elite, master")
async def change_map(interaction: discord.Interaction, map_name: str):
    uid = str(interaction.user.id)
    init_user(uid)
    
    map_name = map_name.lower()
    if map_name not in ENEMY_TYPES:
        return await interaction.response.send_message("❌ Tên map không hợp lệ! Các map: beginner, very_easy, easy, quite_normal, normal, quite_hard, hard, elite, master")
    
    if map_name not in user_data[uid]["unlocked_maps"]:
        req_level = ENEMY_TYPES[map_name]["level_req"]
        return await interaction.response.send_message(f"🔒 Bạn chưa mở khóa map này! Cần level {req_level} và dùng `/pass` để vượt ải.")
    
    user_data[uid]["current_map"] = map_name
    save_db()
    
    map_data = ENEMY_TYPES[map_name]
    await interaction.response.send_message(f"🗺️ Đã chuyển sang map **{map_data['name']}**!\n⏱️ Thời gian phản xạ: {map_data['time_limit']}s | 💰 Phần thưởng: {map_data['reward_range'][0]}-{map_data['reward_range'][1]} xu")

@bot.tree.command(name='map_info', description="🗺️ Xem thông tin các map")
async def map_info(interaction: discord.Interaction):
    msg = f"**🗺️ THÔNG TIN CÁC MAP**\n━━━━━━━━━━━━━━━━━━━━━\n"
    for key, data in ENEMY_TYPES.items():
        msg += f"\n**{data['name']}**\n"
        msg += f"   📊 Level yêu cầu: {data['level_req']}+\n"
        msg += f"   ⏱️ Thời gian: {data['time_limit']}s\n"
        msg += f"   💰 Xu: {data['reward_range'][0]}-{data['reward_range'][1]}\n"
        msg += f"   ✨ Exp: {data['exp_reward']}\n"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━\n💡 Dùng `/pass` để vượt ải mở khóa map mới!"
    await interaction.response.send_message(msg)

@bot.tree.command(name='shop', description="🛒 Xem cửa hàng")
async def shop(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    msg = f"**🛒 CỬA HÀNG SĂN QUÁI**\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 **Xu của bạn:** {user_data[uid]['gold']}\n\n"
    msg += f"**⚔️ VŨ KHÍ**\n• `kiếm sắt` - 150 xu (+25% dame)\n• `kiếm thép` - 300 xu (+50% dame)\n• `rìu chiến` - 500 xu (+80% dame)\n• `kiếm huyền thoại` - 1000 xu (+120% dame)\n\n"
    msg += f"**🛡️ GIÁP**\n• `áo da` - 120 xu (-25% dame nhận)\n• `áo giáp sắt` - 280 xu (-45% dame)\n• `áo thần` - 600 xu (-65% dame)\n\n"
    msg += f"**💊 VẬT PHẨM**\n• `bình máu nhỏ` - 50 xu (hồi 30% HP)\n• `bình máu lớn` - 100 xu (hồi 60% HP)\n• `bình máu to` - 200 xu (hồi 100% HP)\n• `bùa may mắn` - 150 xu (+10% dame 1 trận)\n• `thẻ hồi sinh` - 300 xu (revive 1 lần)\n\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n💡 Dùng `/buy [tên]` để mua, `/use [tên]` để xài"
    await interaction.response.send_message(msg)

@bot.tree.command(name='buy', description="💰 Mua đồ")
@app_commands.describe(item="Tên vật phẩm")
async def buy(interaction: discord.Interaction, item: str):
    uid = str(interaction.user.id)
    init_user(uid)
    
    items = {
        "kiếm sắt": {"price": 150, "type": "weapon", "value": "kiếm sắt"},
        "kiếm thép": {"price": 300, "type": "weapon", "value": "kiếm thép"},
        "rìu chiến": {"price": 500, "type": "weapon", "value": "rìu chiến"},
        "kiếm huyền thoại": {"price": 1000, "type": "weapon", "value": "kiếm huyền thoại"},
        "áo da": {"price": 120, "type": "armor", "value": "áo da"},
        "áo giáp sắt": {"price": 280, "type": "armor", "value": "áo giáp sắt"},
        "áo thần": {"price": 600, "type": "armor", "value": "áo thần"},
        "bình máu nhỏ": {"price": 50, "type": "consumable", "value": "bình máu nhỏ"},
        "bình máu lớn": {"price": 100, "type": "consumable", "value": "bình máu lớn"},
        "bình máu to": {"price": 200, "type": "consumable", "value": "bình máu to"},
        "bùa may mắn": {"price": 150, "type": "consumable", "value": "bùa may mắn"},
        "thẻ hồi sinh": {"price": 300, "type": "consumable", "value": "thẻ hồi sinh"}
    }
    
    item_lower = item.lower()
    if item_lower not in items:
        return await interaction.response.send_message("❌ Không có món này! Dùng `/shop` để xem.")
    
    data = items[item_lower]
    if user_data[uid]["gold"] < data["price"]:
        return await interaction.response.send_message(f"💸 Bạn cần {data['price']} xu nhưng chỉ có {user_data[uid]['gold']} xu!")
    
    user_data[uid]["gold"] -= data["price"]
    
    if data["type"] in ["weapon", "armor"]:
        old = user_data[uid]["weapon"] if data["type"] == "weapon" else user_data[uid]["armor"]
        if data["type"] == "weapon":
            user_data[uid]["weapon"] = data["value"]
        else:
            user_data[uid]["armor"] = data["value"]
        msg = f"✅ Đã mua **{data['value']}**! Thay thế `{old}` → `{data['value']}`"
    else:
        if "inventory" not in user_data[uid]:
            user_data[uid]["inventory"] = {}
        user_data[uid]["inventory"][data["value"]] = user_data[uid]["inventory"].get(data["value"], 0) + 1
        msg = f"✅ Đã mua **{data['value']}** x1! Hiện có: {user_data[uid]['inventory'][data['value']]} cái"
    
    save_db()
    await interaction.response.send_message(f"{msg}\n💰 Xu còn lại: {user_data[uid]['gold']}")

@bot.tree.command(name='use', description="💊 Sử dụng vật phẩm")
@app_commands.describe(item="Tên vật phẩm")
async def use_item(interaction: discord.Interaction, item: str):
    uid = str(interaction.user.id)
    init_user(uid)
    
    if "inventory" not in user_data[uid]:
        user_data[uid]["inventory"] = {}
    
    item_lower = item.lower()
    if user_data[uid]["inventory"].get(item_lower, 0) == 0:
        return await interaction.response.send_message(f"❌ Bạn không có **{item_lower}** nào!")
    
    user_data[uid]["inventory"][item_lower] -= 1
    if user_data[uid]["inventory"][item_lower] == 0:
        del user_data[uid]["inventory"][item_lower]
    
    if "bình máu" in item_lower:
        heal_pct = {"bình máu nhỏ": 0.3, "bình máu lớn": 0.6, "bình máu to": 1.0}
        heal = int(user_data[uid]["hp_max"] * heal_pct[item_lower])
        user_data[uid]["hp_current"] = min(user_data[uid]["hp_max"], user_data[uid]["hp_current"] + heal)
        msg = f"💚 Dùng **{item_lower}**: hồi {heal} HP! Hiện tại: {user_data[uid]['hp_current']}/{user_data[uid]['hp_max']}"
    elif item_lower == "bùa may mắn":
        if "active_buffs" not in user_data[uid]:
            user_data[uid]["active_buffs"] = []
        user_data[uid]["active_buffs"].append({"type": "dame", "remaining": 1, "name": "bùa may mắn"})
        msg = f"✨ Dùng **bùa may mắn**: +10% dame trong trận tiếp theo!"
    elif item_lower == "thẻ hồi sinh":
        user_data[uid]["death_time"] = None
        if user_data[uid]["hp_current"] == 0:
            user_data[uid]["hp_current"] = user_data[uid]["hp_max"] // 2
        msg = f"🔄 Dùng **thẻ hồi sinh**: hồi sinh với {user_data[uid]['hp_current']}/{user_data[uid]['hp_max']} HP!"
    else:
        msg = f"✅ Đã dùng **{item_lower}**!"
    
    save_db()
    await interaction.response.send_message(msg)

@bot.tree.command(name='daily', description="🎁 Nhận 50 xu mỗi ngày")
async def daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    today = datetime.now().date()
    last = user_data[uid].get("last_daily")
    
    if last and datetime.strptime(last, "%Y-%m-%d").date() == today:
        return await interaction.response.send_message("⏰ Hôm nay bạn đã nhận rồi! Quay lại mai nha!")
    
    user_data[uid]["gold"] += 50
    user_data[uid]["last_daily"] = str(today)
    save_db()
    
    await interaction.response.send_message(f"🎁 Bạn nhận **50 xu**! Hiện có: {user_data[uid]['gold']} xu")

@bot.tree.command(name='inv', description="📦 Xem túi đồ")
async def inventory(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    d = user_data[uid]
    current_map = ENEMY_TYPES.get(d.get("current_map", "beginner"), ENEMY_TYPES["beginner"])
    
    msg = f"**📦 TÚI ĐỒ CỦA {interaction.user.display_name}**\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 **Xu:** {d['gold']}\n"
    msg += f"⚔️ **Vũ khí:** {d['weapon']}\n"
    msg += f"🛡️ **Giáp:** {d['armor']}\n"
    msg += f"❤️ **HP:** {d['hp_current']}/{d['hp_max']}\n"
    msg += f"📊 **Level:** {d['level']} (exp: {d['exp']}/100)\n"
    msg += f"🗺️ **Map hiện tại:** {current_map['name']}\n"
    
    if "inventory" in d and d["inventory"]:
        msg += f"\n💊 **Vật phẩm:**\n"
        for item, count in d["inventory"].items():
            msg += f"• {item}: {count} cái\n"
    else:
        msg += f"\n💊 **Vật phẩm:** Không có\n"
    
    if "active_buffs" in d and d["active_buffs"]:
        msg += f"\n✨ **Buff:**\n"
        for buff in d["active_buffs"]:
            msg += f"• {buff['name']}\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━\n💡 Dùng `/use [tên]` để xài vật phẩm"
    await interaction.response.send_message(msg)

@bot.tree.command(name='tutorial', description="📖 Hướng dẫn chơi")
async def tutorial(interaction: discord.Interaction):
    msg = """**📖 HƯỚNG DẪN SĂN QUÁI**
━━━━━━━━━━━━━━━━━━━━━

**🎮 CÁCH CHƠI**
1. `/go_hunt @bạn` (rủ thêm 1-3 bạn)
2. Gõ `ok` trong 30s để tham gia
3. Mỗi lượt bot yêu cầu gõ **chữ cái** trong thời gian map quy định
   - ✅ Gõ đúng: đánh quái
   - ❌ Gõ sai/chậm: quái đánh bạn

**🗺️ HỆ THỐNG MAP (9 cấp độ)**
• Beginner (8s) → Very Easy (7.5s) → Easy (6s) → Quite Normal (5.5s)
• Normal (5s) → Quite Hard (4.5s) → Hard (4s) → Elite (3s) → Master (2.75s)
- Dùng `/pass` để vượt ải mở map mới
- Dùng `/change_map` để đổi map săn

**👾 SĂN BOSS**
- `/boss` -> boss mạnh hơn, respawn 3 phút
- Phần thưởng cao hơn (200-500 xu)

**🛒 SHOP & VẬT PHẨM**
- `/shop` xem đồ, `/buy [tên]` mua
- Vũ khí: tăng dame | Giáp: giảm sát thương

**🎁 HÀNG NGÀY**
- `/daily` nhận 50 xu/ngày
- `/inv` xem túi đồ

━━━━━━━━━━━━━━━━━━━━━
💡 Mỗi lần săn xong chờ 10s để quái respawn!"""
    await interaction.response.send_message(msg)

@bot.tree.command(name='backup', description="💾 Lưu dữ liệu lên GitHub Gist")
async def backup(interaction: discord.Interaction):
    if not GIST_TOKEN:
        return await interaction.response.send_message("❌ Chưa cấu hình GIST_TOKEN trong environment!")
    
    await interaction.response.defer()
    save_db()
    
    with open(DATA_FILE, "r") as f:
        data = f.read()
    
    headers = {"Authorization": f"token {GIST_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    if GIST_ID:
        url = f"https://api.github.com/gists/{GIST_ID}"
        payload = {"files": {"hunt_bot_backup.json": {"content": data}}}
        resp = requests.patch(url, headers=headers, json=payload)
    else:
        url = "https://api.github.com/gists"
        payload = {"description": "Discord Hunt Bot Backup", "public": False, "files": {"hunt_bot_backup.json": {"content": data}}}
        resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code in [200, 201]:
        if not GIST_ID:
            new_id = resp.json()["id"]
            await interaction.followup.send(f"✅ Backup thành công!\n🔑 **GIST ID:** `{new_id}`\n📌 Hãy thêm biến môi trường `GIST_ID={new_id}` để restore sau này!")
        else:
            await interaction.followup.send("✅ Backup thành công!")
    else:
        await interaction.followup.send(f"❌ Backup thất bại: {resp.text}")

@bot.tree.command(name='restore', description="🔄 Khôi phục dữ liệu từ GitHub Gist")
async def restore(interaction: discord.Interaction):
    if not GIST_TOKEN or not GIST_ID:
        return await interaction.response.send_message("❌ Chưa cấu hình GIST_TOKEN hoặc GIST_ID!")
    
    await interaction.response.defer()
    
    headers = {"Authorization": f"token {GIST_TOKEN}"}
    url = f"https://api.github.com/gists/{GIST_ID}"
    resp = requests.get(url, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        content = data["files"]["hunt_bot_backup.json"]["content"]
        
        with open(DATA_FILE, "w") as f:
            f.write(content)
        
        global user_data
        user_data = json.loads(content)
        
        await interaction.followup.send(f"✅ Restore thành công! Dữ liệu từ: {data.get('updated_at', 'unknown')}")
    else:
        await interaction.followup.send(f"❌ Restore thất bại: {resp.text}")

# ==================== RUN ====================
threading.Thread(target=run_flask, daemon=True).start()
bot.run(TOKEN)