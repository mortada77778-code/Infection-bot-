import discord
from discord.ext import commands
import random
import os
import sqlite3
import asyncio
from datetime import datetime


# =========================================================
# 🪄 إعدادات البوت
# =========================================================

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")

PREFIX = "!"

AUTHOR_SIGNATURE = "✦ صُنع بعناية بواسطة سيدريك 🪄"

DB_FILE = "magic_bot.db"

MAX_HP = 200

# نظام المانا الجديد
MAX_MANA = 100
START_MANA = 100

# استعادة 50% من تكلفة التعويذة
MANA_REGEN_PERCENT = 0.50

DUEL_TIMEOUT = 180

# =========================================================
# 🏰 إعدادات الغارة
# =========================================================

VILLAGE_MAX_HP = 500
RAID_DAMAGE_MIN = 15
RAID_DAMAGE_MAX = 25
RAID_COOLDOWN = 10

raid_active = False
village_hp = VILLAGE_MAX_HP

raid_attacks = {}


# =========================================================
# Discord
# =========================================================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


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
}


def make_embed(
    title,
    description="",
    color=None
):

    embed = discord.Embed(
        title=title,
        description=description,
        color=color or COLORS["magic"],
        timestamp=datetime.utcnow()
    )

    embed.set_footer(
        text=AUTHOR_SIGNATURE
    )

    return embed


# =========================================================
# 🏠 البيوت
# =========================================================

HOUSE_DATA = {

    "جريفندور": {
        "emoji": "🦁",
        "english": "Gryffindor",
        "color": 0x740909,
        "desc": "الجرأة والشجاعة والفروسية."
    },

    "هافلباف": {
        "emoji": "🦡",
        "english": "Hufflepuff",
        "color": 0xECB939,
        "desc": "الإخلاص والعدالة والعمل الجاد."
    },

    "رافنكلو": {
        "emoji": "🦅",
        "english": "Ravenclaw",
        "color": 0x0E1A40,
        "desc": "الحكمة والذكاء والإبداع."
    },

    "سليذرين": {
        "emoji": "🐍",
        "english": "Slytherin",
        "color": 0x1A472A,
        "desc": "الطموح والدهاء والقيادة."
    }
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
    "سليذيرين": "سليذرين",
    "slytherin": "سليذرين",
}


def normalize_house(name):

    if not name:
        return None

    return HOUSE_ALIASES.get(
        name.strip().lower()
    )


# =========================================================
# 🗄️ قاعدة البيانات
# =========================================================

def get_db():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()

    cur = conn.cursor()

    # -----------------------------------------
    # نقاط البيوت
    # -----------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS house_scores (

            guild_id INTEGER NOT NULL,

            house TEXT NOT NULL,

            points INTEGER NOT NULL DEFAULT 0,

            PRIMARY KEY (
                guild_id,
                house
            )
        )
    """)

    # -----------------------------------------
    # الطلاب والبيوت
    # -----------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS members_houses (

            guild_id INTEGER NOT NULL,

            user_id INTEGER NOT NULL,

            house TEXT NOT NULL,

            joined_at TEXT NOT NULL,

            PRIMARY KEY (
                guild_id,
                user_id
            )
        )
    """)

    # -----------------------------------------
    # سجل النقاط
    # -----------------------------------------

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

    # -----------------------------------------
    # إحصائيات اللاعبين
    # -----------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (

            guild_id INTEGER NOT NULL,

            user_id INTEGER NOT NULL,

            wins INTEGER NOT NULL DEFAULT 0,

            losses INTEGER NOT NULL DEFAULT 0,

            draws INTEGER NOT NULL DEFAULT 0,

            total_damage INTEGER NOT NULL DEFAULT 0,

            total_duels INTEGER NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL,

            PRIMARY KEY (
                guild_id,
                user_id
            )
        )
    """)

    # -----------------------------------------
    # سجل المبارزات
    # -----------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS duel_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            player1_id INTEGER NOT NULL,

            player2_id INTEGER NOT NULL,

            winner_id INTEGER,

            player1_damage INTEGER NOT NULL DEFAULT 0,

            player2_damage INTEGER NOT NULL DEFAULT 0,

            rounds INTEGER NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL
        )
    """)

    # -----------------------------------------
    # الفعاليات
    # -----------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            title TEXT NOT NULL,

            description TEXT NOT NULL,

            created_by INTEGER NOT NULL,

            active INTEGER NOT NULL DEFAULT 1,

            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    conn.close()


# =========================================================
# 🏠 تجهيز البيوت للسيرفر
# =========================================================

def ensure_guild(guild_id):

    conn = get_db()

    cur = conn.cursor()

    for house in HOUSE_DATA:

        cur.execute("""
            INSERT OR IGNORE INTO house_scores
            (
                guild_id,
                house,
                points
            )

            VALUES (?, ?, 0)
        """, (
            guild_id,
            house
        ))

    conn.commit()

    conn.close()


# =========================================================
# 👤 تسجيل الطالب
# =========================================================

def register_student(
    guild_id,
    user_id,
    house
):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO members_houses
        (
            guild_id,
            user_id,
            house,
            joined_at
        )

        VALUES (?, ?, ?, ?)

        ON CONFLICT(
            guild_id,
            user_id
        )

        DO UPDATE SET
            house = excluded.house
    """, (
        guild_id,
        user_id,
        house,
        datetime.utcnow().isoformat()
    ))

    conn.commit()

    conn.close()


def get_student_house(
    guild_id,
    user_id
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

    return row["house"] if row else None


# =========================================================
# 🏆 نقاط كأس المنازل
# =========================================================

def add_points(
    guild_id,
    house,
    amount,
    user_id,
    moderator_id,
    reason
):

    ensure_guild(
        guild_id
    )

    conn = get_db()

    cur = conn.cursor()

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

    cur.execute("""
        INSERT INTO point_logs
        (
            guild_id,
            house,
            amount,
            user_id,
            moderator_id,
            reason,
            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        guild_id,
        house,
        amount,
        user_id,
        moderator_id,
        reason,
        datetime.utcnow().isoformat()
    ))

    log_id = cur.lastrowid

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


def get_scores(guild_id):

    ensure_guild(
        guild_id
    )

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        SELECT house, points

        FROM house_scores

        WHERE guild_id = ?

        ORDER BY points DESC
    """, (
        guild_id,
    ))

    rows = cur.fetchall()

    conn.close()

    return rows


# =========================================================
# ↩️ التراجع
# =========================================================

def undo_last_action(guild_id):

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
        guild_id,
    ))

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
    """, (
        row["id"],
    ))

    conn.commit()

    conn.close()

    return row


# =========================================================
# 🏆 Embed الكأس
# =========================================================

def create_cup_embed(guild):

    rows = get_scores(
        guild.id
    )

    medals = [
        "🥇",
        "🥈",
        "🥉",
        "4️⃣"
    ]

    embed = make_embed(
        "🏆 كأس المنازل",

        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ **ترتيب المنازل الحالي**\n"
        "━━━━━━━━━━━━━━━━━━━━",

        COLORS["gold"]
    )

    for index, row in enumerate(rows):

        house = row["house"]

        points = row["points"]

        info = HOUSE_DATA[
            house
        ]

        medal = (
            medals[index]
            if index < len(medals)
            else f"{index + 1}️⃣"
        )

        embed.add_field(
            name=(
                f"{medal} "
                f"{info['emoji']} "
                f"{house}"
            ),

            value=(
                f"⭐ **{points:,} نقطة**"
            ),

            inline=False
        )

    return embed


# =========================================================
# ⚔️ نظام المبارزات
# =========================================================

SPELLS = {

    "expelliarmus": {
        "name": "إكسبليارموس",
        "emoji": "🪄",
        "cost": 15,
        "damage": 25,
        "type": "attack"
    },

    "stupefy": {
        "name": "ستوبفاي",
        "emoji": "💫",
        "cost": 25,
        "damage": 40,
        "type": "attack"
    },

    "confringo": {
        "name": "كونفرينغو",
        "emoji": "🔥",
        "cost": 35,
        "damage": 55,
        "type": "attack"
    },

    "reducto": {
        "name": "ريداكتو",
        "emoji": "💥",
        "cost": 30,
        "damage": 45,
        "type": "attack"
    },

    "incendio": {
        "name": "إنسينديو",
        "emoji": "🔥",
        "cost": 20,
        "damage": 30,
        "type": "attack"
    },

    "depulso": {
        "name": "ديبولسو",
        "emoji": "🌪️",
        "cost": 20,
        "damage": 30,
        "type": "attack"
    },

    "protego": {
        "name": "بروتيغو",
        "emoji": "🛡️",
        "cost": 20,
        "damage": 0,
        "type": "shield"
    },

    "episkey": {
        "name": "إبيسكي",
        "emoji": "💚",
        "cost": 25,
        "damage": 0,
        "type": "heal"
    }
}


active_duels = {}


class DuelPlayer:

    def __init__(self, user):

        self.user = user

        self.hp = MAX_HP

        self.mana = START_MANA

        self.shield = 0

        self.damage_dealt = 0

        self.spell = None


class DuelSession:

    def __init__(
        self,
        guild,
        player1,
        player2
    ):

        self.guild = guild

        self.player1 = DuelPlayer(
            player1
        )

        self.player2 = DuelPlayer(
            player2
        )

        self.round = 0

        self.finished = False

        self.message = None


    def get_player(
        self,
        user_id
    ):

        if self.player1.user.id == user_id:
            return self.player1

        if self.player2.user.id == user_id:
            return self.player2

        return None


def hp_bar(hp):

    hp = max(
        0,
        min(MAX_HP, hp)
    )

    total = 10

    filled = round(
        hp / MAX_HP * total
    )

    return (
        "🟩" * filled +
        "⬛" * (total - filled)
    )


def mana_bar(mana):

    mana = max(
        0,
        min(MAX_MANA, mana)
    )

    total = 10

    filled = round(
        mana / MAX_MANA * total
    )

    return (
        "🔵" * filled +
        "⚫" * (total - filled)
    )


def duel_embed(
    session
):

    p1 = session.player1

    p2 = session.player2

    description = (

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🧙 **{p1.user.mention}**\n"
        f"{hp_bar(p1.hp)} "
        f"`{max(0,p1.hp)}/{MAX_HP}`\n"
        f"{mana_bar(p1.mana)} "
        f"`{p1.mana}/{MAX_MANA}`\n\n"

        "⚔️ VS ⚔️\n\n"

        f"🧙 **{p2.user.mention}**\n"
        f"{hp_bar(p2.hp)} "
        f"`{max(0,p2.hp)}/{MAX_HP}`\n"
        f"{mana_bar(p2.mana)} "
        f"`{p2.mana}/{MAX_MANA}`\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        f"⚔️ الجولة: **{session.round + 1}**\n\n"

        "✨ اختاروا تعاويذكم."
    )

    return make_embed(
        "⚔️ المبارزة السحرية",
        description,
        COLORS["magic"]
    )


# =========================================================
# 🔘 زر التعويذة
# =========================================================

class SpellButton(
    discord.ui.Button
):

    def __init__(
        self,
        spell_id
    ):

        spell = SPELLS[
            spell_id
        ]

        super().__init__(
            label=spell["name"],
            emoji=spell["emoji"],
            style=discord.ButtonStyle.secondary
        )

        self.spell_id = spell_id


    async def callback(
        self,
        interaction
    ):

        view = self.view

        session = view.session

        if session.finished:

            return await interaction.response.send_message(
                "❌ انتهت المبارزة.",
                ephemeral=True
            )

        player = session.get_player(
            interaction.user.id
        )

        if not player:

            return await interaction.response.send_message(
                "❌ أنت لست طرفاً في المبارزة.",
                ephemeral=True
            )

        if player.spell:

            return await interaction.response.send_message(
                "⚠️ لقد اخترت تعويذتك بالفعل.",
                ephemeral=True
            )

        spell = SPELLS[
            self.spell_id
        ]

        if player.mana < spell["cost"]:

            return await interaction.response.send_message(
                (
                    f"🔵 لا تملك مانا كافية.\n"
                    f"التكلفة: `{spell['cost']}`"
                ),
                ephemeral=True
            )

        player.spell = self.spell_id

        await interaction.response.send_message(
            (
                f"✨ تم اختيار "
                f"**{spell['name']}**."
            ),
            ephemeral=True
        )

        if (
            session.player1.spell
            and
            session.player2.spell
        ):

            await view.execute_round()


# =========================================================
# ⚔️ واجهة المبارزة
# =========================================================

class DuelView(
    discord.ui.View
):

    def __init__(
        self,
        session
    ):

        super().__init__(
            timeout=DUEL_TIMEOUT
        )

        self.session = session

        for spell_id in SPELLS:

            self.add_item(
                SpellButton(
                    spell_id
                )
            )


    async def execute_round(
        self
    ):

        session = self.session

        if session.finished:
            return

        session.round += 1

        p1 = session.player1

        p2 = session.player2

        s1 = SPELLS[
            p1.spell
        ]

        s2 = SPELLS[
            p2.spell
        ]

        # -----------------------------------------
        # المانا
        # -----------------------------------------

        p1.mana -= s1["cost"]

        p2.mana -= s2["cost"]

        # -----------------------------------------
        # الدرع
        # -----------------------------------------

        p1.shield = (
            35
            if s1["type"] == "shield"
            else 0
        )

        p2.shield = (
            35
            if s2["type"] == "shield"
            else 0
        )

        # -----------------------------------------
        # العلاج
        # -----------------------------------------

        if s1["type"] == "heal":

            p1.hp = min(
                MAX_HP,
                p1.hp + 35
            )

        if s2["type"] == "heal":

            p2.hp = min(
                MAX_HP,
                p2.hp + 35
            )

        # -----------------------------------------
        # الضرر
        # -----------------------------------------

        damage1 = 0

        damage2 = 0

        if s1["type"] == "attack":

            damage1 = s1["damage"]

        if s2["type"] == "attack":

            damage2 = s2["damage"]

        # -----------------------------------------
        # الدرع
        # -----------------------------------------

        if p2.shield:

            damage1 = max(
                0,
                damage1 - p2.shield
            )

        if p1.shield:

            damage2 = max(
                0,
                damage2 - p1.shield
            )

        # -----------------------------------------
        # فرصة تخفيض الضرر
        # -----------------------------------------

        if damage1 and random.random() < 0.10:

            damage1 = round(
                damage1 * 0.5
            )

        if damage2 and random.random() < 0.10:

            damage2 = round(
                damage2 * 0.5
            )

        p2.hp -= damage1

        p1.hp -= damage2

        p1.damage_dealt += damage1

        p2.damage_dealt += damage2

        # -----------------------------------------
        # استعادة 50% من المانا المصروفة
        # -----------------------------------------

        p1.mana = min(
            MAX_MANA,
            p1.mana +
            round(
                s1["cost"] *
                MANA_REGEN_PERCENT
            )
        )

        p2.mana = min(
            MAX_MANA,
            p2.mana +
            round(
                s2["cost"] *
                MANA_REGEN_PERCENT
            )
        )

        # -----------------------------------------
        # النتيجة
        # -----------------------------------------

        winner = None

        if p1.hp <= 0 and p2.hp <= 0:

            session.finished = True

            update_player_stats(
                session.guild.id,
                p1.user.id,
                "draw",
                p1.damage_dealt
            )

            update_player_stats(
                session.guild.id,
                p2.user.id,
                "draw",
                p2.damage_dealt
            )

            log_duel(
                session,
                None
            )

            result = (
                f"### ⚔️ الجولة {session.round}\n\n"
                f"{p1.user.mention} "
                f"**{s1['name']}** → "
                f"`{damage1}` ضرر\n\n"
                f"{p2.user.mention} "
                f"**{s2['name']}** → "
                f"`{damage2}` ضرر\n\n"
                "🤝 **انتهت المبارزة بالتعادل!**"
            )

        elif p1.hp <= 0:

            winner = p2

        elif p2.hp <= 0:

            winner = p1

        if winner:

            session.finished = True

            loser = (
                p1
                if winner == p2
                else p2
            )

            update_player_stats(
                session.guild.id,
                winner.user.id,
                "win",
                winner.damage_dealt
            )

            update_player_stats(
                session.guild.id,
                loser.user.id,
                "loss",
                loser.damage_dealt
            )

            log_duel(
                session,
                winner.user.id
            )

            result = (
                f"### ⚔️ الجولة {session.round}\n\n"
                f"{p1.user.mention} "
                f"**{s1['name']}** → "
                f"`{damage1}` ضرر\n\n"
                f"{p2.user.mention} "
                f"**{s2['name']}** → "
                f"`{damage2}` ضرر\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏆 **الفائز:** "
                f"{winner.user.mention}\n"
                f"⚔️ **الخاسر:** "
                f"{loser.user.mention}"
            )

        else:

            result = (
                f"### ⚔️ الجولة {session.round}\n\n"
                f"{p1.user.mention} "
                f"**{s1['name']}** → "
                f"`{damage1}` ضرر\n\n"
                f"{p2.user.mention} "
                f"**{s2['name']}** → "
                f"`{damage2}` ضرر\n\n"

                f"{p1.user.mention}\n"
                f"{hp_bar(p1.hp)} "
                f"`{max(0,p1.hp)}/{MAX_HP}`\n\n"

                f"{p2.user.mention}\n"
                f"{hp_bar(p2.hp)} "
                f"`{max(0,p2.hp)}/{MAX_HP}`"
            )

        p1.spell = None

        p2.spell = None

        if session.finished:

            active_duels.pop(
                p1.user.id,
                None
            )

            active_duels.pop(
                p2.user.id,
                None
            )

            self.stop()

            await session.message.edit(
                embed=make_embed(
                    "⚔️ نتيجة المبارزة",
                    result,
                    COLORS["gold"]
                ),
                view=None
            )

            return

        await session.message.edit(
            embed=make_embed(
                "⚔️ المبارزة السحرية",
                result +
                "\n\n✨ اختاروا تعاويذ الجولة القادمة.",
                COLORS["magic"]
            ),
            view=self
        )


    async def on_timeout(
        self
    ):

        session = self.session

        if session.finished:
            return

        session.finished = True

        p1 = session.player1

        p2 = session.player2

        active_duels.pop(
            p1.user.id,
            None
        )

        active_duels.pop(
            p2.user.id,
            None
        )

        if session.message:

            await session.message.edit(
                embed=make_embed(
                    "⏰ انتهت مهلة المبارزة",
                    (
                        f"{p1.user.mention}\n"
                        "ضد\n"
                        f"{p2.user.mention}\n\n"
                        "لم يتم إكمال المبارزة."
                    ),
                    COLORS["danger"]
                ),
                view=None
            )


# =========================================================
# 📊 إحصائيات المبارزين
# =========================================================

def ensure_player(
    guild_id,
    user_id
):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO players
        (
            guild_id,
            user_id,
            created_at
        )

        VALUES (?, ?, ?)
    """, (
        guild_id,
        user_id,
        datetime.utcnow().isoformat()
    ))

    conn.commit()

    conn.close()


def get_player_stats(
    guild_id,
    user_id
):

    ensure_player(
        guild_id,
        user_id
    )

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        SELECT *

        FROM players

        WHERE guild_id = ?

        AND user_id = ?
    """, (
        guild_id,
        user_id
    ))

    row = cur.fetchone()

    conn.close()

    return row


def update_player_stats(
    guild_id,
    user_id,
    result,
    damage
):

    ensure_player(
        guild_id,
        user_id
    )

    conn = get_db()

    cur = conn.cursor()

    if result == "win":

        cur.execute("""
            UPDATE players

            SET
                wins = wins + 1,
                total_damage =
                    total_damage + ?,
                total_duels =
                    total_duels + 1

            WHERE guild_id = ?

            AND user_id = ?
        """, (
            damage,
            guild_id,
            user_id
        ))

    elif result == "loss":

        cur.execute("""
            UPDATE players

            SET
                losses = losses + 1,
                total_damage =
                    total_damage + ?,
                total_duels =
                    total_duels + 1

            WHERE guild_id = ?

            AND user_id = ?
        """, (
            damage,
            guild_id,
            user_id
        ))

    else:

        cur.execute("""
            UPDATE players

            SET
                draws = draws + 1,
                total_damage =
                    total_damage + ?,
                total_duels =
                    total_duels + 1

            WHERE guild_id = ?

            AND user_id = ?
        """, (
            damage,
            guild_id,
            user_id
        ))

    conn.commit()

    conn.close()


def log_duel(
    session,
    winner_id
):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO duel_logs
        (
            guild_id,

            player1_id,
            player2_id,

            winner_id,

            player1_damage,
            player2_damage,

            rounds,

            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session.guild.id,

        session.player1.user.id,
        session.player2.user.id,

        winner_id,

        session.player1.damage_dealt,
        session.player2.damage_dealt,

        session.round,

        datetime.utcnow().isoformat()
    ))

    conn.commit()

    conn.close()


# =========================================================
# ⚔️ بدء المبارزة
# =========================================================

@bot.command(name="مبارزة")
async def duel_command(
    ctx,
    opponent: discord.Member = None
):

    if not opponent:

        return await ctx.send(
            embed=make_embed(
                "⚔️ المبارزة",
                "`!مبارزة @الساحر`",
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

    if ctx.author.id in active_duels:

        return await ctx.send(
            "❌ أنت داخل مبارزة بالفعل."
        )

    if opponent.id in active_duels:

        return await ctx.send(
            "❌ هذا الساحر داخل مبارزة بالفعل."
        )

    session = DuelSession(
        ctx.guild,
        ctx.author,
        opponent
    )

    active_duels[
        ctx.author.id
    ] = session

    active_duels[
        opponent.id
    ] = session

    view = DuelView(
        session
    )

    message = await ctx.send(
        embed=duel_embed(
            session
        ),
        view=view
    )

    session.message = message


# =========================================================
# 📜 سجل المبارزات
# =========================================================

@bot.command(name="سجل-المبارزات")
async def duel_history(ctx):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        SELECT *

        FROM duel_logs

        WHERE guild_id = ?

        ORDER BY id DESC

        LIMIT 10
    """, (
        ctx.guild.id,
    ))

    rows = cur.fetchall()

    conn.close()

    embed = make_embed(
        "📜 سجل المبارزات",
        "",
        COLORS["gold"]
    )

    if not rows:

        embed.description = (
            "لا توجد مبارزات مسجلة."
        )

    else:

        for row in rows:

            winner = (
                f"<@{row['winner_id']}>"
                if row["winner_id"]
                else "🤝 تعادل"
            )

            embed.add_field(
                name=(
                    f"⚔️ <@{row['player1_id']}> "
                    f"ضد "
                    f"<@{row['player2_id']}>"
                ),

                value=(
                    f"🏆 الفائز: {winner}\n"
                    f"🔢 الجولات: `{row['rounds']}`\n"
                    f"💥 الضرر: "
                    f"`{row['player1_damage']}` "
                    f"- "
                    f"`{row['player2_damage']}`"
                ),

                inline=False
            )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 📊 إحصائيات
# =========================================================

@bot.command(name="احصائيات")
async def stats_command(
    ctx,
    member: discord.Member = None
):

    member = (
        member
        or ctx.author
    )

    row = get_player_stats(
        ctx.guild.id,
        member.id
    )

    house = get_student_house(
        ctx.guild.id,
        member.id
    )

    if house in HOUSE_DATA:

        house_text = (
            f"{HOUSE_DATA[house]['emoji']} "
            f"**{house}**"
        )

    else:

        house_text = "غير مسجل"

    embed = make_embed(
        "📊 إحصائيات الساحر",
        f"🧙 **{member.mention}**",
        COLORS["blue"]
    )

    embed.add_field(
        name="🏠 المنزل",
        value=house_text,
        inline=True
    )

    embed.add_field(
        name="🏆 الانتصارات",
        value=f"`{row['wins']}`",
        inline=True
    )

    embed.add_field(
        name="💀 الخسائر",
        value=f"`{row['losses']}`",
        inline=True
    )

    embed.add_field(
        name="🤝 التعادلات",
        value=f"`{row['draws']}`",
        inline=True
    )

    embed.add_field(
        name="⚔️ المبارزات",
        value=f"`{row['total_duels']}`",
        inline=True
    )

    embed.add_field(
        name="💥 الضرر",
        value=f"`{row['total_damage']}`",
        inline=True
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 🏆 ترتيب المبارزين
# =========================================================

@bot.command(name="ترتيب-المبارزين")
async def duel_ranking(ctx):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        SELECT *

        FROM players

        WHERE guild_id = ?

        ORDER BY
            wins DESC,
            total_damage DESC

        LIMIT 10
    """, (
        ctx.guild.id,
    ))

    rows = cur.fetchall()

    conn.close()

    embed = make_embed(
        "🏆 ترتيب المبارزين",
        "أقوى السحرة في المبارزات.",
        COLORS["gold"]
    )

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    if not rows:

        embed.description = (
            "لا توجد بيانات."
        )

    else:

        for index, row in enumerate(rows):

            medal = (
                medals[index]
                if index < 3
                else f"`#{index + 1}`"
            )

            embed.add_field(
                name=(
                    f"{medal} "
                    f"<@{row['user_id']}>"
                ),

                value=(
                    f"🏆 الانتصارات: "
                    f"**{row['wins']}**\n"
                    f"💥 الضرر: "
                    f"**{row['total_damage']}**"
                ),

                inline=False
            )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 🎩 قبعة التنسيق
# =========================================================

QUESTIONS = [

    (
        "ما الصفة التي تريد أن يعرفك الناس بها؟",

        [
            ("الشجاعة", "جريفندور"),
            ("الطموح", "سليذرين"),
            ("الحكمة", "رافنكلو"),
            ("الإخلاص", "هافلباف")
        ]
    ),

    (
        "وجدت باباً غامضاً، ماذا تفعل؟",

        [
            ("أفتحه فوراً", "جريفندور"),
            ("أبحث عن أفضل طريقة لاستغلاله", "سليذرين"),
            ("أحل اللغز أولاً", "رافنكلو"),
            ("أتأكد أنه آمن للجميع", "هافلباف")
        ]
    ),

    (
        "ما الشيء الذي ترفضه أكثر؟",

        [
            ("الجبن", "جريفندور"),
            ("غياب الطموح", "سليذرين"),
            ("الجهل", "رافنكلو"),
            ("الظلم", "هافلباف")
        ]
    ),

    (
        "أين تفضل قضاء وقتك؟",

        [
            ("في مغامرة", "جريفندور"),
            ("أخطط لمستقبلي", "سليذرين"),
            ("في المكتبة", "رافنكلو"),
            ("مع الأصدقاء", "هافلباف")
        ]
    )
]


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

        self.index = 0

        self.scores = {
            house: 0
            for house in HOUSE_DATA
        }

        self.build_buttons()


    def build_buttons(self):

        self.clear_items()

        question = QUESTIONS[
            self.index
        ]

        for label, house in question[1]:

            self.add_item(
                SortingButton(
                    label,
                    house
                )
            )


class SortingButton(
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
        interaction
    ):

        view = self.view

        if interaction.user.id != view.user.id:

            return await interaction.response.send_message(
                "❌ هذا الاختبار ليس لك.",
                ephemeral=True
            )

        view.scores[
            self.house
        ] += 1

        view.index += 1

        if view.index < len(QUESTIONS):

            view.build_buttons()

            question = QUESTIONS[
                view.index
            ]

            embed = make_embed(
                "🎩 قبعة التنسيق",

                f"### السؤال {view.index + 1}\n\n"
                f"**{question[0]}**",

                COLORS["gold"]
            )

            return await interaction.response.edit_message(
                embed=embed,
                view=view
            )

        winner = max(
            view.scores,
            key=view.scores.get
        )

        register_student(
            view.guild_id,
            view.user.id,
            winner
        )

        info = HOUSE_DATA[
            winner
        ]

        embed = make_embed(
            "✨ القرار النهائي",

            (
                f"🧙 الساحر: "
                f"{view.user.mention}\n\n"

                f"{info['emoji']} **البيت:**\n"
                f"## {winner}\n\n"

                f"*{info['desc']}*\n\n"

                "📜 تم تسجيل اسمك رسمياً."
            ),

            info["color"]
        )

        await interaction.response.edit_message(
            embed=embed,
            view=None
        )

        view.stop()


@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):

    if get_student_house(
        ctx.guild.id,
        ctx.author.id
    ):

        return await ctx.send(
            embed=make_embed(
                "🎩 قبعة التنسيق",
                "⚠️ تم اختيار منزلك مسبقاً.",
                COLORS["danger"]
            )
        )

    view = SortingHatView(
        ctx.author,
        ctx.guild.id
    )

    question = QUESTIONS[0]

    embed = make_embed(
        "🎩 قبعة التنسيق",

        (
            "*تستقر القبعة فوق رأسك وتبدأ في قراءة أفكارك...*\n\n"

            "### السؤال 1\n\n"

            f"**{question[0]}**"
        ),

        COLORS["gold"]
    )

    await ctx.send(
        embed=embed,
        view=view
    )


# =========================================================
# 🏆 أوامر كأس المنازل
# =========================================================

@bot.command(name="الكأس")
async def cup_command(ctx):

    await ctx.send(
        embed=create_cup_embed(
            ctx.guild
        )
    )


@bot.command(name="تراجع")
async def undo_command(ctx):

    if not can_manage_cup(
        ctx.author
    ):

        return await ctx.send(
            "❌ ليس لديك صلاحية."
        )

    row = undo_last_action(
        ctx.guild.id
    )

    if not row:

        return await ctx.send(
            "❌ لا توجد عملية قابلة للتراجع."
        )

    await ctx.send(
        embed=make_embed(
            "↩️ تم التراجع",

            (
                f"🏠 المنزل: "
                f"**{row['house']}**\n"

                f"⭐ العملية: "
                f"**{row['amount']:+,} نقطة**\n"

                f"📝 السبب: "
                f"{row['reason']}"
            ),

            COLORS["gold"]
        )
    )


def can_manage_cup(
    member
):

    if member.guild_permissions.administrator:

        return True

    allowed = {
        "مدير الكأس",
        "مشرف الكأس",
        "House Cup",
        "Cup Manager"
    }

    return any(
        role.name in allowed
        for role in member.roles
    )


@bot.command(name="إضافة-نقاط")
@commands.has_permissions(administrator=True)
async def add_points_command(
    ctx,
    user_id: int,
    points: int,
    *,
    reason: str = "بدون سبب"
):

    if points <= 0:

        return await ctx.send(
            "❌ النقاط يجب أن تكون أكبر من صفر."
        )

    try:

        member = await ctx.guild.fetch_member(
            user_id
        )

    except:

        return await ctx.send(
            "❌ لم أجد هذا الـID."
        )

    house = get_student_house(
        ctx.guild.id,
        member.id
    )

    if not house:

        return await ctx.send(
            f"❌ {member.mention} غير مسجل في منزل."
        )

    _, new_score = add_points(
        ctx.guild.id,
        house,
        points,
        member.id,
        ctx.author.id,
        reason
    )

    info = HOUSE_DATA[
        house
    ]

    await ctx.send(
        embed=make_embed(
            "✨ تم تسجيل النقاط",

            (
                f"🧙 الساحر: "
                f"{member.mention}\n"

                f"🏠 المنزل: "
                f"{info['emoji']} **{house}**\n"

                f"⭐ النقاط: "
                f"**+{points:,}**\n"

                f"🏆 الرصيد الجديد: "
                f"**{new_score:,}**\n"

                f"📝 السبب: "
                f"{reason}"
            ),

            COLORS["success"]
        )
    )


@bot.command(name="خصم-نقاط")
@commands.has_permissions(administrator=True)
async def remove_points_command(
    ctx,
    house_name: str,
    points: int,
    *,
    reason: str = "بدون سبب"
):

    house = normalize_house(
        house_name
    )

    if not house:

        return await ctx.send(
            "❌ اسم البيت غير صحيح."
        )

    if points <= 0:

        return await ctx.send(
            "❌ النقاط يجب أن تكون أكبر من صفر."
        )

    _, new_score = add_points(
        ctx.guild.id,
        house,
        -points,
        None,
        ctx.author.id,
        reason
    )

    await ctx.send(
        embed=make_embed(
            "⚠️ تم خصم النقاط",

            (
                f"🏠 البيت: "
                f"{HOUSE_DATA[house]['emoji']} "
                f"**{house}**\n"

                f"⭐ الخصم: "
                f"**-{points:,}**\n"

                f"🏆 الرصيد الحالي: "
                f"**{new_score:,}**\n"

                f"📝 السبب: "
                f"{reason}"
            ),

            COLORS["danger"]
        )
    )


# =========================================================
# 🌟 ترتيب الطلاب
# =========================================================

@bot.command(name="ترتيب-الطلاب")
async def students_leaderboard(ctx):

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

        GROUP BY user_id

        ORDER BY total_points DESC

        LIMIT 10
    """, (
        ctx.guild.id,
    ))

    rows = cur.fetchall()

    conn.close()

    embed = make_embed(
        "🌟 لوحة شرف السحرة",
        "أعلى الطلاب جمعاً للنقاط.",
        COLORS["gold"]
    )

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    if not rows:

        embed.description = (
            "لا توجد نقاط مسجلة للطلاب."
        )

    else:

        for index, row in enumerate(rows):

            medal = (
                medals[index]
                if index < 3
                else f"`#{index + 1}`"
            )

            emoji = HOUSE_DATA.get(
                row["house"],
                {}
            ).get(
                "emoji",
                "✨"
            )

            embed.add_field(
                name=(
                    f"{medal} "
                    f"<@{row['user_id']}>"
                ),

                value=(
                    f"🏠 {emoji} "
                    f"**{row['house']}**\n"

                    f"⭐ "
                    f"**{row['total_points']:,} نقطة**"
                ),

                inline=False
            )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 📜 سجل كأس المنازل
# =========================================================

@bot.command(name="السجل")
async def cup_logs(ctx):

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
        "",
        COLORS["blue"]
    )

    if not rows:

        embed.description = (
            "لا توجد عمليات مسجلة."
        )

    else:

        for row in rows:

            user = (
                f"<@{row['user_id']}>"
                if row["user_id"]
                else "🏠 البيت مباشرة"
            )

            embed.add_field(
                name=(
                    f"#{row['id']} • "
                    f"{row['house']}"
                ),

                value=(
                    f"👤 {user}\n"
                    f"⭐ `{row['amount']:+,}`\n"
                    f"📝 {row['reason']}"
                ),

                inline=False
            )

    await ctx.send(
        embed=embed
    )


# =========================================================
# ⚔️ نظام الغارات
# =========================================================

def raid_embed():

    if raid_active:

        status = "🟥 الغارة نشطة"

        color = COLORS["danger"]

    else:

        status = "🟩 لا توجد غارة"

        color = COLORS["success"]

    percent = (
        village_hp /
        VILLAGE_MAX_HP
    ) * 100

    return make_embed(
        "⚔️ الدفاع عن القرية",

        (
            f"### {status}\n\n"

            f"🏰 **صحة القرية**\n"
            f"`{max(0,village_hp)}/"
            f"{VILLAGE_MAX_HP}`\n\n"

            f"📊 الحالة: "
            f"`{percent:.0f}%`\n\n"

            "⚔️ ساهم في الدفاع عن القرية."
        ),

        color
    )


class RaidAttackButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="هجوم",
            emoji="⚔️",
            style=discord.ButtonStyle.danger
        )


    async def callback(
        self,
        interaction
    ):

        global village_hp

        global raid_active

        if not raid_active:

            return await interaction.response.send_message(
                "🟢 لا توجد غارة نشطة.",
                ephemeral=True
            )

        now = asyncio.get_event_loop().time()

        last = raid_attacks.get(
            interaction.user.id,
            0
        )

        if (
            now - last
            <
            RAID_COOLDOWN
        ):

            remaining = (
                RAID_COOLDOWN -
                (now - last)
            )

            return await interaction.response.send_message(
                (
                    f"⏳ انتظر "
                    f"`{remaining:.1f}` ثانية."
                ),
                ephemeral=True
            )

        raid_attacks[
            interaction.user.id
        ] = now

        damage = random.randint(
            RAID_DAMAGE_MIN,
            RAID_DAMAGE_MAX
        )

        village_hp = max(
            0,
            village_hp - damage
        )

        if village_hp <= 0:

            raid_active = False

            await interaction.response.edit_message(

                embed=make_embed(
                    "🏆 تم صد الغارة!",

                    (
                        f"⚔️ المساهمة الأخيرة: "
                        f"{interaction.user.mention}\n\n"

                        "🏰 **تم إنقاذ القرية!**"
                    ),

                    COLORS["success"]
                ),

                view=None
            )

            return

        await interaction.response.edit_message(
            embed=raid_embed(),
            view=self.view
        )

        await interaction.followup.send(
            (
                f"⚔️ {interaction.user.mention} "
                f"سبب **{damage} ضرر**!"
            ),
            ephemeral=True
        )


class RaidView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            RaidAttackButton()
        )


@bot.command(name="بدء-الغارة")
@commands.has_permissions(administrator=True)
async def start_raid(ctx):

    global raid_active

    global village_hp

    if raid_active:

        return await ctx.send(
            "⚠️ توجد غارة نشطة بالفعل."
        )

    raid_active = True

    village_hp = VILLAGE_MAX_HP

    raid_attacks.clear()

    await ctx.send(
        embed=raid_embed(),
        view=RaidView()
    )


@bot.command(name="حالة-الغارة")
async def raid_status(ctx):

    await ctx.send(
        embed=raid_embed()
    )


@bot.command(name="إيقاف-الغارة")
@commands.has_permissions(administrator=True)
async def stop_raid(ctx):

    global raid_active

    raid_active = False

    await ctx.send(
        embed=make_embed(
            "🛡️ انتهت الغارة",
            "تم إيقاف الغارة.",
            COLORS["success"]
        )
    )


# =========================================================
# 🎪 الفعاليات
# =========================================================

@bot.command(name="فعالية")
@commands.has_permissions(administrator=True)
async def create_event(
    ctx,
    title: str,
    *,
    description: str
):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO events
        (
            guild_id,
            title,
            description,
            created_by,
            created_at
        )

        VALUES (?, ?, ?, ?, ?)
    """, (
        ctx.guild.id,
        title,
        description,
        ctx.author.id,
        datetime.utcnow().isoformat()
    ))

    conn.commit()

    conn.close()

    await ctx.send(
        embed=make_embed(
            f"🎪 {title}",
            description,
            COLORS["magic"]
        )
    )


@bot.command(name="الفعاليات")
async def list_events(ctx):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        SELECT title, description

        FROM events

        WHERE guild_id = ?

        AND active = 1

        ORDER BY id DESC

        LIMIT 10
    """, (
        ctx.guild.id,
    ))

    rows = cur.fetchall()

    conn.close()

    embed = make_embed(
        "🎪 الفعاليات السحرية",
        "",
        COLORS["gold"]
    )

    if not rows:

        embed.description = (
            "لا توجد فعاليات نشطة."
        )

    else:

        for row in rows:

            embed.add_field(
                name=(
                    f"🎪 {row['title']}"
                ),

                value=row["description"],

                inline=False
            )

    await ctx.send(
        embed=embed
    )


# =========================================================
# 🧙 معلومات الطالب
# =========================================================

@bot.command(name="طالب")
async def student_info(
    ctx,
    member: discord.Member = None
):

    member = (
        member
        or ctx.author
    )

    house = get_student_house(
        ctx.guild.id,
        member.id
    )

    if house in HOUSE_DATA:

        info = HOUSE_DATA[
            house
        ]

        text = (
            f"{info['emoji']} **{house}**\n\n"
            f"*{info['desc']}*"
        )

    else:

        text = (
            "🎩 لم يتم تنصيب هذا الساحر بعد."
        )

    await ctx.send(
        embed=make_embed(
            "🧙 سجل الطالب",

            (
                f"الساحر: "
                f"{member.mention}\n\n"
                f"{text}"
            ),

            COLORS["blue"]
        )
    )


# =========================================================
# 📖 المساعدة
# =========================================================

@bot.command(name="مساعدة")
async def help_command(ctx):

    embed = make_embed(
        "📖 الأنظمة السحرية",

        (
            "### ⚔️ المبارزات\n"
            "`!مبارزة @عضو`\n"
            "`!سجل-المبارزات`\n"
            "`!احصائيات`\n"
            "`!ترتيب-المبارزين`\n\n"

            "### 🏆 كأس المنازل\n"
            "`!قبعة-التنسيق`\n"
            "`!الكأس`\n"
            "`!إضافة-نقاط ID عدد السبب`\n"
            "`!خصم-نقاط البيت عدد السبب`\n"
            "`!ترتيب-الطلاب`\n"
            "`!السجل`\n"
            "`!تراجع`\n\n"

            "### ⚔️ الغارات\n"
            "`!بدء-الغارة`\n"
            "`!حالة-الغارة`\n"
            "`!إيقاف-الغارة`\n\n"

            "### 🎪 الفعاليات\n"
            "`!فعالية العنوان الوصف`\n"
            "`!الفعاليات`\n\n"

            "### 🧙 الطلاب\n"
            "`!طالب`"
        ),

        COLORS["magic"]
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# ❌ أخطاء الأوامر
# =========================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        return

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        return await ctx.send(
            "❌ لا تملك الصلاحيات المطلوبة."
        )

    if isinstance(
        error,
        commands.MemberNotFound
    ):

        return await ctx.send(
            "❌ لم أتمكن من العثور على العضو."
        )

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        return await ctx.send(
            "❌ هناك معلومات ناقصة في الأمر."
        )

    print(
        f"[ERROR] {error}"
    )


# =========================================================
# 🟢 جاهزية البوت
# =========================================================

@bot.event
async def on_ready():

    init_db()

    for guild in bot.guilds:

        ensure_guild(
            guild.id
        )

    try:

        synced = await bot.tree.sync()

        print(
            f"🪄 تمت مزامنة "
            f"{len(synced)} أوامر Slash."
        )

    except Exception as error:

        print(
            f"⚠️ خطأ في Slash Commands: "
            f"{error}"
        )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        f"🪄 البوت: {bot.user}"
    )

    print(
        f"🏰 السيرفرات: {len(bot.guilds)}"
    )

    print(
        "⚔️ المبارزات: ON"
    )

    print(
        "🏆 كأس المنازل: ON"
    )

    print(
        "🛡️ الغارات: ON"
    )

    print(
        "🎪 الفعاليات: ON"
    )

    print(
        "🌐 Dashboard: خارجي"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )


@bot.event
async def on_guild_join(
    guild
):

    ensure_guild(
        guild.id
    )


# =========================================================
# 🚀 التشغيل
# =========================================================

if __name__ == "__main__":

    if not TOKEN:

        print(
            "❌ لم يتم العثور على BOT_TOKEN "
            "أو DISCORD_TOKEN."
        )

        raise SystemExit(1)

    init_db()

    bot.run(
        TOKEN
    )
