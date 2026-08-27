import discord
from discord.ext import commands, tasks
import random
import os
import json
import asyncio
from datetime import datetime

# =========================================================
# إعدادات البوت
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

# ضع ID قناة الغارات هنا
RAID_CHANNEL_ID = 1540623521774960682

MAX_HP = 200
MAX_MP = 40

DAMAGE_PER_HIT = 10

current_hp = MAX_HP
raid_active = False

player_scores = {}
hospital_patients = set()

# جميع المبارزات النشطة
active_duels = {}


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
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )
    except OSError as e:
        print(f"خطأ أثناء حفظ {filename}: {e}")


def assign_student_house(user_id, username, house_name):
    db = load_json_file(STUDENTS_FILE)

    db[str(user_id)] = {
        "name": username,
        "house": house_name
    }

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


def footer_text(extra=None):
    if extra:
        return f"{extra} • {AUTHOR_SIGNATURE}"

    return AUTHOR_SIGNATURE


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

    return (
        "🟥" * filled +
        "⬛" * (length - filled)
    )


def get_mana_bar(mp, max_mp=40, length=10):
    mp = max(0, min(max_mp, mp))

    filled = round((mp / max_mp) * length)

    return (
        "🔵" * filled +
        "⬛" * (length - filled)
    )


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
    "جريفندور": {
        "name": "جريفندور (Gryffindor)",
        "emoji": "🦁",
        "color": 0x740909,
        "desc": "الجرأة والشجاعة والفروسية من أبرز سمات هذا البيت العريق."
    },

    "سليذيرين": {
        "name": "سليذيرين (Slytherin)",
        "emoji": "🐍",
        "color": 0x1A472A,
        "desc": "الطموح والدهاء والقدرة على القيادة تميز أبناء سليذيرين."
    },

    "رافينكلو": {
        "name": "رافينكلو (Ravenclaw)",
        "emoji": "🦅",
        "color": 0x0E1A40,
        "desc": "الحكمة والذكاء والإبداع هي الركائز الأساسية لهذا البيت."
    },

    "هافلباف": {
        "name": "هافلباف (Hufflepuff)",
        "emoji": "🦡",
        "color": 0xECB939,
        "desc": "الإخلاص والعدالة والعمل الجاد والصبر هي قيم هافلباف."
    }
}


async def display_house_students(ctx, house_key):
    db = load_json_file(STUDENTS_FILE)

    info = HOUSES[house_key]

    members = []

    for uid, data in db.items():
        if data.get("house") == house_key:
            name = data.get("name", "ساحر مجهول")
            members.append(f"• <@{uid}> — **{name}**")

    if members:
        description = (
            f"╔════════════════════╗\n"
            f"   {info['emoji']} **سجل أبناء البيت**\n"
            f"╚════════════════════╝\n\n"
            + "\n".join(members)
        )
    else:
        description = (
            f"{info['emoji']} لا يوجد أي ساحر مسجل في **{info['name']}** حتى الآن."
        )

    embed = make_embed(
        f"🏰 سجل بيت {info['name']}",
        description,
        info["color"]
    )

    embed.add_field(
        name="📜 صفات البيت",
        value=info["desc"],
        inline=False
    )

    await ctx.send(embed=embed)


# =========================================================
# نظام الغارات
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

        self.add_item(
            AttackButton()
        )


class AttackButton(discord.ui.Button):

    def __init__(self):
        super().__init__(
            label="⚔️ شارك في الدفاع",
            style=discord.ButtonStyle.danger,
            custom_id="village_defense_btn"
        )

    async def callback(self, interaction: discord.Interaction):

        global current_hp, raid_active

        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        user_name = interaction.user.display_name

        if user_id in hospital_patients:
            await interaction.followup.send(
                "🏥 **لا يمكنك المشاركة الآن**\n\n"
                "أنت موجود في المستشفى الحربي.\n"
                "يمكن لأحد الأبطال استخدام:\n"
                "`!علاج @الساحر`\n\n"
                f"{AUTHOR_SIGNATURE}",
                ephemeral=True
            )
            return

        if not raid_active:
            await interaction.followup.send(
                "🕯️ **القرية آمنة الآن**\n\n"
                "انتهت الغارة ولا توجد معركة نشطة.",
                ephemeral=True
            )
            return

        spell_name, fail_chance = random.choice(
            list(HARRY_POTTER_SPELLS.items())
        )

        roll = random.randint(1, 100)

        if roll <= fail_chance:

            fail_messages = [
                f"تشتت تركيز **{user_name}** للحظة، وانطفأت شرارة التعويذة قبل أن تبلغ هدفها.",
                f"ارتجفت العصا قليلًا، فتلاشت طاقة **{spell_name}** قبل إصابة العدو.",
                f"صدّ العدو التعويذة في اللحظة الأخيرة.",
            ]

            embed = make_embed(
                "⚠️ المعركة مستمرة",
                (
                    "تتردد أصوات السحر في أرجاء القرية...\n\n"
                    f"🖤 **صحة زعيم الغارة:** `{current_hp}/{MAX_HP}`\n"
                    f"{get_health_bar(current_hp)}\n\n"
                    f"🪄 **{user_name}** استخدم:\n"
                    f"`{spell_name}`\n\n"
                    f"❌ **فشلت التعويذة**\n"
                    f"*{random.choice(fail_messages)}*"
                ),
                COLORS["danger"]
            )

            await interaction.message.edit(
                embed=embed,
                view=VillageDefenseView()
            )

            await interaction.followup.send(
                "❌ فشلت تعويذتك هذه المرة.",
                ephemeral=True
            )

            return

        if user_id not in player_scores:
            player_scores[user_id] = {
                "name": user_name,
                "hits": 0
            }

        player_scores[user_id]["hits"] += 1
        player_scores[user_id]["name"] = user_name

        current_hp = max(
            0,
            current_hp - DAMAGE_PER_HIT
        )

        if current_hp > 0:

            embed = make_embed(
                "🚨 الغارة مستمرة",
                (
                    "╔════════════════════════╗\n"
                    "     ⚔️ **معركة الدفاع عن القرية**\n"
                    "╚════════════════════════╝\n\n"
                    "تواصل جحافل الظلام تقدمها نحو البوابات...\n\n"
                    f"🖤 **زعيم الغارة**\n"
                    f"`{current_hp}/{MAX_HP}`\n"
                    f"{get_health_bar(current_hp)}\n\n"
                    f"🪄 **{user_name}**\n"
                    f"استخدم التعويذة `{spell_name}`\n\n"
                    f"🔥 **الضرر:** `-{DAMAGE_PER_HIT}`\n\n"
                    "*لا تزال المعركة مستمرة...*"
                ),
                COLORS["danger"]
            )

            await interaction.message.edit(
                embed=embed,
                view=VillageDefenseView()
            )

            await interaction.followup.send(
                f"⚔️ أصبت زعيم الغارة بنجاح! الضرر: `{DAMAGE_PER_HIT}`",
                ephemeral=True
            )

            return

        # ============================================
        # نهاية الغارة
        # ============================================

        raid_active = False

        victim_id = None
        hospital_msg = ""

        if player_scores:
            all_fighters = list(player_scores.keys())
            victim_id = random.choice(all_fighters)

            hospital_patients.add(victim_id)

            victim_name = player_scores[victim_id].get(
                "name",
                "مقاتل مجهول"
            )

            hospital_msg = (
                f"\n🏥 **إصابة ميدانية:**\n"
                f"أصيب **{victim_name}** ونُقل إلى المستشفى الحربي.\n"
                f"يمكن علاجه باستخدام `!علاج @الساحر`."
            )

        participants_list = []

        sorted_players = sorted(
            player_scores.items(),
            key=lambda x: x[1]["hits"],
            reverse=True
        )

        for rank, (pid, pdata) in enumerate(sorted_players, start=1):

            participants_list.append(
                f"**{rank}.** <@{pid}> — "
                f"⚔️ `{pdata['hits']}` ضربة "
                f"🔥 `{pdata['hits'] * DAMAGE_PER_HIT}` ضرر"
            )

        description = (
            "╔════════════════════════╗\n"
            "      🏆 **النصر العظيم**\n"
            "╚════════════════════════╝\n\n"
            "انطفأت راية الغارة، وسقط زعيمها.\n"
            "لقد نجح أبطال القرية في صد الهجوم!\n\n"
            "📜 **سجل الأبطال**\n\n"
            + "\n".join(participants_list)
            + "\n"
            + hospital_msg
            + "\n\n"
            "📊 استخدم `!صدارة-الغارة` لعرض سجل أبطال الغارة."
        )

        embed = make_embed(
            "🏆 انتهت الغارة — انتصار الأبطال",
            description,
            COLORS["gold"]
        )

        embed.add_field(
            name="⚔️ الضربة الحاسمة",
            value=f"**{user_name}**",
            inline=True
        )

        embed.add_field(
            name="💀 صحة الزعيم",
            value="`0 / 200`",
            inline=True
        )

        await interaction.message.edit(
            embed=embed,
            view=None
        )

        await interaction.followup.send(
            "🏆 **انتصرت القرية!**",
            ephemeral=True
        )


async def send_raid(channel):

    global current_hp
    global raid_active
    global player_scores

    if raid_active:
        return False

    current_hp = MAX_HP
    raid_active = True
    player_scores.clear()

    embed = make_embed(
        "🚨 إنذار سحري — غارة على القرية",
        (
            "╔════════════════════════╗\n"
            "       ⚠️ **خطر داهم**\n"
            "╚════════════════════════╝\n\n"
            "ظهرت قوى مظلمة عند حدود القرية، "
            "وتتقدم نحو البوابات بسرعة.\n\n"
            f"🖤 **زعيم الغارة**\n"
            f"`{current_hp}/{MAX_HP}`\n"
            f"{get_health_bar(current_hp)}\n\n"
            "⚔️ **أي ساحر قادر على القتال يمكنه المشاركة.**\n\n"
            "*اضغط الزر أسفل هذا الإعلان وأطلق تعويذتك!*"
        ),
        COLORS["danger"]
    )

    await channel.send(
        embed=embed,
        view=VillageDefenseView()
    )

    return True


@bot.command(name="هجوم")
async def start_raid_command(ctx):

    if raid_active:
        await ctx.send(
            embed=make_embed(
                "⚠️ هناك غارة قائمة بالفعل",
                "لا يمكن بدء غارة جديدة بينما المعركة الحالية مستمرة.",
                COLORS["danger"]
            )
        )
        return

    await send_raid(ctx.channel)


# =========================================================
# المستشفى
# =========================================================

@bot.command(name="علاج")
async def cure_hospital_patient(ctx, member: discord.Member = None):

    if member is None:
        await ctx.send(
            embed=make_embed(
                "🏥 المستشفى الحربي",
                "يرجى تحديد الساحر الذي تريد علاجه.\n\n"
                "مثال:\n"
                "`!علاج @الساحر`",
                COLORS["success"]
            )
        )
        return

    if member.id in hospital_patients:

        hospital_patients.remove(member.id)

        embed = make_embed(
            "💚 تم العلاج بنجاح",
            (
                f"🪄 **{ctx.author.display_name}**\n"
                "استخدم مهاراته السحرية لعلاج:\n\n"
                f"🧙 **{member.display_name}**\n\n"
                "✨ عاد الساحر إلى صفوف الأبطال."
            ),
            COLORS["success"]
        )

        await ctx.send(embed=embed)

    else:

        await ctx.send(
            embed=make_embed(
                "🔮 لا توجد إصابة",
                f"الساحر **{member.display_name}** ليس مسجلًا في المستشفى الحربي.",
                COLORS["blue"]
            )
        )


@bot.command(name="المصابين")
async def list_hospital_patients(ctx):

    if not hospital_patients:
        await ctx.send(
            embed=make_embed(
                "🏥 المستشفى الحربي",
                "✨ المستشفى خالٍ من الإصابات.\n\n"
                "جميع الأبطال في الميدان.",
                COLORS["success"]
            )
        )
        return

    report = []

    for pid in hospital_patients:
        report.append(f"🛏️ <@{pid}>")

    embed = make_embed(
        "🏥 سجل المصابين",
        (
            "السحرة الموجودون حاليًا في المستشفى:\n\n"
            + "\n".join(report)
            + "\n\n"
            "🪄 استخدم:\n"
            "`!علاج @الساحر`"
        ),
        COLORS["danger"]
    )

    await ctx.send(embed=embed)


# =========================================================
# صدارة الغارات
# =========================================================

@bot.command(name="صدارة-الغارة")
async def raid_leaderboard(ctx):

    if not player_scores:

        await ctx.send(
            embed=make_embed(
                "📜 سجل أبطال الغارة",
                "لا توجد نتائج مسجلة للغارة الحالية.",
                COLORS["gold"]
            )
        )
        return

    sorted_players = sorted(
        player_scores.values(),
        key=lambda x: x["hits"],
        reverse=True
    )

    medals = ["🥇", "🥈", "🥉"]

    lines = []

    for index, player in enumerate(sorted_players[:10]):

        medal = (
            medals[index]
            if index < len(medals)
            else f"**#{index + 1}**"
        )

        lines.append(
            f"{medal} **{player['name']}**\n"
            f"   ⚔️ {player['hits']} ضربات "
            f"• 🔥 {player['hits'] * DAMAGE_PER_HIT} ضرر"
        )

    embed = make_embed(
        "🏆 صدارة أبطال القرية",
        "\n\n".join(lines),
        COLORS["gold"]
    )

    await ctx.send(embed=embed)


# =========================================================
# المبارزات (معدلة لتوازن المانا)
# =========================================================

SPELLS_DATABASE = {

    "expelliarmus": {
        "name": "Expelliarmus",
        "display": "🪄 Expelliarmus · 4 MP",
        "mana": 4,
        "damage": 20,
        "fail": 10,
        "type": "attack"
    },

    "stupefy": {
        "name": "Stupefy",
        "display": "⚡ Stupefy · 7 MP",
        "mana": 7,
        "damage": 35,
        "fail": 20,
        "type": "attack"
    },

    "confringo": {
        "name": "Confringo",
        "display": "💥 Confringo · 10 MP",
        "mana": 10,
        "damage": 45,
        "fail": 25,
        "type": "attack"
    },

    "reducto": {
        "name": "Reducto",
        "display": "🔨 Reducto · 8 MP",
        "mana": 8,
        "damage": 38,
        "fail": 22,
        "type": "attack"
    },

    "protego": {
        "name": "Protego",
        "display": "🛡️ Protego · 5 MP",
        "mana": 5,
        "shield": 15,
        "fail": 8,
        "type": "defense"
    },

    "episkey": {
        "name": "Episkey",
        "display": "💚 Episkey · 7 MP",
        "mana": 7,
        "heal": 20,
        "fail": 10,
        "type": "heal"
    },

    "incendio": {
        "name": "Incendio",
        "display": "🔥 Incendio · 8 MP",
        "mana": 8,
        "damage": 33,
        "fail": 18,
        "type": "attack"
    },

    "depulso": {
        "name": "Depulso",
        "display": "💨 Depulso · 5 MP",
        "mana": 5,
        "damage": 25,
        "fail": 12,
        "type": "attack"
    }
}


DUEL_FLAVOR_MESSAGES = {

    "attack_hit": [
        "اصطدمت الطاقة السحرية بالهدف بقوة واهتزت أرجاء القاعة!",
        "اندفعت موجة سحرية عبر القاعة قبل أن تصيب الخصم!",
        "انفجرت شرارة سحرية عند نقطة الاصطدام!"
    ],

    "shield_up": [
        "توهجت العصا وتشكل حاجز سحري متين حول الساحر!",
        "ارتفع درع من الطاقة أمام الساحر وامتص الهجمات القادمة!"
    ],

    "heal_magic": [
        "انتشر ضوء أخضر هادئ وأعاد جزءًا من الطاقة المفقودة!",
        "استقرت طاقة الساحر وعادت بعض حيويته!"
    ],

    "spell_fail": [
        "تطايرت شرارات ضعيفة وتلاشت التعويذة قبل اكتمالها.",
        "تشتت التركيز للحظة، وفشلت التعويذة في الظهور بالشكل المطلوب."
    ]
}


class SpellSelectionView(discord.ui.View):

    def __init__(self, duel_session):

        super().__init__(timeout=60)

        self.duel_session = duel_session

        spell_keys = random.sample(
            list(SPELLS_DATABASE.keys()),
            min(6, len(SPELLS_DATABASE))
        )

        for key in spell_keys:
            self.add_item(
                SpellButton(
                    key,
                    SPELLS_DATABASE[key]
                )
            )

    async def on_timeout(self):

        if self.duel_session.finished:
            return

        self.duel_session.finished = True

        for item in self.children:
            item.disabled = True

        try:

            await self.duel_session.message.edit(
                embed=make_embed(
                    "⌛ انتهت مهلة المبارزة",
                    (
                        "لم يتم اختيار التعويذات خلال الوقت المحدد.\n\n"
                        "⚔️ تم إلغاء الجولة وإنهاء المبارزة."
                    ),
                    COLORS["silver"]
                ),
                view=None
            )

        except Exception:
            pass

        self.duel_session.cleanup()


class SpellButton(discord.ui.Button):

    def __init__(self, key, spell):

        super().__init__(
            label=spell["display"],
            style=discord.ButtonStyle.secondary
        )

        self.spell_key = key
        self.spell_data = spell

    async def callback(self, interaction: discord.Interaction):

        session = self.view.duel_session

        if session.finished:
            await interaction.response.send_message(
                "⌛ انتهت هذه المبارزة.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        if user_id not in [session.p1.id, session.p2.id]:

            await interaction.response.send_message(
                "❌ هذه قاعة مبارزة خاصة بالساحرين المشاركين فقط.",
                ephemeral=True
            )
            return

        if user_id == session.p1.id:

            p_data = session.p1_data

            if session.p1_choice is not None:
                await interaction.response.send_message(
                    "⚠️ لقد اخترت تعويذتك بالفعل.",
                    ephemeral=True
                )
                return

            session.p1_choice = self.spell_key

        else:

            p_data = session.p2_data

            if session.p2_choice is not None:
                await interaction.response.send_message(
                    "⚠️ لقد اخترت تعويذتك بالفعل.",
                    ephemeral=True
                )
                return

            session.p2_choice = self.spell_key

        if p_data["mp"] < self.spell_data["mana"]:

            if user_id == session.p1.id:
                session.p1_choice = None
            else:
                session.p2_choice = None

            await interaction.response.send_message(
                "🔮 **ماناك غير كافية!**\n\n"
                f"تحتاج إلى `{self.spell_data['mana']} MP` "
                f"بينما لديك `{p_data['mp']} MP`.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "✓ **تم تسجيل تعويذتك بنجاح.**",
            ephemeral=True
        )

        await session.update_status_message()

        if session.p1_choice and session.p2_choice:

            self.view.stop()

            await session.execute_round()


class DuelSession:

    def __init__(self, ctx, p1, p2):

        self.ctx = ctx

        self.p1 = p1
        self.p2 = p2

        self.p1_data = {
            "hp": 200,
            "mp": 40,
            "shield": 0
        }

        self.p2_data = {
            "hp": 200,
            "mp": 40,
            "shield": 0
        }

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

            f"### 🧙 {self.p1.display_name}\n"
            f"{player_status(self.p1.display_name, self.p1_data)}\n\n"

            f"## ⚔️ VS ⚔️\n\n"

            f"### 🧙 {self.p2.display_name}\n"
            f"{player_status(self.p2.display_name, self.p2_data)}\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n\n"

            f"✨ **حالة الجولة**\n{status_text}"
        )

        embed = make_embed(
            "⚔️ قاعة المبارزات السحرية الكبرى",
            description,
            COLORS["magic"]
        )

        return embed

    async def start_duel(self):

        self.register()

        embed = self.build_main_embed(
            "🪄 يختار كل ساحر تعويذته..."
        )

        view = SpellSelectionView(self)

        self.message = await self.ctx.send(
            embed=embed,
            view=view
        )

    async def update_status_message(self):

        if not self.message:
            return

        p1_status = (
            "✓ تم اختيار التعويذة"
            if self.p1_choice
            else "⏳ في انتظار الاختيار"
        )

        p2_status = (
            "✓ تم اختيار التعويذة"
            if self.p2_choice
            else "⏳ في انتظار الاختيار"
        )

        status = (
            f"🧙 **{self.p1.display_name}:** {p1_status}\n"
            f"🧙 **{self.p2.display_name}:** {p2_status}"
        )

        try:

            await self.message.edit(
                embed=self.build_main_embed(status)
            )

        except discord.HTTPException:
            pass

    async def execute_round(self):

        async with self.lock:

            if self.finished:
                return

            if not self.p1_choice or not self.p2_choice:
                return

            # تجدد المانا في بداية الجولة (بمعدل 12 MP لضمان استمرارية القتال)
            self.p1_data["mp"] = min(
                MAX_MP,
                self.p1_data["mp"] + 12
            )

            self.p2_data["mp"] = min(
                MAX_MP,
                self.p2_data["mp"] + 12
            )

            s1 = SPELLS_DATABASE[self.p1_choice]
            s2 = SPELLS_DATABASE[self.p2_choice]

            self.p1_data["mp"] -= s1["mana"]
            self.p2_data["mp"] -= s2["mana"]

            p1_result = ""
            p2_result = ""

            flavor_picks = []

            # =============================================
            # تنفيذ تعويذة اللاعب الأول
            # =============================================

            p1_fail = random.randint(1, 100) <= s1["fail"]

            if p1_fail:

                p1_result = (
                    f"❌ `{s1['name']}` فشلت — "
                    "لم يحدث تأثير."
                )

                flavor_picks.append(
                    random.choice(
                        DUEL_FLAVOR_MESSAGES["spell_fail"]
                    )
                )

            else:

                if s1["type"] == "attack":

                    damage = s1["damage"]

                    absorbed = min(
                        self.p2_data["shield"],
                        damage
                    )

                    actual_damage = damage - absorbed

                    self.p2_data["shield"] -= absorbed
                    self.p2_data["hp"] -= actual_damage

                    p1_result = (
                        f"✨ `{s1['name']}` نجحت\n"
                        f"🔥 الضرر الأساسي: `{damage}`\n"
                        f"🛡️ امتص الدرع: `{absorbed}`\n"
                        f"💥 الضرر الفعلي: `{actual_damage}`"
                    )

                    flavor_picks.append(
                        random.choice(
                            DUEL_FLAVOR_MESSAGES["attack_hit"]
                        )
                    )

                elif s1["type"] == "defense":

                    self.p1_data["shield"] = s1["shield"]

                    p1_result = (
                        f"🛡️ `{s1['name']}` نجحت\n"
                        f"قوة الدرع: `{s1['shield']}`"
                    )

                    flavor_picks.append(
                        random.choice(
                            DUEL_FLAVOR_MESSAGES["shield_up"]
                        )
                    )

                elif s1["type"] == "heal":

                    old_hp = self.p1_data["hp"]

                    self.p1_data["hp"] = min(
                        MAX_HP,
                        self.p1_data["hp"] + s1["heal"]
                    )

                    healed = self.p1_data["hp"] - old_hp

                    p1_result = (
                        f"💚 `{s1['name']}` نجحت\n"
                        f"الشفاء الفعلي: `+{healed} HP`"
                    )

                    flavor_picks.append(
                        random.choice(
                            DUEL_FLAVOR_MESSAGES["heal_magic"]
                        )
                    )

            # =============================================
            # تنفيذ تعويذة اللاعب الثاني
            # =============================================

            p2_fail = random.randint(1, 100) <= s2["fail"]

            if p2_fail:

                p2_result = (
                    f"❌ `{s2['name']}` فشلت — "
                    "لم يحدث تأثير."
                )

                flavor_picks.append(
                    random.choice(
                        DUEL_FLAVOR_MESSAGES["spell_fail"]
                    )
                )

            else:

                if s2["type"] == "attack":

                    damage = s2["damage"]

                    absorbed = min(
                        self.p1_data["shield"],
                        damage
                    )

                    actual_damage = damage - absorbed

                    self.p1_data["shield"] -= absorbed
                    self.p1_data["hp"] -= actual_damage

                    p2_result = (
                        f"✨ `{s2['name']}` نجحت\n"
                        f"🔥 الضرر الأساسي: `{damage}`\n"
                        f"🛡️ امتص الدرع: `{absorbed}`\n"
                        f"💥 الضرر الفعلي: `{actual_damage}`"
                    )

                    flavor_picks.append(
                        random.choice(
                            DUEL_FLAVOR_MESSAGES["attack_hit"]
                        )
                    )

                elif s2["type"] == "defense":

                    self.p2_data["shield"] = s2["shield"]

                    p2_result = (
                        f"🛡️ `{s2['name']}` نجحت\n"
                        f"قوة الدرع: `{s2['shield']}`"
                    )

                    flavor_picks.append(
                        random.choice(
                            DUEL_FLAVOR_MESSAGES["shield_up"]
                        )
                    )

                elif s2["type"] == "heal":

                    old_hp = self.p2_data["hp"]

                    self.p2_data["hp"] = min(
                        MAX_HP,
                        self.p2_data["hp"] + s2["heal"]
                    )

                    healed = self.p2_data["hp"] - old_hp

                    p2_result = (
                        f"💚 `{s2['name']}` نجحت\n"
                        f"الشفاء الفعلي: `+{healed} HP`"
                    )

                    flavor_picks.append(
                        random.choice(
                            DUEL_FLAVOR_MESSAGES["heal_magic"]
                        )
                    )

            # =============================================
            # حماية القيم
            # =============================================

            self.p1_data["hp"] = max(
                0,
                min(MAX_HP, self.p1_data["hp"])
            )

            self.p2_data["hp"] = max(
                0,
                min(MAX_HP, self.p2_data["hp"])
            )

            self.p1_data["shield"] = max(
                0,
                self.p1_data["shield"]
            )

            self.p2_data["shield"] = max(
                0,
                self.p2_data["shield"]
            )

            active_flavor = (
                random.choice(flavor_picks)
                if flavor_picks
                else "ترددت أصداء السحر في أنحاء القاعة."
            )

            result_description = (
                f"## ⚔️ الجولة {self.round_num:02d}\n\n"

                f"🧙 **{self.p1.display_name}**\n"
                f"🪄 `{s1['name']}`\n\n"

                f"🧙 **{self.p2.display_name}**\n"
                f"🪄 `{s2['name']}`\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"💬 *{active_flavor}*\n\n"

                "### ✨ نتائج الاشتباك\n\n"

                f"**{self.p1.display_name}**\n"
                f"{p1_result}\n\n"

                f"**{self.p2.display_name}**\n"
                f"{p2_result}\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"❤️ **{self.p1.display_name}:** "
                f"`{self.p1_data['hp']}/200`\n"

                f"❤️ **{self.p2.display_name}:** "
                f"`{self.p2_data['hp']}/200`\n\n"

                "🔮 تجددت المانا في بداية هذه الجولة."
            )

            embed = make_embed(
                "⚡ كشف التعويذات — نتائج الجولة",
                result_description,
                COLORS["gold"]
            )

            # =============================================
            # تحديد نتيجة المبارزة
            # =============================================

            p1_dead = self.p1_data["hp"] <= 0
            p2_dead = self.p2_data["hp"] <= 0

            if p1_dead or p2_dead:

                self.finished = True

                if p1_dead and p2_dead:

                    result_title = "⚖️ تعادل أسطوري"

                    result_text = (
                        "\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
                        "⚖️ **سقط الساحران في الجولة نفسها!**\n\n"
                        "انتهت المبارزة بالتعادل.\n"
                        "لم يتم تسجيل انتصار لأي طرف."
                    )

                    add_result(
                        self.p1.id,
                        self.p1.display_name,
                        "draw"
                    )

                    add_result(
                        self.p2.id,
                        self.p2.display_name,
                        "draw"
                    )

                    embed.title = result_title
                    embed.description += result_text

                else:

                    winner = (
                        self.p1
                        if not p1_dead
                        else self.p2
                    )

                    loser = (
                        self.p2
                        if winner.id == self.p1.id
                        else self.p1
                    )

                    add_result(
                        winner.id,
                        winner.display_name,
                        "win"
                    )

                    result_text = (
                        "\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
                        "👑 **بطل الحلبة**\n\n"
                        f"🏆 {winner.mention}\n\n"
                        f"هُزم الساحر **{loser.display_name}**.\n\n"
                        "✨ تم تسجيل الانتصار في سجل الشرف."
                    )

                    embed.title = "🏆 حسمت المبارزة السحرية"
                    embed.description += result_text

                try:

                    if self.message:
                        await self.message.edit(
                            embed=embed,
                            view=None
                        )

                except discord.HTTPException:
                    pass

                self.cleanup()

                return

            # =============================================
            # الجولة التالية
            # =============================================

            try:

                if self.message:
                    await self.message.edit(
                        embed=embed,
                        view=None
                    )

            except discord.HTTPException:
                pass

            self.round_num += 1

            self.p1_choice = None
            self.p2_choice = None

            await asyncio.sleep(2)

            if self.finished:
                return

            next_embed = self.build_main_embed(
                "✨ الجولة الجديدة بدأت — اختر تعويذتك."
            )

            next_view = SpellSelectionView(self)

            try:

                self.message = await self.ctx.send(
                    embed=next_embed,
                    view=next_view
                )

            except discord.HTTPException:

                self.finished = True
                self.cleanup()


# =========================================================
# سجل المبارزات
# =========================================================

def load_leaderboard():
    return load_json_file(LEADERBOARD_FILE)


def save_leaderboard(data):
    save_json_file(
        LEADERBOARD_FILE,
        data
    )


def add_result(user_id, username, result):

    db = load_leaderboard()

    uid = str(user_id)

    if uid not in db:

        db[uid] = {
            "name": username,
            "wins": 0,
            "draws": 0
        }

    db[uid].setdefault("wins", 0)
    db[uid].setdefault("draws", 0)

    db[uid]["name"] = username

    if result == "win":
        db[uid]["wins"] += 1

    elif result == "draw":
        db[uid]["draws"] += 1

    save_leaderboard(db)


# =========================================================
# أمر المبارزة
# =========================================================

@bot.command(name="مبارزة")
async def duel_command(ctx, member: discord.Member = None):

    if member is None:

        await ctx.send(
            embed=make_embed(
                "⚔️ قاعة المبارزات",
                "يرجى تحديد الساحر الذي تريد مبارزته.\n\n"
                "مثال:\n"
                "`!مبارزة @الساحر`",
                COLORS["magic"]
            )
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            embed=make_embed(
                "⚠️ تعذر بدء المبارزة",
                "لا يمكنك مبارزة نفسك.",
                COLORS["danger"]
            ),
            delete_after=10
        )

        return

    if member.bot:

        await ctx.send(
            embed=make_embed(
                "⚠️ تعذر بدء المبارزة",
                "البوتات لا تدخل قاعة المبارزات.",
                COLORS["danger"]
            ),
            delete_after=10
        )

        return

    if ctx.author.id in active_duels:

        await ctx.send(
            embed=make_embed(
                "⚠️ لديك مبارزة قائمة",
                "يجب أن تنتهي مبارزتك الحالية أولًا.",
                COLORS["danger"]
            ),
            delete_after=10
        )

        return

    if member.id in active_duels:

        await ctx.send(
            embed=make_embed(
                "⚠️ الساحر مشغول",
                f"**{member.display_name}** موجود بالفعل في مبارزة أخرى.",
                COLORS["danger"]
            ),
            delete_after=10
        )

        return

    session = DuelSession(
        ctx,
        ctx.author,
        member
    )

    await session.start_duel()


# =========================================================
# صدارة المبارزات
# =========================================================

@bot.command(name="صدارة-المبارزات")
async def leaderboard_command(ctx):

    db = load_leaderboard()

    if not db:

        await ctx.send(
            embed=make_embed(
                "📜 سجل حلبة المبارزات",
                "لا توجد انتصارات مسجلة حتى الآن.",
                COLORS["gold"]
            )
        )

        return

    sorted_players = sorted(
        db.values(),
        key=lambda x: (
            x.get("wins", 0),
            -x.get("draws", 0)
        ),
        reverse=True
    )[:10]

    lines = []

    medals = ["🥇", "🥈", "🥉"]

    for index, player in enumerate(sorted_players):

        medal = (
            medals[index]
            if index < 3
            else f"**#{index + 1}**"
        )

        wins = player.get("wins", 0)
        draws = player.get("draws", 0)

        lines.append(
            f"{medal} **{player.get('name', 'ساحر')}**\n"
            f"   🏆 `{wins}` انتصار "
            f"• ⚖️ `{draws}` تعادل"
        )

    embed = make_embed(
        "🏆 سجل شرف حلبة المبارزات",
        "\n\n".join(lines),
        COLORS["gold"]
    )

    await ctx.send(embed=embed)


# =========================================================
# قبعة التنسيق
# =========================================================

@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):

    embed = make_embed(
        "🎩 قبعة التنسيق",
        (
            "╔════════════════════╗\n"
            "      🎩 **قبعة التنسيق**\n"
            "╚════════════════════╝\n\n"
            "*تسود القاعة لحظة صمت...*\n\n"
            "تتأمل القبعة شخصية الساحر، "
            "ثم تبدأ في التمتمة بكلمات غامضة...\n\n"
            "⏳ **جارٍ اتخاذ القرار...**"
        ),
        0x8B5A2B
    )

    msg = await ctx.send(embed=embed)

    await asyncio.sleep(3)

    house_key = random.choice(
        list(HOUSES.keys())
    )

    assign_student_house(
        ctx.author.id,
        ctx.author.name,
        house_key
    )

    info = HOUSES[house_key]

    final_embed = make_embed(
        "✨ القرار النهائي لقبعة التنسيق",
        (
            "╔════════════════════╗\n"
            "      🎩 **تم الاختيار**\n"
            "╚════════════════════╝\n\n"

            f"🧙 **الساحر:** {ctx.author.mention}\n\n"

            f"{info['emoji']} **البيت:**\n"
            f"## {info['name']}\n\n"

            f"*{info['desc']}*\n\n"

            "📜 تم تسجيل اسمك رسميًا في سجلات البيت."
        ),
        info["color"]
    )

    await msg.edit(
        embed=final_embed
    )


# =========================================================
# عرض البيوت
# =========================================================

@bot.command(name="عرض_جريفندور")
async def show_gryffindor(ctx):
    await display_house_students(
        ctx,
        "جريفندور"
    )


@bot.command(name="عرض_سليذيرين")
async def show_slytherin(ctx):
    await display_house_students(
        ctx,
        "سليذيرين"
    )


@bot.command(name="عرض_رافينكلو")
async def show_ravenclaw(ctx):
    await display_house_students(
        ctx,
        "رافينكلو"
    )


@bot.command(name="عرض_هافلباف")
async def show_hufflepuff(ctx):
    await display_house_students(
        ctx,
        "هافلباف"
    )


# =========================================================
# الفعاليات السحرية
# =========================================================

EVENTS_FILE = "magic_events.json"


class MagicEventModal(
    discord.ui.Modal,
    title="✨ إنشاء فعالية سحرية"
):

    event_name = discord.ui.TextInput(
        label="اسم الفعالية",
        placeholder="مثال: بطولة السحر الكبرى",
        required=True,
        max_length=100
    )

    referee = discord.ui.TextInput(
        label="الحكم",
        placeholder="اسم الحكم أو منشنه",
        required=True,
        max_length=50
    )

    participants = discord.ui.TextInput(
        label="المشاركون",
        placeholder="أسماء أو منشن المشاركين",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    winner = discord.ui.TextInput(
        label="الفائز — اختياري",
        placeholder="اتركه فارغًا إذا لم تنتهِ الفعالية",
        required=False,
        max_length=50
    )

    presenter = discord.ui.TextInput(
        label="المقدم",
        placeholder="اسم مقدم الفعالية",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):

        db = load_json_file(EVENTS_FILE)

        event_name = self.event_name.value.strip()

        db[event_name] = {
            "referee": self.referee.value.strip(),
            "participants": self.participants.value.strip(),
            "winner": (
                self.winner.value.strip()
                if self.winner.value.strip()
                else "لم يُحدد بعد"
            ),
            "presenter": self.presenter.value.strip(),
            "author": interaction.user.name
        }

        save_json_file(
            EVENTS_FILE,
            db
        )

        embed = make_embed(
            f"📜 {event_name}",
            (
                "╔════════════════════╗\n"
                "      ✨ **فعالية سحرية**\n"
                "╚════════════════════╝"
            ),
            COLORS["gold"]
        )

        embed.add_field(
            name="🎙️ المقدم",
            value=self.presenter.value,
            inline=True
        )

        embed.add_field(
            name="⚖️ الحكم",
            value=self.referee.value,
            inline=True
        )

        embed.add_field(
            name="👥 المشاركون",
            value=self.participants.value,
            inline=False
        )

        embed.add_field(
            name="🏆 الفائز",
            value=(
                self.winner.value
                if self.winner.value.strip()
                else "⏳ لم يُحدد بعد"
            ),
            inline=False
        )

        embed.set_footer(
            text=footer_text(
                f"أنشأها {interaction.user.display_name}"
            )
        )

        await interaction.response.send_message(
            embed=embed
        )


class CreateEventView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(
        label="📝 فتح استمارة الفعالية",
        style=discord.ButtonStyle.success
    )
    async def open_modal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            MagicEventModal()
        )


@bot.command(name="انشاء_فعالية")
async def create_magic_event_cmd(ctx):

    embed = make_embed(
        "🪄 قسم الألعاب السحرية",
        (
            "هل تريد تسجيل فعالية جديدة في السجلات؟\n\n"
            "اضغط الزر أدناه لفتح الاستمارة السحرية."
        ),
        COLORS["magic"]
    )

    await ctx.send(
        embed=embed,
        view=CreateEventView()
    )


@bot.command(name="عرض_فعاليات")
async def show_magic_events(ctx):

    db = load_json_file(EVENTS_FILE)

    if not db:

        await ctx.send(
            embed=make_embed(
                "📜 سجل الفعاليات",
                "لا توجد أي فعاليات مسجلة حاليًا.",
                COLORS["blue"]
            )
        )

        return

    description_parts = []

    for name, data in db.items():

        description_parts.append(
            f"### 📌 {name}\n"
            f"🎙️ **المقدم:** {data.get('presenter', 'غير محدد')}\n"
            f"⚖️ **الحكم:** {data.get('referee', 'غير محدد')}\n"
            f"👥 **المشاركون:** {data.get('participants', 'غير محدد')}\n"
            f"🏆 **الفائز:** {data.get('winner', 'قريبًا')}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    embed = make_embed(
        "📚 السجل الرسمي للفعاليات السحرية",
        "\n\n".join(description_parts),
        COLORS["blue"]
    )

    await ctx.send(embed=embed)


@bot.command(name="مسح_فعالية")
async def delete_magic_event(
    ctx,
    *,
    event_name: str
):

    db = load_json_file(EVENTS_FILE)

    event_name = event_name.strip()

    if event_name in db:

        del db[event_name]

        save_json_file(
            EVENTS_FILE,
            db
        )

        await ctx.send(
            embed=make_embed(
                "🗑️ تم حذف الفعالية",
                f"تم حذف **{event_name}** من السجلات السحرية.",
                COLORS["danger"]
            )
        )

    else:

        await ctx.send(
            embed=make_embed(
                "⚠️ الفعالية غير موجودة",
                f"لم يتم العثور على فعالية باسم:\n`{event_name}`",
                COLORS["danger"]
            )
        )


# =========================================================
# الغارة المجدولة
# =========================================================

@tasks.loop(hours=12)
async def scheduled_attack():

    channel = bot.get_channel(
        RAID_CHANNEL_ID
    )

    if channel is None:
        print(
            f"⚠️ لم يتم العثور على قناة الغارات: {RAID_CHANNEL_ID}"
        )
        return

    if raid_active:
        print("⚠️ توجد غارة قائمة، تم تخطي الغارة المجدولة.")
        return

    try:

        await send_raid(channel)

        print("🚨 تم إطلاق الغارة المجدولة.")

    except Exception as e:

        print(
            f"❌ خطأ أثناء إطلاق الغارة المجدولة: {e}"
        )


@scheduled_attack.before_loop
async def before_scheduled_attack():

    await bot.wait_until_ready()


# =========================================================
# أحداث البوت
# =========================================================

@bot.event
async def on_ready():

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🪄 البوت متصل: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


@bot.event
async def on_command_error(ctx, error):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            embed=make_embed(
                "⚠️ أمر غير مكتمل",
                "يرجى التأكد من كتابة الأمر بالشكل الصحيح.",
                COLORS["danger"]
            ),
            delete_after=10
        )

        return

    if isinstance(
        error,
        commands.MemberNotFound
    ):

        await ctx.send(
            embed=make_embed(
                "⚠️ لم يتم العثور على الساحر",
                "تأكد من أن المنشن أو اسم العضو صحيح.",
                COLORS["danger"]
            ),
            delete_after=10
        )

        return

    if isinstance(
        error,
        commands.CommandOnCooldown
    ):

        await ctx.send(
            embed=make_embed(
                "⏳ تمهل أيها الساحر",
                f"انتظر `{error.retry_after:.1f}` ثانية قبل المحاولة مجددًا.",
                COLORS["blue"]
            ),
            delete_after=10
        )

        return

    print(
        f"❌ خطأ في الأمر {ctx.command}: {error}"
    )


# =========================================================
# تشغيل البوت
# =========================================================

async def setup_bot():

    bot.add_view(
        VillageDefenseView()
    )

    if not scheduled_attack.is_running():
        scheduled_attack.start()


if __name__ == "__main__":

    token = (
        os.getenv("BOT_TOKEN")
        or os.getenv("DISCORD_TOKEN")
    )

    if not token:

        print(
            "⚠️ خطأ: لم يتم العثور على BOT_TOKEN أو DISCORD_TOKEN."
        )

    else:

        async def runner():

            await setup_bot()

            await bot.start(token)

        try:

            asyncio.run(runner())

        except KeyboardInterrupt:

            print("🛑 تم إيقاف البوت.")

        except Exception as e:

            print(
                f"❌ خطأ قاتل أثناء تشغيل البوت: {e}"
            )

