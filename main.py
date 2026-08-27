import discord
from discord.ext import commands, tasks
import random
import os
import json
import asyncio
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is running and active!")

app = web.Application()
app.router.add_get("/", handle)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"
LEADERBOARD_FILE = "duel_leaderboard.json"
STUDENTS_FILE = "hogwarts_students.json"
EVENTS_FILE = "magic_events.json"

def load_json_file(filename):
    if not os.path.exists(filename): return {}
    try:
        with open(filename, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_json_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

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
    "Expelliarmus": 30, "Stupefy": 35, "Expecto Patronum": 45, "Reducto": 50,
    "Petrificus Totalus": 40, "Confundo": 55, "Incendio": 45, "Glisseo": 35,
    "Locomotor Wibbly": 50, "Tarantallegra": 60, "Impedimenta": 40, "Arania Exumai": 35,
    "Levicorpus": 50, "Rictusempra": 45, "Furunculus": 55
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
            await interaction.followup.send(f"🏥 عذراً، أنت مصاب وترقد في المستشفى!{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        if not raid_active:
            await interaction.followup.send(f"⚡ القرية آمنة تماماً، لا يوجد خطر حالياً!{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        spell_name, fail_chance = random.choice(list(HARRY_POTTER_SPELLS.items()))
        if random.randint(1, 100) <= fail_chance:
            await interaction.message.edit(
                content=f"⚠️ **[ إنذار أحمر ]**\n🖤 صحة زعيم الموت: `{current_hp}/{MAX_HP}`\n[{get_health_bar(current_hp, MAX_HP)}]\n\n❌ استخدم **{user_name}** (`{spell_name}`) ولكن **فشلت الهجمة!**{AUTHOR_SIGNATURE}",
                view=VillageDefenseView()
            )
            return

        if user_id not in player_scores: player_scores[user_id] = {"name": user_name, "hits": 0}
        player_scores[user_id]["hits"] += 1
        player_scores[user_id]["name"] = user_name

        if current_hp > 0:
            current_hp = max(0, current_hp - DAMAGE_PER_HIT)
            if current_hp > 0:
                await interaction.message.edit(
                    content=f"⚠️ **[ إنذار أحمر ]**\n🖤 صحة زعيم الموت: `{current_hp}/{MAX_HP}`\n[{get_health_bar(current_hp, MAX_HP)}]\n\n✨ نجح **{user_name}** وأحدث ضرراً (-10 🔥)!",
                    view=VillageDefenseView()
                )
            else:
                raid_active = False
                hospital_msg = ""
                if player_scores:
                    victim_id = random.choice(list(player_scores.keys()))
                    hospital_patients.add(victim_id)
                    hospital_msg = f"\n\n🚑 أصيب البطل **{player_scores[victim_id]['name']}** ونُقل للمستشفى!"

                participants = "".join([f"• <@{pid}> ({p['hits']} ضربات)\n" for pid, p in player_scores.items()])
                await interaction.message.edit(
                    content=f"🏆 **[ نصر أسطوري! ]** تم سحق أكلة الموت!\n\n{participants}{hospital_msg}{AUTHOR_SIGNATURE}",
                    view=None
                )

HOUSES = {
    "جريفندور": {"name": "جريفندور (Gryffindor)", "emoji": "🦁", "color": 0x740909, "desc": "الجرأة، الشجاعة، والفروسية."},
    "سليذيرين": {"name": "سليذيرين (Slytherin)", "emoji": "🐍", "color": 0x1a472a, "desc": "الطموح، الدهاء، والقيادة."},
    "رافينكلو": {"name": "رافينكلو (Ravenclaw)", "emoji": "🦅", "color": 0x0e1a40, "desc": "الذكاء، الحكمة، والإبداع."},
    "هافلباف": {"name": "هافلباف (Hufflepuff)", "emoji": "🦡", "color": 0xecb939, "desc": "العمل الجاد، الإخلاص، والصبر."}
}

async def display_house_students(ctx, house_key):
    db = load_json_file(STUDENTS_FILE)
    info = HOUSES[house_key]
    members = [f"• <@{uid}> ({data['name']})" for uid, data in db.items() if data['house'] == house_key]
    desc = f"📜 **قائمة طلاب {info['emoji']} {info['name']}:**\n\n" + "\n".join(members) if members else f"⚠️ لا يوجد طلاب مسجلين في {info['name']}."
    await ctx.send(embed=discord.Embed(title=f"🏰 سجل {info['name']}", description=desc, color=info['color']).set_footer(text=AUTHOR_SIGNATURE))

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
    "protego": {"name": "Protego", "display": "🛡️ Protego · 10 MP", "mana": 10, "shield": 15, "fail": 8, "type": "defense"},
    "episkey": {"name": "Episkey", "display": "💚 Episkey · 15 MP", "mana": 15, "heal": 20, "fail": 10, "type": "heal"}
}

class SpellSelectionView(discord.ui.View):
    def __init__(self, duel_session):
        super().__init__(timeout=60)
        self.duel_session = duel_session
        for k in random.sample(list(SPELLS_DATABASE.keys()), min(len(SPELLS_DATABASE), 4)):
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
            await interaction.response.send_message("❌ هذه القاعة ليست لك.", ephemeral=True)
            return

        p_data = session.p1_data if user_id == session.p1.id else session.p2_data
        if p_data["mp"] < self.spell_data["mana"]:
            await interaction.response.send_message("⚠️ رصيد المانا غير كافٍ.", ephemeral=True)
            return

        if user_id == session.p1.id:
            if session.p1_choice: return
            session.p1_choice = self.spell_key
        else:
            if session.p2_choice: return
            session.p2_choice = self.spell_key

        await interaction.response.send_message("✓ تم اختيار التعويذة", ephemeral=True)
        await session.update_status_message()

        if session.p1_choice and session.p2_choice:
            self.view.stop()
            await session.execute_round(interaction)

class DuelSession:
    def __init__(self, ctx, p1, p2):
        self.ctx = ctx
        self.p1 = p1
        self.p2 = p2
        self.p1_data = {"hp": 200, "mp": 40}
        self.p2_data = {"hp": 200, "mp": 40}
        self.p1_choice = None
        self.p2_choice = None
        self.round_num = 1
        self.message = None

    async def start_duel(self):
        embed = self.build_main_embed("✨ اختر تعويذتك")
        self.message = await self.ctx.send(embed=embed, view=SpellSelectionView(self))

    def build_main_embed(self, status_text):
        embed = discord.Embed(
            title="⚔️ مبارزة العصي السحرية",
            description=f"**الجولة {self.round_num:02d}**\n\n🧙‍♂️ {self.p1.name} (❤️ {self.p1_data['hp']} | 🔮 {self.p1_data['mp']})\nVS\n🧙‍♂️ {self.p2.name} (❤️ {self.p2_data['hp']})\n\n{status_text}",
            color=0x2b1338
        )
        embed.set_footer(text=AUTHOR_SIGNATURE)
        return embed

    async def update_status_message(self):
        try:
            await self.message.edit(embed=self.build_main_embed(f"الحالة: {self.p1.name} ({'تم' if self.p1_choice else 'يختار'}) | {self.p2.name} ({'تم' if self.p2_choice else 'يختار'})"))
        except: pass

    async def execute_round(self, interaction: discord.Interaction):
        s1, s2 = SPELLS_DATABASE[self.p1_choice], SPELLS_DATABASE[self.p2_choice]
        self.p1_data["mp"] -= s1["mana"]
        self.p2_data["mp"] -= s2["mana"]

        if not random.randint(1, 100) <= s1["fail"]:
            if s1["type"] == "attack": self.p2_data["hp"] -= s1["damage"]
        if not random.randint(1, 100) <= s2["fail"]:
            if s2["type"] == "attack": self.p1_data["hp"] -= s2["damage"]

        self.p1_data["hp"] = max(0, min(200, self.p1_data["hp"]))
        self.p2_data["hp"] = max(0, min(200, self.p2_data["hp"]))

        embed = discord.Embed(
            title=f"⚡ نتائج الجولة {self.round_num}",
            description=f"🧙‍♂️ {self.p1.name}: {s1['name']}\n🧙‍♂️ {self.p2.name}: {s2['name']}\n\n❤️ {self.p1.name}: {self.p1_data['hp']}/200  |  ❤️ {self.p2.name}: {self.p2_data['hp']}/200",
            color=0xd4af37
        )
        embed.set_footer(text=AUTHOR_SIGNATURE)

        if self.p1_data["hp"] == 0 or self.p2_data["hp"] == 0:
            winner = self.p1 if self.p1_data["hp"] > self.p2_data["hp"] else self.p2
            add_win(winner.id, winner.name)
            embed.description += f"\n\n👑 **بطل الحلبة:** {winner.mention}"
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            return

        self.round_num += 1
        self.p1_choice = None
        self.p2_choice = None
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        await asyncio.sleep(4)
        self.message = await self.ctx.send(embed=self.build_main_embed("✨ اختر تعويذتك"), view=SpellSelectionView(self))

@bot.event
async def on_ready():
    print(f"Bot is online: {bot.user}")

@bot.command(name="هجوم")
async def start_raid_command(ctx):
    global current_hp, raid_active, player_scores
    current_hp = MAX_HP
    raid_active = True
    player_scores.clear() 
    await ctx.send(f"🚨 **[ غارة مرعبة تهدد القرية! ]**\n🖤 صحة زعيم الموت: `{current_hp}/{MAX_HP}`\n[{get_health_bar(MAX_HP, MAX_HP)}]" + AUTHOR_SIGNATURE, view=VillageDefenseView())

@bot.command(name="علاج")
async def cure_hospital_patient(ctx, member: discord.Member):
    global hospital_patients
    if member.id in hospital_patients:
        hospital_patients.remove(member.id)
        await ctx.send(f"🏥✨ تم علاج **{member.name}** وعاد للميدان!{AUTHOR_SIGNATURE}")
    else:
        await ctx.send(f"🔮 البطل **{member.name}** ليس مصاباً!{AUTHOR_SIGNATURE}")

@bot.command(name="المصابين")
async def list_hospital_patients(ctx):
    if not hospital_patients:
        await ctx.send(f"🏥 المستشفى خالي تماماً!{AUTHOR_SIGNATURE}")
        return
    await ctx.send("🏥 **[ المصابين ]**\n\n" + "\n".join([f"• <@{pid}>" for pid in hospital_patients]) + AUTHOR_SIGNATURE)

@bot.command(name="صدارة-الغارة")
async def raid_leaderboard(ctx):
    if not player_scores:
        await ctx.send(f"📊 لا توجد سجلات حالياً!{AUTHOR_SIGNATURE}")
        return
    sorted_p = sorted(player_scores.values(), key=lambda x: x["hits"], reverse=True)
    lines = [f"{p['name'][:14]} | {p['hits']} ضربات" for p in sorted_p[:10]]
    await ctx.send(f"🏆 **[ صدارة الغارة ]**\n```text\n" + "\n".join(lines) + "\n```" + AUTHOR_SIGNATURE)

@bot.command(name="قبعة-التنسيق")
async def sorting_hat(ctx):
    msg = await ctx.send(embed=discord.Embed(title="🎩 قبعة التنسيق", description="*تتمتم القبعة...*", color=0x8b5a2b).set_footer(text=AUTHOR_SIGNATURE))
    await asyncio.sleep(3)
    house_key = random.choice(list(HOUSES.keys()))
    assign_student_house(ctx.author.id, ctx.author.name, house_key)
    info = HOUSES[house_key]
    await msg.edit(embed=discord.Embed(title="✨ القرار النهائي!", description=f"المعالج: {ctx.author.mention}\nالبيت: **{info['emoji']} {info['name']}**\n\n*{info['desc']}*", color=info['color']).set_footer(text=AUTHOR_SIGNATURE))

@bot.command(name="عرض_جريفندور")
async def show_gryffindor(ctx): await display_house_students(ctx, "جريفندور")

@bot.command(name="عرض_سليذيرين")
async def show_slytherin(ctx): await display_house_students(ctx, "سليذيرين")

@bot.command(name="عرض_رافينكلو")
async def show_ravenclaw(ctx): await display_house_students(ctx, "رافينكلو")

@bot.command(name="عرض_هافلباف")
async def show_hufflepuff(ctx): await display_house_students(ctx, "هافلباف")

@bot.command(name="اضافة_فعالية")
async def add_magic_event(ctx, event_name: str, *, event_details: str):
    db = load_json_file(EVENTS_FILE)
    db[event_name] = {"details": event_details, "author": ctx.author.name}
    save_json_file(EVENTS_FILE, db)
    await ctx.send(f"✨ تم تسجيل الفعالية السحرية **{event_name}** بنجاح بواسطة قسم الألعاب السحرية!{AUTHOR_SIGNATURE}")

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
        await ctx.send(f"🗑️ تم حذف الفعالية السحرية **{event_name}** بنجاح!{AUTHOR_SIGNATURE}")
    else:
        await ctx.send(f"⚠️ عذراً، لم يتم العثور على فعالية مسجلة بهذا الاسم: `{event_name}`{AUTHOR_SIGNATURE}")

@bot.command(name="مبارزة")
async def duel_command(ctx, member: discord.Member = None):
    if not member or member.id == ctx.author.id or member.bot:
        await ctx.send("⚠️ يرجى عمل منشن لشخص صحيح للمبارزة.", delete_after=10)
        return
    await DuelSession(ctx, ctx.author, member).start_duel()

@bot.command(name="صدارة-المبارزات")
async def leaderboard_command(ctx):
    db = load_leaderboard()
    if not db:
        await ctx.send("⚠️ لا توجد انتصارات مسجلة.")
        return
    sorted_p = sorted(db.values(), key=lambda x: x["wins"], reverse=True)[:10]
    desc = "".join([f"🥇 **{p['name']}** ── 🎯 `{p['wins']}` انتصار\n" for p in sorted_p])
    await ctx.send(embed=discord.Embed(title="📜 صدارة حلبة المبارزات", description=desc, color=0xd4af37).set_footer(text=AUTHOR_SIGNATURE))

@tasks.loop(hours=12)
async def scheduled_attack():
    global current_hp, raid_active, player_scores
    channel = bot.get_channel(1540623521774960682)
    if channel:
        current_hp = MAX_HP
        raid_active = True
        player_scores.clear()
        await channel.send(f"🚨 **[ غارة مرعبة تهدد القرية! ]**" + AUTHOR_SIGNATURE, view=VillageDefenseView())

async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token: return
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    async with bot: await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())

