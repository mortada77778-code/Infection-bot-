import discord
from discord.ext import commands, tasks
import random
import os
import json
import asyncio
from datetime import datetime

# استيراد أدوات الويب (FastAPI) للداشبورد
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
import threading

# =========================================================
# إعدادات البوت والداشبورد المشتركة
# =========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

AUTHOR_SIGNATURE = "✦ صُنع بعناية بواسطة سيدريك 🪄"

LEADERBOARD_FILE = "duel_leaderboard.json"
STUDENTS_FILE = "hogwarts_students.json"
EVENTS_FILE = "magic_events.json"

RAID_CHANNEL_ID = 1540623521774960682

MAX_HP = 200
MAX_MP = 40
DAMAGE_PER_HIT = 10

current_hp = MAX_HP
raid_active = False

player_scores = {}
hospital_patients = set()
active_duels = {}

# إعدادات الـ FastAPI الداشبورد
app = FastAPI(title="Hogwarts Magical Dashboard")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("DASHBOARD_SECRET", "change-this-secret-in-railway"),
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=True
)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://Infection-bot-production.up.railway.app/auth/callback"
)
API_ENDPOINT = "https://discord.com/api/v10"


# =========================================================
# أدوات قاعدة البيانات
# =========================================================

def load_json_file(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except OSError as e:
        print(f"خطأ أثناء حفظ {filename}: {e}")


def assign_student_house(user_id, username, house_name):
    db = load_json_file(STUDENTS_FILE)
    db[str(user_id)] = {"name": username, "house": house_name}
    save_json_file(STUDENTS_FILE, db)


# =========================================================
# تصميم البوت
# =========================================================

COLORS = {
    "magic": 0x2B1338,
    "gold": 0xD4AF37,
    "danger": 0x6E0B14,
    "success": 0x1E5631,
    "blue": 0x162A4A,
    "dark": 0x15121C,
    "silver": 0x777777
}

def make_embed(title, description="", color=None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or COLORS["magic"],
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=AUTHOR_SIGNATURE)
    return embed

def get_health_bar(hp, max_hp=200, length=12):
    hp = max(0, min(max_hp, hp))
    filled = round((hp / max_hp) * length)
    return "🟥" * filled + "⬛" * (length - filled)

def get_mana_bar(mp, max_mp=40, length=10):
    mp = max(0, min(max_mp, mp))
    filled = round((mp / max_mp) * length)
    return "🔵" * filled + "⬛" * (length - filled)

def player_status(name, data):
    shield = data.get("shield", 0)
    shield_text = f"🛡️ {shield}" if shield > 0 else "🛡️ —"
    return (
        f"**{name}**\n"
        f"❤️ `{data['hp']}/{MAX_HP}`\n"
        f"{get_health_bar(data['hp'], MAX_HP)}\n"
        f"🔮 `{data['mp']}/{MAX_MP}`\n"
        f"{get_mana_bar(data['mp'], MAX_MP)}\n"
        f"{shield_text}"
    )


# =========================================================
# البيوت
# =========================================================

HOUSES = {
    "جريفندور": {"name": "جريفندور (Gryffindor)", "emoji": "🦁", "color": 0x740909, "desc": "الجرأة والشجاعة والفروسية من أبرز سمات هذا البيت العريق."},
    "سليذيرين": {"name": "سليذيرين (Slytherin)", "emoji": "🐍", "color": 0x1A472A, "desc": "الطموح والدهاء والقدرة على القيادة تميز أبناء سليذيرين."},
    "رافينكلو": {"name": "رافينكلو (Ravenclaw)", "emoji": "🦅", "color": 0x0E1A40, "desc": "الحكمة والذكاء والإبداع هي الركائز الأساسية لهذا البيت."},
    "هافلباف": {"name": "هافلباف (Hufflepuff)", "emoji": "🦡", "color": 0xECB939, "desc": "الإخلاص والعدالة والعمل الجاد والصبر هي قيم هافلباف."}
}

async def display_house_students(ctx, house_key):
    db = load_json_file(STUDENTS_FILE)
    info = HOUSES[house_key]
    members = [f"• <@{uid}> — **{data.get('name', 'ساحر مجهول')}**" for uid, data in db.items() if data.get("house") == house_key]
    
    description = f"╔════════════════════╗\n   {info['emoji']} **سجل أبناء البيت**\n╚════════════════════╝\n\n" + "\n".join(members) if members else f"{info['emoji']} لا يوجد أي ساحر مسجل في **{info['name']}** حتى الآن."
    
    embed = make_embed(f"🏰 سجل بيت {info['name']}", description, info["color"])
    embed.add_field(name="📜 صفات البيت", value=info["desc"], inline=False)
    await ctx.send(embed=embed)


# =========================================================
# نظام الغارات والمستشفى والصدارة
# =========================================================

HARRY_POTTER_SPELLS = {
    "Expelliarmus (تعويذة نزع السلاح)": 30,
    "Stupefy (تعويذة التخدير والذهول)": 35,
    "Expecto Patronum (تجسيد الباترونوس)": 45,
    "Reducto (تفجير العوائق)": 50,
    "Petrificus Totalus (شلل الجسد التام)": 40,
    "Confundo (تعويذة الارتباك والتشويش)": 55,
    "Incendio (إطلاق النيران الملتهبة)": 45,
    "Glisseo (انزلاق الأرضية المفاجئ)": 35,
    "Locomotor Wibbly (ارتجاف الأرجل)": 50,
    "Tarantallegra (رقصة الأرجل)": 60,
    "Impedimenta (إبطاء الحركة)": 40,
    "Arania Exumai (طرد العناكب والوحوش)": 35,
    "Levicorpus (رفع الخصم)": 50,
    "Rictusempra (تعويذة الدغدغة)": 45,
    "Furunculus (تعويذة البثور)": 55
}

class VillageDefenseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AttackButton())

class AttackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚔️ شارك في الدفاع", style=discord.ButtonStyle.danger, custom_id="village_defense_btn")

    async def callback(self, interaction: discord.Interaction):
        global current_hp, raid_active
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        user_name = interaction.user.display_name

        if user_id in hospital_patients:
            await interaction.followup.send("🏥 أنت في المستشفى الحربي حالياً.", ephemeral=True)
            return
        if not raid_active:
            await interaction.followup.send("🕯️ القرية آمنة ولا توجد غارة نشطة.", ephemeral=True)
            return

        spell_name, fail_chance = random.choice(list(HARRY_POTTER_SPELLS.items()))
        if random.randint(1, 100) <= fail_chance:
            await interaction.followup.send("❌ فشلت تعويذتك هذه المرة.", ephemeral=True)
            return

        if user_id not in player_scores:
            player_scores[user_id] = {"name": user_name, "hits": 0}
        player_scores[user_id]["hits"] += 1
        current_hp = max(0, current_hp - DAMAGE_PER_HIT)

        if current_hp > 0:
            await interaction.followup.send(f"⚔️ أصبت زعيم الغارة! الضرر: `{DAMAGE_PER_HIT}`", ephemeral=True)
            return

        raid_active = False
        if player_scores:
            victim_id = random.choice(list(player_scores.keys()))
            hospital_patients.add(victim_id)

        await interaction.message.edit(embed=make_embed("🏆 انتهت الغارة — انتصر الأبطال", "تم سحق زعيم الغارة بنجاح!", COLORS["gold"]), view=None)

async def send_raid(channel):
    global current_hp, raid_active, player_scores
    if raid_active: return False
    current_hp = MAX_HP
    raid_active = True
    player_scores.clear()
    embed = make_embed("🚨 إنذار سحري — غارة على القرية", f"ظهرت قوى مظلمة عند الحدود!\n\n🖤 صحة الزعيم: `{current_hp}/{MAX_HP}`", COLORS["danger"])
    await channel.send(embed=embed, view=VillageDefenseView())
    return True

@bot.command(name="هجوم")
async def start_raid_command(ctx):
    if raid_active:
        await ctx.send("⚠️ هناك غارة قائمة بالفعل.")
        return
    await send_raid(ctx.channel)

@bot.command(name="علاج")
async def cure_hospital_patient(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("⚠️ يرجى تحديد الساحر لعلاجه بـ `!علاج @الساحر`.")
        return
    if member.id in hospital_patients:
        hospital_patients.remove(member.id)
        await ctx.send(embed=make_embed("💚 علاج ناجح", f"تم علاج الساحر {member.mention} بنجاح.", COLORS["success"]))
    else:
        await ctx.send("🔮 هذا الساحر ليس مصاباً.")

@bot.command(name="المصابين")
async def list_hospital_patients(ctx):
    if not hospital_patients:
        await ctx.send("🏥 المستشفى خالٍ تماماً.")
        return
    report = [f"🛏️ <@{pid}>" for pid in hospital_patients]
    await ctx.send(embed=make_embed("🏥 سجل المصابين", "\n".join(report), COLORS["danger"]))

@bot.command(name="صدارة-الغارة")
async def raid_leaderboard(ctx):
    if not player_scores:
        await ctx.send("📜 لا توجد نتائج مسجلة للغارة.")
        return
    sorted_players = sorted(player_scores.values(), key=lambda x: x["hits"], reverse=True)
    lines = [f"**{p['name']}** — ⚔️ {p['hits']} ضربات" for p in sorted_players[:10]]
    await ctx.send(embed=make_embed("🏆 صدارة أبطال القرية", "\n\n".join(lines), COLORS["gold"]))


# =========================================================
# المبارزات
# =========================================================

SPELLS_DATABASE = {
    "expelliarmus": {"name": "Expelliarmus", "display": "🪄 Expelliarmus · 8 MP", "mana": 8, "damage": 20, "fail": 10, "type": "attack"},
    "stupefy": {"name": "Stupefy", "display": "⚡ Stupefy · 15 MP", "mana": 15, "damage": 35, "fail": 20, "type": "attack"},
    "confringo": {"name": "Confringo", "display": "💥 Confringo · 22 MP", "mana": 22, "damage": 45, "fail": 25, "type": "attack"},
    "reducto": {"name": "Reducto", "display": "🔨 Reducto · 18 MP", "mana": 18, "damage": 38, "fail": 22, "type": "attack"},
    "protego": {"name": "Protego", "display": "🛡️ Protego · 10 MP", "mana": 10, "shield": 15, "fail": 8, "type": "defense"},
    "episkey": {"name": "Episkey", "display": "💚 Episkey · 15 MP", "mana": 15, "heal": 20, "fail": 10, "type": "heal"},
    "incendio": {"name": "Incendio", "display": "🔥 Incendio · 16 MP", "mana": 16, "damage": 33, "fail": 18, "type": "attack"},
    "depulso": {"name": "Depulso", "display": "💨 Depulso · 10 MP", "mana": 10, "damage": 25, "fail": 12, "type": "attack"}
}

class SpellSelectionView(discord.ui.View):
    def __init__(self, duel_session):
        super().__init__(timeout=60)
        self.duel_session = duel_session
        for key in random.sample(list(SPELLS_DATABASE.keys()), min(6, len(SPELLS_DATABASE))):
            self.add_item(SpellButton(key, SPELLS_DATABASE[key]))

    async def on_timeout(self):
        if self.duel_session.finished: return
        self.duel_session.finished = True
        self.duel_session.cleanup()

class SpellButton(discord.ui.Button):
    def __init__(self, key, spell):
        super().__init__(label=spell["display"], style=discord.ButtonStyle.secondary)
        self.spell_key = key
        self.spell_data = spell

    async def callback(self, interaction: discord.Interaction):
        session = self.view.duel_session
        if session.finished: return
        user_id = interaction.user.id
        if user_id not in [session.p1.id, session.p2.id]:
            await interaction.response.send_message("❌ لست مشاركاً في هذه المبارزة.", ephemeral=True)
            return
        
        p_data = session.p1_data if user_id == session.p1.id else session.p2_data
        if user_id == session.p1.id:
            if session.p1_choice: return
            session.p1_choice = self.spell_key
        else:
            if session.p2_choice: return
            session.p2_choice = self.spell_key

        if p_data["mp"] < self.spell_data["mana"]:
            if user_id == session.p1.id: session.p1_choice = None
            else: session.p2_choice = None
            await interaction.response.send_message("🔮 المانا غير كافية!", ephemeral=True)
            return

        await interaction.response.send_message("✓ تم تسجيل تعويذتك.", ephemeral=True)
        await session.update_status_message()
        if session.p1_choice and session.p2_choice:
            self.view.stop()
            await session.execute_round()

class DuelSession:
    def __init__(self, ctx, p1, p2):
        self.ctx = ctx
        self.p1 = p1
        self.p2 = p2
        self.p1_data = {"hp": 200, "mp": 40, "shield": 0}
        self.p2_data = {"hp": 200, "mp": 40, "shield": 0}
        self.p1_choice = None
        self.p2_choice = None
        self.round_num = 1
        self.message = None
        self.finished = False
        self.lock = asyncio.Lock()

    def register(self):
        active_duels[self.p1.id] = self
        active_duels[self.p2.id] = self

    def cleanup(self):
        active_duels.pop(self.p1.id, None)
        active_duels.pop(self.p2.id, None)

    def build_main_embed(self, status_text):
        description = (
            f"## ✦ الجولة {self.round_num:02d} ✦\n\n"
            f"### 🧙 {self.p1.display_name}\n{player_status(self.p1.display_name, self.p1_data)}\n\n"
            f"## ⚔️ VS ⚔️\n\n"
            f"### 🧙 {self.p2.display_name}\n{player_status(self.p2.display_name, self.p2_data)}\n\n"
            f"✨ **حالة الجولة**\n{status_text}"
        )
        return make_embed("⚔️ قاعة المبارزات السحرية الكبرى", description, COLORS["magic"])

    async def start_duel(self):
        self.register()
        embed = self.build_main_embed("🪄 يختار كل ساحر تعويذته...")
        self.message = await self.ctx.send(embed=embed, view=SpellSelectionView(self))

    async def update_status_message(self):
        if not self.message: return
        p1_status = "✓ تم الاختيار" if self.p1_choice else "⏳ يختار..."
        p2_status = "✓ تم الاختيار" if self.p2_choice else "⏳ يختار..."
        status = f"🧙 **{self.p1.display_name}:** {p1_status}\n🧙 **{self.p2.display_name}:** {p2_status}"
        try:
            await self.message.edit(embed=self.build_main_embed(status))
        except: pass

    async def execute_round(self):
        async with self.lock:
            if self.finished or not self.p1_choice or not self.p2_choice: return
            
            self.p1_data["mp"] = min(MAX_MP, self.p1_data["mp"] + 7)
            self.p2_data["mp"] = min(MAX_MP, self.p2_data["mp"] + 7)
            
            s1 = SPELLS_DATABASE[self.p1_choice]
            s2 = SPELLS_DATABASE[self.p2_choice]
            
            self.p1_data["mp"] -= s1["mana"]
            self.p2_data["mp"] -= s2["mana"]

            if not (random.randint(1, 100) <= s1["fail"]) and s1["type"] == "attack":
                dmg = s1["damage"]
                abs_val = min(self.p2_data["shield"], dmg)
                self.p2_data["shield"] -= abs_val
                self.p2_data["hp"] -= (dmg - abs_val)

            if not (random.randint(1, 100) <= s2["fail"]) and s2["type"] == "attack":
                dmg = s2["damage"]
                abs_val = min(self.p1_data["shield"], dmg)
                self.p1_data["shield"] -= abs_val
                self.p1_data["hp"] -= (dmg - abs_val)

            self.p1_data["hp"] = max(0, min(MAX_HP, self.p1_data["hp"]))
            self.p2_data["hp"] = max(0, min(MAX_HP, self.p2_data["hp"]))

            if self.p1_data["hp"] <= 0 or self.p2_data["hp"] <= 0:
                self.finished = True
                winner = self.p1 if self.p1_data["hp"] > 0 else self.p2
                add_result(winner.id, winner.display_name, "win")
                embed = make_embed("🏆 حسمت المعركة", f"👑 بطل الحلبة المنتصر: {winner.mention}", COLORS["gold"])
                if self.message: await self.message.edit(embed=embed, view=None)
                self.cleanup()
                return

            self.round_num += 1
            self.p1_choice = None
            self.p2_choice = None
            if self.message:
                await self.message.edit(embed=self.build_main_embed("✨ الجولة الجديدة بدأت.. اختر تعويذتك."), view=SpellSelectionView(self))

def load_leaderboard(): return load_json_file(LEADERBOARD_FILE)
def save_leaderboard(data): save_json_file(LEADERBOARD_FILE, data)

def add_result(user_id, username, result):
    db = load_leaderboard()
    uid = str(user_id)
    if uid not in db: db[uid] = {"name": username, "wins": 0, "draws": 0}
    db[uid]["wins"] += (1 if result == "win" else 0)
    save_leaderboard(db)

@bot.command(name="مبارزة")
async def duel_command(ctx, member: discord.Member = None):
    if not member or member.id == ctx.author.id or member.bot:
        await ctx.send("⚠️ يرجى منشن ساحر صحيح لمبارزته.")
        return
    if ctx.author.id in active_duels or member.id in active_duels:
        await ctx.send("⚠️ أحد الساحرين مشغول في مبارزة أخرى.")
        return
    await DuelSession(ctx, ctx.author, member).start_duel()

@bot.command(name="صدارة-المبارزات")
async def leaderboard_command(ctx):
    db = load_leaderboard()
    if not db:
        await ctx.send("📜 لا توجد انتصارات مسجلة.")
        return
    sorted_p = sorted(db.values(), key=lambda x: x.get("wins", 0), reverse=True)[:10]
    lines = [f"🥇 **{p['name']}** — 🎯 `{p.get('wins', 0)}` انتصار" for p in sorted_p]
    await ctx.send(embed=make_embed("📜 صدارة حلبة المبارزات", "\n\n".join(lines), COLORS["gold"]))


# =========================================================
# قبعة التنسيق والفعاليات
# =========================================================

@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):
    msg = await ctx.send(embed=make_embed("🎩 قبعة التنسيق", "*تتمتم القبعة بفحص عقلك...*", 0x8B5A2B))
    await asyncio.sleep(3)
    house_key = random.choice(list(HOUSES.keys()))
    assign_student_house(ctx.author.id, ctx.author.name, house_key)
    info = HOUSES[house_key]
    await msg.edit(embed=make_embed("✨ القرار النهائي", f"البيت المُختار: **{info['emoji']} {info['name']}**", info["color"]))

class MagicEventModal(discord.ui.Modal, title="✨ إنشاء فعالية سحرية"):
    event_name = discord.ui.TextInput(label="اسم الفعالية", required=True, max_length=100)
    referee = discord.ui.TextInput(label="الحكم", required=True, max_length=50)
    participants = discord.ui.TextInput(label="المشاركون", required=True, style=discord.TextStyle.paragraph)
    winner = discord.ui.TextInput(label="الفائز", required=False, max_length=50)
    presenter = discord.ui.TextInput(label="المقدم", required=True, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        db = load_json_file(EVENTS_FILE)
        db[self.event_name.value.strip()] = {
            "referee": self.referee.value.strip(),
            "participants": self.participants.value.strip(),
            "winner": self.winner.value.strip() or "لم يُحدد بعد",
            "presenter": self.presenter.value.strip(),
            "author": interaction.user.name
        }
        save_json_file(EVENTS_FILE, db)
        await interaction.response.send_message(embed=make_embed(f"📜 {self.event_name.value}", "✨ تم تسجيل الفعالية بنجاح!", COLORS["gold"]))

class CreateEventView(discord.ui.View):
    @discord.ui.button(label="📝 فتح استمارة الفعالية", style=discord.ButtonStyle.success)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MagicEventModal())

@bot.command(name="انشاء_فعالية")
async def create_magic_event_cmd(ctx):
    await ctx.send(embed=make_embed("🪄 الألعاب السحرية", "اضغط الزر أدناه لفتح الاستمارة:", COLORS["magic"]), view=CreateEventView())

@bot.command(name="عرض_فعاليات")
async def show_magic_events(ctx):
    db = load_json_file(EVENTS_FILE)
    if not db:
        await ctx.send("⚠️ لا توجد فعاليات مسجلة.")
        return
    desc = "\n".join([f"📌 **{k}**\n• المقدم: {v.get('presenter')}\n• الحكم: {v.get('referee')}\n━━━━━━━━━━" for k, v in db.items()])
    await ctx.send(embed=make_embed("📚 الفعاليات السحرية", desc, COLORS["blue"]))

@bot.command(name="مسح_فعالية")
async def delete_magic_event(ctx, *, event_name: str):
    db = load_json_file(EVENTS_FILE)
    if event_name.strip() in db:
        del db[event_name.strip()]
        save_json_file(EVENTS_FILE, db)
        await ctx.send(f"🗑️ تم حذف الفعالية **{event_name}**.")
    else:
        await ctx.send("⚠️ الفعالية غير موجودة.")

@tasks.loop(hours=12)
async def scheduled_attack():
    channel = bot.get_channel(RAID_CHANNEL_ID)
    if channel and not raid_active:
        await send_raid(channel)

@bot.event
async def on_ready():
    print(f"🪄 البوت متصل بنجاح: {bot.user}")


# =========================================================
# لوحة التحكم (FastAPI Dashboard)
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>الوزارة السحرية</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#08060d] text-white min-h-screen flex items-center justify-center p-5"><div class="bg-[#16101f] border border-gold/30 rounded-3xl p-10 max-w-lg w-full text-center shadow-2xl"><div class="text-6xl mb-4">🪄</div><h1 class="text-3xl font-bold text-yellow-500 mb-3">الإدارة السحرية</h1><p class="text-gray-400 mb-6">لوحة التحكم الرسمية لإدارة المملكة السحرية والطلاب.</p><a href="/login" class="block bg-[#5865F2] hover:bg-[#4752C4] py-3 rounded-xl font-bold">الدخول بواسطة Discord ✨</a></div></body></html>""")

@app.get("/login")
async def login():
    return RedirectResponse(f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds")

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_ENDPOINT}/oauth2/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}, headers={"Content-Type": "application/x-www-form-urlencoded"}) as resp:
            if resp.status != 200: raise HTTPException(status_code=400, detail="فشل المصادقة")
            token_data = await resp.json()
        async with session.get(f"{API_ENDPOINT}/users/@me", headers={"Authorization": f"Bearer {token_data.get('access_token')}"}) as resp:
            if resp.status != 200: raise HTTPException(status_code=400, detail="خطأ بيانات المستخدم")
            user = await resp.json()
    request.session["user"] = {"id": user.get("id"), "username": user.get("username"), "global_name": user.get("global_name"), "avatar": user.get("avatar")}
    return RedirectResponse("/dashboard")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user: return RedirectResponse("/login")
    name = user.get("global_name") or user.get("username")
    return HTMLResponse(f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#08060d] text-white min-h-screen p-10"><div class="max-w-4xl mx-auto bg-[#16101f] border border-white/10 rounded-3xl p-8 shadow-xl"><h1 class="text-3xl font-bold text-yellow-500 mb-4">مرحباً بك يا {name} 🪄</h1><p class="text-gray-400 mb-6">البوت متصل ويعمل بكامل طاقته السحرية في خلفية السيرفر.</p><a href="/logout" class="bg-red-500 px-4 py-2 rounded-xl font-bold">تسجيل الخروج</a></div></body></html>""")


# =========================================================
# التشغيل المزدوج (FastAPI + Discord Bot معا في نفس السيرفر)
# =========================================================

def run_fastapi():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        print("⚠️ خطأ: توكن البوت غير موجود!")
    else:
        # تشغيل سرفر الويب في خيط منفصل (Thread) لكي لا يحجب تشغيل البوت
        web_thread = threading.Thread(target=run_fastapi, daemon=True)
        web_thread.start()
        
        # إضافات Views المستمرة
        bot.add_view(VillageDefenseView())
        if not scheduled_attack.is_running():
            scheduled_attack.start()

        # تشغيل ديسكورد بوت الأساسي
        bot.run(token)

