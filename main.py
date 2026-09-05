import discord
from discord.ext import commands
import os
import json
import sqlite3
from datetime import datetime

# =========================================================
# 🪄 إعدادات البوت الأساسية
# =========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

AUTHOR_SIGNATURE = "✦ صُنع بعناية بواسطة سيدريك 🪄"
STUDENTS_FILE = "hogwarts_students.json"
DB_FILE = "house_cup.db"

COLORS = {
    "magic": 0x2B1338,
    "gold": 0xD4AF37,
    "danger": 0x6E0B14,
    "success": 0x1E5631,
    "blue": 0x162A4A,
    "silver": 0x777777,
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

HOUSE_ROLES = {
    "جريفندور": "🦁",
    "هافلباف": "🦡",
    "رافنكلو": "🦅",
    "سليذرين": "🐍",
}

HOUSE_ALIASES = {
    "جريفندور": "جريفندور", "gryffindor": "جريفندور",
    "هافلباف": "هافلباف", "hufflepuff": "هافلباف",
    "رافنكلو": "رافنكلو", "رافينكلو": "رافنكلو", "ravenclaw": "رافنكلو",
    "سليذرين": "سليذرين", "slytherin": "سليذرين",
}

HOUSES = {
    "جريفندور": {"name": "جريفندور (Gryffindor)", "emoji": "🦁", "color": 0x740909, "desc": "الجرأة والشجاعة والفروسية."},
    "سليذرين": {"name": "سليذرين (Slytherin)", "emoji": "🐍", "color": 0x1A472A, "desc": "الطموح والدهاء والقيادة."},
    "رافنكلو": {"name": "رافنكلو (Ravenclaw)", "emoji": "🦅", "color": 0x0E1A40, "desc": "الحكمة والذكاء والإبداع."},
    "هافلباف": {"name": "هافلباف (Hufflepuff)", "emoji": "🦡", "color": 0xECB939, "desc": "الإخلاص والعدالة والعمل الجاد."}
}

# =========================================================
# 🗄️ قاعدة البيانات والتهيئة
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS house_scores (
            guild_id INTEGER NOT NULL,
            house TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, house)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members_houses (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            house TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

def ensure_guild(guild_id: int):
    conn = get_db()
    cur = conn.cursor()
    for house in HOUSE_ROLES:
        cur.execute("INSERT OR IGNORE INTO house_scores (guild_id, house, points) VALUES (?, ?, 0)", (guild_id, house))
    conn.commit()
    conn.close()

def can_manage_cup(member: discord.Member):
    if member.guild_permissions.administrator:
        return True
    allowed_roles = {"مدير الكأس", "مشرف الكأس", "House Cup", "Cup Manager"}
    return any(role.name in allowed_roles for role in member.roles)

def load_json_file(filename):
    if not os.path.exists(filename): return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except: return False

def assign_student_house(user_id, username, house_name, guild_id=None):
    db = load_json_file(STUDENTS_FILE)
    if not isinstance(db, dict): db = {}
    db[str(user_id)] = {"name": username, "house": house_name}
    save_json_file(STUDENTS_FILE, db)
    if guild_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO members_houses (guild_id, user_id, house) VALUES (?, ?, ?) ON CONFLICT(guild_id, user_id) DO UPDATE SET house = excluded.house", (guild_id, user_id, house_name))
        conn.commit()
        conn.close()

def student_already_sorted(guild_id: int, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT house FROM members_houses WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cur.fetchone()
    conn.close()
    if row: return True
    return str(user_id) in load_json_file(STUDENTS_FILE)

# =========================================================
# 🎩 قبعة التنسيق
# =========================================================

class SortingHatView(discord.ui.View):
    def __init__(self, user, guild_id):
        super().__init__(timeout=120)
        self.user = user
        self.guild_id = guild_id
        self.current_question = 0
        self.scores = {"جريفندور": 0, "سليذرين": 0, "رافنكلو": 0, "هافلباف": 0}
        self.finished = False
        self.questions = [
            {"q": "ما الصفة التي تريد أن يُذكر بها اسمك؟", "options": [("🦁 الشجاعة والبسالة", "جريفندور"), ("🐍 الطموح وتحقيق الأهداف", "سليذرين"), ("🦅 الحكمة والمعرفة", "رافنكلو"), ("🦡 العدالة ومساعدة الآخرين", "هافلباف")]},
            {"q": "أمامك باب غامض لا تعرف ما خلفه، ماذا تفعل؟", "options": [("🦁 أفتحه دون تردد", "جريفندور"), ("🐍 أبحث عن أفضل طريقة لاستغلاله", "سليذرين"), ("🦅 أحاول حل اللغز أولاً", "رافنكلو"), ("🦡 أتأكد أنه لن يؤذي أحداً", "هافلباف")]},
        ]
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        for text, house in self.questions[self.current_question]["options"]:
            self.add_item(SortingOptionButton(text, house))

    def create_question_embed(self):
        q = self.questions[self.current_question]
        return make_embed("🎩 قبعة التنسيق", f"### السؤال {self.current_question + 1}/2\n\n**{q['q']}**", 0x8B5A2B)

class SortingOptionButton(discord.ui.Button):
    def __init__(self, label, house):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.house = house

    async def callback(self, interaction: discord.Interaction):
        view: SortingHatView = self.view
        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("❌ ليست لك!", ephemeral=True)
        view.scores[self.house] += 1
        view.current_question += 1
        if view.current_question < len(view.questions):
            view.update_buttons()
            return await interaction.response.edit_message(embed=view.create_question_embed(), view=view)
        
        view.finished = True
        winning_house = max(view.scores, key=view.scores.get)
        assign_student_house(view.user.id, view.user.name, winning_house, view.guild_id)
        info = HOUSES[winning_house]
        await interaction.response.edit_message(embed=make_embed("✨ القرار النهائي", f"🧙 {view.user.mention}\n{info['emoji']} **المنزل:** {info['name']}", info["color"]), view=None)

@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):
    if not ctx.guild: return
    if student_already_sorted(ctx.guild.id, ctx.author.id):
        return await ctx.send(embed=make_embed("⚠️ عذراً", "لقد تم اختيار منزلك مسبقاً!", COLORS["danger"]), delete_after=10)
    view = SortingHatView(ctx.author, ctx.guild.id)
    view.clear_items()
    btn = discord.ui.Button(label="🎩 ابدأ الاختبار", style=discord.ButtonStyle.primary)
    async def start_cb(i):
        if i.user.id != ctx.author.id: return
        view.update_buttons()
        await i.response.edit_message(embed=view.create_question_embed(), view=view)
    btn.callback = start_cb
    view.add_item(btn)
    await ctx.send(embed=make_embed("🎩 قبعة التنسيق", "اضغط الزر لبدء الاختبار."), view=view)

# =========================================================
# 🎪 نظام الفعاليات المتكامل
# =========================================================

def create_event(guild_id: int, name: str, description: str, creator_id: int):
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO events (guild_id, name, description, created_by, created_at, updated_at, active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (guild_id, name.strip(), description.strip(), creator_id, now, now))
    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    return event_id

def get_event(guild_id: int, event_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE guild_id = ? AND id = ? AND active = 1", (guild_id, event_id))
    event = cur.fetchone()
    conn.close()
    return event

def get_all_events(guild_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE guild_id = ? AND active = 1 ORDER BY id DESC", (guild_id,))
    events = cur.fetchall()
    conn.close()
    return events

def delete_event(guild_id: int, event_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE events SET active = 0, updated_at = ? WHERE guild_id = ? AND id = ? AND active = 1", (datetime.utcnow().isoformat(), guild_id, event_id))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def update_event(guild_id: int, event_id: int, name: str, description: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE events SET name = ?, description = ?, updated_at = ? WHERE guild_id = ? AND id = ? AND active = 1", (name.strip(), description.strip(), datetime.utcnow().isoformat(), guild_id, event_id))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated

class EventModal(discord.ui.Modal, title="🎪 تسجيل فعالية جديدة"):
    name = discord.ui.TextInput(label="اسم الفعالية", placeholder="مثال: مسابقة المخلوقات", required=True, max_length=100)
    desc = discord.ui.TextInput(label="وصف الفعالية", placeholder="اكتب التفاصيل...", style=discord.TextStyle.paragraph, required=True, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild: return
        if not can_manage_cup(interaction.user):
            return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
        event_id = create_event(interaction.guild.id, self.name.value, self.desc.value, interaction.user.id)
        embed = make_embed("🎪 تم تسجيل الفعالية", f"📌 **الاسم:** {self.name.value}\n🆔 **الرقم:** `{event_id}`", COLORS["success"])
        await interaction.response.send_message(embed=embed)

class EventCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🎪 تسجيل فعالية", style=discord.ButtonStyle.primary)
    async def create_event_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage_cup(interaction.user):
            return await interaction.response.send_message("❌ ليس لديك صلاحية.", ephemeral=True)
        await interaction.response.send_modal(EventModal())

@bot.command(name="تسجيل-فعالية")
async def register_event(ctx):
    if not ctx.guild or not can_manage_cup(ctx.author): return
    await ctx.send(embed=make_embed("🎪 إدارة الفعاليات", "اضغط الزر بالأسفل لتسجيل فعالية جديدة.", COLORS["gold"]), view=EventCreateView())

@bot.command(name="الفعاليات")
async def list_events(ctx):
    if not ctx.guild: return
    events = get_all_events(ctx.guild.id)
    if not events: return await ctx.send(embed=make_embed("📚 سجل الفعاليات", "لا توجد فعاليات مسجلة.", COLORS["blue"]))
    embed = make_embed("📚 سجل الفعاليات", "الفعاليات المحفوظة:")
    for ev in events[:25]:
        embed.add_field(name=f"🎪 {ev['name']}", value=f"🆔 الرقم: `{ev['id']}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="فعالية")
async def show_event(ctx, event_id: int = None):
    if not ctx.guild or event_id is None: return
    ev = get_event(ctx.guild.id, event_id)
    if not ev: return await ctx.send(embed=make_embed("❌ غير موجودة", "رقم الفعالية غير صحيح.", COLORS["danger"]))
    creator = ctx.guild.get_member(ev["created_by"])
    embed = make_embed(f"🎪 {ev['name']}", ev["description"], COLORS["gold"])
    embed.add_field(name="🆔 الرقم", value=f"`{ev['id']}`", inline=True)
    embed.add_field(name="🧙 المنشئ", value=creator.mention if creator else "غير معروف", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="استدعاء-فعالية")
async def invoke_event(ctx, event_id: int = None):
    if not ctx.guild or event_id is None: return
    ev = get_event(ctx.guild.id, event_id)
    if not ev: return await ctx.send(embed=make_embed("❌ غير موجودة", "رقم الفعالية غير صحيح.", COLORS["danger"]))
    embed = make_embed(f"📢 {ev['name']}", f"✨ **إعلان الفعالية**\n\n{ev['description']}\n\n🆔 **الرقم:** `{ev['id']}`", COLORS["gold"])
    await ctx.send(embed=embed)

@bot.command(name="حذف-فعالية")
async def delete_event_command(ctx, event_id: int = None):
    if not ctx.guild or not can_manage_cup(ctx.author) or event_id is None: return
    if delete_event(ctx.guild.id, event_id):
        await ctx.send(embed=make_embed("🗑️ تم الحذف", f"تم حذف الفعالية رقم `{event_id}` بنجاح.", COLORS["success"]))
    else:
        await ctx.send(embed=make_embed("❌ خطأ", "لم يتم العثور على الفعالية.", COLORS["danger"]))

# =========================================================
# 🚀 تشغيل البوت
# =========================================================

@bot.event
async def on_ready():
    init_db()
    try:
        await bot.tree.sync()
    except:
        pass
    print(f"🪄 بوت كأس المنازل والفعاليات يعمل الآن: {bot.user}")

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("⚠️ تنبيه: لم يتم العثور على متغير البيئة BOT_TOKEN")
    bot.run(token)
