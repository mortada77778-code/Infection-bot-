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
# إعدادات البوت والبيانات الأساسية
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

# ثوابت المبارزات والغارات
MAX_HP = 200
MAX_MP = 100  # الحد الأقصى للمانا 100
DAMAGE_PER_HIT = 10

current_hp = MAX_HP
raid_active = False
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

COLORS = {
    "magic": 0x2B1338, "gold": 0xD4AF37, "danger": 0xED4245,
    "success": 0x57F287, "blue": 0x5865F2, "dark": 0x15121C
}

def make_embed(title, description="", color=None):
    embed = discord.Embed(title=title, description=description, color=color or COLORS["gold"], timestamp=datetime.utcnow())
    embed.set_footer(text=AUTHOR_SIGNATURE)
    return embed


# =========================================================
# قاعدة البيانات (SQLite - Persistence & Safe Initialization)
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS duel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            winner_id INTEGER,
            loser_id INTEGER,
            p1_hp INTEGER,
            p2_hp INTEGER,
            rounds INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS duel_stats (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            draws INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
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


# =========================================================
# أدوات JSON والتخزين المساعد
# =========================================================

def load_json_file(filename):
    if not os.path.exists(filename): return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, (dict, list)) else {}
    except: return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

def assign_student_house(user_id, username, house_name, guild_id=None):
    db = load_json_file(STUDENTS_FILE)
    if isinstance(db, dict):
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
    return str(user_id) in students_db if isinstance(students_db, dict) else False


# =========================================================
# أوامر وعروض كأس المنازل وإضافة النقاط
# =========================================================

@bot.command(name="الكأس")
async def cup_command(ctx):
    ensure_guild(ctx.guild.id)
    rows = get_scores(ctx.guild.id)
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    embed = make_embed(
        "🏆 كأس المنازل",
        "━━━━━━━━━━━━━━━━━━━━\n✨ **ترتيب المنازل الحالي**\n━━━━━━━━━━━━━━━━━━━━",
        COLORS["gold"]
    )
    for index, row in enumerate(rows):
        house, points = row["house"], row["points"]
        emoji = HOUSE_ROLES.get(house, "✨")
        medal = medals[index] if index < len(medals) else f"{index + 1}️⃣"
        embed.add_field(name=f"{medal} {emoji} {house}", value=f"⭐ **{points:,} نقطة**", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="تراجع")
async def undo_cmd(ctx):
    if not can_manage_cup(ctx.author): 
        return await ctx.send(embed=make_embed("❌ خطأ", "ليس لديك صلاحية لإدارة الكأس.", COLORS["danger"]), delete_after=10)
    row = undo_last_action(ctx.guild.id)
    if not row: 
        return await ctx.send(embed=make_embed("❌ خطأ", "لا توجد عملية قابلة للتراجع.", COLORS["danger"]), delete_after=10)
    await ctx.send(embed=make_embed("↩️ تم التراجع بنجاح", f"المنزل: {row['house']}\nالعملية السابقة: {row['amount']:,} نقطة", COLORS["success"]))

@bot.command(name="السجل")
async def logs_cmd(ctx):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM point_logs WHERE guild_id = ? ORDER BY id DESC LIMIT 10", (ctx.guild.id,))
    rows = cur.fetchall()
    conn.close()

    embed = make_embed("📜 سجل كأس المنازل", "آخر 10 عمليات تمت على النقاط", COLORS["blue"])
    if not rows:
        embed.description = "لا توجد عمليات مسجلة حتى الآن."
    for row in rows:
        user_mention = f"<@{row['user_id']}>" if row['user_id'] else "البيت ككل"
        undone_status = " ↩️ (متراجع عنها)" if row['undone'] else ""
        embed.add_field(
            name=f"#{row['id']} • {row['house']}{undone_status}",
            value=f"⭐ **{row['amount']:+,}** | الساحر: {user_mention}\n📝 السبب: {row['reason']}",
            inline=False
        )
    await ctx.send(embed=embed)


# =========================================================
# استمارات إضافة النقاط (/إضافة-نقاط و /نقاط_البيت)
# =========================================================

class AddPointsModal(discord.ui.Modal, title="✨ استمارة إضافة نقاط السحر"):
    student_input = discord.ui.TextInput(label="آي دي (ID) الساحر", placeholder="مثال: 84920391820", required=True)
    points_input = discord.ui.TextInput(label="عدد النقاط", placeholder="مثال: 50", required=True)
    reason_input = discord.ui.TextInput(label="السبب", placeholder="الفوز في مسابقة الأعشاب", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        student_text = self.student_input.value.strip()
        points_text = self.points_input.value.strip()
        reason = self.reason_input.value.strip()

        target_member = None
        cleaned_id = "".join(filter(str.isdigit, student_text))
        if cleaned_id.isdigit():
            target_member = interaction.guild.get_member(int(cleaned_id))
            if not target_member:
                try: target_member = await interaction.guild.fetch_member(int(cleaned_id))
                except: pass

        if not target_member:
            return await interaction.response.send_message(embed=make_embed("❌ خطأ", "لم أتمكن من العثور على الساحر بالآي دي المدخل!", COLORS["danger"]), ephemeral=True)

        try:
            points = int(points_text)
            if points <= 0: raise ValueError()
        except ValueError:
            return await interaction.response.send_message(embed=make_embed("❌ خطأ", "عدد النقاط يجب أن يكون رقماً صحيحاً أكبر من الصفر.", COLORS["danger"]), ephemeral=True)

        house = house_from_database(interaction.guild.id, target_member.id)
        if not house:
            students_db = load_json_file(STUDENTS_FILE)
            if isinstance(students_db, dict) and str(target_member.id) in students_db:
                house = students_db[str(target_member.id)].get("house")

        if not house:
            return await interaction.response.send_message(embed=make_embed("❌ خطأ", f"الساحر {target_member.mention} لم يفرز في منزل بعد!", COLORS["danger"]), ephemeral=True)

        _, new_score = add_points(interaction.guild.id, house, points, target_member.id, interaction.user.id, reason)
        emoji = HOUSE_ROLES.get(house, "✨")

        embed = make_embed("✨ تم تسجيل النقاط بنجاح", "", COLORS["success"])
        embed.add_field(name="🧙 الساحر", value=target_member.mention, inline=True)
        embed.add_field(name="🏠 المنزل", value=f"{emoji} **{house}**", inline=True)
        embed.add_field(name="⭐ النقاط المضافة", value=f"**+{points:,}**", inline=True)
        embed.add_field(name="📝 السبب", value=reason, inline=False)
        embed.add_field(name="🏆 رصيد المنزل الجديد", value=f"**{new_score:,} نقطة**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="إضافة-نقاط", description="فتح استمارة إضافة النقاط للساحر عبر الـ ID")
async def slash_add_points_form(interaction: discord.Interaction):
    if not can_manage_cup(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية لإدارة كأس المنازل.", ephemeral=True)
    await interaction.response.send_modal(AddPointsModal())


class HousePointsModal(discord.ui.Modal, title="✨ نقاط البيت المباشرة"):
    house_input = discord.ui.TextInput(label="اسم المنزل", placeholder="جريفندور، سليذرين، رافنكلو، هافلباف", required=True)
    points_input = discord.ui.TextInput(label="عدد النقاط", placeholder="مثال: 50", required=True)
    operation_input = discord.ui.TextInput(label="نوع العملية", placeholder="اكتب: إضافة أو خصم", required=True)
    reason_input = discord.ui.TextInput(label="السبب", placeholder="مسابقة Quidditch", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        selected_house = normalize_house(self.house_input.value)
        if not selected_house:
            return await interaction.response.send_message(embed=make_embed("❌ خطأ", "اسم المنزل غير صحيح.", COLORS["danger"]), ephemeral=True)

        try:
            points = int(self.points_input.value.strip())
            if points <= 0: raise ValueError()
        except ValueError:
            return await interaction.response.send_message(embed=make_embed("❌ خطأ", "عدد النقاط يجب أن يكون رقماً صحيحاً.", COLORS["danger"]), ephemeral=True)

        op_text = self.operation_input.value.strip().lower()
        if "خصم" in op_text or "-" in op_text:
            final_points = -points
            embed_title = "⚠️ تم خصم النقاط من البيت"
            embed_color = COLORS["danger"]
        else:
            final_points = points
            embed_title = "✨ تم إضافة النقاط للبيت بنجاح"
            embed_color = COLORS["success"]

        _, new_score = add_points(interaction.guild.id, selected_house, final_points, None, interaction.user.id, self.reason_input.value.strip())
        emoji = HOUSE_ROLES.get(selected_house, "✨")

        embed = make_embed(embed_title, "", embed_color)
        embed.add_field(name="🏠 المنزل المستهدف", value=f"{emoji} **{selected_house}**", inline=True)
        embed.add_field(name="⭐ النقاط", value=f"**{final_points:+,}**", inline=True)
        embed.add_field(name="📝 السبب", value=self.reason_input.value.strip(), inline=False)
        embed.add_field(name="🏆 رصيد المنزل الحالي", value=f"**{new_score:,} نقطة**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="نقاط_البيت", description="إضافة أو خصم نقاط للبيت ككل مباشرة")
async def slash_house_points(interaction: discord.Interaction):
    if not can_manage_cup(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية لإدارة كأس المنازل.", ephemeral=True)
    await interaction.response.send_modal(HousePointsModal())


# =========================================================
# ترتيب الطلاب (/ترتيب_الطلاب) بالـ Mentions الحقيقية
# =========================================================

@bot.tree.command(name="ترتيب_الطلاب", description="عرض لوحة شرف الطلاب الأعلى نقاطاً بالـ Mentions الحقيقية")
async def slash_students_leaderboard(interaction: discord.Interaction):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, house, SUM(amount) as total_points
        FROM point_logs
        WHERE guild_id = ? AND user_id IS NOT NULL AND undone = 0 AND amount > 0
        GROUP BY user_id
        ORDER BY total_points DESC
        LIMIT 10
    """, (interaction.guild.id,))
    rows = cur.fetchall()
    conn.close()

    embed = make_embed("🌟 لوحة شرف السحرة الأبطال", "أعلى الطلاب جمعاً للنقاط في السيرفر", COLORS["gold"])
    if not rows:
        embed.description = "لا توجد أي نقاط مسجلة بأسماء طلاب حتى الآن."
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for index, row in enumerate(rows):
            medal = medals[index] if index < len(medals) else f"{index + 1}️⃣"
            emoji = HOUSE_ROLES.get(row["house"], "✨")
            embed.add_field(
                name=f"{medal} الساحر: <@{row['user_id']}>",
                value=f"🏠 المنزل: {emoji} **{row['house']}** | ⭐ **{row['total_points']:,} نقطة**",
                inline=False
            )
    await interaction.response.send_message(embed=embed)


# =========================================================
# قبعة التنسيق التفاعلية (4 أسئلة متسلسلة بأمان تام)
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
        self.is_finished = False
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
        self.load_current_question_buttons()

    def load_current_question_buttons(self):
        self.clear_items()
        if self.current_question < len(self.questions):
            for text, house in self.questions[self.current_question]["options"]:
                self.add_item(QuizOptionButton(text, house))

class QuizOptionButton(discord.ui.Button):
    def __init__(self, label, house):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.house = house

    async def callback(self, interaction: discord.Interaction):
        view: SortingHatQuizView = self.view
        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("❌ هذه ليست قبعتك!", ephemeral=True)
        if view.is_finished: return

        view.scores[self.house] += 1
        view.current_question += 1

        if view.current_question < len(view.questions):
            view.load_current_question_buttons()
            q_data = view.questions[view.current_question]
            embed = make_embed("🎩 اختبار قبعة التنسيق", f"**{q_data['q']}**", COLORS["gold"])
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            view.is_finished = True
            winning_house = max(view.scores, key=view.scores.get)
            assign_student_house(view.user.id, view.user.name, winning_house, view.guild_id)
            info = HOUSES[winning_house]
            
            final_embed = make_embed(
                "✨ القرار النهائي لقبعة التنسيق",
                f"🧙 **الساحر:** {view.user.mention}\n\n{info['emoji']} **البيت:**\n## {info['name']}\n\n*{info['desc']}*\n\n📜 تم تسجيل اسمك رسمياً بالـ ID في سجلات البيت.",
                info["color"]
            )
            for child in view.children: child.disabled = True
            await interaction.response.edit_message(embed=final_embed, view=None)
            view.stop()

@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):
    if student_already_sorted(ctx.guild.id, ctx.author.id):
        return await ctx.send(embed=make_embed("⚠️ عذراً", "لقد تم اختيار منزلك مسبقاً!", COLORS["danger"]), delete_after=10)

    view = SortingHatQuizView(ctx.author, ctx.guild.id)
    first_q_text = view.questions[0]["q"]
    embed = make_embed("🎩 قبعة التنسيق", f"*تستقر القبعة على رأسك وتهمس بأسئلتها الأربعة...*\n\n**{first_q_text}**", COLORS["gold"])
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg


# =========================================================
# نظام المبارزات والتعويذات (نظام المانا المحدث 100)
# =========================================================

# =========================================================
# نظام المبارزات والتعويذات المتكامل (كامل ونظيف)
# =========================================================

SPELLS = {
    "Expelliarmus": {"cost": 15, "damage": 25, "heal": 0, "desc": "تعويذة تجريد الخصم من سلاحه بضربة خاطفة."},
    "Stupefy": {"cost": 20, "damage": 35, "heal": 0, "desc": "تعويذة الإقعاد لتخدير الخصم وإلحاق ضرر كبير."},
    "Confringo": {"cost": 30, "damage": 50, "heal": 0, "desc": "لعنة الانفجار الكبرى، ضرر هائل بتكلفة مانا عالية."},
    "Protego": {"cost": 10, "damage": 0, "heal": 15, "desc": "درع سحري يمتص الضرر ويمنح استشفاء خفيفاً."},
    "Episkey": {"cost": 25, "damage": 0, "heal": 40, "desc": "تعويذة علاجية لترميم الجروح العميقة ورفع نقاط الـ HP."},
    "Incendio": {"cost": 20, "damage": 30, "heal": 0, "desc": "ألسنة لهب سحرية تحرق ساحة المعركة."},
}

class DuelSpellSelect(discord.ui.Select):
    def __init__(self, duel_session, player_id):
        self.duel_session = duel_session
        self.player_id = player_id
        options = [discord.SelectOption(label=name, description=data["desc"], emoji="🪄") for name, data in SPELLS.items()]
        super().__init__(placeholder="اختر تعويذتك السحرية لهذه الجولة...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("❌ هذه ليست مبارزتك!", ephemeral=True)
        
        spell_name = self.values[0]
        spell = SPELLS[spell_name]
        session = self.duel_session

        if interaction.user.id == session.p1.id:
            if session.p1_mana < spell["cost"]:
                return await interaction.response.send_message("❌ مانتك غير كافية لهذه التعويذة!", ephemeral=True)
            session.p1_choice = spell_name
        else:
            if session.p2_mana < spell["cost"]:
                return await interaction.response.send_message("❌ مانتك غير كافية لهذه التعويذة!", ephemeral=True)
            session.p2_choice = spell_name

        await interaction.response.send_message(f"✨ لقد اخترت: **{spell_name}** بنجاح!", ephemeral=True)
        
        if session.p1_choice and session.p2_choice:
            await session.process_round(interaction)

class DuelView(discord.ui.View):
    def __init__(self, duel_session):
        super().__init__(timeout=60)
        self.duel_session = duel_session
        self.add_item(DuelSpellSelect(duel_session, duel_session.p1.id))
        self.add_item(DuelSpellSelect(duel_session, duel_session.p2.id))

class DuelSession:
    def __init__(self, p1, p2, guild_id):
        self.p1 = p1
        self.p2 = p2
        self.guild_id = guild_id
        self.p1_hp = MAX_HP
        self.p2_hp = MAX_HP
        self.p1_mana = MAX_MP
        self.p2_mana = MAX_MP
        self.p1_choice = None
        self.p2_choice = None
        self.round_count = 0

    async def process_round(self, interaction):
        self.round_count += 1
        s1 = SPELLS[self.p1_choice]
        s2 = SPELLS[self.p2_choice]

        self.p1_mana = min(MAX_MP, self.p1_mana - s1["cost"] + 20)
        self.p2_mana = min(MAX_MP, self.p2_mana - s2["cost"] + 20)

        p1_net_damage = max(0, s1["damage"] - s2["heal"])
        p2_net_damage = max(0, s2["damage"] - s1["heal"])

        self.p2_hp = max(0, self.p2_hp - p1_net_damage + s1["heal"])
        self.p1_hp = max(0, self.p1_hp - p2_net_damage + s2["heal"])

        result_desc = (
            f"⚔️ **نتيجة الجولة #{self.round_count}:**\n\n"
            f"🧙 {self.p1.mention} استخدم **{self.p1_choice}** (ضرر: {s1['damage']} | علاج: {s1['heal']})\n"
            f"🧙 {self.p2.mention} استخدم **{self.p2_choice}** (ضرر: {s2['damage']} | علاج: {s2['heal']})\n\n"
            f"❤️ **{self.p1.name}:** HP: {self.p1_hp}/{MAX_HP} | Mana: {self.p1_mana}/{MAX_MP}\n"
            f"❤️ **{self.p2.name}:** HP: {self.p2_hp}/{MAX_HP} | Mana: {self.p2_mana}/{MAX_MP}"
        )

        self.p1_choice = None
        self.p2_choice = None

        if self.p1_hp <= 0 or self.p2_hp <= 0:
            winner = self.p1 if self.p2_hp <= 0 else self.p2
            loser = self.p2 if winner == self.p1 else self.p1
            
            self.save_duel_record(winner.id, loser.id)

            win_embed = make_embed(
                "🏆 انتهت المبارزة السحرية!",
                f"{result_desc}\n\n🎉 **الفائز المنتصر:** {winner.mention} 🪄\n💀 **الخاسر الشجاع:** {loser.mention}",
                COLORS["gold"]
            )
            await interaction.message.edit(embed=win_embed, view=None)
            if self.p1.id in active_duels: del active_duels[self.p1.id]
            if self.p2.id in active_duels: del active_duels[self.p2.id]
        else:
            embed = make_embed("⚔️ ساحة المبارزات السحرية", result_desc, COLORS["blue"])
            view = DuelView(self)
            await interaction.message.edit(embed=embed, view=view)

    def save_duel_record(self, winner_id, loser_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO duel_logs (guild_id, player1_id, player2_id, winner_id, loser_id, p1_hp, p2_hp, rounds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.guild_id, self.p1.id, self.p2.id, winner_id, loser_id, self.p1_hp, self.p2_hp, self.round_count, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
        
        for uid in [self.p1.id, self.p2.id]:
            cur.execute("""
                INSERT INTO duel_stats (guild_id, user_id, wins, losses, draws)
                VALUES (?, ?, 0, 0, 0)
                ON CONFLICT(guild_id, user_id) DO NOTHING
            """, (self.guild_id, uid))

        cur.execute("UPDATE duel_stats SET wins = wins + 1 WHERE guild_id = ? AND user_id = ?", (self.guild_id, winner_id))
        cur.execute("UPDATE duel_stats SET losses = losses + 1 WHERE guild_id = ? AND user_id = ?", (self.guild_id, loser_id))
        conn.commit()
        conn.close()

@bot.tree.command(name="مبارزة", description="تحدي ساحر آخر في مبارزة سحرية")
@app_commands.describe(opponent="الساحر الخصم الذي تريد مبارزته")
async def slash_duel(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.id == interaction.user.id:
        return await interaction.response.send_message("❌ لا يمكنك مبارزة نفسك!", ephemeral=True)
    if opponent.bot:
        return await interaction.response.send_message("❌ لا يمكنك مبارزة بوت سحري!", ephemeral=True)
    if interaction.user.id in active_duels or opponent.id in active_duels:
        return await interaction.response.send_message("❌ أحد الساحرين منشغل في مبارزة أخرى حالياً!", ephemeral=True)

    session = DuelSession(interaction.user, opponent, interaction.guild.id)
    active_duels[interaction.user.id] = session
    active_duels[opponent.id] = session

    embed = make_embed(
        "⚔️ تحدي مبارزة سحرية جديدة!",
        f"🧙 **المتحدي:** {interaction.user.mention}\n🧙 **الخصم:** {opponent.mention}\n\nاختر تعويذتك الأولى من القائمة أدناه!",
        COLORS["gold"]
    )
    view = DuelView(session)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="ترتيب_المبارزين", description="عرض لوحة شرف أفضل المبارزين في السيرفر")
async def slash_dueler_leaderboard(interaction: discord.Interaction):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, wins, losses, (wins + losses) as total
        FROM duel_stats
        WHERE guild_id = ?
        ORDER BY wins DESC
        LIMIT 10
    """, (interaction.guild.id,))
    rows = cur.fetchall()
    conn.close()

    embed = make_embed("🏆 لوحة شرف المبارزين الأبطال", "ترتيب السحرة الأقوى في المبارزات", COLORS["gold"])
    if not rows:
        embed.description = "لا توجد أي مبارزات مسجلة حتى الآن."
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for index, row in enumerate(rows):
            medal = medals[index] if index < len(medals) else f"{index + 1}️⃣"
            embed.add_field(
                name=f"{medal} الساحر: <@{row['user_id']}>",
                value=f"🏆 انتصارات: **{row['wins']}** | 💀 خسائر: **{row['losses']}** | ⚔️ إجمالي: **{row['total']}**",
                inline=False
            )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="تعويذة", description="استعراض قائمة التعويذات السحرية وتفاصيلها المعتمدة")
async def slash_spells_list(interaction: discord.Interaction):
    embed = make_embed("🪄 سجل التعويذات السحرية المعتمدة", "قائمة التعويذات المتاحة للاستخدام في المبارزات", COLORS["magic"])
    for name, data in SPELLS.items():
        embed.add_field(
            name=f"✨ {name}",
            value=f"🔮 تكلفة المانا: **{data['cost']}** | ⚡ الضرر: **{data['damage']}** | 💖 العلاج: **{data['heal']}**\n📝 *{data['desc']}*",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)



# =========================================================
# نظام الفعاليات المتكامل (إنشاء وعرض بصفحات آمنة)
# =========================================================

class AddEventModal(discord.ui.Modal, title="✨ إنشاء فعالية سحرية جديدة"):
    title_input = discord.ui.TextInput(label="اسم الفعالية", placeholder="مثال: بطولة الثلاثة معالجة", required=True)
    date_input = discord.ui.TextInput(label="موعد الفعالية", placeholder="مثال: الجمعة القادمة 9 مساءً", required=True)
    points_input = discord.ui.TextInput(label="النقاط المرصودة", placeholder="مثال: 150", required=True)
    desc_input = discord.ui.TextInput(label="تفاصيل الفعالية", placeholder="شرح مبسط عن تفاصيل الفعالية...", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        title = self.title_input.value.strip()
        date = self.date_input.value.strip()
        points_str = self.points_input.value.strip()
        desc = self.desc_input.value.strip()

        try:
            points = int(points_str)
        except ValueError:
            return await interaction.response.send_message("❌ عدد النقاط يجب أن يكون رقماً صحيحاً.", ephemeral=True)

        events_data = load_json_file(EVENTS_FILE)
        if not isinstance(events_data, dict):
            events_data = {}

        event_id = str(len(events_data) + 1)
        events_data[event_id] = {
            "title": title,
            "date": date,
            "points": points,
            "description": desc,
            "user_id": interaction.user.id,
            "organizer": interaction.user.name
        }

        save_json_file(EVENTS_FILE, events_data)

        embed = make_embed("✨ تم إنشاء وتسجيل الفعالية بنجاح", "", COLORS["success"])
        embed.add_field(name="🪄 الفعالية", value=title, inline=True)
        embed.add_field(name="👤 المنظم", value=interaction.user.mention, inline=True)
        embed.add_field(name="⭐ النقاط", value=f"**{points:,}**", inline=True)
        embed.add_field(name="📅 الموعد", value=date, inline=False)
        embed.add_field(name="📝 التفاصيل", value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="إضافة_فعالية", description="فتح استمارة لإنشاء وتسجيل فعالية جديدة في سجل السحر")
async def slash_add_event(interaction: discord.Interaction):
    if not can_manage_cup(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية لإنشاء الفعاليات.", ephemeral=True)
    await interaction.response.send_modal(AddEventModal())

class EventsPaginationView(discord.ui.View):
    def __init__(self, events_list, author_id):
        super().__init__(timeout=180)
        self.events_list = events_list
        self.author_id = author_id
        self.current_page = 0
        self.per_page = 3
        self.max_pages = max(1, (len(events_list) + self.per_page - 1) // self.per_page)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1

    def create_embed(self):
        embed = make_embed(
            "📚 السجل الرسمي للفعاليات السحرية",
            f"صفحة **{self.current_page + 1}** من **{self.max_pages}**",
            COLORS["blue"]
        )
        if not self.events_list:
            embed.description = "❌ لا توجد أي فعاليات مسجلة في السجلات حالياً. استخدم `/إضافة_فعالية` لإنشاء واحدة!"
            return embed

        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.events_list[start:end]

        for item in page_items:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "فعالية سحرية")
            user_id = item.get("user_id")
            user_mention = f"<@{user_id}>" if user_id else item.get("organizer", "مجهول")
            date = item.get("date", "غير محدد")
            desc = item.get("description", "لا توجد تفاصيل.")
            points = item.get("points", 0)
            
            embed.add_field(
                name=f"🪄 {title} (⭐ {points:,} نقطة)",
                value=f"👤 المنظم: {user_mention}\n📅 الموعد: {date}\n📝 التفاصيل: {desc}",
                inline=False
            )
        return embed

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ هذه الأزرار ليست لك.", ephemeral=True)
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶️ التالي", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ هذه الأزرار ليست لك.", ephemeral=True)
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

@bot.tree.command(name="سجل_الفعاليات", description="عرض سجل فعاليات كأس المنازل بنظام الصفحات الآمن")
async def slash_events_log(interaction: discord.Interaction):
    try:
        raw_data = load_json_file(EVENTS_FILE)
        events_list = list(raw_data.values()) if isinstance(raw_data, dict) else (raw_data if isinstance(raw_data, list) else [])
        view = EventsPaginationView(events_list, interaction.user.id)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ أثناء عرض السجل: {e}", ephemeral=True)


# =========================================================
# نظام الغارات والمستشفى (Raid & Hospital)
# =========================================================

@bot.command(name="غارة")
async def raid_command(ctx):
    global raid_active, current_hp
    if not can_manage_cup(ctx.author):
        return await ctx.send(embed=make_embed("❌ خطأ", "ليس لديك صلاحية لبدء غارة سحرية.", COLORS["danger"]), delete_after=10)
    
    raid_active = True
    current_hp = MAX_HP
    embed = make_embed(
        "🚨 بدأت غارة سحرية مرعبة!",
        f"المخلوق الشرير ظهر في القناة! استخدموا تعويذات الهجوم للقضاء عليه.\n❤️ **HP الوحش:** {current_hp}/{MAX_HP}",
        COLORS["danger"]
    )
    await ctx.send(embed=embed)

@bot.command(name="هجوم")
async def attack_command(ctx):
    global raid_active, current_hp
    if not raid_active:
        return await ctx.send(embed=make_embed("⚠️ تنبيه", "لا توجد غارة نشطة حالياً!", COLORS["gold"]), delete_after=10)
    
    if ctx.author.id in hospital_patients:
        return await ctx.send(embed=make_embed("🏥 المستشفى", f"{ctx.author.mention} أنت في مستشفى سان مونجو ولا يمكنك القتال حالياً!", COLORS["danger"]), delete_after=10)

    current_hp = max(0, current_hp - DAMAGE_PER_HIT)
    embed = make_embed(
        "⚡ هجوم ناجح!",
        f"الساحر {ctx.author.mention} هاجم الوحش وألحق به **{DAMAGE_PER_HIT}** ضرراً!\n❤️ **HP الوحش المتبقي:** {current_hp}/{MAX_HP}",
        COLORS["success"]
    )
    if current_hp <= 0:
        raid_active = False
        embed.title = "🏆 انتصار ساحق!"
        embed.description = f"🎉 لقد تم القضاء على الوحش الشرير بنجاح بفضل شجاعة السحرة!"
    await ctx.send(embed=embed)


# =========================================================
# التشغيل النهائي للبوت
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
        print("⚠️ خطأ: لم يتم العثور على توكن البوت في الـ Environment Variables!")
    else:
        bot.run(token)
