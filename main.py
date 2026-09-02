import discord
from discord.ext import commands
from discord import app_commands
import random
import os
import json
import sqlite3
from datetime import datetime


# =========================================================
# 🪄 إعدادات البوت
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


# =========================================================
# 🎨 الألوان
# =========================================================

COLORS = {
    "magic": 0x2B1338,
    "gold": 0xD4AF37,
    "danger": 0x6E0B14,
    "success": 0x1E5631,
    "blue": 0x162A4A,
    "dark": 0x15121C,
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


# =========================================================
# 🏠 كأس المنازل
# =========================================================

HOUSE_ROLES = {
    "جريفندور": "🦁",
    "هافلباف": "🦡",
    "رافنكلو": "🦅",
    "سليذرين": "🐍",
}

HOUSE_ALIASES = {
    "جريفندور": "جريفندور",
    "gryffindor": "جريفندور",

    "هافلباف": "هافلباف",
    "hufflepuff": "هافلباف",

    "رافنكلو": "رافنكلو",
    "رافينكلو": "رافنكلو",
    "ravenclaw": "رافنكلو",

    "سليذرين": "سليذرين",
    "slytherin": "سليذرين",
}


HOUSES = {
    "جريفندور": {
        "name": "جريفندور (Gryffindor)",
        "emoji": "🦁",
        "color": 0x740909,
        "desc": "الجرأة والشجاعة والفروسية."
    },

    "سليذرين": {
        "name": "سليذرين (Slytherin)",
        "emoji": "🐍",
        "color": 0x1A472A,
        "desc": "الطموح والدهاء والقيادة."
    },

    "رافنكلو": {
        "name": "رافنكلو (Ravenclaw)",
        "emoji": "🦅",
        "color": 0x0E1A40,
        "desc": "الحكمة والذكاء والإبداع."
    },

    "هافلباف": {
        "name": "هافلباف (Hufflepuff)",
        "emoji": "🦡",
        "color": 0xECB939,
        "desc": "الإخلاص والعدالة والعمل الجاد."
    }
}


# =========================================================
# 🗄️ قاعدة البيانات
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
            INSERT OR IGNORE INTO house_scores
            (guild_id, house, points)
            VALUES (?, ?, 0)
        """, (guild_id, house))

    conn.commit()
    conn.close()


def can_manage_cup(member: discord.Member):
    if member.guild_permissions.administrator:
        return True

    allowed_roles = {
        "مدير الكأس",
        "مشرف الكأس",
        "House Cup",
        "Cup Manager"
    }

    return any(
        role.name in allowed_roles
        for role in member.roles
    )


def normalize_house(name):
    if not name:
        return None

    return HOUSE_ALIASES.get(
        name.strip().lower()
    )


def house_from_database(
    guild_id: int,
    user_id: int
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT house
        FROM members_houses
        WHERE guild_id = ? AND user_id = ?
    """, (
        guild_id,
        user_id
    ))

    row = cur.fetchone()
    conn.close()

    return row["house"] if row else None


def add_points(
    guild_id: int,
    house: str,
    amount: int,
    user_id,
    moderator_id: int,
    reason: str
):
    ensure_guild(guild_id)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE house_scores
        SET points = points + ?
        WHERE guild_id = ? AND house = ?
    """, (
        amount,
        guild_id,
        house
    ))

    cur.execute("""
        INSERT INTO point_logs
        (
            guild_id,
            house,
            amount,
            user_id,
            moderator_id,
            reason,
            created_at,
            undone
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (
        guild_id,
        house,
        amount,
        user_id,
        moderator_id,
        reason,
        datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    log_id = cur.lastrowid

    cur.execute("""
        SELECT points
        FROM house_scores
        WHERE guild_id = ? AND house = ?
    """, (
        guild_id,
        house
    ))

    row = cur.fetchone()
    new_points = row["points"]

    conn.commit()
    conn.close()

    return log_id, new_points


def undo_last_action(guild_id: int):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM point_logs
        WHERE guild_id = ?
        AND undone = 0
        ORDER BY id DESC
        LIMIT 1
    """, (guild_id,))

    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    cur.execute("""
        UPDATE house_scores
        SET points = points - ?
        WHERE guild_id = ?
        AND house = ?
    """, (
        row["amount"],
        guild_id,
        row["house"]
    ))

    cur.execute("""
        UPDATE point_logs
        SET undone = 1
        WHERE id = ?
    """, (row["id"],))

    conn.commit()
    conn.close()

    return row


def get_scores(guild_id: int):

    ensure_guild(guild_id)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT house, points
        FROM house_scores
        WHERE guild_id = ?
        ORDER BY points DESC
    """, (guild_id,))

    rows = cur.fetchall()

    conn.close()

    return rows


def create_cup_embed(guild: discord.Guild):

    rows = get_scores(guild.id)

    medals = [
        "🥇",
        "🥈",
        "🥉",
        "4️⃣"
    ]

    embed = discord.Embed(
        title="🏆 كأس المنازل",
        description=(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✨ **ترتيب المنازل الحالي**\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        color=COLORS["gold"]
    )

    for index, row in enumerate(rows):

        house = row["house"]
        points = row["points"]

        emoji = HOUSE_ROLES.get(
            house,
            "✨"
        )

        medal = (
            medals[index]
            if index < len(medals)
            else f"{index + 1}️⃣"
        )

        embed.add_field(
            name=f"{medal} {emoji} {house}",
            value=f"⭐ **{points:,} نقطة**",
            inline=False
        )

    embed.set_footer(
        text=AUTHOR_SIGNATURE
    )

    return embed


# =========================================================
# 📁 JSON
# =========================================================

def load_json_file(filename):

    if not os.path.exists(filename):
        return {}

    try:

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        return data

    except Exception as e:

        print(
            f"JSON load error ({filename}): {e}"
        )

        return {}


def save_json_file(
    filename,
    data
):

    try:

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )

        return True

    except Exception as e:

        print(
            f"JSON save error ({filename}): {e}"
        )

        return False


# =========================================================
# 🎩 تسجيل الطلاب
# =========================================================

def assign_student_house(
    user_id,
    username,
    house_name,
    guild_id=None
):

    db = load_json_file(
        STUDENTS_FILE
    )

    if not isinstance(db, dict):
        db = {}

    db[str(user_id)] = {
        "name": username,
        "house": house_name
    }

    save_json_file(
        STUDENTS_FILE,
        db
    )

    if guild_id:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO members_houses
            (guild_id, user_id, house)
            VALUES (?, ?, ?)

            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET
            house = excluded.house
        """, (
            guild_id,
            user_id,
            house_name
        ))

        conn.commit()
        conn.close()


def student_already_sorted(
    guild_id: int,
    user_id: int
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT house
        FROM members_houses
        WHERE guild_id = ?
        AND user_id = ?
    """, (
        guild_id,
        user_id
    ))

    row = cur.fetchone()

    conn.close()

    if row:
        return True

    students_db = load_json_file(
        STUDENTS_FILE
    )

    if not isinstance(
        students_db,
        dict
    ):
        return False

    return str(user_id) in students_db


# =========================================================
# 🎩 قبعة التنسيق
# =========================================================

class SortingHatView(
    discord.ui.View
):

    def __init__(
        self,
        user,
        guild_id
    ):

        super().__init__(
            timeout=120
        )

        self.user = user
        self.guild_id = guild_id

        self.current_question = 0

        self.scores = {
            "جريفندور": 0,
            "سليذرين": 0,
            "رافنكلو": 0,
            "هافلباف": 0
        }

        self.finished = False

        self.questions = [

            {
                "q": "ما الصفة التي تريد أن يُذكر بها اسمك؟",
                "options": [
                    ("🦁 الشجاعة والبسالة", "جريفندور"),
                    ("🐍 الطموح وتحقيق الأهداف", "سليذرين"),
                    ("🦅 الحكمة والمعرفة", "رافنكلو"),
                    ("🦡 العدالة ومساعدة الآخرين", "هافلباف")
                ]
            },

            {
                "q": "أمامك باب غامض لا تعرف ما خلفه، ماذا تفعل؟",
                "options": [
                    ("🦁 أفتحه دون تردد", "جريفندور"),
                    ("🐍 أبحث عن أفضل طريقة لاستغلاله", "سليذرين"),
                    ("🦅 أحاول حل اللغز أولاً", "رافنكلو"),
                    ("🦡 أتأكد أنه لن يؤذي أحداً", "هافلباف")
                ]
            },

            {
                "q": "ما الشيء الذي ترفضه أكثر؟",
                "options": [
                    ("🦁 الجبن", "جريفندور"),
                    ("🐍 انعدام الطموح", "سليذرين"),
                    ("🦅 الجهل", "رافنكلو"),
                    ("🦡 الظلم", "هافلباف")
                ]
            },

            {
                "q": "أين تفضل قضاء وقت فراغك؟",
                "options": [
                    ("🦁 في المغامرات والتحديات", "جريفندور"),
                    ("🐍 في التخطيط لمستقبلي", "سليذرين"),
                    ("🦅 بين الكتب والمكتبة", "رافنكلو"),
                    ("🦡 مع الأصدقاء في مكان هادئ", "هافلباف")
                ]
            }
        ]

        self.update_buttons()


    def update_buttons(self):

        self.clear_items()

        question = self.questions[
            self.current_question
        ]

        for text, house in question["options"]:

            self.add_item(
                SortingOptionButton(
                    text,
                    house
                )
            )


    def create_question_embed(self):

        question = self.questions[
            self.current_question
        ]

        progress = (
            self.current_question + 1
        )

        return make_embed(
            "🎩 قبعة التنسيق",
            (
                f"### السؤال {progress}/4\n\n"
                f"**{question['q']}**\n\n"
                "اختر الإجابة التي تشبهك أكثر."
            ),
            0x8B5A2B
        )


class SortingOptionButton(
    discord.ui.Button
):

    def __init__(
        self,
        label,
        house
    ):

        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary
        )

        self.house = house


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        view: SortingHatView = self.view

        if interaction.user.id != view.user.id:

            return await interaction.response.send_message(
                "❌ هذه ليست قبعة التنسيق الخاصة بك!",
                ephemeral=True
            )

        if view.finished:
            return

        view.scores[
            self.house
        ] += 1

        view.current_question += 1

        if view.current_question < len(
            view.questions
        ):

            view.update_buttons()

            return await interaction.response.edit_message(
                embed=view.create_question_embed(),
                view=view
            )

        # -----------------------------------------
        # النهاية
        # -----------------------------------------

        view.finished = True

        highest_score = max(
            view.scores.values()
        )

        tied_houses = [
            house
            for house, score in view.scores.items()
            if score == highest_score
        ]

        winning_house = random.choice(
            tied_houses
        )

        assign_student_house(
            view.user.id,
            view.user.name,
            winning_house,
            view.guild_id
        )

        info = HOUSES[
            winning_house
        ]

        final_embed = make_embed(
            "✨ القرار النهائي لقبعة التنسيق",
            (
                f"🧙 **الساحر:** {view.user.mention}\n\n"
                f"{info['emoji']} **البيت:**\n"
                f"## {info['name']}\n\n"
                f"*{info['desc']}*\n\n"
                "📜 تم تسجيل اسمك رسمياً في سجلات البيت."
            ),
            info["color"]
        )

        await interaction.response.edit_message(
            embed=final_embed,
            view=None
        )

        view.stop()


@bot.command(
    name="قبعة-التنسيق"
)
async def sorting_hat(ctx):

    if not ctx.guild:
        return

    if student_already_sorted(
        ctx.guild.id,
        ctx.author.id
    ):

        return await ctx.send(
            embed=make_embed(
                "⚠️ عذراً",
                "لقد تم اختيار منزلك مسبقاً!",
                COLORS["danger"]
            ),
            delete_after=10
        )

    view = SortingHatView(
        ctx.author,
        ctx.guild.id
    )

    embed = make_embed(
        "🎩 قبعة التنسيق",
        (
            "تقترب القبعة القديمة منك...\n\n"
            "✨ **اضغط الزر التالي لبدء اختبار التنسيق.**\n\n"
            "لن يتم تسجيل أي منزل قبل الانتهاء من الأسئلة الأربعة."
        ),
        0x8B5A2B
    )

    view.clear_items()

    view.add_item(
        StartSortingButton()
    )

    await ctx.send(
        embed=embed,
        view=view
    )


class StartSortingButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="🎩 ابدأ اختبار التنسيق",
            style=discord.ButtonStyle.primary
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        view: SortingHatView = self.view

        if interaction.user.id != view.user.id:

            return await interaction.response.send_message(
                "❌ هذا الاختبار ليس لك!",
                ephemeral=True
            )

        view.update_buttons()

        await interaction.response.edit_message(
            embed=view.create_question_embed(),
            view=view
        )


# =========================================================
# ⭐ إضافة نقاط طالب
# =========================================================

class AddPointsModal(
    discord.ui.Modal,
    title="✨ استمارة إضافة النقاط"
):

    student_input = discord.ui.TextInput(
        label="آي دي الساحر",
        placeholder="مثال: 84920391820",
        style=discord.TextStyle.short,
        required=True
    )

    points_input = discord.ui.TextInput(
        label="عدد النقاط",
        placeholder="مثال: 50",
        style=discord.TextStyle.short,
        required=True
    )

    reason_input = discord.ui.TextInput(
        label="سبب إضافة النقاط",
        placeholder="مثال: الفوز في مسابقة",
        style=discord.TextStyle.paragraph,
        required=True
    )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        student_text = self.student_input.value.strip()
        points_text = self.points_input.value.strip()
        reason = self.reason_input.value.strip()

        cleaned_id = "".join(
            filter(
                str.isdigit,
                student_text
            )
        )

        target_member = None

        if cleaned_id.isdigit():

            target_member = interaction.guild.get_member(
                int(cleaned_id)
            )

            if not target_member:

                try:
                    target_member = await interaction.guild.fetch_member(
                        int(cleaned_id)
                    )
                except Exception:
                    pass

        if not target_member:

            return await interaction.response.send_message(
                "❌ لم أتمكن من العثور على الساحر!",
                ephemeral=True
            )

        try:

            points = int(points_text)

            if points <= 0:
                raise ValueError

        except ValueError:

            return await interaction.response.send_message(
                "❌ عدد النقاط يجب أن يكون رقماً صحيحاً أكبر من صفر.",
                ephemeral=True
            )

        house = house_from_database(
            interaction.guild.id,
            target_member.id
        )

        if not house:

            students_db = load_json_file(
                STUDENTS_FILE
            )

            if isinstance(
                students_db,
                dict
            ):

                user_data = students_db.get(
                    str(target_member.id)
                )

                if user_data:
                    house = user_data.get(
                        "house"
                    )

        if not house:

            return await interaction.response.send_message(
                f"❌ {target_member.mention} لم يتم تنصيبه في منزل بعد!",
                ephemeral=True
            )

        log_id, new_score = add_points(
            interaction.guild.id,
            house,
            points,
            target_member.id,
            interaction.user.id,
            reason
        )

        emoji = HOUSE_ROLES.get(
            house,
            "✨"
        )

        embed = make_embed(
            "✨ تم تسجيل النقاط بنجاح",
            (
                f"🧙 **الساحر:** {target_member.mention}\n"
                f"🏠 **المنزل:** {emoji} {house}\n"
                f"⭐ **النقاط:** +{points:,}\n"
                f"📝 **السبب:** {reason}\n\n"
                f"🏆 **رصيد المنزل:** {new_score:,} نقطة"
            ),
            COLORS["success"]
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


@bot.tree.command(
    name="إضافة-نقاط",
    description="فتح استمارة إضافة نقاط لطالب"
)
async def slash_add_points_form(
    interaction: discord.Interaction
):

    if not can_manage_cup(
        interaction.user
    ):

        return await interaction.response.send_message(
            "❌ ليس لديك صلاحية لإدارة كأس المنازل.",
            ephemeral=True
        )

    await interaction.response.send_modal(
        AddPointsModal()
    )


# =========================================================
# 🏠 نقاط البيت
# =========================================================

class HousePointsModal(
    discord.ui.Modal,
    title="✨ نقاط البيت المباشرة"
):

    house_input = discord.ui.TextInput(
        label="اسم المنزل",
        placeholder="جريفندور، سليذرين، رافنكلو، هافلباف",
        style=discord.TextStyle.short,
        required=True
    )

    points_input = discord.ui.TextInput(
        label="عدد النقاط",
        placeholder="مثال: 50",
        style=discord.TextStyle.short,
        required=True
    )

    operation_input = discord.ui.TextInput(
        label="نوع العملية",
        placeholder="إضافة أو خصم",
        style=discord.TextStyle.short,
        required=True
    )

    reason_input = discord.ui.TextInput(
        label="السبب",
        placeholder="سبب العملية",
        style=discord.TextStyle.paragraph,
        required=True
    )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        selected_house = normalize_house(
            self.house_input.value
        )

        if not selected_house:

            return await interaction.response.send_message(
                "❌ اسم المنزل غير صحيح!",
                ephemeral=True
            )

        try:

            points = int(
                self.points_input.value
            )

            if points <= 0:
                raise ValueError

        except ValueError:

            return await interaction.response.send_message(
                "❌ عدد النقاط غير صحيح.",
                ephemeral=True
            )

        operation = (
            self.operation_input.value
            .strip()
            .lower()
        )

        reason = (
            self.reason_input.value
            .strip()
        )

        if (
            "خصم" in operation
            or "ناقص" in operation
            or "-" in operation
        ):

            final_points = -points
            title = "⚠️ تم خصم النقاط"
            color = COLORS["danger"]

        else:

            final_points = points
            title = "✨ تم إضافة النقاط"
            color = COLORS["success"]

        _, new_score = add_points(
            interaction.guild.id,
            selected_house,
            final_points,
            None,
            interaction.user.id,
            reason
        )

        emoji = HOUSE_ROLES[
            selected_house
        ]

        embed = make_embed(
            title,
            (
                f"🏠 **المنزل:** {emoji} {selected_house}\n"
                f"⭐ **النقاط:** {final_points:+,}\n"
                f"📝 **السبب:** {reason}\n\n"
                f"🏆 **الرصيد الحالي:** {new_score:,}"
            ),
            color
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


@bot.tree.command(
    name="نقاط_البيت",
    description="إضافة أو خصم نقاط للبيت"
)
async def slash_house_points(
    interaction: discord.Interaction
):

    if not can_manage_cup(
        interaction.user
    ):

        return await interaction.response.send_message(
            "❌ ليس لديك صلاحية لإدارة كأس المنازل.",
            ephemeral=True
        )

    await interaction.response.send_modal(
        HousePointsModal()
    )


# =========================================================
# 🌟 ترتيب الطلاب
# =========================================================

@bot.tree.command(
    name="ترتيب_الطلاب",
    description="عرض الطلاب الأعلى نقاطاً"
)
async def slash_students_leaderboard(
    interaction: discord.Interaction
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            house,
            SUM(amount) AS total_points
        FROM point_logs
        WHERE guild_id = ?
        AND user_id IS NOT NULL
        AND undone = 0
        AND amount > 0
        GROUP BY user_id
        ORDER BY total_points DESC
        LIMIT 10
    """, (
        interaction.guild.id,
    ))

    rows = cur.fetchall()

    conn.close()

    embed = make_embed(
        "🌟 لوحة شرف السحرة",
        "✨ أعلى الطلاب جمعاً لنقاط كأس المنازل.",
        COLORS["gold"]
    )

    if not rows:

        embed.description = (
            "❌ لا توجد نقاط مسجلة بأسماء طلاب حتى الآن."
        )

    medals = [
        "🥇",
        "🥈",
        "🥉",
        "4️⃣",
        "5️⃣",
        "6️⃣",
        "7️⃣",
        "8️⃣",
        "9️⃣",
        "🔟"
    ]

    for index, row in enumerate(rows):

        user_id = row["user_id"]
        house = row["house"]
        points = row["total_points"]

        emoji = HOUSE_ROLES.get(
            house,
            "✨"
        )

        embed.add_field(
            name=f"{medals[index]} الساحر: <@{user_id}>",
            value=(
                f"🏠 {emoji} **{house}**\n"
                f"⭐ **{points:,} نقطة**"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# 🏆 أمر الكأس
# =========================================================

@bot.command(name="الكأس")
async def cup_command(ctx):

    if not ctx.guild:
        return

    ensure_guild(
        ctx.guild.id
    )

    await ctx.send(
        embed=create_cup_embed(
            ctx.guild
        )
    )


# =========================================================
# ↩️ التراجع
# =========================================================

@bot.command(name="تراجع")
async def undo_cmd(ctx):

    if not can_manage_cup(
        ctx.author
    ):

        return await ctx.send(
            "❌ ليس لديك صلاحية.",
            delete_after=10
        )

    row = undo_last_action(
        ctx.guild.id
    )

    if not row:

        return await ctx.send(
            "❌ لا توجد عملية قابلة للتراجع.",
            delete_after=10
        )

    await ctx.send(
        embed=make_embed(
            "↩️ تم التراجع",
            (
                f"🏠 المنزل: {row['house']}\n"
                f"⭐ العملية: {row['amount']:,} نقطة"
            ),
            COLORS["gold"]
        )
    )


# =========================================================
# 📜 سجل كأس المنازل
# =========================================================

@bot.command(name="السجل")
async def logs_cmd(ctx):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM point_logs
        WHERE guild_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (
        ctx.guild.id,
    ))

    rows = cur.fetchall()

    conn.close()

    embed = make_embed(
        "📜 سجل كأس المنازل",
        "آخر 10 عمليات.",
        COLORS["blue"]
    )

    if not rows:
        embed.description = "لا توجد عمليات مسجلة."

    for row in rows:

        embed.add_field(
            name=f"#{row['id']} • {row['house']}",
            value=(
                f"⭐ {row['amount']:+,}\n"
                f"📝 {row['reason']}\n"
                f"🕐 {row['created_at']}"
            ),
            inline=False
        )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 🎪 نظام فعاليات كأس المنازل
# =========================================================

def load_events():

    if not os.path.exists(
        EVENTS_FILE
    ):
        return []

    try:

        with open(
            EVENTS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

    except Exception as e:

        print(
            f"Events load error: {e}"
        )

        return []

    # -----------------------------------------
    # إذا كان الملف قائمة مباشرة
    # -----------------------------------------

    if isinstance(
        data,
        list
    ):

        return [
            event
            for event in data
            if isinstance(event, dict)
        ]

    # -----------------------------------------
    # إذا كان Dictionary
    # -----------------------------------------

    if isinstance(
        data,
        dict
    ):

        if isinstance(
            data.get("events"),
            list
        ):

            return [
                event
                for event in data["events"]
                if isinstance(event, dict)
            ]

        # دعم ملفات الأحداث القديمة
        events = []

        for key, value in data.items():

            if isinstance(
                value,
                dict
            ):

                event = dict(value)

                if not event.get("id"):
                    event["id"] = key

                events.append(event)

        return events

    return []


def save_events(events):

    return save_json_file(
        EVENTS_FILE,
        events
    )


def event_value(
    event,
    *keys,
    default="غير محدد"
):

    for key in keys:

        value = event.get(
            key
        )

        if value is not None:

            value = str(
                value
            ).strip()

            if value:
                return value

    return default


def create_event_id(
    events
):

    highest = 0

    for event in events:

        try:

            event_id = int(
                event.get(
                    "id",
                    0
                )
            )

            highest = max(
                highest,
                event_id
            )

        except (
            ValueError,
            TypeError
        ):
            continue

    return highest + 1


# =========================================================
# 📝 استمارة تسجيل فعالية
# =========================================================

class EventRegistrationModal(
    discord.ui.Modal,
    title="🎪 تسجيل فعالية جديدة"
):

    event_name = discord.ui.TextInput(
        label="اسم الفعالية",
        placeholder="مثال: بطولة كأس المنازل الكبرى",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )

    event_description = discord.ui.TextInput(
        label="وصف الفعالية",
        placeholder="اكتب وصفاً مختصراً عن الفعالية...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    event_result = discord.ui.TextInput(
        label="النتيجة / الفائز",
        placeholder="مثال: فاز منزل هافلباف",
        style=discord.TextStyle.short,
        required=False,
        max_length=300
    )

    event_date = discord.ui.TextInput(
        label="تاريخ الفعالية",
        placeholder="مثال: 2026-09-02",
        style=discord.TextStyle.short,
        required=False,
        max_length=50
    )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:

            return await interaction.response.send_message(
                "❌ لا يمكن تسجيل فعالية خارج السيرفر.",
                ephemeral=True
            )

        if not can_manage_cup(
            interaction.user
        ):

            return await interaction.response.send_message(
                "❌ ليس لديك صلاحية تسجيل فعاليات كأس المنازل.",
                ephemeral=True
            )

        events = load_events()

        new_id = create_event_id(
            events
        )

        date_value = (
            self.event_date.value.strip()
            if self.event_date.value.strip()
            else datetime.utcnow().strftime(
                "%Y-%m-%d"
            )
        )

        result_value = (
            self.event_result.value.strip()
            if self.event_result.value.strip()
            else "لم يتم تسجيل النتيجة"
        )

        event = {
            "id": new_id,
            "guild_id": interaction.guild.id,
            "name": self.event_name.value.strip(),
            "description": self.event_description.value.strip(),
            "result": result_value,
            "date": date_value,
            "created_by": interaction.user.id,
            "created_at": datetime.utcnow().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }

        events.append(
            event
        )

        if not save_events(
            events
        ):

            return await interaction.response.send_message(
                "❌ حدث خطأ أثناء حفظ الفعالية.",
                ephemeral=True
            )

        embed = make_embed(
            "🎪 تم تسجيل الفعالية",
            (
                f"🆔 **رقم الفعالية:** `{new_id}`\n"
                f"📜 **الاسم:** {event['name']}\n\n"
                f"📝 **الوصف:**\n{event['description']}\n\n"
                f"🏆 **النتيجة:** {event['result']}\n"
                f"📅 **التاريخ:** {event['date']}\n"
                f"👤 **سجلها:** {interaction.user.mention}\n\n"
                "ℹ️ **ملاحظة:** تسجيل الفعالية لا يضيف أي نقاط تلقائياً إلى كأس المنازل."
            ),
            COLORS["success"]
        )

        await interaction.response.send_message(
            embed=embed
        )


@bot.command(
    name="تسجيل-فعالية"
)
async def register_event(
    ctx
):

    if not ctx.guild:

        return await ctx.send(
            "❌ هذا الأمر يعمل داخل السيرفر فقط."
        )

    if not can_manage_cup(
        ctx.author
    ):

        return await ctx.send(
            "❌ ليس لديك صلاحية تسجيل فعاليات كأس المنازل.",
            delete_after=10
        )

    await ctx.send_modal(
        EventRegistrationModal()
    )


# =========================================================
# 📜 واجهة سجل الفعاليات
# =========================================================

EVENTS_PER_PAGE = 5


class EventHistoryView(
    discord.ui.View
):

    def __init__(
        self,
        user,
        events
    ):

        super().__init__(
            timeout=180
        )

        self.user = user
        self.events = events
        self.page = 0

        self.update_buttons()


    @property
    def total_pages(self):

        return max(
            1,
            (
                len(self.events)
                + EVENTS_PER_PAGE
                - 1
            )
            // EVENTS_PER_PAGE
        )


    def update_buttons(self):

        self.previous_button.disabled = (
            self.page <= 0
        )

        self.next_button.disabled = (
            self.page >= self.total_pages - 1
        )


    def create_embed(self):

        start = (
            self.page
            * EVENTS_PER_PAGE
        )

        end = start + EVENTS_PER_PAGE

        page_events = self.events[
            start:end
        ]

        embed = make_embed(
            "📜 سجل فعاليات كأس المنازل",
            (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🎪 **أرشيف الفعاليات المسجلة**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📖 الصفحة **{self.page + 1}** "
                f"من **{self.total_pages}**"
            ),
            COLORS["blue"]
        )

        if not page_events:

            embed.description += (
                "\n\n❌ لا توجد فعاليات مسجلة."
            )

            return embed

        for event in page_events:

            event_id = event_value(
                event,
                "id",
                "event_id",
                default="?"
            )

            name = event_value(
                event,
                "name",
                "title",
                "event_name",
                default="فعالية بدون اسم"
            )

            description = event_value(
                event,
                "description",
                "details",
                "desc",
                default="لا يوجد وصف."
            )

            result = event_value(
                event,
                "result",
                "winner",
                "outcome",
                default="لم يتم تسجيل النتيجة"
            )

            date = event_value(
                event,
                "date",
                "event_date",
                "created_at",
                "time",
                default="غير محدد"
            )

            # منع الحقل من تجاوز حد Discord
            if len(description) > 700:
                description = (
                    description[:697]
                    + "..."
                )

            if len(result) > 300:
                result = (
                    result[:297]
                    + "..."
                )

            embed.add_field(
                name=f"🎪 #{event_id} — {name}",
                value=(
                    f"📝 **الوصف:**\n"
                    f"{description}\n\n"
                    f"🏆 **النتيجة:** {result}\n"
                    f"📅 **التاريخ:** {date}"
                ),
                inline=False
            )

        return embed


    async def interaction_check(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.id != self.user.id:

            await interaction.response.send_message(
                "❌ هذا السجل تم فتحه بواسطة عضو آخر.",
                ephemeral=True
            )

            return False

        return True


    @discord.ui.button(
        label="السابق",
        emoji="◀️",
        style=discord.ButtonStyle.secondary
    )
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if self.page > 0:
            self.page -= 1

        self.update_buttons()

        await interaction.response.edit_message(
            embed=self.create_embed(),
            view=self
        )


    @discord.ui.button(
        label="إغلاق",
        emoji="⏹️",
        style=discord.ButtonStyle.danger
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=make_embed(
                "📜 سجل الفعاليات",
                "🔒 تم إغلاق سجل الفعاليات.",
                COLORS["silver"]
            ),
            view=self
        )

        self.stop()


    @discord.ui.button(
        label="التالي",
        emoji="▶️",
        style=discord.ButtonStyle.secondary
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if self.page < self.total_pages - 1:
            self.page += 1

        self.update_buttons()

        await interaction.response.edit_message(
            embed=self.create_embed(),
            view=self
        )


    async def on_timeout(self):

        for item in self.children:
            item.disabled = True


# =========================================================
# 📜 أمر سجل الفعاليات
# =========================================================

@bot.command(
    name="سجل-الفعاليات"
)
async def events_history(
    ctx
):

    if not ctx.guild:

        return await ctx.send(
            "❌ هذا الأمر يعمل داخل السيرفر فقط."
        )

    events = load_events()

    # -----------------------------------------
    # فلترة فعاليات السيرفر
    # -----------------------------------------

    guild_events = []

    for event in events:

        event_guild_id = event.get(
            "guild_id"
        )

        if event_guild_id is None:

            # دعم السجلات القديمة
            guild_events.append(
                event
            )

            continue

        try:

            if int(event_guild_id) == ctx.guild.id:
                guild_events.append(
                    event
                )

        except (
            ValueError,
            TypeError
        ):
            continue

    # -----------------------------------------
    # ترتيب الأحدث أولاً
    # -----------------------------------------

    guild_events.reverse()

    if not guild_events:

        return await ctx.send(
            embed=make_embed(
                "📜 سجل فعاليات كأس المنازل",
                (
                    "❌ لا توجد فعاليات مسجلة حتى الآن.\n\n"
                    "يمكن للمشرف استخدام:\n"
                    "`!تسجيل-فعالية`"
                ),
                COLORS["blue"]
            )
        )

    view = EventHistoryView(
        ctx.author,
        guild_events
    )

    await ctx.send(
        embed=view.create_embed(),
        view=view
    )


# =========================================================
# 🗑️ حذف فعالية
# =========================================================

@bot.command(
    name="حذف-فعالية"
)
async def delete_event(
    ctx,
    event_id: int = None
):

    if not ctx.guild:

        return await ctx.send(
            "❌ هذا الأمر يعمل داخل السيرفر فقط."
        )

    if not can_manage_cup(
        ctx.author
    ):

        return await ctx.send(
            "❌ ليس لديك صلاحية حذف فعاليات.",
            delete_after=10
        )

    if event_id is None:

        return await ctx.send(
            embed=make_embed(
                "🗑️ حذف فعالية",
                (
                    "استخدم الأمر بهذا الشكل:\n\n"
                    "`!حذف-فعالية 1`\n\n"
                    "حيث **1** هو رقم الفعالية."
                ),
                COLORS["danger"]
            )
        )

    events = load_events()

    found_event = None
    new_events = []

    for event in events:

        try:

            current_id = int(
                event.get(
                    "id",
                    event.get(
                        "event_id",
                        -1
                    )
                )
            )

        except (
            ValueError,
            TypeError
        ):

            current_id = -1

        event_guild_id = event.get(
            "guild_id"
        )

        same_guild = (
            event_guild_id is None
            or str(event_guild_id)
            == str(ctx.guild.id)
        )

        if (
            current_id == event_id
            and same_guild
            and found_event is None
        ):

            found_event = event

            continue

        new_events.append(
            event
        )

    if not found_event:

        return await ctx.send(
            embed=make_embed(
                "❌ لم يتم العثور على الفعالية",
                f"لا توجد فعالية بالرقم `{event_id}`.",
                COLORS["danger"]
            )
        )

    if not save_events(
        new_events
    ):

        return await ctx.send(
            "❌ حدث خطأ أثناء تحديث ملف الفعاليات."
        )

    name = event_value(
        found_event,
        "name",
        "title",
        "event_name",
        default="فعالية"
    )

    await ctx.send(
        embed=make_embed(
            "🗑️ تم حذف الفعالية",
            (
                f"🆔 **رقم الفعالية:** `{event_id}`\n"
                f"🎪 **الفعالية:** {name}\n\n"
                "تم حذفها من سجل الفعاليات بنجاح."
            ),
            COLORS["danger"]
        )
    )


# =========================================================
# ⚔️ نظام المبارزات السحرية
# =========================================================

MAX_HP = 200
MAX_MP = 100

DUEL_TIMEOUT = 180

active_duels = {}


# =========================================================
# ✨ التعاويذ
# =========================================================

SPELLS = {

    # ⚔️ هجوم

    "stupefy": {
        "name": "ستوبيفاي",
        "type": "attack",
        "accuracy": 65,
        "cost": 15,
        "damage": 25
    },

    "expelliarmus": {
        "name": "إكسبليارمس",
        "type": "attack",
        "accuracy": 80,
        "cost": 12,
        "damage": 20
    },

    "reducto": {
        "name": "ريدوكتو",
        "type": "attack",
        "accuracy": 50,
        "cost": 25,
        "damage": 40
    },

    "confringo": {
        "name": "كونفرينجو",
        "type": "attack",
        "accuracy": 65,
        "cost": 20,
        "damage": 32
    },

    "expulso": {
        "name": "إكسبولسو",
        "type": "attack",
        "accuracy": 75,
        "cost": 18,
        "damage": 28
    },

    "bombarda": {
        "name": "بومباردا",
        "type": "attack",
        "accuracy": 65,
        "cost": 20,
        "damage": 35
    },

    "bombarda_maxima": {
        "name": "بومباردا ماكسيما",
        "type": "attack",
        "accuracy": 40,
        "cost": 35,
        "damage": 55
    },

    "diffindo": {
        "name": "ديفيندو",
        "type": "attack",
        "accuracy": 70,
        "cost": 16,
        "damage": 27
    },

    "flipendo": {
        "name": "فليبيندو",
        "type": "attack",
        "accuracy": 80,
        "cost": 12,
        "damage": 20
    },

    "depulso": {
        "name": "ديبولسو",
        "type": "attack",
        "accuracy": 75,
        "cost": 16,
        "damage": 25
    },

    "incendio": {
        "name": "إنسينديو",
        "type": "attack",
        "accuracy": 75,
        "cost": 17,
        "damage": 26
    },

    "glacius": {
        "name": "جلاسيوس",
        "type": "attack",
        "accuracy": 65,
        "cost": 20,
        "damage": 30
    },

    "aguamenti": {
        "name": "أجوامينتي",
        "type": "attack",
        "accuracy": 80,
        "cost": 12,
        "damage": 18
    },

    # 🌀 تحكم

    "impedimenta": {
        "name": "إمبيديمينتا",
        "type": "control",
        "accuracy": 65,
        "cost": 20,
        "control": 1
    },

    "petrificus_totalus": {
        "name": "بيتريفيكوس توتالوس",
        "type": "control",
        "accuracy": 50,
        "cost": 30,
        "control": 1
    },

    "levicorpus": {
        "name": "ليفيكوربوس",
        "type": "control",
        "accuracy": 70,
        "cost": 18,
        "control": 1
    },

    "locomotor_mortis": {
        "name": "لوكوموتور مورتيس",
        "type": "control",
        "accuracy": 65,
        "cost": 20,
        "control": 1
    },

    "tarantallegra": {
        "name": "تارانتاليجرا",
        "type": "control",
        "accuracy": 75,
        "cost": 15,
        "control": 1
    },

    "rictusempra": {
        "name": "ريكتوسيمبرا",
        "type": "control",
        "accuracy": 80,
        "cost": 12,
        "control": 1
    },

    "confundo": {
        "name": "كونفوندو",
        "type": "control",
        "accuracy": 55,
        "cost": 25,
        "control": 1
    },

    "obscuro": {
        "name": "أوبسكورو",
        "type": "control",
        "accuracy": 70,
        "cost": 18,
        "control": 1
    },

    "silencio": {
        "name": "سيلينسيو",
        "type": "control",
        "accuracy": 55,
        "cost": 22,
        "control": 1
    },

    # 🛡️ دفاع

    "protego": {
        "name": "بروتيجو",
        "type": "defense",
        "accuracy": 100,
        "cost": 15,
        "shield": 30
    },

    "finite_incantatem": {
        "name": "فاينايت إنكانتاتيم",
        "type": "defense",
        "accuracy": 100,
        "cost": 15,
        "cleanse": True
    },

    "liberacorpus": {
        "name": "ليبيراكوربوس",
        "type": "defense",
        "accuracy": 100,
        "cost": 15,
        "shield": 20,
        "cleanse": True
    },

    "arresto_momentum": {
        "name": "أريستو مومينتوم",
        "type": "defense",
        "accuracy": 85,
        "cost": 20,
        "shield": 35
    },

    # 💚 علاج

    "episkey": {
        "name": "إبيسكي",
        "type": "heal",
        "accuracy": 85,
        "cost": 20,
        "heal_percent": 50
    },

    "cure": {
        "name": "Cure",
        "type": "heal",
        "accuracy": 100,
        "cost": 25,
        "heal": 60
    },

    "vulnera_sanentur": {
        "name": "فولنيرا سانينتور",
        "type": "heal",
        "accuracy": 60,
        "cost": 30,
        "heal": 85
    },

    # ✨ مساعدات

    "accio": {
        "name": "آكيو",
        "type": "auxiliary",
        "accuracy": 75,
        "cost": 12,
        "effect": "mana",
        "mana": 20
    },

    "duro": {
        "name": "دورو",
        "type": "auxiliary",
        "accuracy": 65,
        "cost": 15,
        "effect": "shield",
        "shield": 25
    },

    "lumos_solem": {
        "name": "لوموس سوليم",
        "type": "auxiliary",
        "accuracy": 85,
        "cost": 10,
        "effect": "accuracy",
        "bonus": 10
    },

    "expecto_patronum": {
        "name": "إكسبكتو باترونوم",
        "type": "auxiliary",
        "accuracy": 60,
        "cost": 25,
        "effect": "shield",
        "shield": 40
    }
}


# =========================================================
# ⚔️ بيانات المبارزة
# =========================================================

class Duel:

    def __init__(
        self,
        player1,
        player2
    ):

        self.player1 = player1
        self.player2 = player2

        self.hp = {
            player1.id: MAX_HP,
            player2.id: MAX_HP
        }

        self.mp = {
            player1.id: MAX_MP,
            player2.id: MAX_MP
        }

        self.shield = {
            player1.id: 0,
            player2.id: 0
        }

        self.stunned = {
            player1.id: 0,
            player2.id: 0
        }

        self.accuracy_bonus = {
            player1.id: 0,
            player2.id: 0
        }

        self.round_number = 0
        self.current_spells = {}
        self.selections = {}
        self.message = None
        self.finished = False
        self.created_at = datetime.utcnow()


    def get_opponent(
        self,
        user_id
    ):

        if user_id == self.player1.id:
            return self.player2

        return self.player1


    def random_spells(self):

        attacks = [
            key
            for key, spell in SPELLS.items()
            if spell["type"] == "attack"
        ]

        controls = [
            key
            for key, spell in SPELLS.items()
            if spell["type"] == "control"
        ]

        defenses = [
            key
            for key, spell in SPELLS.items()
            if spell["type"] == "defense"
        ]

        heals = [
            key
            for key, spell in SPELLS.items()
            if spell["type"] == "heal"
        ]

        selected = (
            random.sample(attacks, 2)
            + random.sample(defenses, 2)
            + random.sample(controls, 1)
            + random.sample(heals, 1)
        )

        random.shuffle(
            selected
        )

        return selected


    def hp_bar(
        self,
        user_id
    ):

        hp = self.hp[user_id]

        total_blocks = 10

        filled = round(
            hp
            / MAX_HP
            * total_blocks
        )

        filled = max(
            0,
            min(
                total_blocks,
                filled
            )
        )

        return (
            "🟩" * filled
            + "⬛" * (
                total_blocks - filled
            )
        )


    def mp_bar(
        self,
        user_id
    ):

        mp = self.mp[user_id]

        total_blocks = 10

        filled = round(
            mp
            / MAX_MP
            * total_blocks
        )

        filled = max(
            0,
            min(
                total_blocks,
                filled
            )
        )

        return (
            "🔵" * filled
            + "⬛" * (
                total_blocks - filled
            )
        )


    def status_text(
        self,
        user
    ):

        uid = user.id

        status = (
            f"🧙 {user.mention}\n"
            f"❤️ **HP:** {self.hp[uid]}/{MAX_HP}\n"
            f"{self.hp_bar(uid)}\n"
            f"💧 **Mana:** {self.mp[uid]}/{MAX_MP}\n"
            f"{self.mp_bar(uid)}\n"
            f"🛡️ **الدرع:** {self.shield[uid]}"
        )

        if self.stunned[uid] > 0:

            status += (
                "\n🌀 **مُقيّد هذه الجولة**"
            )

        return status


# =========================================================
# 🎯 زر التعويذة
# =========================================================

class SpellButton(
    discord.ui.Button
):

    def __init__(
        self,
        spell_key,
        duel
    ):

        spell = SPELLS[
            spell_key
        ]

        spell_type = spell["type"]

        if spell_type == "attack":

            style = discord.ButtonStyle.danger
            emoji = "⚔️"

        elif spell_type == "defense":

            style = discord.ButtonStyle.primary
            emoji = "🛡️"

        elif spell_type == "control":

            style = discord.ButtonStyle.secondary
            emoji = "🌀"

        elif spell_type == "heal":

            style = discord.ButtonStyle.success
            emoji = "💚"

        else:

            style = discord.ButtonStyle.secondary
            emoji = "✨"

        label = (
            f"{spell['name']} • "
            f"{spell['cost']}💧"
        )

        super().__init__(
            label=label[:80],
            emoji=emoji,
            style=style
        )

        self.spell_key = spell_key
        self.duel = duel


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        duel = self.duel

        if duel.finished:

            return await interaction.response.send_message(
                "❌ هذه المبارزة انتهت.",
                ephemeral=True
            )

        if interaction.user.id not in [
            duel.player1.id,
            duel.player2.id
        ]:

            return await interaction.response.send_message(
                "❌ أنت لست طرفاً في هذه المبارزة.",
                ephemeral=True
            )

        uid = interaction.user.id

        if uid in duel.selections:

            return await interaction.response.send_message(
                "⚠️ لقد اخترت تعويذتك بالفعل في هذه الجولة.",
                ephemeral=True
            )

        spell = SPELLS[
            self.spell_key
        ]

        if duel.mp[uid] < spell["cost"]:

            return await interaction.response.send_message(
                (
                    f"❌ لا تملك مانا كافية.\n"
                    f"تحتاج إلى **{spell['cost']}💧** "
                    f"ولديك **{duel.mp[uid]}💧**."
                ),
                ephemeral=True
            )

        duel.selections[
            uid
        ] = self.spell_key

        await interaction.response.send_message(
            (
                f"✨ اخترت **{spell['name']}**.\n"
                "انتظر اختيار الساحر الآخر..."
            ),
            ephemeral=True
        )

        if len(
            duel.selections
        ) == 2:

            await process_duel_round(
                duel
            )

        else:

            await update_duel_waiting_message(
                duel
            )


# =========================================================
# ⚔️ View المبارزة
# =========================================================

class DuelSpellView(
    discord.ui.View
):

    def __init__(
        self,
        duel
    ):

        super().__init__(
            timeout=DUEL_TIMEOUT
        )

        self.duel = duel

        for spell_key in duel.current_spells:

            self.add_item(
                SpellButton(
                    spell_key,
                    duel
                )
            )


    async def on_timeout(
        self
    ):

        if self.duel.finished:
            return

        duel = self.duel

        duel.finished = True

        active_duels.pop(
            duel.player1.id,
            None
        )

        active_duels.pop(
            duel.player2.id,
            None
        )

        if duel.message:

            try:

                embed = make_embed(
                    "⌛ انتهت مهلة المبارزة",
                    (
                        f"⚔️ انتهت المبارزة بين "
                        f"{duel.player1.mention} و"
                        f"{duel.player2.mention}.\n\n"
                        "لم يتم تسجيل فائز لأن أحد الطرفين "
                        "لم يختر تعويذته في الوقت المحدد."
                    ),
                    COLORS["danger"]
                )

                await duel.message.edit(
                    embed=embed,
                    view=None
                )

            except Exception:
                pass


# =========================================================
# 📊 رسالة انتظار الاختيار
# =========================================================

async def update_duel_waiting_message(
    duel
):

    if not duel.message:
        return

    selected = len(
        duel.selections
    )

    embed = make_duel_embed(
        duel,
        (
            "⚡ **اختيار التعويذة**\n\n"
            f"تم اختيار التعويذة من "
            f"**{selected}/2** من المبارزين.\n\n"
            "🪄 المبارز الآخر يختار تعويذته..."
        )
    )

    try:

        await duel.message.edit(
            embed=embed
        )

    except Exception:
        pass


# =========================================================
# 🧙 Embed المبارزة
# =========================================================

def make_duel_embed(
    duel,
    description
):

    p1 = duel.player1
    p2 = duel.player2

    embed = discord.Embed(
        title=(
            f"⚔️ المبارزة السحرية — "
            f"الجولة {duel.round_number}"
        ),
        description=description,
        color=0x5B2C83
    )

    embed.add_field(
        name=f"🧙 {p1.display_name}",
        value=duel.status_text(p1),
        inline=True
    )

    embed.add_field(
        name=f"🧙 {p2.display_name}",
        value=duel.status_text(p2),
        inline=True
    )

    embed.set_footer(
        text=AUTHOR_SIGNATURE
    )

    return embed


# =========================================================
# 🎲 تنفيذ الجولة
# =========================================================

async def process_duel_round(
    duel
):

    if duel.finished:
        return

    duel.round_number += 1

    p1 = duel.player1
    p2 = duel.player2

    id1 = p1.id
    id2 = p2.id

    spell1_key = duel.selections[id1]
    spell2_key = duel.selections[id2]

    spell1 = SPELLS[
        spell1_key
    ]

    spell2 = SPELLS[
        spell2_key
    ]

    duel.mp[id1] -= spell1["cost"]
    duel.mp[id2] -= spell2["cost"]

    round_messages = []


    def cast(
        caster,
        target,
        spell
    ):

        cid = caster.id
        tid = target.id

        if duel.stunned[cid] > 0:

            duel.stunned[cid] -= 1

            return (
                f"🌀 {caster.mention} كان مقيّداً "
                "ولم يتمكن من استخدام التعويذة!"
            )

        accuracy = min(
            100,
            spell["accuracy"]
            + duel.accuracy_bonus[cid]
        )

        duel.accuracy_bonus[cid] = 0

        success = (
            random.randint(1, 100)
            <= accuracy
        )

        if not success:

            return (
                f"💨 {caster.mention} حاول استخدام "
                f"**{spell['name']}** لكن التعويذة أخفقت."
            )

        spell_type = spell["type"]

        # ⚔️ هجوم

        if spell_type == "attack":

            damage = spell["damage"]

            blocked = min(
                duel.shield[tid],
                damage
            )

            duel.shield[tid] -= blocked
            damage -= blocked

            duel.hp[tid] = max(
                0,
                duel.hp[tid] - damage
            )

            if blocked > 0:

                return (
                    f"⚔️ {caster.mention} استخدم "
                    f"**{spell['name']}** على {target.mention}.\n"
                    f"🛡️ تم امتصاص **{blocked}** بالدرع.\n"
                    f"❤️ الضرر الفعلي: **{damage}**."
                )

            return (
                f"⚔️ {caster.mention} أطلق "
                f"**{spell['name']}** على {target.mention} "
                f"وألحق **{damage} ضرر**."
            )

        # 🛡️ دفاع

        if spell_type == "defense":

            shield = spell.get(
                "shield",
                0
            )

            duel.shield[cid] += shield

            if spell.get(
                "cleanse"
            ):

                duel.stunned[cid] = 0

            return (
                f"🛡️ {caster.mention} استخدم "
                f"**{spell['name']}**.\n"
                f"🛡️ الدرع: +{shield}"
            )

        # 🌀 تحكم

        if spell_type == "control":

            duel.stunned[tid] = 1

            return (
                f"🌀 {caster.mention} استخدم "
                f"**{spell['name']}** على "
                f"{target.mention}.\n"
                "⛓️ تم تقييد الخصم للجولة التالية."
            )

        # 💚 علاج

        if spell_type == "heal":

            old_hp = duel.hp[cid]

            if "heal_percent" in spell:

                amount = int(
                    MAX_HP
                    * spell["heal_percent"]
                    / 100
                )

            else:

                amount = spell.get(
                    "heal",
                    0
                )

            duel.hp[cid] = min(
                MAX_HP,
                duel.hp[cid] + amount
            )

            healed = (
                duel.hp[cid]
                - old_hp
            )

            return (
                f"💚 {caster.mention} استخدم "
                f"**{spell['name']}** واستعاد "
                f"**{healed} HP**."
            )

        # ✨ مساعد

        if spell_type == "auxiliary":

            effect = spell.get(
                "effect"
            )

            if effect == "mana":

                amount = spell.get(
                    "mana",
                    0
                )

                duel.mp[cid] = min(
                    MAX_MP,
                    duel.mp[cid] + amount
                )

                return (
                    f"✨ {caster.mention} استخدم "
                    f"**{spell['name']}** واستعاد "
                    f"**{amount}💧 مانا**."
                )

            if effect == "shield":

                amount = spell.get(
                    "shield",
                    0
                )

                duel.shield[cid] += amount

                return (
                    f"✨ {caster.mention} استخدم "
                    f"**{spell['name']}**.\n"
                    f"🛡️ +{amount} درع."
                )

            if effect == "accuracy":

                bonus = spell.get(
                    "bonus",
                    0
                )

                duel.accuracy_bonus[cid] += bonus

                return (
                    f"✨ {caster.mention} استخدم "
                    f"**{spell['name']}**.\n"
                    f"🎯 دقة التعويذة القادمة +{bonus}%."
                )

        return "✨ تم تنفيذ التعويذة."


    first_message = cast(
        p1,
        p2,
        spell1
    )

    second_message = cast(
        p2,
        p1,
        spell2
    )

    round_messages.append(
        first_message
    )

    round_messages.append(
        second_message
    )

    # 💧 استعادة نصف تكلفة التعويذة

    mana_recovery_1 = max(
        1,
        spell1["cost"] // 2
    )

    mana_recovery_2 = max(
        1,
        spell2["cost"] // 2
    )

    duel.mp[id1] = min(
        MAX_MP,
        duel.mp[id1] + mana_recovery_1
    )

    duel.mp[id2] = min(
        MAX_MP,
        duel.mp[id2] + mana_recovery_2
    )

    round_messages.append(
        (
            f"💧 استعادة المانا: "
            f"{p1.mention} **+{mana_recovery_1}** | "
            f"{p2.mention} **+{mana_recovery_2}**"
        )
    )

    duel.selections.clear()

    winner = None
    loser = None

    # 🤝 تعادل

    if (
        duel.hp[id1] <= 0
        and duel.hp[id2] <= 0
    ):

        duel.finished = True

        active_duels.pop(
            id1,
            None
        )

        active_duels.pop(
            id2,
            None
        )

        description = (
            "\n\n".join(
                round_messages
            )
            + "\n\n"
            "🤝 **انتهت المبارزة بالتعادل!**"
        )

        embed = make_duel_embed(
            duel,
            description
        )

        embed.title = (
            "⚔️ نهاية المبارزة — تعادل"
        )

        embed.color = COLORS["gold"]

        if duel.message:

            await duel.message.edit(
                embed=embed,
                view=None
            )

        save_duel_result(
            duel,
            None
        )

        return

    if duel.hp[id1] <= 0:

        winner = p2
        loser = p1

    elif duel.hp[id2] <= 0:

        winner = p1
        loser = p2

    # 🏆 فوز

    if winner:

        duel.finished = True

        active_duels.pop(
            id1,
            None
        )

        active_duels.pop(
            id2,
            None
        )

        description = (
            "\n\n".join(
                round_messages
            )
            + "\n\n"
            f"🏆 **الفائز:** {winner.mention}\n"
            f"💫 **المهزوم:** {loser.mention}"
        )

        embed = make_duel_embed(
            duel,
            description
        )

        embed.title = (
            "🏆 نهاية المبارزة"
        )

        embed.color = COLORS["gold"]

        if duel.message:

            await duel.message.edit(
                embed=embed,
                view=None
            )

        save_duel_result(
            duel,
            winner
        )

        return

    # 🔮 جولة جديدة

    duel.current_spells = (
        duel.random_spells()
    )

    description = (
        "\n\n".join(
            round_messages
        )
        + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ **جولة جديدة!**\n"
        "اختر تعويذتك من الأزرار بالأسفل.\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    embed = make_duel_embed(
        duel,
        description
    )

    new_view = DuelSpellView(
        duel
    )

    if duel.message:

        await duel.message.edit(
            embed=embed,
            view=new_view
        )


# =========================================================
# 📜 سجل المبارزات
# =========================================================

def load_duel_data():

    data = load_json_file(
        LEADERBOARD_FILE
    )

    if not isinstance(
        data,
        dict
    ):

        data = {}

    if "players" not in data:
        data["players"] = {}

    if "matches" not in data:
        data["matches"] = []

    return data


def save_duel_data(
    data
):

    save_json_file(
        LEADERBOARD_FILE,
        data
    )


def save_duel_result(
    duel,
    winner
):

    data = load_duel_data()

    p1_id = str(
        duel.player1.id
    )

    p2_id = str(
        duel.player2.id
    )

    for user_id, member in [
        (p1_id, duel.player1),
        (p2_id, duel.player2)
    ]:

        if user_id not in data["players"]:

            data["players"][user_id] = {
                "name": member.name,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "matches": 0
            }

        data["players"][user_id]["name"] = (
            member.name
        )

        data["players"][user_id]["matches"] += 1

    if winner is None:

        data["players"][p1_id]["draws"] += 1
        data["players"][p2_id]["draws"] += 1

        result = "draw"

    else:

        winner_id = str(
            winner.id
        )

        loser = duel.get_opponent(
            winner.id
        )

        loser_id = str(
            loser.id
        )

        data["players"][winner_id]["wins"] += 1
        data["players"][loser_id]["losses"] += 1

        result = "win"

    data["matches"].append({
        "player1_id": duel.player1.id,
        "player2_id": duel.player2.id,
        "winner_id": (
            winner.id
            if winner
            else None
        ),
        "result": result,
        "rounds": duel.round_number,
        "created_at": datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    })

    data["matches"] = data[
        "matches"
    ][-500:]

    save_duel_data(
        data
    )


# =========================================================
# ⚔️ طلب مبارزة
# =========================================================

class DuelRequestView(
    discord.ui.View
):

    def __init__(
        self,
        challenger,
        opponent
    ):

        super().__init__(
            timeout=60
        )

        self.challenger = challenger
        self.opponent = opponent
        self.accepted = False


    @discord.ui.button(
        label="قبول المبارزة",
        emoji="⚔️",
        style=discord.ButtonStyle.success
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.opponent.id:

            return await interaction.response.send_message(
                "❌ هذه الدعوة ليست موجهة إليك.",
                ephemeral=True
            )

        if (
            self.challenger.id in active_duels
            or self.opponent.id in active_duels
        ):

            return await interaction.response.send_message(
                "❌ أحد المبارزين داخل مبارزة بالفعل.",
                ephemeral=True
            )

        self.accepted = True

        duel = Duel(
            self.challenger,
            self.opponent
        )

        duel.round_number = 1

        duel.current_spells = (
            duel.random_spells()
        )

        active_duels[
            self.challenger.id
        ] = duel

        active_duels[
            self.opponent.id
        ] = duel

        embed = make_duel_embed(
            duel,
            (
                "⚡ **بدأت المبارزة!**\n\n"
                "كل ساحر لديه **200 HP** و"
                "**100 Mana**.\n\n"
                "اختر تعويذتك من الأزرار.\n"
                "التعويذات المعروضة في كل جولة "
                "يتم اختيارها عشوائياً."
            )
        )

        view = DuelSpellView(
            duel
        )

        await interaction.response.edit_message(
            embed=embed,
            view=view
        )

        duel.message = (
            await interaction.original_response()
        )


    @discord.ui.button(
        label="رفض",
        emoji="❌",
        style=discord.ButtonStyle.danger
    )
    async def decline(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.opponent.id:

            return await interaction.response.send_message(
                "❌ هذه الدعوة ليست موجهة إليك.",
                ephemeral=True
            )

        await interaction.response.edit_message(
            embed=make_embed(
                "❌ تم رفض المبارزة",
                (
                    f"{self.opponent.mention} رفض "
                    f"مبارزة {self.challenger.mention}."
                ),
                COLORS["danger"]
            ),
            view=None
        )

        self.stop()


# =========================================================
# ⚔️ أمر مبارزة
# =========================================================

@bot.command(
    name="مبارزة"
)
async def duel_command(
    ctx,
    opponent: discord.Member = None
):

    if not ctx.guild:

        return await ctx.send(
            "❌ هذا الأمر يعمل داخل السيرفر فقط."
        )

    if opponent is None:

        return await ctx.send(
            embed=make_embed(
                "⚔️ المبارزة السحرية",
                (
                    "استخدم الأمر بهذا الشكل:\n\n"
                    "`!مبارزة @الساحر`\n\n"
                    "ثم انتظر موافقته."
                ),
                COLORS["blue"]
            )
        )

    if opponent.id == ctx.author.id:

        return await ctx.send(
            "❌ لا يمكنك مبارزة نفسك."
        )

    if opponent.bot:

        return await ctx.send(
            "❌ لا يمكنك مبارزة بوت."
        )

    if (
        ctx.author.id in active_duels
        or opponent.id in active_duels
    ):

        return await ctx.send(
            "❌ أحد الطرفين داخل مبارزة بالفعل."
        )

    embed = make_embed(
        "⚔️ تحدي مبارزة سحرية",
        (
            f"🧙 **المتحدي:** {ctx.author.mention}\n"
            f"🧙 **المدعو:** {opponent.mention}\n\n"
            "هل تقبل دخول المبارزة؟\n\n"
            "❤️ **HP:** 200\n"
            "💧 **Mana:** 400"
        ),
        COLORS["magic"]
    )

    view = DuelRequestView(
        ctx.author,
        opponent
    )

    await ctx.send(
        content=opponent.mention,
        embed=embed,
        view=view
    )


# =========================================================
# 📜 سجل مبارزات لاعب
# =========================================================

@bot.command(
    name="سجل-مبارزاتي"
)
async def my_duel_history(
    ctx
):

    data = load_duel_data()

    user_id = str(
        ctx.author.id
    )

    stats = data["players"].get(
        user_id
    )

    if not stats:

        return await ctx.send(
            embed=make_embed(
                "📜 سجل المبارزات",
                (
                    f"{ctx.author.mention}\n\n"
                    "لم تخض أي مبارزة حتى الآن."
                ),
                COLORS["blue"]
            )
        )

    embed = make_embed(
        "⚔️ سجل المبارزات",
        f"🧙 الساحر: {ctx.author.mention}",
        COLORS["blue"]
    )

    embed.add_field(
        name="🏆 الانتصارات",
        value=f"**{stats['wins']}**",
        inline=True
    )

    embed.add_field(
        name="💫 الخسائر",
        value=f"**{stats['losses']}**",
        inline=True
    )

    embed.add_field(
        name="🤝 التعادلات",
        value=f"**{stats['draws']}**",
        inline=True
    )

    embed.add_field(
        name="⚔️ إجمالي المبارزات",
        value=f"**{stats['matches']}**",
        inline=False
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 🏆 ترتيب المبارزين
# =========================================================

@bot.command(
    name="ترتيب-المبارزين"
)
async def duel_leaderboard(
    ctx
):

    data = load_duel_data()

    players = data.get(
        "players",
        {}
    )

    if not players:

        return await ctx.send(
            embed=make_embed(
                "🏆 ترتيب المبارزين",
                "❌ لا توجد مبارزات مسجلة بعد.",
                COLORS["gold"]
            )
        )

    sorted_players = sorted(
        players.items(),
        key=lambda item: (
            item[1].get("wins", 0),
            -item[1].get("losses", 0)
        ),
        reverse=True
    )

    embed = make_embed(
        "🏆 ترتيب المبارزين",
        (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚔️ **أقوى السحرة في المبارزات**\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        COLORS["gold"]
    )

    medals = [
        "🥇",
        "🥈",
        "🥉",
        "4️⃣",
        "5️⃣",
        "6️⃣",
        "7️⃣",
        "8️⃣",
        "9️⃣",
        "🔟"
    ]

    for index, (
        user_id,
        stats
    ) in enumerate(
        sorted_players[:10]
    ):

        mention = f"<@{user_id}>"

        embed.add_field(
            name=f"{medals[index]} {mention}",
            value=(
                f"🏆 **{stats.get('wins', 0)}** انتصار | "
                f"💫 **{stats.get('losses', 0)}** خسارة | "
                f"🤝 **{stats.get('draws', 0)}** تعادل"
            ),
            inline=False
        )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 📜 آخر المبارزات
# =========================================================

@bot.command(
    name="سجل-المبارزات"
)
async def duel_matches_history(
    ctx
):

    data = load_duel_data()

    matches = data.get(
        "matches",
        []
    )

    if not matches:

        return await ctx.send(
            embed=make_embed(
                "📜 سجل المبارزات",
                "❌ لا توجد مبارزات مسجلة.",
                COLORS["blue"]
            )
        )

    matches = matches[
        -10:
    ][::-1]

    embed = make_embed(
        "📜 آخر المبارزات",
        "آخر 10 مبارزات مسجلة.",
        COLORS["blue"]
    )

    for index, match in enumerate(
        matches,
        start=1
    ):

        p1 = f"<@{match['player1_id']}>"
        p2 = f"<@{match['player2_id']}>"

        winner_id = match.get(
            "winner_id"
        )

        if winner_id:

            result = (
                f"🏆 الفائز: <@{winner_id}>"
            )

        else:

            result = (
                "🤝 النتيجة: تعادل"
            )

        embed.add_field(
            name=f"⚔️ المبارزة #{index}",
            value=(
                f"{p1} ضد {p2}\n"
                f"{result}\n"
                f"🔮 الجولات: {match['rounds']}\n"
                f"🕐 {match['created_at']}"
            ),
            inline=False
        )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 📊 حالة المبارزة
# =========================================================

@bot.command(
    name="مبارزتي"
)
async def duel_status(
    ctx
):

    duel = active_duels.get(
        ctx.author.id
    )

    if not duel:

        return await ctx.send(
            embed=make_embed(
                "⚔️ حالة المبارزة",
                "أنت لست داخل مبارزة حالياً.",
                COLORS["blue"]
            )
        )

    opponent = duel.get_opponent(
        ctx.author.id
    )

    embed = make_duel_embed(
        duel,
        (
            f"⚔️ أنت في مبارزة ضد "
            f"{opponent.mention}.\n\n"
            "اختر تعويذتك من رسالة المبارزة."
        )
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 📚 معلومات التعاويذ
# =========================================================

@bot.command(
    name="التعاويذ"
)
async def spells_command(
    ctx
):

    embed = make_embed(
        "📚 كتاب التعاويذ",
        (
            "التعاويذ المتاحة في نظام المبارزات.\n\n"
            "⚔️ هجوم\n"
            "🛡️ دفاع\n"
            "🌀 تحكم\n"
            "💚 علاج\n"
            "✨ مساعدة"
        ),
        COLORS["magic"]
    )

    attacks = [
        spell
        for spell in SPELLS.values()
        if spell["type"] == "attack"
    ]

    controls = [
        spell
        for spell in SPELLS.values()
        if spell["type"] == "control"
    ]

    defenses = [
        spell
        for spell in SPELLS.values()
        if spell["type"] == "defense"
    ]

    heals = [
        spell
        for spell in SPELLS.values()
        if spell["type"] == "heal"
    ]

    embed.add_field(
        name="⚔️ الهجوم",
        value="\n".join(
            f"• {x['name']} — "
            f"{x['accuracy']}% — "
            f"{x['cost']}💧"
            for x in attacks
        ),
        inline=False
    )

    embed.add_field(
        name="🌀 التحكم",
        value="\n".join(
            f"• {x['name']} — "
            f"{x['accuracy']}% — "
            f"{x['cost']}💧"
            for x in controls
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️ الدفاع",
        value="\n".join(
            f"• {x['name']} — "
            f"{x['accuracy']}% — "
            f"{x['cost']}💧"
            for x in defenses
        ),
        inline=False
    )

    embed.add_field(
        name="💚 العلاج",
        value="\n".join(
            f"• {x['name']} — "
            f"{x['accuracy']}% — "
            f"{x['cost']}💧"
            for x in heals
        ),
        inline=False
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 🧹 إلغاء مبارزة
# =========================================================

@bot.command(
    name="إلغاء-المبارزة"
)
@commands.has_permissions(
    administrator=True
)
async def cancel_duel(
    ctx
):

    duel = active_duels.get(
        ctx.author.id
    )

    if not duel:

        return await ctx.send(
            "❌ لا توجد مبارزة مرتبطة بك."
        )

    duel.finished = True

    active_duels.pop(
        duel.player1.id,
        None
    )

    active_duels.pop(
        duel.player2.id,
        None
    )

    if duel.message:

        try:

            await duel.message.edit(
                embed=make_embed(
                    "🛑 تم إلغاء المبارزة",
                    (
                        "تم إلغاء المبارزة بواسطة الإدارة.\n\n"
                        "❌ لم يتم تسجيل نتيجة."
                    ),
                    COLORS["danger"]
                ),
                view=None
            )

        except Exception:
            pass

    await ctx.send(
        "✅ تم إلغاء المبارزة."
    )


# =========================================================
# 🐛 معالجة الأخطاء
# =========================================================

@duel_command.error
async def duel_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.MemberNotFound
    ):

        await ctx.send(
            "❌ لم أتمكن من العثور على هذا الساحر."
        )


@cancel_duel.error
async def cancel_duel_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ هذا الأمر للإدارة فقط."
        )


@delete_event.error
async def delete_event_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.send(
            "❌ رقم الفعالية يجب أن يكون رقماً صحيحاً."
        )


# =========================================================
# 🧙 الأحداث
# =========================================================

@bot.event
async def on_ready():

    init_db()

    for guild in bot.guilds:

        ensure_guild(
            guild.id
        )

    try:

        await bot.tree.sync()

        print(
            "🪄 تم مزامنة أوامر Slash Commands بنجاح."
        )

    except Exception as e:

        print(
            f"⚠️ خطأ في مزامنة الأوامر: {e}"
        )

    print(
        f"🪄 البوت متصل بنجاح: {bot.user}"
    )


@bot.event
async def on_guild_join(
    guild: discord.Guild
):

    ensure_guild(
        guild.id
    )


# =========================================================
# 🚀 تشغيل البوت
# =========================================================

if __name__ == "__main__":

    init_db()

    token = (
        os.getenv("BOT_TOKEN")
        or os.getenv("DISCORD_TOKEN")
    )

    if not token:

        print(
            "⚠️ خطأ: لم يتم العثور على توكن البوت!"
        )

    else:

        bot.run(
            token
)
