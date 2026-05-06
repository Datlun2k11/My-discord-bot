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
            base = random.randint(20, 40)
        else:
            base = random.randint(8, 18)
        reduce = get_armor_reduce(user_data[uid]["armor"])
        return int(base * (1 - reduce))
    else:
        base = random.randint(10, 25) + user_data[uid]["level"] * 2
        bonus = get_weapon_bonus(user_data[uid]["weapon"])
        # Buff từ vật phẩm
        if "active_buffs" in user_data[uid]:
            for buff in user_data[uid]["active_buffs"]:
                if buff["type"] == "dame":
                    bonus += 10
        return int(base * (1 + bonus / 100))

def get_next_letter():
    return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

def get_next_boss_symbol():
    symbols = ["A", "B", "C", "1", "2", "3", "@", "#", "$", "%", "&", "?"]
    return random.choice(symbols)

def format_reward(gold, player_count):
    if player_count == 0:
        return 0
    remainder = gold % player_count
    return gold - remainder

# ==================== AI FUNNY COMMENT ====================
async def get_funny_comment(win, monster_type="normal"):
    if not GROQ_KEY:
        return random.choice(["Quái thấy m đẹp trai quá nên tự xỉu!", "Thắng rồi, đi ăn mừng đi bro!"])
    
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    prompt = f"Hãy viết 1 câu cực kỳ hài hước, lầy lội, style GenZ khi người chơi {'THẮNG' if win else 'THUA'} một trận đấu với {'BOSS MẠNH' if monster_type == 'boss' else 'QUÁI THƯỜNG'} trong game Discord. Chỉ 1 câu ngắn gọn, tối đa 20 từ."
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
    
    # Tính HP
    total_hp_players = sum(p["hp_max"] for p in players)
    if is_boss:
        monster_hp = int(total_hp_players * 1.2)  # Boss có HP cao hơn
    else:
        monster_hp = int(total_hp_players * 0.7)
    
    battle_data = {
        "players": players,
        "monster_hp": monster_hp,
        "monster_hp_max": monster_hp,
        "current_turn": 0,
        "game_over": False,
        "is_boss": is_boss,
        "start_time": datetime.now(),
        "channel_id": channel_id
    }
    bot.active_battles[channel_id] = battle_data
    
    channel = bot.get_channel(channel_id)
    monster_type = "🔥 BOSS 🔥" if is_boss else "🐉 QUÁI DỮ 🐉"
    await channel.send(f"⚔️ **TRẬN CHIẾN BẮT ĐẦU!** ⚔️\n{monster_type} có **{monster_hp} HP**!")
    
    await process_turn(channel_id)

async def process_turn(channel_id):
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
    
    # Random ký tự hoặc số (boss khó hơn)
    if battle["is_boss"]:
        symbol = get_next_boss_symbol()
        prompt = f"🔤 **Đến lượt {player['user'].mention}** – hãy nói chữ hoặc số: **{symbol}** trong 5 giây!"
    else:
        letter = get_next_letter()
        symbol = letter
        prompt = f"🔤 **Đến lượt {player['user'].mention}** – hãy nói chữ: **{letter}** trong 5 giây!"
    
    await channel.send(f"{prompt}\n🐉 HP quái: {battle['monster_hp']}/{battle['monster_hp_max']} | 💚 HP bạn: {player['hp_current']}/{player['hp_max']}")
    
    def check(m):
        return m.author.id == player["user"].id and m.content.strip().upper() == symbol and m.channel.id == channel_id
    
    try:
        await bot.wait_for('message', timeout=5.0, check=check)
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
    await process_turn(channel_id)

async def end_battle(channel_id, win):
    battle = bot.active_battles.pop(channel_id, None)
    if not battle:
        return
    
    channel = bot.get_channel(channel_id)
    alive_players = [p for p in battle["players"] if p["hp_current"] > 0]
    
    # AI phán xét
    funny = await get_funny_comment(win, monster_type="boss" if battle["is_boss"] else "normal")
    
    if win and alive_players:
        if battle["is_boss"]:
            reward_total = random.randint(200, 500)
            reward_total = format_reward(reward_total, len(alive_players))
            reward_each = reward_total // len(alive_players)
            bonus_item = random.choice(["bình máu lớn", "bùa may mắn", "kiếm thép", None])
        else:
            reward_total = random.randint(60, 180)
            reward_total = format_reward(reward_total, len(alive_players))
            reward_each = reward_total // len(alive_players)
            bonus_item = None
        
        msg = f"{funny}\n━━━━━━━━━━━━━━━━━━━━━\n🏆 **CHIẾN THẮNG!** 🏆\n"
        msg += f"🎁 **Phần thưởng:** {reward_total} xu (mỗi người {reward_each} xu)\n"
        
        for p in alive_players:
            uid = str(p["user"].id)
            user_data[uid]["gold"] += reward_each
            user_data[uid]["total_wins"] += 1
            user_data[uid]["exp"] += 30 if battle["is_boss"] else 20
            user_data[uid]["total_hunts"] += 1
            
            # Level up
            exp_needed = 100 * user_data[uid]["level"]
            old_level = user_data[uid]["level"]
            while user_data[uid]["exp"] >= exp_needed:
                user_data[uid]["level"] += 1
                user_data[uid]["exp"] -= exp_needed
                user_data[uid]["hp_max"] = 50 + user_data[uid]["level"] * 5
                user_data[uid]["hp_current"] = user_data[uid]["hp_max"]
                exp_needed = 100 * user_data[uid]["level"]
            
            if user_data[uid]["level"] > old_level:
                msg += f"✨ {p['user'].mention}: **Lên level {user_data[uid]['level']}!** 💪\n"
            else:
                msg += f"✅ {p['user'].mention}: +{reward_each} xu, +{30 if battle['is_boss'] else 20} exp\n"
            
            # Tặng item nếu trúng
            if bonus_item and random.random() < 0.3:
                if "inventory" not in user_data[uid]:
                    user_data[uid]["inventory"] = {}
                user_data[uid]["inventory"][bonus_item] = user_data[uid]["inventory"].get(bonus_item, 0) + 1
                msg += f"🎁 {p['user'].mention} nhận thêm **{bonus_item}**!\n"
        
        save_db()
        await channel.send(msg)
        
    else:
        msg = f"{funny}\n━━━━━━━━━━━━━━━━━━━━━\n💀 **THẤT BẠI!** 💀\nCả đội đã chết. Hãy dùng `/daily` kiếm xu mua đồ và thử lại."
        await channel.send(msg)

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
    
    # Check boss cooldown (2 phút)
    if interaction.channel_id in boss_cooldowns:
        remaining = int((boss_cooldowns[interaction.channel_id] - datetime.now()).seconds)
        if remaining > 0:
            return await interaction.followup.send(f"👾 BOSS đang hồi sinh! Còn {remaining} giây nữa mới xuất hiện lại.")
    
    # Check cooldown & death
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
    
    # Set cooldown (boss 2 phút, cá nhân 60s)
    boss_cooldowns[interaction.channel_id] = datetime.now() + timedelta(seconds=120)
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

# ==================== SHOP & ITEMS ====================
@bot.tree.command(name='shop', description="🛒 Xem cửa hàng")
async def shop(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    msg = f"**🛒 CỬA HÀNG SĂN QUÁI**\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 **Xu của bạn:** {user_data[uid]['gold']}\n\n"
    msg += f"**⚔️ VŨ KHÍ**\n• `kiếm sắt` - 150 xu (+25% dame)\n• `kiếm thép` - 300 xu (+50% dame)\n• `rìu chiến` - 500 xu (+80% dame)\n• `kiếm huyền thoại` - 1000 xu (+120% dame)\n\n"
    msg += f"**🛡️ GIÁP**\n• `áo da` - 120 xu (-25% dame nhận)\n• `áo giáp sắt` - 280 xu (-45% dame)\n• `áo thần` - 600 xu (-65% dame)\n\n"
    msg += f"**💊 VẬT PHẨM**\n• `bình máu nhỏ` - 50 xu (hồi 30% HP)\n• `bình máu lớn` - 100 xu (hồi 60% HP)\n• `bình máu to` - 200 xu (hồi 100% HP)\n• `bùa may mắn` - 150 xu (+10% dame 1 trận)\n• `thẻ hồi sinh` - 300 xu (revive 1 lần)\n• `bùa nhân đôi` - 500 xu (x2 xu thưởng)\n\n"
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
        "thẻ hồi sinh": {"price": 300, "type": "consumable", "value": "thẻ hồi sinh"},
        "bùa nhân đôi": {"price": 500, "type": "consumable", "value": "bùa nhân đôi"}
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
    elif item_lower == "bùa nhân đôi":
        if "active_buffs" not in user_data[uid]:
            user_data[uid]["active_buffs"] = []
        user_data[uid]["active_buffs"].append({"type": "double_reward", "remaining": 1, "name": "bùa nhân đôi"})
        msg = f"✨ Dùng **bùa nhân đôi**: x2 xu thưởng sau trận!"
    else:
        msg = f"✅ Đã dùng **{item_lower}**!"
    
    save_db()
    await interaction.response.send_message(msg)

# ==================== OTHER COMMANDS ====================
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
    
    msg = f"**📦 TÚI ĐỒ CỦA {interaction.user.display_name}**\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 **Xu:** {d['gold']}\n"
    msg += f"⚔️ **Vũ khí:** {d['weapon']}\n"
    msg += f"🛡️ **Giáp:** {d['armor']}\n"
    msg += f"❤️ **HP:** {d['hp_current']}/{d['hp_max']}\n"
    msg += f"📊 **Level:** {d['level']} (exp: {d['exp']}/100)\n"
    
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
3. Mỗi lượt bot yêu cầu gõ **chữ cái** (A-Z) trong 5s
   - ✅ Gõ đúng: đánh quái
   - ❌ Gõ sai/chậm: quái đánh bạn
4. HP quái = 70% tổng HP cả đội
5. Thắng -> chia đều xu + exp

**👾 SĂN BOSS**
- `/boss` -> boss mạnh hơn (HP cao hơn, đánh đau hơn)
- Yêu cầu cả chữ + số + ký tự (@#$%)
- Phần thưởng cao hơn (200-500 xu + item)
- BOSS respawn sau 2-5 phút

**🛒 SHOP & VẬT PHẨM**
- `/shop` xem đồ, `/buy [tên]` mua
- Vũ khí: tăng dame | Giáp: giảm sát thương nhận
- Bình máu: hồi HP | Bùa: buff tạm thời

**🎁 HÀNG NGÀY**
- `/daily` nhận 50 xu/ngày
- `/inv` xem túi đồ

━━━━━━━━━━━━━━━━━━━━━
💡 Mỗi lần săn xong chờ 10s để quái respawn!"""
    await interaction.response.send_message(msg)

# ==================== BACKUP SYSTEM ====================
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