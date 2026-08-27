import discord
from discord.ext import commands, tasks
import random
import os
import json
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"
LEADERBOARD_FILE = "duel_leaderboard.json"
STUDENTS_FILE = "hogwarts_students.json"
EVENTS_FILE = "magic_events.json"

def load_json_file(filename):
    if not os.path.exists(filename): 
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f: 
            return json.load(f)
    except:
        return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f: 
            json.dump(data, f, ensure_ascii=False, indent=4)
    except:
        pass

def assign_student_house(user_id, username, house_name):
    db = load_json_file(STUDENTS_FILE)
    db[str(user_id)] = {"name": username, "house": house_name}
    save_json_file(STUDENTS_FILE, db)

MAX_HP = 200          
current_hp = MAX_HP
DAMAGE_PER_HIT = 10
raid_active = False

player_scores = {}      
hospital_patients = set() 

HARRY_POTTER_SPELLS = {
    "Expelliarmus (تعويذة نزع السلاح)": 30,
    "Stupefy (تعويذة التخدير والذهول)": 35,
    "Expecto Patronum (تجسيد الباترونوس)": 45,
    "Reducto (تفجير العوائق)": 50,
    "Petrificus Totalus (شلل الجسد التام)": 40,
    "Confundo (تعويذة الارتباك والتشويش)": 55,
    "Incendio (إطلاق النيران الملتهبة)": 45,
    "Glisseo (انزلاق الأرضية المفاجئ)": 35,
    "Locomotor Wibbly (جعل الأرجل ترتجف كالهلام)": 50,
    "Tarantallegra (رقصة الأرجل الخارجة عن السيطرة)": 60,
    "Impedimenta (تعويذة إبطاء الحركة)": 40,
    "Arania Exumai (طرد العناكب والوحوش)": 35,
    "Levicorpus (رفع الخصم من كاحله في الهواء)": 50,
    "Rictusempra (تعويذة الدغدغة القوية)": 45,
    "Furunculus (ظهور بثور غريبة على الوجه)": 55
}

def get_health_bar(hp, max_hp=200):
    filled = max(0, min(10, hp // (max_hp // 10)))
    return "🟥" * filled + "🟩" * (10 - filled)

class VillageDefenseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AttackButton())

class AttackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚔️ سحق أكلة الموت! (هجوم)", style=discord.ButtonStyle.danger, custom_id="village_defense_btn")

    async def callback(self, interaction: discord.Interaction):
        global current_hp, raid_active
        await interaction.response.defer()
        
        user_id = interaction.user.id
        user_name = interaction.user.name

        if user_id in hospital_patients:
            await interaction.followup.send(f"🏥 عذراً، أنت مصاب بإصابة بالغة وترقد في المستشفى! لا يمكنك المشاركة حتى يعالجك أي بطل بالأمر: `!علاج`{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        if not raid_active:
            await interaction.followup.send(f"⚡ القرية آمنة تماماً، لا يوجد أي خطر حالياً!{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        spell_name, fail_chance = random.choice(list(HARRY_POTTER_SPELLS.items()))
        roll = random.randint(1, 100)
        
        if roll <= fail_chance:
            fail_messages = [
                f"💨 تشتت تركيز الساحر **{user_name}** وارتجفت عصاه فانطلقت تعويذة `{spell_name}` بلا أي تأثير!",
                f"🌀 اخفقت النبرة الصوتية لـ **{user_name}** وفشلت طاقة `{spell_name}` في اختراق حصون أكلة الموت!",
                f"🛡️ تنبه زعيم Death Eaters وتصدى لتعويذة `{spell_name}` بكل سهولة ويسر!"
            ]
            await interaction.message.edit(
                content=f"⚠️ **[ إنذار أحمر: معركة ملحمية تدور الآن! ]**\n"
                        f"أعوان Death Eaters يتقدمون بظلامهم لمحاولة حرق أسوار القرية!\n\n"
                        f"🖤 صحة زعيم الموت المهاجم: `{current_hp}/{MAX_HP}`\n"
                        f"[{get_health_bar(current_hp, MAX_HP)}]\n\n"
                        f"❌ استخدم البطل **{user_name}** تعويذة (`{spell_name}`) بنسبة فشل ({fail_chance}%) ولكن **فشلت الهجمة!** {random.choice(fail_messages)}"
                        f"{AUTHOR_SIGNATURE}",
                view=VillageDefenseView()
            )
            return

        if user_id not in player_scores: player_scores[user_id] = {"name": user_name, "hits": 0}
        player_scores[user_id]["hits"] += 1
        player_scores[user_id]["name"] = user_name

        if current_hp > 0:
            current_hp = max(0, current_hp - DAMAGE_PER_HIT)
            if current_hp > 0:
                health_bar = get_health_bar(current_hp, MAX_HP)
                await interaction.message.edit(
                    content=f"⚠️ **[ إنذار أحمر: معركة ملحمية تدور الآن! ]**\n"
                            f"أعوان Death Eaters يتقدمون بظلامهم لمحاولة حرق أسوار القرية!\n\n"
                            f"🖤 صحة زعيم الموت المهاجم: `{current_hp}/{MAX_HP}`\n"
                            f"[{health_bar}]\n\n"
                            f"✨ اختار البوت تعويذة هجومية: (`{spell_name}` - فشل: {fail_chance}%)\n"
                            f"نجح البطل **{user_name}** وأحدث ضرراً بالزعيم (-10 🔥)!",
                    view=VillageDefenseView()
                )
            else:
                raid_active = False
                hospital_msg = ""
                if player_scores:
                    all_fighters = list(player_scores.keys())
                    victim_id = random.choice(all_fighters)
                    hospital_patients.add(victim_id)
                    victim_name = player_scores[victim_id].get("name", "مقاتل مجهول")
                    hospital_msg = f"\n\n🚑 **طوارئ المعركة:** أصيب البطل **{victim_name}** بإصابة بالغة ونُقل للمستشفى! (يمكن لأي بطل علاجه بـ `!علاج @{victim_name}`)."

                participants_list = "📜 **[ قائمة الأبطال المشاركين في التصدي للغارة ]**:\n"
                for pid, pdata in player_scores.items():
                    participants_list += f"• <@{pid}> (عدد الضربات: **{pdata['hits']}** | الضرر الكلي: **{pdata['hits'] * DAMAGE_PER_HIT}**)\n"

                await interaction.message.edit(
                    content=f"🏆 **[ نصر أسطوري لا يُنسى! ]**\n"
                            f"بفضل عزيمة الأبطال وبسالة **{user_name}** ومن معه، تم سحق جيش Death Eaters وطردهم! 🎉🛡️\n\n"
                            f"{participants_list}"
                            f"{hospital_msg}\n\n"
                            f"📊 استخدم أمر `!صدارة-الغارة` لعرض جدول الأبطال."
                            f"{AUTHOR_SIGNATURE}",
                    view=None
                )

HOUSES = {
    "جريفندور": {"name": "جريفندور (Gryffindor)", "emoji": "🦁", "color": 0x740909, "desc": "الجرأة، الشجاعة، والفروسية هي سمات أصحاب هذا البيت العريق."},
    "سليذيرين": {"name": "سليذيرين (Slytherin)", "emoji": "🐍", "color": 0x1a472a, "desc": "الطموح، الدهاء، والقدرة الفائقة على القيادة تُميز صقور سليذيرين."},
    "رافينكلو": {"name": "رافينكلو (Ravenclaw)", "emoji": "🦅", "color": 0x0e1a40, "desc": "الذكاء، الحكمة، والإبداع اللامحدود هي ركائز عقلية أصحاب رافينكلو."},
    "هافلباف": {"name": "هافلباف (Hufflepuff)", "emoji": "🦡", "color": 0xecb939, "desc": "العمل الجاد، الإخلاص، العدالة، والصبر هي القيم العليا لهافلباف."}
}

async def display_house_students(ctx, house_key):
    db = load_json_file(STUDENTS_FILE)
    info = HOUSES[house_key]
    members = [f"• <@{uid}> ({data.get('name', 'ساحر')})" for uid, data in db.items() if data.get('house') == house_key]

    desc = f"📜 **قائمة طلاب بيت {info['emoji']} {info['name']}:**\n\n" + "\n".join(members) if members else f"⚠️ لا يوجد أي طلاب مسجلين في بيت **{info['name']}** حتى الآن."
    await ctx.send(embed=discord.Embed(title=f"🏰 سجل طلاب بيت {info['name']}", description=desc, color=info['color']).set_footer(text=AUTHOR_SIGNATURE))

def load_leaderboard():
    return load_json_file(LEADERBOARD_FILE)

def save_leaderboard(data):
    save_json_file(LEADERBOARD_FILE, data)

def add_win(user_id, username):
    db = load_leaderboard()
    uid = str(user_id)
    if uid not in db: db[uid] = {"name": username, "wins": 0}
    db[uid]["wins"] += 1
    db[uid]["name"] = username
    save_leaderboard(db)

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

DUEL_FLAVOR_MESSAGES = {
    "attack_hit": [
        "اشتعلت الشرارة من طرف العصا، ودوّى صوت اصطدام السحر بقوة!",
        "ارتجّت جدران القاعة من شدة العصف السحري المباشر!",
        "اندفعت طاقة مرعبة نحو الهدف دون أن يمتلك فرصة للهروب!"
    ],
    "shield_up": [
        "توهجت الأطراف بنور فضي خافت، وتشكل جدار من الطاقة الصلبة حول الساحر!",
        "التفَّ درع واقٍ محكم حول الساحر ليمتص صدمة القادم!"
    ],
    "heal_magic": [
        "تسلل دفء سحري غامض ليعيد ترتيب طاقات الجسد المنهك!",
        "لمع نور أخضر هادئ يداوي آثار الضربات العنيفة!"
    ],
    "spell_fail": [
        "تطاير شرار خافت وفشلت التعويذة في مغادرة طرف العصا!",
        "تشتت التركيز للحظة عابرة فأجهضت التعويذة في مهدها!"
    ]
}

class SpellSelectionView(discord.ui.View):
    def __init__(self, duel_session):
        super().__init__(timeout=60)
        self.duel_session = duel_session
        for k in random.sample(list(SPELLS_DATABASE.keys()), 6):
            self.add_item(SpellButton(k, SPELLS_DATABASE[k]))

class SpellButton(discord.ui.Button):
    def __init__(self, key, spell):
        super().__init__(label=spell["display"], style=discord.ButtonStyle.secondary)
        self.spell_key = key
        self.spell_data = spell

    async def callback(self, interaction: discord.Interaction):
        session = self.view.duel_session
        user_id = interaction.user.id
        if user_id not in [session.p1.id, session.p2.id]:
            await interaction.response.send_message("❌ هذه القاعة ليست مخصصة لك.", ephemeral=True)
            return

        p_data = session.p1_data if user_id == session.p1.id else session.p2_data
        if p_data["mp"] < self.spell_data["mana"]:
            await interaction.response.send_message("⚠️ رصيد المانا غير كافٍ لإنشاء هذه التعويذة.", ephemeral=True)
            return

        if user_id == session.p1.id:
            if session.p1_choice: return
            session.p1_choice = self.spell_key
        else:
            if session.p2_choice: return
            session.p2_choice = self.spell_key

        await interaction.response.send_message("✓ تم اختيار التعويذة بنجاح", ephemeral=True)
        await session.update_status_message()

        if session.p1_choice and session.p2_choice:
            self.view.stop()
            await session.execute_round(interaction)

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

    async def start_duel(self):
        embed = self.build_main_embed("✨ حان الوقت.. اختر تعويذتك السحرية من الأسفل")
        view = SpellSelectionView(self)
        self.message = await self.ctx.send(embed=embed, view=view)

    def build_main_embed(self, status_text):
        embed = discord.Embed(
            title="⚔️ قاعة المبارزات السحرية الكبرى",
            description=f"**الجولة {self.round_num:02d}**\n\n"
                        f"🧙‍♂️ {self.p1.name}   ❤️ {self.p1_data['hp']}   🔮 {self.p1_data['mp']}\n"
                        f"VS\n"
                        f"🧙‍♂️ {self.p2.name}   ❤️ {self.p2_data['hp']}   🔮 {self.p2_data['mp']}\n\n"
                        f"──────────────────\n"
                        f"{status_text}",
            color=0x2b1338
        )
        embed.set_footer(text=AUTHOR_SIGNATURE)
        return embed

    async def update_status_message(self):
        p1_status = "✓ تم الاختيار" if self.p1_choice else "⏳ يختار..."
        p2_status = "✓ تم الاختيار" if self.p2_choice else "⏳ يختار..."
        text = f"حالة الخصوم:\n{self.p1.name}: {p1_status}  |  {self.p2.name}: {p2_status}"
        embed = self.build_main_embed(text)
        try:
            await self.message.edit(embed=embed)
        except: pass

    async def execute_round(self, interaction: discord.Interaction):
        self.p1_data["mp"] = min(40, self.p1_data["mp"] + 7)
        self.p2_data["mp"] = min(40, self.p2_data["mp"] + 7)

        s1 = SPELLS_DATABASE[self.p1_choice]
        s2 = SPELLS_DATABASE[self.p2_choice]

        self.p1_data["mp"] -= s1["mana"]
        self.p2_data["mp"] -= s2["mana"]

        p1_fail = random.randint(1, 100) <= s1["fail"]
        p2_fail = random.randint(1, 100) <= s2["fail"]

        p1_result_line, p2_result_line = "", ""
        flavor_picks = []

        if p1_fail:
            p1_result_line = f"{s1['name']} فشلت — لم تسبب ضررًا"
            flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["spell_fail"]))
        else:
            if s1["type"] == "attack":
                dmg = s1["damage"]
                absorbed = min(self.p2_data["shield"], dmg)
                rem = dmg - absorbed
                self.p2_data["shield"] -= absorbed
                self.p2_data["hp"] -= rem
                p1_result_line = f"{s1['name']} نجحت — {dmg} ضرر"
                flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["attack_hit"]))
            elif s1["type"] == "defense":
                self.p1_data["shield"] = s1["shield"]
                p1_result_line = f"{s1['name']} نجحت — درع بقوة {s1['shield']}"
                flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["shield_up"]))
            elif s1["type"] == "heal":
                self.p1_data["hp"] = min(200, self.p1_data["hp"] + s1["heal"])
                p1_result_line = f"{s1['name']} نجحت — شفاء +{s1['heal']} HP"
                flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["heal_magic"]))

        if p2_fail:
            p2_result_line = f"{s2['name']} فشلت — لم تسبب ضررًا"
            flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["spell_fail"]))
        else:
            if s2["type"] == "attack":
                dmg = s2["damage"]
                absorbed = min(self.p1_data["shield"], dmg)
                rem = dmg - absorbed
                self.p1_data["shield"] -= absorbed
                self.p1_data["hp"] -= rem
                p2_result_line = f"{s2['name']} نجحت — {dmg} ضرر"
                flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["attack_hit"]))
            elif s2["type"] == "defense":
                self.p2_data["shield"] = s2["shield"]
                p2_result_line = f"{s2['name']} نجحت — درع بقوة {s2['shield']}"
                flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["shield_up"]))
            elif s2["type"] == "heal":
                self.p2_data["hp"] = min(200, self.p2_data["hp"] + s2["heal"])
                p2_result_line = f"{s2['name']} نجحت — شفاء +{s2['heal']} HP"
                flavor_picks.append(random.choice(DUEL_FLAVOR_MESSAGES["heal_magic"]))

        self.p1_data["hp"] = max(0, min(200, self.p1_data["hp"]))
        self.p2_data["hp"] = max(0, min(200, self.p2_data["hp"]))
        self.p1_data["shield"] = max(0, self.p1_data["shield"])
        self.p2_data["shield"] = max(0, self.p2_data["shield"])

        active_flavor = random.choice(flavor_picks) if flavor_picks else "تردد صدى التعويذات القوية في أرجاء قاعة المبارزة."

        result_desc = (
            f"**⚔️ الجولة {self.round_num:02d}**\n\n"
            f"🧙‍♂️ {self.p1.name}: {s1['name']}\n"
            f"🧙‍♂️ {self.p2.name}: {s2['name']}\n\n"
            f"💬 *\"{active_flavor}\"*\n\n"
            f"✨ **نتائج الاشتباك**\n"
            f"• {self.p1.name}: {p1_result_line}\n"
            f"• {self.p2.name}: {p2_result_line}\n\n"
            f"──────────────────\n"
            f"❤️ {self.p1.name} ({self.p1_data['hp']}/200)  |  ❤️ {self.p2.name} ({self.p2_data['hp']}/200)\n\n"
            f"🔮 تجددت المانا (+7) للجميع في بداية الجولة القادمة."
        )

        embed = discord.Embed(title="⚡ كشف التعويذات ونتائج الجولة", description=result_desc, color=0xd4af37)
        embed.set_footer(text=AUTHOR_SIGNATURE)

        if self.p1_data["hp"] == 0 or self.p2_data["hp"] == 0:
            winner = self.p1 if self.p1_data["hp"] > self.p2_data["hp"] else self.p2
            add_win(winner.id, winner.name)
            embed.title = "🏆 حسمت المعركة السحرية الكبرى"
            embed.description += f"\n\n👑 **بطل الحلبة المنتصر:** {winner.mention}\n*(تم تسجيل الانتصار في سجلات شرف صدارة المبارزات)*"
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            return

        self.round_num += 1
        self.p1_choice = None
        self.p2_choice = None

        await interaction.response.edit_message(content=None, embed=embed, view=None)
        await asyncio.sleep(4)
        
        next_embed = self.build_main_embed("✨ الجولة الجديدة بدأت.. اختر تعويذتك الآن")
        next_view = SpellSelectionView(self)
        self.message = await self.ctx.send(embed=next_embed, view=next_view)

@bot.event
async def on_ready():
    print(f"Bot is online: {bot.user}")

@bot.command(name="هجوم")
async def start_raid_command(ctx):
    global current_hp, raid_active, player_scores
    current_hp = MAX_HP
    raid_active = True
    player_scores.clear() 
    health_bar = get_health_bar(MAX_HP, MAX_HP)
    await ctx.send(
        f"🚨 **[ غارة مرعبة تهدد القرية! ]**\n"
        f"تجمع قتلة السحرة وجماعة Death Eaters في الأفق ومعهما طاقة مظلمة لتهشيم البوابات!\n\n"
        f"🖤 صحة زعيم الموت المهاجم: `{current_hp}/{MAX_HP}`\n"
        f"[{health_bar}]\n\n"
        f"🛡️ يا أهالي القرية والأبطال، اضغطوا على زر الهجوم أدناه بسرعة لإنقاذ الوطن!"
        f"{AUTHOR_SIGNATURE}",
        view=VillageDefenseView()
    )

@bot.command(name="علاج")
async def cure_hospital_patient(ctx, member: discord.Member):
    global hospital_patients
    if member.id in hospital_patients:
        hospital_patients.remove(member.id)
        await ctx.send(f"🏥✨ نجح البطل **{ctx.author.name}** في علاج البطل **{member.name}** وعاد لصفوف الدفاع!{AUTHOR_SIGNATURE}")
    else:
        await ctx.send(f"🔮 البطل **{member.name}** ليس مصاباً في المستشفى الحربي!{AUTHOR_SIGNATURE}")

@bot.command(name="المصابين")
async def list_hospital_patients(ctx):
    if not hospital_patients:
        await ctx.send(f"🏥 المستشفى خالي تماماً من الإصابات.. الجميع في الميدان!{AUTHOR_SIGNATURE}")
        return
    report = "🏥 **[ قائمة الأبطال المصابين في المستشفى ]** 🏥\n\n"
    for pid in hospital_patients: report += f"🛌 المصاب: <@{pid}>\n"
    await ctx.send(report + "\n🪄 استخدم `!علاج @الساحر` لإسعافهم!" + AUTHOR_SIGNATURE)

@bot.command(name="صدارة-الغارة")
async def raid_leaderboard(ctx):
    if not player_scores:
        await ctx.send(f"📊 لوحة صدارة الغارة فارغة حالياً!{AUTHOR_SIGNATURE}")
        return
    sorted_players = sorted(player_scores.values(), key=lambda x: x["hits"], reverse=True)
    table_lines = [f"{'المرتبة':<8} | {'اسم البطل':<15} | {'الضربات':<8}", "-" * 36]
    medals = ["🥇 الأول", "🥈 الثاني", "🥉 الثالث"]
    for i, p in enumerate(sorted_players[:10]):
        table_lines.append(f"{medals[i] if i < len(medals) else f' #{i+1}     ':<8} | {p['name'][:14].ljust(15)} | {str(p['hits']).ljust(8)}")
    await ctx.send(f"🏆 **[ صدارة أبطال القرية ]**\n```text\n" + "\n".join(table_lines) + "\n```" + AUTHOR_SIGNATURE)

@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):
    msg = await ctx.send(embed=discord.Embed(title="🎩 قبعة التنسيق", description="*تتمتم القبعة بكلمات غامضة وهي تفحص أعماق عقلك...*", color=0x8b5a2b).set_footer(text=AUTHOR_SIGNATURE))
    await asyncio.sleep(3)
    house_key = random.choice(list(HOUSES.keys()))
    assign_student_house(ctx.author.id, ctx.author.name, house_key)
    info = HOUSES[house_key]
    await msg.edit(embed=discord.Embed(title="✨ القرار النهائي لقبعة التنسيق!", description=f"المعالج: {ctx.author.mention}\n\nالبيت المُختار: **{info['emoji']} {info['name']}**\n\n*{info['desc']}*\n\n*(تم تسجيلك رسمياً في سجلات هذا البيت!)*", color=info['color']).set_footer(text=AUTHOR_SIGNATURE))

@bot.command(name="عرض_جريفندور")
async def show_gryffindor(ctx): await display_house_students(ctx, "جريفندور")

@bot.command(name="عرض_سليذيرين")
async def show_slytherin(ctx): await display_house_students(ctx, "سليذيرين")

@bot.command(name="عرض_رافينكلو")
async def show_ravenclaw(ctx): await display_house_students(ctx, "رافينكلو")

@bot.command(name="عرض_هافلباف")
async def show_hufflepuff(ctx): await display_house_students(ctx, "هافلباف")

@bot.command(name="انشاء_فعالية")
async def create_magic_event(ctx, event_name: str, *, event_details: str):
    db = load_json_file(EVENTS_FILE)
    db[event_name] = {"details": event_details, "author": ctx.author.name}
    save_json_file(EVENTS_FILE, db)
    await ctx.send(f"✨ تم إنشاء وتسجيل الفعالية السحرية **{event_name}** بنجاح لصالح قسم الألعاب السحرية!{AUTHOR_SIGNATURE}")

@bot.command(name="عرض_فعاليات")
async def show_magic_events(ctx):
    db = load_json_file(EVENTS_FILE)
    if not db:
        await ctx.send(f"⚠️ لا توجد أي فعاليات مسجلة لقسم الألعاب السحرية حالياً.{AUTHOR_SIGNATURE}")
        return
    desc = ""
    for name, data in db.items():
        desc += f"📌 **{name}**\n• التفاصيل: {data['details']}\n• المشرف: {data['author']}\n──────────────────\n"
    await ctx.send(embed=discord.Embed(title="📜 سجل فعاليات قسم الألعاب السحرية", description=desc, color=0x00ffcc).set_footer(text=AUTHOR_SIGNATURE))

@bot.command(name="مسح_فعالية")
async def delete_magic_event(ctx, *, event_name: str):
    db = load_json_file(EVENTS_FILE)
    if event_name in db:
        del db[event_name]
        save_json_file(EVENTS_FILE, db)
        await ctx.send(f"🗑️ تم حذف الفعالية السحرية **{event_name}** بنجاح من السجلات!{AUTHOR_SIGNATURE}")
    else:
        await ctx.send(f"⚠️ عذراً، لم يتم العثور على فعالية مسجلة بهذا الاسم: `{event_name}`{AUTHOR_SIGNATURE}")

@bot.command(name="مبارزة")
async def duel_command(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("⚠️ يرجى عمل منشن للساحر المراد مبارزته: `!مبارزة @الشخص`", delete_after=10)
        return
    if member.id == ctx.author.id:
        await ctx.send("⚠️ لا يمكنك مبارزة نفسك.", delete_after=10)
        return
    if member.bot:
        await ctx.send("⚠️ البوتات لا تشارك في مبارزات العصي.", delete_after=10)
        return
    await DuelSession(ctx, ctx.author, member).start_duel()

@bot.command(name="صدارة-المبارزات")
async def leaderboard_command(ctx):
    db = load_leaderboard()
    if not db:
        await ctx.send(f"⚠️ لا توجد انتصارات مسجلة في سجل المبارزات حتى الآن.{AUTHOR_SIGNATURE}")
        return
    sorted_p = sorted(db.values(), key=lambda x: x["wins"], reverse=True)[:10]
    desc = "".join([f"🥇 **{p['name']}** ── 🎯 `{p['wins']}` انتصار\n" for p in sorted_p])
    await ctx.send(embed=discord.Embed(title="📜 صدارة حلبة المبارزات السحرية", description=desc, color=0xd4af37).set_footer(text=AUTHOR_SIGNATURE))

@tasks.loop(hours=12)
async def scheduled_attack():
    global current_hp, raid_active, player_scores
    channel = bot.get_channel(1540623521774960682)
    if channel:
        current_hp = MAX_HP
        raid_active = True
        player_scores.clear()
        health_bar = get_health_bar(MAX_HP, MAX_HP)
        await channel.send(
            f"🚨 **[ غارة مرعبة تهدد القرية! ]**\n"
            f"تجمع قتلة السحرة وجماعة Death Eaters في الأفق ومعهما طاقة مظلمة لتهشيم البوابات!\n\n"
            f"🖤 صحة زعيم الموت المهاجم: `{current_hp}/{MAX_HP}`\n"
            f"[{health_bar}]\n\n"
            f"🛡️ يا أهالي القرية، استعدوا للمعركة واضغطوا على زر الهجوم أدناه!"
            f"{AUTHOR_SIGNATURE}",
            view=VillageDefenseView()
        )

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        print("⚠️ خطأ: توكن البوت غير موجود!")
    else:
        bot.run(token)
