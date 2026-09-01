import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import json
import os
from datetime import datetime

# إعدادات البوت الأساسية
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ثوابت اللعبة
MAX_HP = 100
MAX_MP = 100
active_duels = {}

COLORS = {
    "gold": 0xFFD700,
    "blue": 0x1E90FF,
    "magic": 0x8A2BE2
}

def make_embed(title, description, color):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="نظام ساحة السحرة وكأس المنازل 🪄")
    return embed

def get_db():
    conn = sqlite3.connect("house_cup.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS duel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            player1_id INTEGER,
            player2_id INTEGER,
            winner_id INTEGER,
            loser_id INTEGER,
            p1_hp INTEGER,
            p2_hp INTEGER,
            rounds INTEGER,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS duel_stats (
            guild_id INTEGER,
            user_id INTEGER,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    conn.commit()
    conn.close()

@bot.event
async def on_ready():
    init_db()
    try:
        synced = await bot.tree.sync()
        print(f"تم تسجيل {len(synced)} أمر بنجاح يا برنس! البوت يعمل الآن باسم: {bot.user}")
    except Exception as e:
        print(f"خطأ في مزامنة الأوامر: {e}")

# =========================================================
# نظام المبارزات والتعويذات المتكامل
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

        # خصم التكلفة وإضافة 20 نقطة مانا ثابتة مع التأكد من عدم تجاوز الحد الأقصى 100
        self.p1_mana = min(MAX_MP, max(0, self.p1_mana - s1["cost"]) + 20)
        self.p2_mana = min(MAX_MP, max(0, self.p2_mana - s2["cost"]) + 20)

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

# تشغيل البوت عبر التوكن البيئي
bot.run(os.environ.get("BOT_TOKEN"))
