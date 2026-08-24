import discord
from discord.ext import commands, tasks
import random
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"

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
    empty = 10 - filled
    return "🟥" * filled + "🟩" * empty

class VillageDefenseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AttackButton())

class AttackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="⚔️ سحق أكلة الموت! (هجوم)",
            style=discord.ButtonStyle.danger,
            custom_id="village_defense_btn"
        )

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

        if user_id not in player_scores:
            player_scores[user_id] = {"name": user_name, "hits": 0}
        player_scores[user_id]["hits"] += 1
        player_scores[user_id]["name"] = user_name

        if current_hp > 0:
            current_hp -= DAMAGE_PER_HIT  
            if current_hp < 0:
                current_hp = 0
            
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
                            f"📊 استخدم الأوامر التالية للمتابعة:\n"
                            f"• `!صدارة` (لعرض جدول الأبطال)\n"
                            f"• `!المصابين` (لعرض قائمة المصابين في المستشفى)"
                            f"{AUTHOR_SIGNATURE}",
                    view=None
                )
        else:
            await interaction.followup.send(f"⚡ انتهت المعركة مسبقاً وتم القضاء على الخطر!{AUTHOR_SIGNATURE}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح باسم البوت الجبار في ريلواي: {bot.user}")

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
        
        await ctx.send(
            f"🏥✨ **[ إعلان إسعاف عاجل ]** ✨🏥\n\n"
            f"🪄 نجح البطل **{ctx.author.name}** في إجراء الإسعافات الطبية وعلاج البطل **{member.name}**!\n"
            f"🎉 مبروك الشفاء! عاد البطل إلى صفوف الدفاع بكامل طاقته! ⚔️🔥"
            f"{AUTHOR_SIGNATURE}"
        )
    else:
        await ctx.send(
            f"🔮 يا أستاذ، البطل **{member.name}** ليس مصاباً في المستشفى الحربي.. هو بكامل طاقته ولا يحتاج لعلاج!"
            f"{AUTHOR_SIGNATURE}"
        )

@cure_hospital_patient.error
async def cure_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ حدد البطل المراد علاجه، هكذا: `!علاج @الساحر`" + AUTHOR_SIGNATURE)

@bot.command(name="المصابين")
async def list_hospital_patients(ctx):
    if not hospital_patients:
        await ctx.send(f"🏥 المستشفى الحربي خالي تماماً من الإصابات.. الجميع في الميدان وجاهزون للمعركة!{AUTHOR_SIGNATURE}")
        return
    
    report = "🏥 **[ قائمة الأبطال المصابين في المستشفى الحربي ]** 🏥\n\n"
    for pid in hospital_patients:
        report += f"🛌 البطل المصاب: <@{pid}> (ينتظر الإسعاف)\n"
    report += "\n🪄 استخدم أمر `!علاج @الساحر` لإسعافهم بسرعة!" + AUTHOR_SIGNATURE
    await ctx.send(report)

@bot.command(name="صدارة")
async def leaderboard_command(ctx):
    if not player_scores:
        await ctx.send(f"📊 لوحة الصدارة فارغة حالياً! لا توجد مشاركات في المعارك بعد.{AUTHOR_SIGNATURE}")
        return

    sorted_players = sorted(player_scores.values(), key=lambda x: x["hits"], reverse=True)
    table_lines = [f"{'المرتبة':<8} | {'اسم البطل':<15} | {'الضربات':<8} | {'الضرر':<6}", "-" * 45]
    medals = ["🥇 الأول", "🥈 الثاني", "🥉 الثالث", " 4     ", " 5     ", " 6     ", " 7     ", " 8     ", " 9     ", " 10    "]
    
    for i, player in enumerate(sorted_players[:10]):
        rank = medals[i]
        name = player["name"][:14].ljust(15)
        hits = str(player["hits"]).ljust(8)
        damage = str(player["hits"] * DAMAGE_PER_HIT).ljust(6)
        table_lines.append(f"{rank:<8} | {name} | {hits} | {damage}")
    
    await ctx.send(
        f"🏆 **[ لوحة شرف أبطال القرية ]** 🏆\n```text\n" + "\n".join(table_lines) + "\n```\n"
        f"🎁 *استمروا في الدفاع لتتصدر القمة!*{AUTHOR_SIGNATURE}"
    )

@tasks.loop(hours=12)
async def scheduled_attack():
    global current_hp, raid_active, player_scores
    channel_id = 1540623521774960682  
    channel = bot.get_channel(channel_id)
    
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

bot.run(os.getenv("BOT_TOKEN"))
