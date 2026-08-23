import discord
from discord.ext import commands, tasks
import random
import os

# ----------------- إعدادات البوت والصلاحيات ----------------- #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# التوقيع الرسمي للصانع
AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"

# إعدادات المعركة والمستشفى الحربي
MAX_HP = 200          
current_hp = MAX_HP
DAMAGE_PER_HIT = 10
raid_active = False

player_scores = {}      # {user_id: {"name": "اسم", "hits": عدد الضربات}}
hospital_patients = set() # مجموعة IDs المصابين في المستشفى
medical_history = {}    # أرشيف السجلات الطبية الشامل

# قاموس تعاويذ هاري بوتر الحقيقية مع نسب فشل عالية وتكتيكية
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

def init_user_history(user_id):
    if user_id not in medical_history:
        medical_history[user_id] = {
            "attack_count": 0,
            "hospital_visits": 0,
            "cures_received": 0
        }

def get_health_bar(hp, max_hp=200):
    filled = max(0, min(10, hp // (max_hp // 10)))
    empty = 10 - filled
    return "🟥" * filled + "🟩" * empty

# ----------------- واجهة الدفاع المتغيرة بتعاويذ هاري بوتر ----------------- #
class VillageDefenseView(discord.ui.View):
    def __init__(self, current_spell_label=None):
        super().__init__(timeout=None)
        
        spell_name = current_spell_label if current_spell_label else random.choice(list(HARRY_POTTER_SPELLS.keys()))
        fail_chance = HARRY_POTTER_SPELLS[spell_name]
        
        self.add_item(DynamicSpellButton(spell_name, fail_chance))

class DynamicSpellButton(discord.ui.Button):
    def __init__(self, label, fail_chance):
        super().__init__(
            label=f"🪄 {label.split(' (')[0]} ({fail_chance}%)",
            style=discord.ButtonStyle.danger,
            custom_id=f"hp_spell_{random.randint(1000, 9999)}"
        )
        self.spell_name = label
        self.fail_chance = fail_chance

    async def callback(self, interaction: discord.Interaction):
        global current_hp, raid_active
        
        await interaction.response.defer()
        
        user_id = interaction.user.id
        user_name = interaction.user.name

        init_user_history(user_id)

        if user_id in hospital_patients:
            await interaction.followup.send(f"🏥 عذراً، أنت مصاب بإصابة بالغة وترقد في المستشفى! لا يمكنك المشاركة حتى يعالجك أي بطل بالأمر: `!علاج`{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        if not raid_active:
            await interaction.followup.send(f"⚡ القرية آمنة تماماً، لا يوجد أي خطر حالياً!{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        # ----------------- تطبيق نسبة الفشل للتعويذة ----------------- #
        roll = random.randint(1, 100)
        
        if roll <= self.fail_chance:
            fail_messages = [
                f"💨 تشتت تركيز الساحر **{user_name}** وارتجفت عصاه فانطلقت تعويذة `{self.spell_name}` بلا أي تأثير!",
                f"🌀 اخفقت النبرة الصوتية لـ **{user_name}** وفشلت طاقة `{self.spell_name}` في اختراق حصون أكلة الموت!",
                f"🛡️ تنبه زعيم Death Eaters وتصدى لتعويذة `{self.spell_name}` بكل سهولة ويسر!"
            ]
            await interaction.message.edit(
                content=f"⚠️ **[ إنذار أحمر: معركة ملحمية تدور الآن! ]**\n"
                        f"أعوان Death Eaters يتقدمون بظلامهم لمحاولة حرق أسوار القرية!\n\n"
                        f"🖤 صحة زعيم الموت المهاجم: `{current_hp}/{MAX_HP}`\n"
                        f"[{get_health_bar(current_hp, MAX_HP)}]\n\n"
                        f"❌ **فشلت التعويذة!** {random.choice(fail_messages)}"
                        f"{AUTHOR_SIGNATURE}",
                view=VillageDefenseView()
            )
            return

        # تسجيل النقاط والضربات الناجحة للمشارك
        if user_id not in player_scores:
            player_scores[user_id] = {"name": user_name, "hits": 0}
        player_scores[user_id]["hits"] += 1
        player_scores[user_id]["name"] = user_name
        
        medical_history[user_id]["attack_count"] += 1

        if current_hp > 0:
            current_hp -= DAMAGE_PER_HIT  
            if current_hp < 0:
                current_hp = 0
            
            if current_hp > 0:
                health_bar = get_health_bar(current_hp, MAX_HP)
                next_view = VillageDefenseView()
                await interaction.message.edit(
                    content=f"⚠️ **[ إنذار أحمر: معركة ملحمية تدور الآن! ]**\n"
                            f"أعوان Death Eaters يتقدمون بظلامهم لمحاولة حرق أسوار القرية!\n\n"
                            f"🖤 صحة زعيم الموت المهاجم: `{current_hp}/{MAX_HP}`\n"
                            f"[{health_bar}]\n\n"
                            f"✨ نجح البطل **{user_name}** بتعويذة (`{self.spell_name}`) وأحدث ضرراً بالزعيم (-10 🔥)!",
                    view=next_view
                )
            else:
                raid_active = False
                
                # اختيار ضحية عشوائية للمستشفى وتجهيز قائمة المشاركين
                hospital_msg = ""
                if player_scores:
                    all_fighters = list(player_scores.keys())
                    victim_id = random.choice(all_fighters)
                    hospital_patients.add(victim_id)
                    init_user_history(victim_id)
                    medical_history[victim_id]["hospital_visits"] += 1
                    
                    victim_name = player_scores[victim_id].get("name", "مقاتل مجهول")
                    hospital_msg = f"\n\n🚑 **طوارئ المعركة:** أصيب البطل **{victim_name}** بإصابة بالغة ونُقل للمستشفى! (يمكن لأي بطل علاجه بـ `!علاج @{victim_name}`)."

                # بناء قائمة المشاركين في المعركة
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
                            f"• `!مستشفى` (لعرض المصابين)\n"
                            f"• `!تاريخ_مرضي` (لمراجعة سجلك)"
                            f"{AUTHOR_SIGNATURE}",
                    view=None
                )
        else:
            await interaction.followup.send(f"⚡ انتهت المعركة مسبقاً وتم القضاء على الخطر!{AUTHOR_SIGNATURE}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح باسم البوت الجبار في ريلواي: {bot.user}")

# ----------------- ⚡ أمر الهجوم اليدوي وبدء الغارة ----------------- #
@bot.command(name="هجوم")
async def start_raid_command(ctx):
    global current_hp, raid_active, player_scores
    current_hp = MAX_HP
    raid_active = True
    player_scores.clear() # تصفير قائمة المشاركين لمعركة جديدة
    
    health_bar = get_health_bar(MAX_HP, MAX_HP)
    await ctx.send(
        f"🚨 **[ غارة مرعبة تهدد القرية! ]**\n"
        f"تجمع قتلة السحرة وجماعة Death Eaters في الأفق ومعهما طاقة مظلمة لتهشيم البوابات!\n\n"
        f"🖤 صحة زعيم الموت المهاجم: `{current_hp}/{MAX_HP}`\n"
        f"[{health_bar}]\n\n"
        f"🛡️ يا أهالي القرية والأبطال، اضغطوا على زر التعويذة أدناه بسرعة لإنقاذ الوطن!"
        f"{AUTHOR_SIGNATURE}",
        view=VillageDefenseView()
    )

# ----------------- 🩹 أمر العلاج والإسعاف ----------------- #
@bot.command(name="علاج")
async def cure_hospital_patient(ctx, member: discord.Member):
    global hospital_patients
    if member.id in hospital_patients:
        hospital_patients.remove(member.id)
        init_user_history(member.id)
        medical_history[member.id]["cures_received"] += 1
        
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

# ----------------- 🏥 قائمة المستشفى ----------------- #
@bot.command(name="مستشفى")
async def list_hospital_patients(ctx):
    if not hospital_patients:
        await ctx.send(f"🏥 المستشفى الحربي خالي تماماً من الإصابات.. الجميع في الميدان وجاهزون للمعركة!{AUTHOR_SIGNATURE}")
        return
    
    report = "🏥 **[ قائمة الأبطال المصابين في المستشفى الحربي ]** 🏥\n\n"
    for pid in hospital_patients:
        report += f"🛌 البطل المصاب: <@{pid}> (ينتظر الإسعاف)\n"
    report += "\n🪄 استخدم أمر `!علاج @الساحر` لإسعافهم بسرعة!" + AUTHOR_SIGNATURE
    await ctx.send(report)

# ----------------- 📜 السجل العسكري والصحي ----------------- #
@bot.command(name="تاريخ_مرضي")
async def medical_history_command(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    init_user_history(target.id)
    
    stats = medical_history[target.id]
    await ctx.send(
        f"📋 **[ السجل العسكري والصحي للبطل ]** 📋\n"
        f"الملف الخاص بالبطل: {target.mention}\n\n"
        f"⚡ ضربات الهجوم الناجحة: **{stats['attack_count']}** ضربة\n"
        f"🛌 إصابات معارك ناتجة عن الغارات: **{stats['hospital_visits']}** مرة\n"
        f"🩹 مرات علاج وإنقاذ الأبطال الآخرين: **{stats['cures_received']}** مرة\n\n"
        f"🏥 *مركز هوجوورتس الحربي الرسمي.*"
        f"{AUTHOR_SIGNATURE}"
    )

# ----------------- 🏆 لوحة شرف الصدارة ----------------- #
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

# ⏰ الغارة التلقائية (كل 12 ساعة)
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
            f"🛡️ يا أهالي القرية، استعدوا للمعركة واضغطوا على زر التعويذة أدناه!"
            f"{AUTHOR_SIGNATURE}",
            view=VillageDefenseView()
        )

bot.run(os.getenv("BOT_TOKEN"))
