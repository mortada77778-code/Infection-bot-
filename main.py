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
# قاعدة البيانات (SQLite)
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
# أدوات JSON
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
# أوامر وعروض كأس المنازل
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
# نظام المبارزات والتعويذات (نظام المانا المحدث 100)
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
        self.p1_mana = 100
        self.p2_mana = 100
        self.p1_choice = None
        self.p2_choice = None
        self.round_count = 0

    async def process_round(self, interaction):
        self.round_count += 1
        s1 = SPELLS[self.p1_choice]
        s2 = SPELLS[self.p2_choice]

        # خصم التكلفة + إضافة 50% من قيمة الاستهلاك
        regen_1 = int(s1["cost"] * 0.5)
        regen_2 = int(s2["cost"] * 0.5)

        self.p1_mana = max(0, self.p1_mana - s1["cost"] + regen_1)
        self.p2_mana = max(0, self.p2_mana - s2["cost"] + regen_2)

        # كل جولتين يتم إضافة 25% من القيمة الكلية للمانا (25 نقطة)
        if self.round_count % 2 == 0:
            bonus_regen = int(100 * 0.25)
            self.p1_mana = min(100, self.p1_mana + bonus_regen)
            self.p2_mana = min(100, self.p2_mana + bonus_regen)

        self.p1_mana = max(0, min(100, self.p1_mana))
        self.p2_mana = max(0, min(100, self.p2_mana))

        p1_net_damage = max(0, s1["damage"] - s2["heal"])
        p2_net_damage = max(0, s2["damage"] - s1["heal"])

        self.p2_hp = max(0, self.p2_hp - p1_net_damage + s1["heal"])
        self.p1_hp = max(0, self.p1_hp - p2_net_damage + s2["heal"])

        result_desc = (
            f"⚔️ **نتيجة الجولة #{self.round_count}:**\n\n"
            f"🧙 {self.p1.mention} استخدم **{self.p1_choice}** (ضرر: {s1['damage']} | علاج: {s1['heal']})\n"
            f"🧙 {self.p2.mention} استخدم **{self.p2_choice}** (ضرر: {s2['damage']} | علاج: {s2['heal']})\n\n"
            f"❤️ **{self.p1.name}:** HP: {self.p1_hp}/{MAX_HP} | Mana: {self.p1_mana}/100\n"
            f"❤️ **{self.p2.name}:** HP: {self.p2_hp}/{MAX_HP} | Mana: {self.p2_mana}/100"
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


# =========================================================
# نظام الفعاليات (Pagination)
# =========================================================

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
            embed.description = "❌ لا توجد أي فعاليات مسجلة في السجلات حالياً."
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

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        print("⚠️ خطأ: لم يتم العثور على توكن البوت!")
    else:
        bot.run(token)
