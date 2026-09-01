import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
import os

# =========================================================
#                     إعدادات البوت
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN") or "PUT_YOUR_BOT_TOKEN_HERE"

DB_FILE = "house_cup.db"

AUTHOR_SIGNATURE = "✦ تم صنعه بواسطة سيدريك ✦"

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
    "ravenclaw": "رافنكلو",

    "سليذرين": "سليذرين",
    "slytherin": "سليذرين",
}


# =========================================================
#                     Discord Bot
# =========================================================

intents = discord.Intents.default()

intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# =========================================================
#                     أدوات عامة
# =========================================================

def apply_signature(embed: discord.Embed):
    """
    إضافة توقيع سيدريك إلى الـ Embed.
    """
    embed.set_footer(text=AUTHOR_SIGNATURE)
    return embed


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
#                     قاعدة البيانات
# =========================================================

def init_db():

    conn = get_db()
    cur = conn.cursor()

    # نقاط المنازل
    cur.execute("""
        CREATE TABLE IF NOT EXISTS house_scores (
            guild_id INTEGER NOT NULL,
            house TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, house)
        )
    """)

    # ربط الأعضاء بالمنازل
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members_houses (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            house TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    # سجل العمليات
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
        """, (
            guild_id,
            house
        ))

    conn.commit()
    conn.close()


# =========================================================
#                     الصلاحيات
# =========================================================

def can_manage_cup(member: discord.Member):

    if member.guild_permissions.administrator:
        return True

    allowed_roles = {
        "مدير الكأس",
        "مشرف الكأس",
        "House Cup",
        "Cup Manager"
    }

    for role in member.roles:

        if role.name in allowed_roles:
            return True

    return False


# =========================================================
#                     المنازل
# =========================================================

def normalize_house(name):

    if not name:
        return None

    return HOUSE_ALIASES.get(
        name.strip().lower()
    )


def house_from_roles(member: discord.Member):

    found = []

    for role in member.roles:

        house = normalize_house(role.name)

        if house and house not in found:
            found.append(house)

    if len(found) == 1:
        return found[0], None

    if len(found) > 1:

        return None, (
            "العضو لديه أكثر من رتبة منزل:\n"
            + "\n".join(
                f"• {HOUSE_ROLES[h]} {h}"
                for h in found
            )
        )

    return None, None


def house_from_database(
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
        return row["house"]

    return None


def resolve_member_house(member: discord.Member):

    # الأولوية لرتبة Discord
    house, error = house_from_roles(member)

    if error:
        return None, error

    if house:
        return house, None

    # ثم قاعدة البيانات
    house = house_from_database(
        member.guild.id,
        member.id
    )

    if house:
        return house, None

    return None, None


# =========================================================
#                     النقاط
# =========================================================

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

    # تحديث النقاط
    cur.execute("""
        UPDATE house_scores

        SET points = points + ?

        WHERE guild_id = ?
        AND house = ?
    """, (
        amount,
        guild_id,
        house
    ))

    # تسجيل العملية
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
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    log_id = cur.lastrowid

    # الحصول على الرصيد الجديد
    cur.execute("""
        SELECT points

        FROM house_scores

        WHERE guild_id = ?
        AND house = ?
    """, (
        guild_id,
        house
    ))

    row = cur.fetchone()

    new_points = row["points"]

    conn.commit()
    conn.close()

    return log_id, new_points


# =========================================================
#                     التراجع
# =========================================================

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
    """, (
        guild_id
    ))

    row = cur.fetchone()

    if not row:

        conn.close()

        return None

    # عكس العملية
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

    # وضع علامة تراجع
    cur.execute("""
        UPDATE point_logs

        SET undone = 1

        WHERE id = ?
    """, (
        row["id"],
    ))

    conn.commit()
    conn.close()

    return row


# =========================================================
#                     ترتيب المنازل
# =========================================================

def get_scores(guild_id: int):

    ensure_guild(guild_id)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT house, points

        FROM house_scores

        WHERE guild_id = ?

        ORDER BY points DESC
    """, (
        guild_id
    ))

    rows = cur.fetchall()

    conn.close()

    return rows


def create_cup_embed(
    guild: discord.Guild
):

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
        color=0xD4AF37
    )

    for index, row in enumerate(rows):

        house = row["house"]
        points = row["points"]

        emoji = HOUSE_ROLES[house]

        medal = (
            medals[index]
            if index < len(medals)
            else f"{index + 1}️⃣"
        )

        embed.add_field(
            name=(
                f"{medal} {emoji} {house}"
            ),
            value=(
                f"⭐ **{points:,} نقطة**"
            ),
            inline=False
        )

    apply_signature(embed)

    return embed


# =========================================================
#                     سجل العمليات
# =========================================================

async def show_logs(
    interaction: discord.Interaction
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *

        FROM point_logs

        WHERE guild_id = ?

        ORDER BY id DESC

        LIMIT 10
    """, (
        interaction.guild.id
    ))

    rows = cur.fetchall()

    conn.close()

    embed = discord.Embed(
        title="📜 سجل كأس المنازل",
        description=(
            "آخر 10 عمليات مسجلة"
        ),
        color=0x5865F2
    )

    if not rows:

        embed.description = (
            "لا توجد عمليات مسجلة حتى الآن."
        )

    for row in rows:

        amount = row["amount"]

        sign = (
            "+"
            if amount >= 0
            else ""
        )

        member_text = (
            f"<@{row['user_id']}>"
            if row["user_id"]
            else "🏠 للمنزل مباشرة"
        )

        undone = (
            "\n↩️ **تم التراجع عن العملية**"
            if row["undone"]
            else ""
        )

        embed.add_field(
            name=(
                f"#{row['id']} • "
                f"{HOUSE_ROLES[row['house']]} "
                f"{row['house']}"
            ),
            value=(
                f"⭐ **{sign}{amount:,} نقطة**\n"
                f"👤 {member_text}\n"
                f"📝 {row['reason']}\n"
                f"🛡️ <@{row['moderator_id']}>\n"
                f"🕐 {row['created_at']}"
                f"{undone}"
            ),
            inline=False
        )

    apply_signature(embed)

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
#                     Modal إضافة النقاط
# =========================================================

class AddPointsModal(discord.ui.Modal):

    title = "➕ إضافة نقاط"

    member = discord.ui.TextInput(
        label="ID العضو — اختياري",
        placeholder=(
            "ضع ID العضو أو اتركه فارغًا"
        ),
        required=False,
        max_length=25
    )

    house = discord.ui.TextInput(
        label="المنزل — اختياري",
        placeholder=(
            "هافلباف / جريفندور / رافنكلو / سليذرين"
        ),
        required=False,
        max_length=30
    )

    points = discord.ui.TextInput(
        label="عدد النقاط",
        placeholder="مثال: 25",
        required=True,
        max_length=10
    )

    reason = discord.ui.TextInput(
        label="سبب النقاط",
        placeholder="مثال: الفوز في المسابقة",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # ---------------------------------------------
        # التحقق من النقاط
        # ---------------------------------------------

        try:

            amount = int(
                self.points.value.strip()
            )

            if amount <= 0:
                raise ValueError

        except ValueError:

            return await interaction.response.send_message(
                "❌ عدد النقاط يجب أن يكون رقمًا أكبر من صفر.",
                ephemeral=True
            )

        # ---------------------------------------------
        # المنزل اليدوي
        # ---------------------------------------------

        selected_house = normalize_house(
            self.house.value
        )

        if self.house.value.strip() and not selected_house:

            return await interaction.response.send_message(
                "❌ اسم المنزل غير صحيح.",
                ephemeral=True
            )

        member_obj = None

        # ---------------------------------------------
        # العضو
        # ---------------------------------------------

        if self.member.value.strip():

            try:

                user_id = int(
                    self.member.value.strip()
                )

            except ValueError:

                return await interaction.response.send_message(
                    "❌ ID العضو غير صحيح.",
                    ephemeral=True
                )

            try:

                member_obj = (
                    await interaction.guild.fetch_member(
                        user_id
                    )
                )

            except discord.NotFound:

                return await interaction.response.send_message(
                    "❌ لم أجد هذا العضو في السيرفر.",
                    ephemeral=True
                )

            # محاولة معرفة المنزل
            detected_house, error = resolve_member_house(
                member_obj
            )

            if error:

                return await interaction.response.send_message(
                    f"⚠️ {error}",
                    ephemeral=True
                )

            if detected_house:

                # منع التعارض
                if (
                    selected_house
                    and
                    selected_house != detected_house
                ):

                    return await interaction.response.send_message(
                        (
                            "❌ يوجد تعارض في المنزل.\n\n"
                            f"العضو مسجل في "
                            f"**{detected_house}** "
                            f"لكن اخترت "
                            f"**{selected_house}**."
                        ),
                        ephemeral=True
                    )

                selected_house = detected_house

        # ---------------------------------------------
        # التأكد من وجود منزل
        # ---------------------------------------------

        if not selected_house:

            return await interaction.response.send_message(
                (
                    "❌ لم أستطع تحديد المنزل.\n\n"
                    "إما اختر عضوًا لديه منزل "
                    "أو اكتب اسم المنزل يدويًا."
                ),
                ephemeral=True
            )

        # ---------------------------------------------
        # تسجيل العملية
        # ---------------------------------------------

        user_id = (
            member_obj.id
            if member_obj
            else None
        )

        log_id, new_score = add_points(
            guild_id=interaction.guild.id,
            house=selected_house,
            amount=amount,
            user_id=user_id,
            moderator_id=interaction.user.id,
            reason=self.reason.value.strip()
        )

        emoji = HOUSE_ROLES[selected_house]

        embed = discord.Embed(
            title="✨ تم تسجيل النقاط",
            color=0x57F287
        )

        embed.add_field(
            name="🏠 المنزل",
            value=(
                f"{emoji} **{selected_house}**"
            ),
            inline=True
        )

        embed.add_field(
            name="⭐ النقاط",
            value=f"**+{amount:,}**",
            inline=True
        )

        if member_obj:

            embed.add_field(
                name="👤 العضو",
                value=member_obj.mention,
                inline=False
            )

        embed.add_field(
            name="📝 السبب",
            value=self.reason.value.strip(),
            inline=False
        )

        embed.add_field(
            name="🏆 رصيد المنزل",
            value=(
                f"**{new_score:,} نقطة**"
            ),
            inline=False
        )

        embed.add_field(
            name="🔖 رقم العملية",
            value=f"#{log_id}",
            inline=False
        )

        apply_signature(embed)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# =========================================================
#                     Modal خصم النقاط
# =========================================================

class RemovePointsModal(
    discord.ui.Modal
):

    title = "➖ خصم نقاط"

    member = discord.ui.TextInput(
        label="ID العضو — اختياري",
        placeholder="ضع ID العضو أو اتركه فارغًا",
        required=False,
        max_length=25
    )

    house = discord.ui.TextInput(
        label="المنزل — اختياري",
        placeholder=(
            "هافلباف / جريفندور / رافنكلو / سليذرين"
        ),
        required=False,
        max_length=30
    )

    points = discord.ui.TextInput(
        label="عدد النقاط",
        placeholder="مثال: 10",
        required=True,
        max_length=10
    )

    reason = discord.ui.TextInput(
        label="سبب الخصم",
        placeholder="مثال: مخالفة قوانين المسابقة",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            amount = int(
                self.points.value.strip()
            )

            if amount <= 0:
                raise ValueError

        except ValueError:

            return await interaction.response.send_message(
                "❌ عدد النقاط يجب أن يكون رقمًا أكبر من صفر.",
                ephemeral=True
            )

        selected_house = normalize_house(
            self.house.value
        )

        if self.house.value.strip() and not selected_house:

            return await interaction.response.send_message(
                "❌ اسم المنزل غير صحيح.",
                ephemeral=True
            )

        member_obj = None

        # ---------------------------------------------
        # العضو
        # ---------------------------------------------

        if self.member.value.strip():

            try:

                user_id = int(
                    self.member.value.strip()
                )

            except ValueError:

                return await interaction.response.send_message(
                    "❌ ID العضو غير صحيح.",
                    ephemeral=True
                )

            try:

                member_obj = (
                    await interaction.guild.fetch_member(
                        user_id
                    )
                )

            except discord.NotFound:

                return await interaction.response.send_message(
                    "❌ لم أجد هذا العضو في السيرفر.",
                    ephemeral=True
                )

            detected_house, error = resolve_member_house(
                member_obj
            )

            if error:

                return await interaction.response.send_message(
                    f"⚠️ {error}",
                    ephemeral=True
                )

            if detected_house:

                if (
                    selected_house
                    and
                    selected_house != detected_house
                ):

                    return await interaction.response.send_message(
                        "❌ المنزل المختار لا يطابق منزل العضو.",
                        ephemeral=True
                    )

                selected_house = detected_house

        # ---------------------------------------------
        # التأكد من المنزل
        # ---------------------------------------------

        if not selected_house:

            return await interaction.response.send_message(
                "❌ يجب تحديد المنزل أو عضو يمكن معرفة منزله.",
                ephemeral=True
            )

        # ---------------------------------------------
        # تنفيذ الخصم
        # ---------------------------------------------

        user_id = (
            member_obj.id
            if member_obj
            else None
        )

        log_id, new_score = add_points(
            guild_id=interaction.guild.id,
            house=selected_house,
            amount=-amount,
            user_id=user_id,
            moderator_id=interaction.user.id,
            reason=self.reason.value.strip()
        )

        emoji = HOUSE_ROLES[selected_house]

        embed = discord.Embed(
            title="⚠️ تم خصم النقاط",
            color=0xED4245
        )

        embed.add_field(
            name="🏠 المنزل",
            value=(
                f"{emoji} **{selected_house}**"
            ),
            inline=True
        )

        embed.add_field(
            name="⭐ النقاط",
            value=f"**-{amount:,}**",
            inline=True
        )

        if member_obj:

            embed.add_field(
                name="👤 العضو",
                value=member_obj.mention,
                inline=False
            )

        embed.add_field(
            name="📝 السبب",
            value=self.reason.value.strip(),
            inline=False
        )

        embed.add_field(
            name="🏆 الرصيد الحالي",
            value=(
                f"**{new_score:,} نقطة**"
            ),
            inline=False
        )

        embed.add_field(
            name="🔖 رقم العملية",
            value=f"#{log_id}",
            inline=False
        )

        apply_signature(embed)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# =========================================================
#                     لوحة كأس المنازل
# =========================================================

class CupView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # ---------------------------------------------
    # إضافة
    # ---------------------------------------------

    @discord.ui.button(
        label="إضافة نقاط",
        emoji="➕",
        style=discord.ButtonStyle.success,
        custom_id="house_cup:add"
    )
    async def add_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not can_manage_cup(
            interaction.user
        ):

            return await interaction.response.send_message(
                "❌ ليس لديك صلاحية إدارة كأس المنازل.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            AddPointsModal()
        )

    # ---------------------------------------------
    # خصم
    # ---------------------------------------------

    @discord.ui.button(
        label="خصم نقاط",
        emoji="➖",
        style=discord.ButtonStyle.danger,
        custom_id="house_cup:remove"
    )
    async def remove_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not can_manage_cup(
            interaction.user
        ):

            return await interaction.response.send_message(
                "❌ ليس لديك صلاحية إدارة كأس المنازل.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            RemovePointsModal()
        )

    # ---------------------------------------------
    # الإحصائيات
    # ---------------------------------------------

    @discord.ui.button(
        label="الترتيب",
        emoji="📊",
        style=discord.ButtonStyle.primary,
        custom_id="house_cup:ranking"
    )
    async def ranking_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            embed=create_cup_embed(
                interaction.guild
            ),
            view=CupView()
        )

    # ---------------------------------------------
    # السجل
    # ---------------------------------------------

    @discord.ui.button(
        label="السجل",
        emoji="📜",
        style=discord.ButtonStyle.secondary,
        custom_id="house_cup:logs"
    )
    async def logs_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await show_logs(
            interaction
        )

    # ---------------------------------------------
    # تحديث
    # ---------------------------------------------

    @discord.ui.button(
        label="تحديث",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="house_cup:refresh"
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            embed=create_cup_embed(
                interaction.guild
            ),
            view=CupView()
        )


# =========================================================
#                     أمر /الكأس
# =========================================================

@bot.tree.command(
    name="الكأس",
    description="عرض لوحة كأس المنازل"
)
async def cup_command(
    interaction: discord.Interaction
):

    ensure_guild(
        interaction.guild.id
    )

    await interaction.response.send_message(
        embed=create_cup_embed(
            interaction.guild
        ),
        view=CupView()
    )


# =========================================================
#                     أمر /تعيين_منزل
# =========================================================

@bot.tree.command(
    name="تعيين_منزل",
    description="تعيين منزل لعضو في قاعدة بيانات البوت"
)
@app_commands.describe(
    member="العضو",
    house="المنزل"
)
@app_commands.choices(
    house=[
        app_commands.Choice(
            name="🦁 جريفندور",
            value="جريفندور"
        ),
        app_commands.Choice(
            name="🦡 هافلباف",
            value="هافلباف"
        ),
        app_commands.Choice(
            name="🦅 رافنكلو",
            value="رافنكلو"
        ),
        app_commands.Choice(
            name="🐍 سليذرين",
            value="سليذرين"
        )
    ]
)
async def set_house(
    interaction: discord.Interaction,
    member: discord.Member,
    house: app_commands.Choice[str]
):

    if not can_manage_cup(
        interaction.user
    ):

        return await interaction.response.send_message(
            "❌ ليس لديك صلاحية.",
            ephemeral=True
        )

    selected_house = house.value

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO members_houses
        (
            guild_id,
            user_id,
            house
        )

        VALUES (?, ?, ?)

        ON CONFLICT(guild_id, user_id)

        DO UPDATE SET
            house = excluded.house
    """, (
        interaction.guild.id,
        member.id,
        selected_house
    ))

    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="🏠 تم تعيين المنزل",
        color=0xD4AF37
    )

    embed.add_field(
        name="👤 العضو",
        value=member.mention,
        inline=False
    )

    embed.add_field(
        name="🏠 المنزل",
        value=(
            f"{HOUSE_ROLES[selected_house]} "
            f"**{selected_house}**"
        ),
        inline=False
    )

    apply_signature(embed)

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
#                     أمر /تراجع
# =========================================================

@bot.tree.command(
    name="تراجع",
    description="التراجع عن آخر عملية نقاط"
)
async def undo_command(
    interaction: discord.Interaction
):

    if not can_manage_cup(
        interaction.user
    ):

        return await interaction.response.send_message(
            "❌ ليس لديك صلاحية.",
            ephemeral=True
        )

    row = undo_last_action(
        interaction.guild.id
    )

    if not row:

        return await interaction.response.send_message(
            "❌ لا توجد عملية قابلة للتراجع.",
            ephemeral=True
        )

    amount = row["amount"]

    sign = (
        "+"
        if amount >= 0
        else ""
    )

    embed = discord.Embed(
        title="↩️ تم التراجع عن العملية",
        color=0xFAA61A
    )

    embed.add_field(
        name="🔖 العملية",
        value=f"#{row['id']}",
        inline=True
    )

    embed.add_field(
        name="🏠 المنزل",
        value=(
            f"{HOUSE_ROLES[row['house']]} "
            f"{row['house']}"
        ),
        inline=True
    )

    embed.add_field(
        name="⭐ العملية الأصلية",
        value=f"{sign}{amount:,} نقطة",
        inline=False
    )

    embed.add_field(
        name="📝 السبب",
        value=row["reason"],
        inline=False
    )

    apply_signature(embed)

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
#                     أمر /السجل
# =========================================================

@bot.tree.command(
    name="السجل",
    description="عرض آخر عمليات كأس المنازل"
)
async def logs_command(
    interaction: discord.Interaction
):

    await show_logs(
        interaction
    )


# =========================================================
#                     أمر /نقاط
# =========================================================

@bot.tree.command(
    name="نقاط",
    description="عرض نقاط منزل معين"
)
@app_commands.describe(
    house="المنزل"
)
@app_commands.choices(
    house=[
        app_commands.Choice(
            name="🦁 جريفندور",
            value="جريفندور"
        ),
        app_commands.Choice(
            name="🦡 هافلباف",
            value="هافلباف"
        ),
        app_commands.Choice(
            name="🦅 رافنكلو",
            value="رافنكلو"
        ),
        app_commands.Choice(
            name="🐍 سليذرين",
            value="سليذرين"
        )
    ]
)
async def points_command(
    interaction: discord.Interaction,
    house: app_commands.Choice[str]
):

    ensure_guild(
        interaction.guild.id
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT points

        FROM house_scores

        WHERE guild_id = ?
        AND house = ?
    """, (
        interaction.guild.id,
        house.value
    ))

    row = cur.fetchone()

    conn.close()

    points = (
        row["points"]
        if row
        else 0
    )

    embed = discord.Embed(
        title="🏆 نقاط المنزل",
        color=0xD4AF37
    )

    embed.add_field(
        name="🏠 المنزل",
        value=(
            f"{HOUSE_ROLES[house.value]} "
            f"**{house.value}**"
        ),
        inline=False
    )

    embed.add_field(
        name="⭐ النقاط",
        value=f"**{points:,}**",
        inline=False
    )

    apply_signature(embed)

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
#                     تشغيل البوت
# =========================================================

@bot.event
async def on_ready():

    init_db()

    bot.add_view(
        CupView()
    )

    try:

        synced = await bot.tree.sync()

        print(
            f"تمت مزامنة "
            f"{len(synced)} أمر Slash."
        )

    except Exception as error:

        print(
            "خطأ أثناء مزامنة الأوامر:",
            error
        )

    print(
        f"🏆 تم تشغيل كأس المنازل "
        f"بواسطة {bot.user}"
    )


@bot.event
async def on_guild_join(
    guild: discord.Guild
):

    ensure_guild(
        guild.id
    )


# =========================================================
#                     بدء التشغيل
# =========================================================

if __name__ == "__main__":

    if TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":

        print(
            "❌ لم يتم وضع توكن البوت."
        )

    else:

        bot.run(TOKEN)
