import discord
from discord.ext import commands, tasks
import random
import os
import json
from flask import Flask
from threading import Thread

# إعداد سيرفر الويب البسيط لإبقاء البوت مستيقظاً على Render
app = Flask('')

@app.route('/')
def home():
    return "I'm alive, Cedric!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# إعدادات البوت والصلاحيات
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # مهم جداً لقراءة أعضاء السيرفر وإصابتهم عشوائياً
bot = commands.Bot(command_prefix="!", intents=intents)

# التوقيع الرسمي للصانع
AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"

# ملف حفظ البيانات للمرضى
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
    """تحميل المرضى وآخر شخص أصيب من الملف الخارجي"""
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
    """حفظ البيانات فوراً في الملف"""
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

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح باسم الساحر: {bot.user}")
    daily_plague_outbreak.start()

# ----------------- نظام الإصابة اليومية التلقائي (كل 24 ساعة) ----------------- #
@tasks.loop(hours=24)
async def daily_plague_outbreak():
    global last_victim_id
    channel_id = 1540623521774960682  # استبدله بـ ID قناتك
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
            save_data(sick_patients, last_victim_id)
            
            disease_desc = random.choice(MAGICAL_DISEASES)
            
            await channel.send(
                f"🚨 **[ عدوى اليوم السحرية في قلعة هوجوورتس! ]** 🚨\n"
                f"مع إشراقة شمس اليوم الجديد، تسلل وباء خفي من مستشفى سانت مانجو وأصاب أحد السحرة عشوائياً!\n\n"
                f"👤 الساحر المصاب اليوم: <@{victim.id}>\n"
                f"📉 نوع الإصابة: {disease_desc}\n\n"
                f"⚠️ **يا أبطال القلعة، استخدموا أمر `!علاج @{victim.name}` فوراً لإنقاذه!**"
                f"{AUTHOR_SIGNATURE}"
            )

# ----------------- أمر عدوى تجريبي (لتجربة إصابة أي شخص فوراً) ----------------- #
@bot.command(name="عدوى")
@commands.has_permissions(administrator=True)
async def test_infect(ctx, member: discord.Member):
    global sick_patients, last_victim_id
    sick_patients.add(member.id)
    last_victim_id = member.id
    save_data(sick_patients, last_victim_id)
    
    disease_desc = random.choice(MAGICAL_DISEASES)
    
    await ctx.send(
        f"🧪 **[ اختبار المعمل السحري - نشر العدوى ]** 🧪\n"
        f"بأمر مباشر من المطور، تم نقل العدوى إلى الساحر **{member.name}**!\n\n"
        f"👤 الضحية: <@{member.id}>\n"
        f"📉 نوع الإصابة: {disease_desc}\n\n"
        f"🪄 *جرّب الآن استخدام أمر `!علاج @{member.name}` لاختبار نظام الشفاء!*"
        f"{AUTHOR_SIGNATURE}"
    )

@test_infect.error
async def test_infect_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ يا ريت تحدد الساحر المراد نقله للعدوى، مثلاً:\n`!عدوى @اسم_الساحر`" + AUTHOR_SIGNATURE)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ عذراً يا أستاذ، أمر العدوى التجريبي هذا مخصص لمشرفي القلعة فقط!" + AUTHOR_SIGNATURE)

# ----------------- أمر العلاج الإجباري للمرضى ----------------- #
@bot.command(name="علاج")
async def cure_sick_person(ctx, member: discord.Member):
    global sick_patients
    if member.id in sick_patients:
        sick_patients.remove(member.id)
        save_data(sick_patients, last_victim_id)
        await ctx.send(
            f"🌿✨ **[ إعلان شفاء عاجل من جناح المستشفى ]** ✨🌿\n\n"
            f"🪄 نجح البطل الأسطوري **{ctx.author.name}** في تحضير الترياق السحري وتقديم الجرعة للساحر **{member.name}**!\n"
            f"💨 (تلاشى الدخان الأخضر واختفت الأعراض المرعبة فوراً).. وعادت للساحر صحته الكاملة!\n\n"
            f"🎉 **مبروك الشفاء!** لقد نجا البطل وعاد لممارسة سحره وحياته في القلعة بكامل طاقته! ⚔️🔥"
            f"{AUTHOR_SIGNATURE}"
        )
    else:
        await ctx.send(
            f"🔮 يا أستاذ، الساحر **{member.name}** ليس مصاباً بأي وباء أو مرض حالياً.. هو في قمة صحته وسحره ولا يحتاج لعلاج!"
            f"{AUTHOR_SIGNATURE}"
        )

@cure_sick_person.error
async def cure_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"⚠️ يا ريت تحدد الساحر المرضان المراد علاجه بشكل صحيح، مثلاً:\n`!علاج @اسم_الساحر`"
            f"{AUTHOR_SIGNATURE}"
        )

# ----------------- أمر لعرض قائمة المرضى والمصابين الحاليين ----------------- #
@bot.command(name="مرضى")
async def list_sick_patients(ctx):
    if not sick_patients:
        await ctx.send(
            f"🏥 **[ سجلات مستشفى سانت مانجو والأوبئة ]**:\n"
            f"✨ الحمد لله، ممرات القلعة خالية تماماً من الأمراض والأوبئة السحرية.. الجميع يتمتع بصحة ممتازة!"
            f"{AUTHOR_SIGNATURE}"
        )
        return
    
    report = "🏥 **[ قائمة السحرة المصابين بالأوبئة واللعنات حالياً ]** 🏥\n\n"
    for pid in sick_patients:
        report += f"🛌 الساحر المصاب: `<@{pid}>` (يرقد بانتظار الترياق)\n"
    
    report += "\n🪄 *أسرعوا واستخدموا أمر `!علاج @الساحر` لإنقاذهم من اللعنة!*"
    report += AUTHOR_SIGNATURE
    await ctx.send(report)

# تشغيل البوت باستخدام متغير البيئة في رندر
bot.run(os.getenv("BOT_TOKEN"))
