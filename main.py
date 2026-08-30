import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
import json
import sqlite3
import asyncio
from datetime import datetime

# =========================================================
# إعدادات البوت والبيانات
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
DB_FILE = "house_cup.db"

RAID_CHANNEL_ID = 1540623521774960682

MAX_HP = 200
MAX_MP = 40
DAMAGE_PER_HIT = 10

current_hp = MAX_HP
raid_active = False

player_scores = {}
hospital_patients = set()
active_duels = {}

HOUSE_ROLES = {
    "جريفندور": "🦁",
    "هافلباف": "🦡",
    "رافنكلو": "🦅",
    "سليذرين": "🐍",
}

HOUSE_ALIASES = {
    "جريفندور": "جريفندور", "gryffindor": "جريفندور",
    "هافلباف": "هافلباف", "hufflepuff": "هافلباف",
    "رافنكلو": "رافنكلو", "ravenclaw": "رافنكلو",
    "سليذرين": "سليذرين", "slytherin": "سليذرين",
}


# =========================================================
# أدوات قاعدة بيانات كأس المنازل (SQLite)
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
        CREATE TABLE IF NOT EXISTS point_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            house TEXT NOT NULL,
            amount INTEGER NOT NULL,
            user_id INTEGER,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            undone INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def ensure_guild(guild_id: int):
    conn = get_db()
    cur = conn.cursor()
    for house in HOUSE_ROLES:
        cur.execute("""
            INSERT OR IGNORE INTO house_scores (guild_id, house, points)
            VALUES (?, ?, 0)
        """, (guild_id, house))
    conn.commit()
    conn.close()

def can_manage_cup(member: discord.Member):
    if member.guild_permissions.administrator:
        return True
    allowed_roles = {"مدير الكأس", "مشرف الكأس", "House Cup", "Cup Manager"}
    return any(role.name in allowed_roles for role in member.roles)

def normalize_house(name):
    if not name: return None
    return HOUSE_ALIASES.get(name.strip().lower())

def house_from_database(guild_id: int, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT house FROM members_houses WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cur.fetchone()
    conn.close()
    return row["house"] if row else None

def add_points(guild_id: int, house: str, amount: int, user_id, moderator_id: int, reason: str):
    ensure_guild(guild_id)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE house_scores SET points = points + ? WHERE guild_id = ? AND house = ?", (amount, guild_id, house))
    cur.execute("""
        INSERT INTO point_logs (guild_id, house, amount, user_id, moderator_id, reason, created_at, undone)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (guild_id, house, amount, user_id, moderator_id, reason, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
    log_id = cur.lastrowid
    cur.execute("SELECT points FROM house_scores WHERE guild_id = ? AND house = ?", (guild_id, house))
    row = cur.fetchone()
    new_points = row["points"]
    conn.commit()
    conn.close()
    return log_id, new_points

def undo_last_action(guild_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM point_logs WHERE guild_id = ? AND undone = 0 ORDER BY id DESC LIMIT 1", (guild_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    cur.execute("UPDATE house_scores SET points = points - ? WHERE guild_id = ? AND house = ?", (row["amount"], guild_id, row["house"]))
    cur.execute("UPDATE point_logs SET undone = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return row

def get_scores(guild_id: int):
    ensure_guild(guild_id)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT house, points FROM house_scores WHERE guild_id = ? ORDER BY points DESC", (guild_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def create_cup_embed(guild: discord.Guild):
    rows = get_scores(guild.id)
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    embed = discord.Embed(
        title="🏆 كأس المنازل",
        description="━━━━━━━━━━━━━━━━━━━━\n✨ **ترتيب المنازل الحالي**\n━━━━━━━━━━━━━━━━━━━━",
        color=0xD4AF37
    )
    for index, row in enumerate(rows):
        house, points = row["house"], row["points"]
        emoji = HOUSE_ROLES[house]
        medal = medals[index] if index < len(medals) else f"{index + 1}️⃣"
        embed.add_field(name=f"{medal} {emoji} {house}", value=f"⭐ **{points:,} نقطة**", inline=False)
    embed.set_footer(text=AUTHOR_SIGNATURE)
    return embed


# =========================================================
# أدوات JSON والتخزين
# =========================================================

def load_json_file(filename):
    if not os.path.exists(filename): return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except: return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

def assign_student_house(user_id, username, house_name, guild_id=None):
    db = load_json_file(STUDENTS_FILE)
    db[str(user_id)] = {"name": username, "house": house_name}
    save_json_file(STUDENTS_FILE, db)

    if guild_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO members_houses (guild_id, user_id, house)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET house = excluded.house
        """, (guild_id, user_id, house_name))
        conn.commit()
        conn.close()

def student_already_sorted(guild_id: int, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT house FROM members_houses WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cur.fetchone()
    conn.close()
    if row: return True
    students_db = load_json_file(STUDENTS_FILE)
    return str(user_id) in students_db


# =========================================================
# تصميم البوت والألوان
# =========================================================

COLORS = {
    "magic": 0x2B1338, "gold": 0xD4AF37, "danger": 0x6E0B14,
    "success": 0x1E5631, "blue": 0x162A4A, "dark": 0x15121C, "silver": 0x777777
}

def make_embed(title, description="", color=None):
    embed = discord.Embed(title=title, description=description, color=color or COLORS["magic"], timestamp=datetime.utcnow())
    embed.set_footer(text=AUTHOR_SIGNATURE)
    return embed


# =========================================================
# البيوت وقبعة التنسيق (4 أسئلة)
# =========================================================

HOUSES = {
    "جريفندور": {"name": "جريفندور (Gryffindor)", "emoji": "🦁", "color": 0x740909, "desc": "الجرأة والشجاعة والفروسية."},
    "سليذيرين": {"name": "سليذيرين (Slytherin)", "emoji": "🐍", "color": 0x1A472A, "desc": "الطموح والدهاء والقيادة."},
    "رافينكلو": {"name": "رافينكلو (Ravenclaw)", "emoji": "🦅", "color": 0x0E1A40, "desc": "الحكمة والذكاء والإبداع."},
    "هافلباف": {"name": "هافلباف (Hufflepuff)", "emoji": "🦡", "color": 0xECB939, "desc": "الإخلاص والعدالة والعمل الجاد."}
}

class SortingHatQuizView(discord.ui.View):
    def __init__(self, user, guild_id):
        super().__init__(timeout=60)
        self.user = user
        self.guild_id = guild_id
        self.scores = {"جريفندور": 0, "سليذيرين": 0, "رافينكلو": 0, "هافلباف": 0}
        self.current_question = 0
        self.questions = [
            {
                "q": "السؤال الأول: ما هو الشيء الذي تفضل أن يُذكر به اسمك بعد رحيلك؟",
                "options": [
                    ("الشجاعة والبسالة في وجه الأخطار", "جريفندور"),
                    ("المجد والطموح وتحقيق الأهداف الكبرى", "سليذيرين"),
                    ("الحكمة والمعرفة واكتشاف أسرار الكون", "رافينكلو"),
                    ("العدالة واللطف ومساعدة الأصدقاء", "هافلباف")
                ]
            },
            {
                "q": "السؤال الثاني: أمامك باب مغلق ومجهول، ماذا تفعل؟",
                "options": [
                    ("أقوم فتحه بقوة ودون تردد لأسبر غوره", "جريفندور"),
                    ("أدرس الطريقة الذكية لاستغلاله لمصلحتي", "سليذيرين"),
                    ("أبحث عن اللغز المفتاحي وأحل رموزه أولاً", "رافينكلو"),
                    ("أتأكد من أنه لا يضر أحداً قبل أن أقترب منه", "هافلباف")
                ]
            },
            {
                "q": "السؤال الثالث: ما هي الصفة التي تكرهها أكثر في الآخرين؟",
                "options": [
                    ("الجبن والتراجع عند الشدائد", "جريفندور"),
                    ("الكسل وفقدان الطموح والرضا بالقاع", "سليذيرين"),
                    ("الجهل وسطحية التفكير", "رافينكلو"),
                    ("الظلم والأنانية وقسوة القلوب", "هافلباف")
                ]
            },
            {
                "q": "السؤال الرابع: في وقت الفراغ، ما هو المكان الذي تفضل قضاء وقتك فيه؟",
                "options": [
                    ("ميدان التحدي والمغامرات الخارجية", "جريفندور"),
                    ("التخطيط لمشاريعي المستقبلية والانفراد بالتميز", "سليذيرين"),
                    ("المكتبة الكبرى بين الكتب القديمة والأسرار", "رافينكلو"),
                    ("الحدائق الهادئة ومشاركة الأصدقاء الجلسات", "هافلباف")
                ]
            }
        ]
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.current_question < len(self.questions):
            for text, house in self.questions[self.current_question]["options"]:
                self.add_item(QuizOptionButton(text, house))

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        try: await self.message.edit(content="⏳ انتهى وقت التنسيق.", view=None)
        except: pass

class QuizOptionButton(discord.ui.Button):
    def __init__(self, label, house):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.house = house

    async def callback(self, interaction: discord.Interaction):
        view: SortingHatQuizView = self.view
        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("❌ هذه ليست قبعتك!", ephemeral=True)

        view.scores[self.house] += 1
        view.current_question += 1

        if view.current_question < len(view.questions):
            view.update_buttons()
            q_data = view.questions[view.current_question]
            embed = make_embed("🎩 اختبار قبعة التنسيق", f"**{q_data['q']}**", 0x8B5A2B)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            winning_house = max(view.scores, key=view.scores.get)
            assign_student_house(view.user.id, view.user.name, winning_house, view.guild_id)
            info = HOUSES[winning_house]
            final_embed = make_embed(
                "✨ القرار النهائي لقبعة التنسيق",
                f"🧙 **الساحر:** {view.user.mention}\n\n{info['emoji']} **البيت:**\n## {info['name']}\n\n*{info['desc']}*",
                info["color"]
            )
            for child in view.children: child.disabled = True
            await interaction.response.edit_message(embed=final_embed, view=None)

@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):
    if student_already_sorted(ctx.guild.id, ctx.author.id):
        return await ctx.send(embed=make_embed("⚠️ عذراً", "لقد تم اختيار منزلك مسبقاً!", COLORS["danger"]), delete_after=10)

    first_q = "*تستقر القبعة على رأسك وتهمس بأسئلتها الأربعة...*\n\n**السؤال الأول: ما هو الشيء الذي تفضل أن يُذكر به اسمك بعد رحيلك؟**"
    embed = make_embed("🎩 قبعة التنسيق", first_q, 0x8B5A2B)
    view = SortingHatQuizView(ctx.author, ctx.guild.id)
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg


# =========================================================
# استمارة إضافة النقاط للطالب (Modal)
# =========================================================

class AddPointsModal(discord.ui.Modal, title="✨ استمارة إضافة نقاط السحر"):
    student_input = discord.ui.TextInput(
        label="منشن الساحر أو الآي دي (ID)",
        placeholder="مثال: @سيدريك أو 123456789",
        style=discord.TextStyle.short,
        required=True
    )
    points_input = discord.ui.TextInput(
        label="عدد النقاط",
        placeholder="اكتب رقماً صحيحاً مثل: 50",
        style=discord.TextStyle.short,
        required=True
    )
    reason_input = discord.ui.TextInput(
        label="سبب إضافة النقاط",
        placeholder="مثال: الفوز في مسابقة الأعشاب السحرية",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        student_text = self.student_input.value.strip()
        points_text = self.points_input.value.strip()
        reason = self.reason_input.value.strip()

        target_member = None
        if interaction.guild:
            cleaned_id = student_text.replace("<@", "").replace(">", "").replace("!", "")
            if cleaned_id.isdigit():
                target_member = interaction.guild.get_member(int(cleaned_id))
                if not target_member:
                    try:
                        target_member = await interaction.guild.fetch_member(int(cleaned_id))
                    except:
                        pass

        if not target_member:
            return await interaction.response.send_message("❌ لم أتمكن من العثور على هذا الساحر! تأكد من المنشن.", ephemeral=True)

        try:
            points = int(points_text)
            if points <= 0: raise ValueError()
        except ValueError:
            return await interaction.response.send_message("❌ عدد النقاط يجب أن يكون رقماً صحيحاً أكبر من الصفر.", ephemeral=True)

        house = house_from_database(interaction.guild.id, target_member.id)
        if not house:
            students_db = load_json_file(STUDENTS_FILE)
            user_data = students_db.get(str(target_member.id))
            if user_data and "house" in user_data:
                house = user_data["house"]

        if not house:
            return await interaction.response.send_message(f"❌ الساحر {target_member.mention} لم يتم تنصيبه في منزل بعد!", ephemeral=True)

        log_id, new_score = add_points(interaction.guild.id, house, points, target_member.id, interaction.user.id, reason)
        emoji = HOUSE_ROLES[house]

        embed = discord.Embed(title="✨ تم تسجيل النقاط بنجاح عبر الاستمارة", color=0x57F287)
        embed.add_field(name="🧙 الساحر", value=target_member.mention, inline=True)
        embed.add_field(name="🏠 المنزل المرتبط", value=f"{emoji} **{house}**", inline=True)
        embed.add_field(name="⭐ النقاط المضافة", value=f"**+{points:,}**", inline=True)
        embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.add_field(name="🏆 رصيد المنزل الجديد", value=f"**{new_score:,} نقطة**", inline=False)
        embed.set_footer(text=AUTHOR_SIGNATURE)

        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="إضافة-نقاط", description="فتح استمارة إضافة النقاط للساحر سراً")
async def slash_add_points_form(interaction: discord.Interaction):
    if not can_manage_cup(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية لإدارة كأس المنازل.", ephemeral=True)
    await interaction.response.send_modal(AddPointsModal())


# =========================================================
# أوامر كأس المنازل الأساسية
# =========================================================

@bot.command(name="الكأس")
async def cup_command(ctx):
    ensure_guild(ctx.guild.id)
    await ctx.send(embed=create_cup_embed(ctx.guild))

@bot.command(name="تراجع")
async def undo_cmd(ctx):
    if not can_manage_cup(ctx.author): return await ctx.send("❌ ليس لديك صلاحية.", delete_after=10)
    row = undo_last_action(ctx.guild.id)
    if not row: return await ctx.send("❌ لا توجد عملية قابلة للتراجع.", delete_after=10)
    await ctx.send(embed=make_embed("↩️ تم التراجع", f"المنزل: {row['house']}\nالعملية: {row['amount']:,} نقطة", COLORS["gold"]))

@bot.command(name="السجل")
async def logs_cmd(ctx):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM point_logs WHERE guild_id = ? ORDER BY id DESC LIMIT 10", (ctx.guild.id,))
    rows = cur.fetchall()
    conn.close()

    embed = discord.Embed(title="📜 سجل كأس المنازل", description="آخر 10 عمليات", color=0x5865F2)
    if not rows: embed.description = "لا توجد عمليات مسجلة."
    for row in rows:
        embed.add_field(name=f"#{row['id']} • {row['house']}", value=f"⭐ {row['amount']} | 📝 {row['reason']}", inline=False)
    embed.set_footer(text=AUTHOR_SIGNATURE)
    await ctx.send(embed=embed)


# =========================================================
# تشغيل البوت والأحداث
# =========================================================

@bot.event
async def on_ready():
    init_db()
    try:
        await bot.tree.sync()
        print("🪄 تم مزامنة الأوامر التفاعلية (Slash Commands) بنجاح.")
    except Exception as e:
        print(f"⚠️ خطأ في مزامنة الأوامر: {e}")
    print(f"🪄 بوت هوجوارتس متصل بنجاح: {bot.user}")

@bot.event
async def on_guild_join(guild: discord.Guild):
    ensure_guild(guild.id)

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        print("⚠️ خطأ: لم يتم العثور على توكن البوت!")
    else:
        bot.run(token)
