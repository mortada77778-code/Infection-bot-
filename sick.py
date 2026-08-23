import discord
from discord.ext import commands, tasks
import random
import os
import json

# ----------------- إعدادات البوت والصلاحيات ----------------- #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # مهم جداً لقراءة أعضاء السيرفر وإصابتهم عشوائياً
bot = commands.Bot(command_prefix="!", intents=intents)

# التوقيع الرسمي للصانع
AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"

# ملف حفظ بيانات المرضى والأوبئة
DATA_FILE = "plague_data.json"

# أكثر من 30 مرض سحري ولعنة من عالم هاري بوتر
MAGICAL_DISEASES = [
    "🦠 **حمى التنين الخطيرة** (ارتفعت حرارة الساحر وأصبح ينفث دخاناً كثيفاً من أنفه!)",
    "🧪 **تسمم الجرعات المظلمة** (ظهرت على جسده بقع خضراء غريبة يفقد بسببها توازنه تماماً!)",
    "🦇 **لعنة مصاصي الدماء الصغار** (فقد الساحر القدرة على الكلام وأصبح يهذي بكلمات غامضة!)",
    "🌀 **دوار المستنقعات السحرية** (شعر بدوخة شديدة تفقده القدرة على توجيه عصاه السحرية!)",
    "🐍 **سحر لسان الباسيلسك** (تحول لسان الساحر إلى لسان ثعبان وأصبح يتحدث لغة الثلاث رؤوس!)",
    "🧊 **متلازمة الصقيع القطبي** (تجمدت أطراف أصابعه ولا يستطيع إمساك عصاه السحرية بسببه!)",
    "🍄 **وباء الفطر المضيء** (بدأت تنمو فطور مضيئة على وجهه وجسمه تضيء في الظلام!)",
    "⚡ **ماس كهربائي سحري** (كلما حاول لمس شيء تتطاير من أصابعه شرارة برق مؤلمة!)",
    "💤 **لعنة النوم الأبدي المصغر** (يكاد يغفو واقفاً ولا يستطيع فتح عينه لأكثر من ثوانٍ!)",
    "🐸 **متلازمة التحول الضفدعي** (بدأ صوت الساحر يشبه نقيق الضفادع مع انتفاخ طفيف في الوجنتين!)",
    "👻 **مس شيطاني بارد** (شعر ببرودة مرعبة تسري في عروقه وتجعله يرتجف طوال الوقت!)",
    "📜 **مرض هذيان التعاويذ** (نسي اسمه تماماً وأصبح يصرخ بتعويذات عشوائية بصوت مرتفع!)",
    "🥀 **لعنة الذبول السحري** (فقدت ملابسه وشعره ألوانها وأصبحت باهتة كالأشباح!)",
    "🦅 **جنون طيور البومة** (أصبح يحرك رأسه بزاوية 180 درجة ويصدر أصوات تشبه بومة الحراسة!)",
    "🌪️ **عاصفة العطس العنيف** (كل عطسة يطلقها تتسبب في إحداث هواء قسري يطير من حوله!)",
    "🍯 **لعنة العسل السام** (أصبح يشتهي أكل التراب والكتب القديمة بدلاً من الطعام!)",
    "🕸️ **هوس نسيج العناكب** (يتخيل أن هناك خيوط عنكبوت خفية تغطي وجهه ويحاول إزالتها باسترخاء!)",
    "🔮 **عمى البصيرة السحرية** (فقد القدرة على رؤية الألوان وأصبح العالم أمامه بالأبيض والأسود!)",
    "🦴 **طقطقة العظام الإيقاعية** (كلما تحرك أصدرت عظامه أصوات طقطقة مزعجة تشبه قرع الطبول!)",
    "🔥 **احتراق الحنجرة الداخلي** (يشعر وكأنه بلع جمراً ملتهباً ويطلب الماء باستمرار!)",
    "💧 **التعرق اللامع** (يفرز جسمه عرقاً لامعاً برائحة تشبه مسحوق الأعشاب المرة!)",
    "🐈 **حساسية القطط المفرطة** (يصاب بنوبة عطس وهيسترية كلما اقترب أحدهم من حيوان أليف!)",
    "🪵 **تصلب الجذع الخشبي** (بدأت ذراعاه تتصلب وتصبح خشنة كأنها أغصان شجرة الصنوبر!)",
    "🕳️ **ثقب الذاكرة المؤقت** (نسي تماماً كيف يقوم بإلقاء أسطح التعاويذ البسيطة!)",
    "🔊 **صفير الأذن الحاد** (يسمع طنين وصوت صفير صفارات الإنذار سحرية داخل رأسه بلا توقف!)",
    "💫 **دوار النجوم المتطايرة** (يرى نجوم صغيرة تدور حول رأسه في كل مكان يذهب إليه!)",
    "🪞 **رهاب المرايا والانعكاسات** (يخاف بشدة من النظر إلى أي سطح عاكس أو ماء صافٍ!)",
    "🧌 **تضخم القدمين المفاجئ** (أصبحت قدماه بحجم قدمي عملاق ولا يستطيع ارتداء حذائه!)",
    "🧂 **متلازمة العطش الصحراوي** (يشعر بجفاف تام في حلقه مهما شرب من السوائل!)",
    "🎭 **تغير الصوت المستمر** (يتغير صوت الساحر في كل جملة ينطقها بين صوت رفيع وآخر غليظ!)",
    "🪶 **خفة الوزن المفرطة** (أصبح وزنه خفيفاً لدرجة أن نسمة هواء قوية قد ترفعه في الهواء!)",
    "🌑 **لعنة الظل الهارب** (انفصل ظله عنه وأصبح يتحرك بطريقة مزعجة خلفه دون سيطرة!)"
]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                patients = set(int(pid) for pid in data.get("sick_patients", []))
                last_victim = data.get("last_victim", None)
                return patients, last_victim
        except Exception:
            pass
    return set(), None

def save_data(patients, last_victim):
    data = {
        "sick_patients": list(patients),
        "last_victim": last_victim
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

sick_patients, last_victim_id = load_data()

# ----------------- إعدادات المعركة وأرشيف السجلات الطبية ----------------- #
MAX_HP = 200          
current_hp = MAX_HP
DAMAGE_PER_HIT = 10
raid_active = False

player_scores = {}      # {user_id: {"name": "اسم", "hits": عدد الضربات}}
medical_history = {}    # أرشيف السجلات الطبية الشامل

def init_user_history(user_id):
    if user_id not in medical_history:
        medical_history[user_id] = {
            "attack_count": 0,
            "hospital_visits": 0,
            "cures_received": 0,
            "plague_count": 0
        }

def get_health_bar(hp):
    filled = hp // 20
    empty = 10 - filled
    return "🟥" * filled + "🟩" * empty

# ----------------- واجهة الدفاع عن القرية (زر الهجوم) ----------------- #
class VillageDefenseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚔️ سحق أكلة الموت! (هجوم)", style=discord.ButtonStyle.danger, custom_id="village_defense_btn")
    async def defense_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global current_hp, raid_active
        
        await interaction.response.defer()
        
        user_id = interaction.user.id
        user_name = interaction.user.name

        init_user_history(user_id)

        # فحص لو اللاعب مريض
        if user_id in sick_patients:
            await interaction.followup.send(f"🏥 يا وحش أنت مصاب بوباء سحري وتتلقى العلاج! لا يمكنك المشاركة في المعركة حتى يعالجك أي بطل بالأمر `!علاج`.{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        if not raid_active:
            await interaction.followup.send(f"⚡ القرية آمنة تماماً يا وحش، مافي أي خطر حالياً!{AUTHOR_SIGNATURE}", ephemeral=True)
            return

        # تسجيل النقاط وتاريخ الهجوم
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
                health_bar = get_health_bar(current_hp)
                await interaction.message.edit(
                    content=f"⚠️ **[ إنذار أحمر: معركة ملحمية تدور الآن! ]** ⚠️\n"
                            f"أعوان **Death Eaters** يتقدمون بظلامهم ويحاولون حرق أسوار القرية!\n\n"
                            f"🖤 **صحة زعيم الموت المهاجم:** `{current_hp}/{MAX_HP}`\n"
                            f"[{health_bar}]\n\n"
                            f"⚡ *استمروا في الضرب! آخر ضربة قوية وجهها البطل:* **{user_name}** (-10 ضرر 🔥)"
                            f"{AUTHOR_SIGNATURE}"
                )
            else:
                raid_active = False
                
                hospital_msg = ""
                if player_scores:
                    all_fighters = list(player_scores.keys())
                    victim_id = random.choice(all_fighters)
                    sick_patients.add(victim_id)
                    init_user_history(victim_id)
                    medical_history[victim_id]["hospital_visits"] += 1
                    
                    victim_name = player_scores[victim_id].get("name", "مقاتل مجهول")
                    disease_desc = random.choice(MAGICAL_DISEASES)
                    hospital_msg = f"\n\n🚑 **طوارئ المعركة:** أصيب البطل **{victim_name}** بلعنة قوية أثناء القتال ونُقل للمستشفى!\n📉 الإصابة: {disease_desc}\n*يمكن لأي بطل علاجه بـ `!علاج @{victim_name}`.*"

                await interaction.message.edit(
                    content=f"🏆 **[ نصر أسطوري لا يُنسى! ]** 🏆\n"
                            f"بفضل عزيمة الأبطال وبسالة **{user_name}** ومن معه، تم سحق جيش الـ Death Eaters وطردهم من حدود القرية! 🎉🛡️✨"
                            f"{hospital_msg}\n\n"
                            f"📊 *اكتب أمر `!صدارة` لمراجعة جدول الأبطال، أو `!مرضى` لعرض المصابين، أو `!تاريخ_مرضي` لسجلاتك!*"
                            f"{AUTHOR_SIGNATURE}"
                )
        else:
            await interaction.followup.send(f"⚡ المعركة انتهت وتم القضاء على الخطر مسبقاً!{AUTHOR_SIGNATURE}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح باسم البوت الجبار في ريلواي: {bot.user}")
    bot.add_view(VillageDefenseView())
    scheduled_attack.start()
    daily_plague_outbreak.start()

# ----------------- ⚡ أمر الهجوم اليدوي وبدء الغارة ----------------- #
@bot.command(name="هجوم")
async def start_raid_command(ctx):
    global current_hp, raid_active
    current_hp = MAX_HP
    raid_active = True
    
    health_bar = get_health_bar(MAX_HP)
    await ctx.send(
        f"🚨 **[ غارة مرعبة تهدد القرية! ]** 🚨\n"
        f"تجمع قتلة السحرة وجماعة **Death Eaters** في الأفق ومعهما طاقة مظلمة لتهشيم البوابات!\n\n"
        f"🖤 **صحة زعيم الموت المهاجم:** `{current_hp}/{MAX_HP}`\n"
        f"[{health_bar}]\n\n"
        f"🛡️ **يا أهالي القرية والأبطال، استعدوا للمعركة واضغطوا على زر الدفاع أدناه بسرعة لانقاذ الوطن!**"
        f"{AUTHOR_SIGNATURE}",
        view=VillageDefenseView()
    )

# ----------------- 🦠 نظام العدوى اليومية التلقائية (كل 24 ساعة) ----------------- #
@tasks.loop(hours=24)
async def daily_plague_outbreak():
    global last_victim_id
    channel_id = 1540623521774960682  # معرف قناتك
    channel = bot.get_channel(channel_id)
    
    if channel and channel.guild.members:
        available_members = [
            m for m in channel.guild.members 
            if not m.bot and m.id != last_victim_id and m.id not in sick_patients
        ]
        
        if not available_members:
            available_members = [m for m in channel.guild.members if not m.bot]
            
        if available_members:
            victim = random.choice(available_members)
            sick_patients.add(victim.id)
            last_victim_id = victim.id
            init_user_history(victim.id)
            medical_history[victim.id]["plague_count"] += 1
            save_data(sick_patients, last_victim_id)
            
            disease_desc = random.choice(MAGICAL_DISEASES)
            
            await channel.send(
                f"🚨 **[ عدوى اليوم السحرية في قلعة هوجوورتس! ]** 🚨\n"
                f"مع إشراقة شمس اليوم الجديد، تسلل وباء خفي وأصاب أحد السحرة عشوائياً!\n\n"
                f"👤 الساحر المصاب اليوم: <@{victim.id}>\n"
                f"📉 نوع الإصابة: {disease_desc}\n\n"
                f"⚠️ **يا أبطال القلعة، استخدموا أمر `!علاج @{victim.name}` فوراً لإنقاذه!**"
                f"{AUTHOR_SIGNATURE}"
            )

# ----------------- أمر عدوى تجريبي (للمشرفين) ----------------- #
@bot.command(name="عدوى")
@commands.has_permissions(administrator=True)
async def test_infect(ctx, member: discord.Member):
    global sick_patients, last_victim_id
    sick_patients.add(member.id)
    last_victim_id = member.id
    init_user_history(member.id)
    medical_history[member.id]["plague_count"] += 1
    save_data(sick_patients, last_victim_id)
    
    disease_desc = random.choice(MAGICAL_DISEASES)
    
    await ctx.send(
        f"🧪 **[ اختبار المعمل السحري - نشر العدوى ]** 🧪\n"
        f"بأمر مباشر، تم نقل العدوى إلى الساحر **{member.name}**!\n\n"
        f"👤 الضحية: <@{member.id}>\n"
        f"📉 نوع الإصابة: {disease_desc}\n\n"
        f"🪄 *جرّب الآن استخدام أمر `!علاج @{member.name}` لاختبار نظام الشفاء!*"
        f"{AUTHOR_SIGNATURE}"
    )

@test_infect.error
async def test_infect_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ حدد الساحر المراد نقله للعدوى، مثلاً: `!عدوى @اسم_الساحر`" + AUTHOR_SIGNATURE)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ عذراً، أمر العدوى التجريبي مخصص لمشرفي القلعة فقط!" + AUTHOR_SIGNATURE)

# ----------------- أمر العلاج (متاح لأي شخص في السيرفر) ----------------- #
@bot.command(name="علاج")
async def cure_sick_person(ctx, member: discord.Member):
    global sick_patients
    if member.id in sick_patients:
        sick_patients.remove(member.id)
        save_data(sick_patients, last_victim_id)
        init_user_history(member.id)
        medical_history[member.id]["cures_received"] += 1
        
        await ctx.send(
            f"🌿✨ **[ إعلان شفاء عاجل من المستشفى ]** ✨🌿\n\n"
            f"🪄 نجح البطل الشهام **{ctx.author.name}** في تحضير الترياق وإسعاف الساحر **{member.name}**!\n"
            f"💨 (تلاشى الدخان واختفت الأعراض المرعبة).. وعادت للساحر صحته الكاملة!\n\n"
            f"🎉 **مبروك الشفاء!** لقد نجا البطل وعاد لممارسة سحره وحياته في القلعة بكامل طاقته! ⚔️🔥"
            f"{AUTHOR_SIGNATURE}"
        )
    else:
        await ctx.send(
            f"🔮 يا أستاذ، الساحر **{member.name}** ليس مصاباً بأي وباء أو مرض حالياً.. هو في قمة صحته ولا يحتاج لعلاج!"
            f"{AUTHOR_SIGNATURE}"
        )

@cure_sick_person.error
async def cure_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ حدد الساحر المراد علاجه بشكل صحيح، مثلاً: `!علاج @اسم_الساحر`" + AUTHOR_SIGNATURE)

# ----------------- أمر لعرض قائمة المرضى والمصابين ----------------- #
@bot.command(name="مرضى")
async def list_sick_patients(ctx):
    if not sick_patients:
        await ctx.send(
            f"🏥 **[ سجلات مستشفى الأوبئة ]**:\n"
            f"✨ الحمد لله، ممرات القلعة خالية تماماً من الأمراض والأوبئة.. الجميع يتمتع بصحة ممتازة!"
            f"{AUTHOR_SIGNATURE}"
        )
        return
    
    report = "🏥 **[ قائمة السحرة المصابين بالأوبئة واللعنات حالياً ]** 🏥\n\n"
    for pid in sick_patients:
        report += f"🛌 الساحر المصاب: `<@{pid}>` (يرقد بانتظار الترياق والعلاج)\n"
    
    report += "\n🪄 *أسرعوا واستخدموا أمر `!علاج @الساحر` لإنقاذهم!*"
    report += AUTHOR_SIGNATURE
    await ctx.send(report)

# ----------------- 📜 أمر السجل الطبي الشامل (!تاريخ_مرضي) 📜 ----------------- #
@bot.command(name="تاريخ_مرضي")
async def medical_history_command(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    init_user_history(target.id)
    
    stats = medical_history[target.id]
    attacks_num = stats["attack_count"]
    hospital_visits = stats["hospital_visits"]
    plagues_num = stats["plague_count"]
    cures_num = stats["cures_received"]
    
    await ctx.send(
        f"📋 **[ أرشيف السجلات الطبية لقرية هوجوورتس ]** 📋\n"
        f"الملف الخاص بالبطل: {target.mention}\n\n"
        f"⚡ ضربات الهجوم في معارك أكلة الموت: **{attacks_num}** ضربة\n"
        f"🛌 إصابات معارك ناتجة عن الغارات: **{hospital_visits}** مرة\n"
        f"🦠 الإصابة بالأوبئة واللعنات السحرية: **{plagues_num}** مرة\n"
        f"🩹 مرات تقديم العلاج والإنقاذ للآخرين: **{cures_num}** مرة\n\n"
        f"🏥 *السجل محفوظ بمركز هوجوورتس الطبي الرسمي.*"
        f"{AUTHOR_SIGNATURE}"
    )

# ----------------- 🏆 لوحة شرف الصدارة ----------------- #
@bot.command(name="صدارة")
async def leaderboard_command(ctx):
    if not player_scores:
        await ctx.send(f"📊 **لوحة الصدارة فارغة حالياً! مافي زول شارك في المعارك لسه.**{AUTHOR_SIGNATURE}")
        return

    sorted_players = sorted(player_scores.values(), key=lambda x: x["hits"], reverse=True)
    
    table_lines = []
    table_lines.append(f"{'المرتبة':<8} | {'اسم البطل':<15} | {'الضربات':<8} | {'الضرر':<6}")
    table_lines.append("-" * 45)
    
    medals = ["🥇 الأول", "🥈 الثاني", "🥉 الثالث", " 4     ", " 5     ", " 6     ", " 7     ", " 8     ", " 9     ", " 10    "]
    for i, player in enumerate(sorted_players[:10]):
        rank = medals[i]
        name = player["name"][:14].ljust(15)
        hits = str(player["hits"]).ljust(8)
        damage = str(player["hits"] * DAMAGE_PER_HIT).ljust(6)
        
        table_lines.append(f"{rank:<8} | {name} | {hits} | {damage}")
    
    formatted_table = "```text\n" + "\n".join(table_lines) + "\n```"
    
    await ctx.send(
        f"🏆 **[ لوحة شرف أبطال القرية - صدارة المدافعين ]** 🏆\n"
        f"{formatted_table}\n"
        f"🎁 *استمروا في الدفاع عن القرية لزيادة نقاطكم وتصدر القمة!*"
        f"{AUTHOR_SIGNATURE}"
    )

# ⏰ الغارة التلقائية لأكلة الموت (كل 12 ساعة)
@tasks.loop(hours=12)
async def scheduled_attack():
    global current_hp, raid_active
    channel_id = 1540623521774960682  
    channel = bot.get_channel(channel_id)
    
    if channel:
        current_hp = MAX_HP
        raid_active = True
        health_bar = get_health_bar(MAX_HP)
        
        hospital_msg = ""
        if player_scores:
            all_fighters = list(player_scores.keys())
            victim_id = random.choice(all_fighters)
            sick_patients.add(victim_id)
            init_user_history(victim_id)
            medical_history[victim_id]["hospital_visits"] += 1
            victim_name = player_scores[victim_id].get("name", "مقاتل مجهول")
            hospital_msg = f"\n\n🚑 **طوارئ الغارة السابقة:** أُصيب البطل **{victim_name}** ونُقل للمستشفى! يمكن لأي بطل علاجه بـ `!علاج @{victim_name}`."

        await channel.send(
            f"🚨 **[ غارة مرعبة تهدد القرية! ]** 🚨\n"
            f"تجمع قتلة السحرة وجماعة **Death Eaters** في الأفق ومعهما طاقة مظلمة لتهشيم البوابات!\n\n"
            f"🖤 **صحة زعيم الموت المهاجم:** `{current_hp}/{MAX_HP}`\n"
            f"[{health_bar}]"
            f"{hospital_msg}\n\n"
            f"🛡️ **يا أهالي القرية والأبطال، استعدوا للمعركة واضغطوا على زر الدفاع أدناه بسرعة لانقاذ الوطن!**"
            f"{AUTHOR_SIGNATURE}",
            view=VillageDefenseView()
        )

# تشغيل البوت بالتوكن الآمن في ريلواي
bot.run(os.getenv("BOT_TOKEN"))
