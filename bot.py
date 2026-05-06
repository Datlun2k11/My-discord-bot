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
app = Flask(__name__)

@app.route('/')
def home():
    return "🐉 Bot săn quái turn-based đang chạy!"

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# ==================== DISCORD BOT ====================
class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)
        self.active_battles = {}  # channel_id -> battle data

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Bot {self.user} đã sẵn sàng với hệ thống săn quái turn-based!")

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
            "map": "Rừng khởi đầu",
            "hp_max": 55,
            "hp_current": 55,
            "death_time": None,
            "total_hunts": 0,
            "total_wins": 0
        }
        save_db()

def get_damage(user_id, is_monster=False):
    """Tính sát thương"""
    uid = str(user_id)
    if is_monster:
        base = 8 + (user_data[uid].get("level", 1) // 2)
        armor = user_data[uid]["armor"]
        reduce = {"áo rách": 0, "áo da": 0.25, "áo thép": 0.45}
        return int(base * (1 - reduce.get(armor, 0)))
    else:
        base = 10 + user_data[uid]["level"] * 2
        weapon = user_data[uid]["weapon"]
        bonus = {"kiếm gỉ": 0, "kiếm sắt": 0.2, "kiếm thần": 0.5}
        return int(base * (1 + bonus.get(weapon, 0)))

def get_next_letter():
    return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

def format_reward_for_players(gold, player_count):
    """Ép gold chia hết cho số người chơi"""
    if player_count == 0:
        return 0
    gold = random.randint(50, 150)
    remainder = gold % player_count
    return gold - remainder

# ==================== TURN-BASED BATTLE ====================
async def start_battle(interaction, players):
    """Bắt đầu battle turn-based"""
    channel_id = interaction.channel_id
    total_hp_players = sum(p["hp"] for p in players)
    monster_hp = int(total_hp_players * 0.7)
    if monster_hp < 20:
        monster_hp = 20
    
    battle_data = {
        "players": players,
        "monster_hp": monster_hp,
        "current_turn": 0,
        "game_over": False,
        "reward": 0,
        "start_time": datetime.now(),
        "message": None
    }
    bot.active_battles[channel_id] = battle_data
    
    embed = discord.Embed(title="⚔️ TRẬN CHIẾN BẮT ĐẦU ⚔️", color=discord.Color.blue())
    embed.add_field(name="🐉 Quái vật", value=f"HP: {monster_hp}", inline=True)
    player_list = "\n".join([f"👤 {p['user'].mention} | HP: {p['hp']}/{p['hp_max']}" for p in players])
    embed.add_field(name="🗡️ Đội hình", value=player_list, inline=False)
    embed.set_footer(text="Mỗi lượt bạn có 5s để gõ đúng chữ cái được yêu cầu!")
    
    msg = await interaction.followup.send(embed=embed)
    battle_data["message"] = msg
    await process_turn(channel_id)

async def process_turn(channel_id):
    battle = bot.active_battles.get(channel_id)
    if not battle or battle["game_over"]:
        return
    
    alive_players = [p for p in battle["players"] if p["hp"] > 0]
    if not alive_players or battle["monster_hp"] <= 0:
        await end_battle(channel_id, win=(battle["monster_hp"] <= 0))
        return
    
    current = battle["current_turn"] % len(alive_players)
    player = alive_players[current]
    battle["current_turn"] += 1
    
    letter = get_next_letter()
    channel = bot.get_channel(channel_id)
    
    # Tin nhắn thường, không embed
    await channel.send(f"🔤 **Đến lượt {player['user'].mention}:** hãy nói chữ **{letter}** trong 3 giây!\n🐉 HP Quái: {battle['monster_hp']} | 💚 HP bạn: {player['hp']}/{player['hp_max']}")
    
    def check(m):
        return m.author.id == player["user"].id and m.content.strip().upper() == letter and m.channel.id == channel_id
    
    try:
        await bot.wait_for('message', timeout=5.0, check=check)
        dmg = get_damage(player["user"].id)
        battle["monster_hp"] = max(0, battle["monster_hp"] - dmg)
        await channel.send(f"✅ {player['user'].mention} đánh trúng! **Gây {dmg} sát thương.** Quái còn {battle['monster_hp']} HP.")
    except asyncio.TimeoutError:
        dmg = get_damage(player["user"].id, is_monster=True)
        player["hp"] = max(0, player["hp"] - dmg)
        await channel.send(f"❌ {player['user'].mention} **không kịp!** Quái đánh {dmg} sát thương. Bạn còn {player['hp']} HP.")
        
        if player["hp"] == 0:
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
    alive = [p for p in battle["players"] if p["hp"] > 0]
    
    if win and alive:
        reward_total = random.randint(60, 180)
        # Làm tròn chia hết
        reward_total = reward_total - (reward_total % len(alive))
        reward_each = reward_total // len(alive)
        
        msg = f"🏆 **CHIẾN THẮNG!** 🏆\nCả đội nhận **{reward_total} xu** (mỗi người {reward_each} xu).\n"
        
        for p in alive:
            uid = str(p["user"].id)
            user_data[uid]["gold"] += reward_each
            user_data[uid]["total_wins"] += 1
            user_data[uid]["exp"] += 20
            user_data[uid]["total_hunts"] += 1
            
            exp_needed = 100 * user_data[uid]["level"]
            old_level = user_data[uid]["level"]
            while user_data[uid]["exp"] >= exp_needed:
                user_data[uid]["level"] += 1
                user_data[uid]["exp"] -= exp_needed
                user_data[uid]["hp_max"] = 50 + user_data[uid]["level"] * 5
                exp_needed = 100 * user_data[uid]["level"]
            
            if user_data[uid]["hp_current"] > user_data[uid]["hp_max"]:
                user_data[uid]["hp_current"] = user_data[uid]["hp_max"]
            
            if user_data[uid]["level"] > old_level:
                msg += f"✨ {p['user'].mention}: +{reward_each} xu, +20 exp **→ Lên level {user_data[uid]['level']}!** 💪\n"
            else:
                msg += f"✅ {p['user'].mention}: +{reward_each} xu, +20 exp ({user_data[uid]['exp']}/100)\n"
        
        save_db()
        await channel.send(msg)
    else:
        await channel.send(f"💀 **THẤT BẠI!** 💀\nCả đội đã chết. Hãy dùng `/daily` kiếm xu mua bình máu và thử lại.")

# ==================== SLASH COMMANDS ====================
@bot.tree.command(name='go_hunt', description="🐉 Săn quái theo lượt, có thể rủ thêm bạn (tối đa 4 người)")
@app_commands.describe(nguoi1="Tag người chơi thứ 2", nguoi2="Tag người chơi thứ 3", nguoi3="Tag người chơi thứ 4")
async def go_hunt(interaction: discord.Interaction, nguoi1: discord.User = None, nguoi2: discord.User = None, nguoi3: discord.User = None):
    await interaction.response.defer()
    
    # Kiểm tra battle đang diễn ra
    if interaction.channel_id in bot.active_battles:
        return await interaction.followup.send("⚠️ Đã có trận chiến trong kênh này! Kết thúc rồi hãy săn tiếp.", ephemeral=True)
    
    # Tập hợp người chơi (chính chủ + tag)
    players = [interaction.user]
    if nguoi1:
        players.append(nguoi1)
    if nguoi2:
        players.append(nguoi2)
    if nguoi3:
        players.append(nguoi3)
    
    # Loại bỏ trùng
    players = list(dict.fromkeys(players))
    
    # Kiểm tra cooldown & death
    invalid = []
    for p in players:
        uid = str(p.id)
        init_user(uid)
        
        # Cooldown 10s
        cd_key = f"{uid}_hunt"
        if cd_key in cooldowns and datetime.now() < cooldowns[cd_key]:
            invalid.append(f"{p.mention} (còn {(cooldowns[cd_key]-datetime.now()).seconds}s)")
        
        # Death cooldown
        death_time = user_data[uid].get("death_time")
        if death_time:
            dt = datetime.fromisoformat(death_time)
            if datetime.now() - dt < timedelta(seconds=20):
                invalid.append(f"{p.mention} (đang chết, còn {20 - (datetime.now()-dt).seconds}s)")
    
    if invalid:
        return await interaction.followup.send(f"❌ Không thể tham gia:\n" + "\n".join(invalid), ephemeral=True)
    
    # Gửi lời mời
    mention_str = " ".join([p.mention for p in players])
    msg = await interaction.followup.send(f"🔥 {mention_str} có muốn tham gia trận chiến không? Gõ **ok** trong 30s!")
    
    confirmed = set()
    confirmed.add(interaction.user.id)  # chủ phòng tự động ok
    
    def check_join(m):
        return m.author.id in [p.id for p in players] and m.content.strip().lower() == "ok" and m.channel.id == interaction.channel_id
    
    try:
        start_time = datetime.now()
        while len(confirmed) < len(players) and (datetime.now() - start_time).seconds < 30:
            done, _ = await asyncio.wait_for(asyncio.gather(asyncio.create_task(bot.wait_for('message', timeout=30-len(confirmed)*3, check=check_join))), timeout=30)
            if done:
                confirmed.add(done[0].author.id)
        final_players = [p for p in players if p.id in confirmed]
    except:
        final_players = [p for p in players if p.id in confirmed]
    
    if len(final_players) == 0:
        return await interaction.followup.send("❌ Không ai tham gia, hủy săn...")
    
    # Chuẩn bị data battle
    battle_players = []
    for p in final_players:
        uid = str(p.id)
        battle_players.append({
            "user": p,
            "hp": user_data[uid]["hp_max"],
            "hp_max": user_data[uid]["hp_max"],
            "uid": uid
        })
        # Set cooldown
        cooldowns[f"{uid}_hunt"] = datetime.now() + timedelta(seconds=10)
    
    await start_battle(interaction, battle_players)

@bot.tree.command(name='tutorial', description="📖 Hướng dẫn chơi game săn quái turn-based")
async def tutorial(interaction: discord.Interaction):
    desc = """**🎮 HƯỚNG DẪN CHƠI**
    
    **1. Bắt đầu**: `/go_hunt [tên_tag]` rủ thêm bạn (tối đa 4 người)
    **2. Tham gia**: Gõ `ok` trong 30s khi được tag
    **3. Cách chơi**: Mỗi lượt bot yêu cầu gõ đúng **chữ cái** (A-Z) trong **3 giây**
       - ✅ Gõ đúng: gây sát thương lên quái
       - ❌ Gõ sai/chậm: quái đánh trúng bạn
    **4. HP quái** luôn thấp hơn tổng HP cả đội
    **5. Chia thưởng**: Xu được chia đều cho người còn sống
    **6. Chết**: hồi sau 20 giây
    **7. Level**: lên level tăng HP tối đa và sát thương
    
    **🛒 Shop**: `/shop` mua vũ khí, giáp, bình máu (thêm sau)
    **📊 Stats**: `/inv` xem trang bị, `/level` xem cấp độ
    """
    await interaction.response.send_message(embed=discord.Embed(title="📘 HƯỚNG DẪN", description=desc, color=discord.Color.green()))

@bot.tree.command(name='shop', description="🛒 Xem cửa hàng vật phẩm")
async def shop(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    
    shop_text = """**🛒 CỬA HÀNG SĂN QUÁI 🛒**
━━━━━━━━━━━━━━━━━━━━━

**⚔️ VŨ KHÍ** (tăng sát thương)
• `kiếm sắt` - 150 xu (+25% dame)
• `kiếm thép` - 300 xu (+50% dame)
• `rìu chiến` - 500 xu (+80% dame)
• `kiếm huyền thoại` - 1000 xu (+120% dame)

**🛡️ GIÁP** (giảm sát thương nhận)
• `áo da` - 120 xu (giảm 25%)
• `áo giáp sắt` - 280 xu (giảm 45%)
• `áo thần` - 600 xu (giảm 65%)

**💊 VẬT PHẨM** (/use [tên])
• `bình máu nhỏ` - 50 xu (hồi 30% HP)
• `bình máu lớn` - 100 xu (hồi 60% HP)
• `bình máu to` - 200 xu (hồi 100% HP)
• `bùa may mắn` - 150 xu (+10% dame 1 trận)
• `thẻ hồi sinh` - 300 xu (revive 1 lần)
• `bùa nhân đôi` - 500 xu (x2 xu thưởng)

━━━━━━━━━━━━━━━━━━━━━
💡 **Cách dùng:** `/buy [tên vật phẩm]`
💰 **Xu của bạn:** `{user_data[uid]['gold']}`
    """
    
    await interaction.response.send_message(shop_text)

@bot.tree.command(name='buy', description="💰 Mua vật phẩm từ shop")
@app_commands.describe(item="Tên vật phẩm muốn mua")
async def buy(interaction: discord.Interaction, item: str):
    uid = str(interaction.user.id)
    init_user(uid)
    
    # Danh sách vật phẩm
    items = {
        # Vũ khí
        "kiếm sắt": {"price": 150, "type": "weapon", "value": "kiếm sắt", "stat": 25},
        "kiếm thép": {"price": 300, "type": "weapon", "value": "kiếm thép", "stat": 50},
        "rìu chiến": {"price": 500, "type": "weapon", "value": "rìu chiến", "stat": 80},
        "kiếm huyền thoại": {"price": 1000, "type": "weapon", "value": "kiếm huyền thoại", "stat": 120},
        # Giáp
        "áo da": {"price": 120, "type": "armor", "value": "áo da", "stat": 25},
        "áo giáp sắt": {"price": 280, "type": "armor", "value": "áo giáp sắt", "stat": 45},
        "áo thần": {"price": 600, "type": "armor", "value": "áo thần", "stat": 65},
        # Vật phẩm (lưu vào inventory riêng)
        "bình máu nhỏ": {"price": 50, "type": "consumable", "value": "bình máu nhỏ", "effect": "heal_30"},
        "bình máu lớn": {"price": 100, "type": "consumable", "value": "bình máu lớn", "effect": "heal_60"},
        "bình máu to": {"price": 200, "type": "consumable", "value": "bình máu to", "effect": "heal_100"},
        "bùa may mắn": {"price": 150, "type": "consumable", "value": "bùa may mắn", "effect": "dame_buff"},
        "thẻ hồi sinh": {"price": 300, "type": "consumable", "value": "thẻ hồi sinh", "effect": "revive"},
        "bùa nhân đôi": {"price": 500, "type": "consumable", "value": "bùa nhân đôi", "effect": "double_reward"}
    }
    
    item_lower = item.lower()
    if item_lower not in items:
        return await interaction.response.send_message("❌ Không có vật phẩm này! Dùng `/shop` để xem danh sách.")
    
    item_data = items[item_lower]
    
    if user_data[uid]["gold"] < item_data["price"]:
        return await interaction.response.send_message(f"💸 Bạn nghèo quá! Cần {item_data['price']} xu nhưng bạn chỉ có {user_data[uid]['gold']} xu.")
    
    # Trừ tiền
    user_data[uid]["gold"] -= item_data["price"]
    
    # Xử lý theo loại
    if item_data["type"] == "weapon":
        old = user_data[uid]["weapon"]
        user_data[uid]["weapon"] = item_data["value"]
        msg = f"⚔️ Đã mua **{item_data['value']}** (+{item_data['stat']}% dame)\nThay thế `{old}` → `{item_data['value']}`"
    
    elif item_data["type"] == "armor":
        old = user_data[uid]["armor"]
        user_data[uid]["armor"] = item_data["value"]
        msg = f"🛡️ Đã mua **{item_data['value']}** (giảm {item_data['stat']}% sát thương)\nThay thế `{old}` → `{item_data['value']}`"
    
    else:  # consumable
        if "inventory" not in user_data[uid]:
            user_data[uid]["inventory"] = {}
        
        inv = user_data[uid]["inventory"]
        inv[item_data["value"]] = inv.get(item_data["value"], 0) + 1
        msg = f"💊 Đã mua **{item_data['value']}** x1\n📦 Hiện có: {inv.get(item_data['value'], 0)} cái"
    
    save_db()
    
    await interaction.response.send_message(f"✅ {msg}\n💰 Xu còn lại: {user_data[uid]['gold']}")

@bot.tree.command(name='use', description="💊 Sử dụng vật phẩm tiêu hao")
@app_commands.describe(item="Tên vật phẩm muốn dùng")
async def use_item(interaction: discord.Interaction, item: str):
    uid = str(interaction.user.id)
    init_user(uid)
    
    if "inventory" not in user_data[uid]:
        user_data[uid]["inventory"] = {}
    
    inv = user_data[uid]["inventory"]
    item_lower = item.lower()
    
    # Danh sách vật phẩm dùng được
    consumables = {
        "bình máu nhỏ": {"heal": 0.3, "name": "bình máu nhỏ"},
        "bình máu lớn": {"heal": 0.6, "name": "bình máu lớn"},
        "bình máu to": {"heal": 1.0, "name": "bình máu to"},
        "bùa may mắn": {"buff": "dame", "duration": 1, "name": "bùa may mắn"},
        "thẻ hồi sinh": {"revive": True, "name": "thẻ hồi sinh"},
        "bùa nhân đôi": {"buff": "reward", "duration": 1, "name": "bùa nhân đôi"}
    }
    
    if item_lower not in consumables:
        return await interaction.response.send_message("❌ Không thể dùng vật phẩm này! Xem `/shop` để biết vật phẩm khả dụng.")
    
    if inv.get(item_lower, 0) == 0:
        return await interaction.response.send_message(f"❌ Bạn không có **{item_lower}** nào cả! Vào `/shop` mua đi.")
    
    # Trừ 1 item
    inv[item_lower] -= 1
    if inv[item_lower] == 0:
        del inv[item_lower]
    
    item_data = consumables[item_lower]
    
    # Xử lý hiệu ứng
    if "heal" in item_data:
        hp_max = user_data[uid]["hp_max"]
        hp_current = user_data[uid]["hp_current"]
        heal_amount = int(hp_max * item_data["heal"])
        new_hp = min(hp_max, hp_current + heal_amount)
        user_data[uid]["hp_current"] = new_hp
        msg = f"💚 Dùng **{item_data['name']}**: hồi {heal_amount} HP!\n❤️ HP hiện tại: {new_hp}/{hp_max}"
    
    elif "buff" in item_data:
        if "active_buffs" not in user_data[uid]:
            user_data[uid]["active_buffs"] = []
        user_data[uid]["active_buffs"].append({
            "type": item_data["buff"],
            "remaining": item_data["duration"],
            "name": item_data["name"]
        })
        msg = f"✨ Dùng **{item_data['name']}**: +10% dame trong {item_data['duration']} trận!"
    
    elif "revive" in item_data:
        user_data[uid]["death_time"] = None
        if user_data[uid]["hp_current"] == 0:
            user_data[uid]["hp_current"] = user_data[uid]["hp_max"] // 2
        msg = f"🔄 Dùng **{item_data['name']}**: hồi sinh với {user_data[uid]['hp_current']}/{user_data[uid]['hp_max']} HP!"
    
    save_db()
    await interaction.response.send_message(msg)

@bot.tree.command(name='inv', description="📦 Xem túi đồ và vật phẩm")
async def inventory(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    d = user_data[uid]
    
    # Trang bị hiện tại
    msg = f"**📦 TÚI ĐỒ CỦA {interaction.user.display_name}**\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"**💰 Xu:** {d['gold']}\n"
    msg += f"**⚔️ Vũ khí:** {d['weapon']}\n"
    msg += f"**🛡️ Giáp:** {d['armor']}\n"
    msg += f"**❤️ HP:** {d['hp_current']}/{d['hp_max']}\n"
    msg += f"**📊 Level:** {d['level']} (exp: {d['exp']}/100)\n"
    
    # Vật phẩm trong inventory
    if "inventory" in d and d["inventory"]:
        msg += f"\n**💊 Vật phẩm mang theo:**\n"
        for item, count in d["inventory"].items():
            msg += f"• {item}: {count} cái\n"
    else:
        msg += f"\n💊 **Vật phẩm:** Không có\n"
    
    # Buff đang active
    if "active_buffs" in d and d["active_buffs"]:
        msg += f"\n✨ **Buff đang có:**\n"
        for buff in d["active_buffs"]:
            msg += f"• {buff['name']} (còn {buff['remaining']} trận)\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━\n💡 Dùng `/use [tên]` để xài vật phẩm!"
    
    await interaction.response.send_message(msg)

@bot.tree.command(name='level', description="📊 Xem thông tin cấp độ")
async def level(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    init_user(uid)
    d = user_data[uid]
    embed = discord.Embed(title=f"📈 CẤP ĐỘ {interaction.user.display_name}", color=discord.Color.purple())
    embed.add_field(name="🎯 Level", value=d["level"], inline=True)
    embed.add_field(name="✨ Exp", value=f"{d['exp']}/100", inline=True)
    embed.add_field(name="❤️ HP", value=f"{d['hp_max']}", inline=True)
    embed.add_field(name="🗺️ Map hiện tại", value=d.get("map", "Rừng khởi đầu"), inline=True)
    await interaction.response.send_message(embed=embed)

# Chạy flask & bot
threading.Thread(target=run_flask, daemon=True).start()
bot.run(TOKEN)
