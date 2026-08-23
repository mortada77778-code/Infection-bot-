import discord
from discord.ext import commands
import random
import os

# 1. إعدادات الصلاحيات الأساسية للبوت
intents = discord.Intents.default()
intents.message_content = True
intents.members =True

bot = commands.Bot(command_prefix="!", intents=intents)

AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"

# قوائم لتتبع الحالات النشطة
attacked_players = set()
infected_players = set()

# سجل تاريخي لتتبع إحصائيات كل لاعب (عدد مرات الإصابة بالأمراض أو الهجمات)
medical_history = {} # مفتاحها الـ ID، وقيمتها القواميس فيها الإحصائيات

def init_user_history(user_id):
    if user_id not in medical_history:
        medical_history[user_id] = {
            "attack_count": 0,
            "plague_count": 0,
            "cures_received": 0
        }

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح، والسجلات الطبية جاهزة! باسم: {bot.user}")


# =====================================================================
# ⚡ أولاً: الصدارة والقمة (قسم الهجوم الحربي الأساسي) ⚡
# =====================================================================

@bot.command(name="هجوم")
async def attack_member(ctx, member: discord.Member):
    if member == ctx.author:
        await ctx.send(f"⚠️ يا {ctx.author.mention}, ما ينفع تهاجم نفسك! وجّه سحرك نحو أعدائك.")
        return

    init_user_history(member.id)
    medical_history[member.id]["attack_count"] += 1 # زيادة عداد إصابات المعارك في سجله
    attacked_players.add(member.id)

    attacks = [
        f"⚡ أطلق تعويذة **الصاعقة المدمرة** على الساحر {member.mention} وشلع مكانه!",
        f"🔥 رمى كرة من **النيران التنينية** مباشرة نحو {member.mention} وأحرق أطرافه!",
        f"🧊 جَمّد أطراف الساحر {member.mention} بتعويذة **الصقيع الجليدي** القاتلة!",
        f"🌪️ أحدث عاصفة من **الرياح العاتية** رفعت {member.mention} في الهواء وسقط بقوة!"
    ]
    chosen = random.choice(attacks)
    await ctx.send(
        f"⚔️ **[ صدارة المعارك السحرية - هوجوورتس ]** ⚔️\n"
        f"المقاتل الأسطوري **{ctx.author.name}** اقتحم ساحة القتال وشن هجوماً مرعباً!\n\n"
        f"{chosen}\n\n"
        f"💥 **استعد لتلقي الإصابة يا {member.mention}! (المستشفى في انتظارك عبر `!علاج`)**"
        f"{AUTHOR_SIGNATURE}"
    )

@bot.command(name="مصابين")
async def list_attacked(ctx):
    if not attacked_players:
        await ctx.send(f"🛡️ ساحة المعركة آمنة تماماً، لا توجد أي إصابات حرب حالياً!{AUTHOR_SIGNATURE}")
        return
    
    members_list = []
    for uid in attacked_players:
        m = ctx.guild.get_member(uid)
        if m:
            members_list.append(m.mention)
            
    await ctx.send(
        f"🏥 **[ سجل إصابات المعارك النشطة ]** 🏥\n"
        f"الساحرات والساحرة الذين أصيبوا مؤخراً:\n" + ", ".join(members_list) +
        f"\n\n🩺 **اضرب `!علاج @الشخص` لإسعافهم!**{AUTHOR_SIGNATURE}"
    )

@bot.command(name="علاج")
async def cure_attacked(ctx, member: discord.Member):
    if member.id in attacked_players:
        attacked_players.remove(member.id)
        init_user_history(member.id)
        medical_history[member.id]["cures_received"] += 1
        await ctx.send(
            f"🩹 **[ مستشفى الإسعافات السحرية ]** 🩹\n"
            f"البطل **{ctx.author.name}** أسعف زميله وعالج {member.mention} من آثار الهجوم المدمر!\n"
            f"🌟 عاد إلى ساحة المعركة بكامل قوته!"
            f"{AUTHOR_SIGNATURE}"
        )
    else:
        await ctx.send(f"✨ يا {ctx.author.mention}, {member.mention} أصلاً غير مصاب بإصابات حرب نشطة!{AUTHOR_SIGNATURE}")


# =====================================================================
# ثانياً: الخدمات المساندة (الأمراض والترياق)
# =====================================================================

@bot.command(name="مرض")
async def plague_member(ctx, member: discord.Member):
    if member == ctx.author:
        await ctx.send(f"⚠️ يا {ctx.author.mention}, ما ينفع تمرض نفسك!")
        return

    init_user_history(member.id)
    medical_history[member.id]["plague_count"] += 1 # زيادة عداد الأوبئة في سجله
    infected_players.add(member.id)

    plagues = [
        f"🦠 أصاب {member.mention} بلعنة **إنفلونزا الدجاج الطائر**!",
        f"🤢 رما عليه فايروس **التسمم الغامض**!",
        f"🤧 أصاب {member.mention} بمرض **العطس المستمر**!"
    ]
    chosen = random.choice(plagues)
    await ctx.send(
        f"☣️ **[ قسم الأوبئة المساند ]** ☣️\n"
        f"تم نشر الوباء بواسطة **{ctx.author.name}**:\n\n"
        f"{chosen}\n\n"
        f"💊 **{member.mention} دخل الحجر! (استخدم `!ترياق` للشفاء)**"
        f"{AUTHOR_SIGNATURE}"
    )

@bot.command(name="مرضى")
async def list_infected(ctx):
    if not infected_players:
        await ctx.send(f"🌿 قسم الأوبئة خالٍ تماماً من الفيروسات حالياً!{AUTHOR_SIGNATURE}")
        return
        
    members_list = []
    for uid in infected_players:
        m = ctx.guild.get_member(uid)
        if m:
            members_list.append(m.mention)
            
    await ctx.send(
        f"🦠 **[ قائمة المرضى بالحجر الصحي ]** 🦠\n" + ", ".join(members_list) +
        f"\n\n🧪 **اضرب `!ترياق @الشخص` لصنع المضاد!**{AUTHOR_SIGNATURE}"
    )

@bot.command(name="ترياق")
async def cure_infected(ctx, member: discord.Member):
    if member.id in infected_players:
        infected_players.remove(member.id)
        init_user_history(member.id)
        medical_history[member.id]["cures_received"] += 1
        await ctx.send(
            f"🧪 **[ معمل الترياق ]** 🧪\n"
            f"صنع **{ctx.author.name}** المضاد السحري وشفا {member.mention} تماماً من الوباء!"
            f"{AUTHOR_SIGNATURE}"
        )
    else:
        await ctx.send(f"✨ يا {ctx.author.mention}, {member.mention} ليس محجوراً صحياً بالأوبئة أصلاً!{AUTHOR_SIGNATURE}")


# =====================================================================
# ثالثاً: أمر السجل الطبي الجديد (!تاريخ_مرضي) 📜
# =====================================================================

@bot.command(name="تاريخ_مرضي")
async def medical_history_command(ctx, member: discord.Member = None):
    # لو ما حدد شخص، بيجيب سجله هو الشخص البعت الأمر
    target = member if member else ctx.author
    init_user_history(target.id)
    
    stats = medical_history[target.id]
    attacks_num = stats["attack_count"]
    plagues_num = stats["plague_count"]
    cures_num = stats["cures_received"]
    
    await ctx.send(
        f"📋 **[ أرشيف السجلات الطبية العسكرية ]** 📋\n"
        f"الملف الخاص بالساحر: {target.mention}\n\n"
        f"⚡ إجمالي إصابات المعارك (الهجمات): **{attacks_num}** مرة\n"
        f"🦠 إجمالي الإصابات بالأوبئة (الأمراض): **{plagues_num}** مرة\n"
        f"🩹 إجمالي مرات العلاج والتلقي للـ ترياق: **{cures_num}** مرة\n\n"
        f"🏥 *السجل محفوظ بمركز هوجوورتس الطبي الرسمي.*"
        f"{AUTHOR_SIGNATURE}"
    )


# =====================================================================
# رابعاً: معلومات البوت وقائمة الأوامر ذات الصدارة
# =====================================================================

@bot.command(name="about")
async def about_bot(ctx):
    await ctx.send(
        "🔮 **[ سجلات معهد هوجوورتس - بوابات الهجوم والمعارك ]** 🔮\n"
        "أنا البوت الحربي الأول، الصدارة دائماً للهجوم والصولات والجولات في السيرفر مع أرشيف طبي متكامل!\n"
        f"🛡️ الحالة: شغال 24 ساعة لخدمة المعارك.\n"
        f"{AUTHOR_SIGNATURE}"
    )

@bot.command(name="اوامر")
async def help_menu(ctx):
    await ctx.send(
        "📜 **[ دليل أوامر البوت والأرشيف الطبي ]** 📜\n\n"
        "⚔️ **[ النجم الأول - قسم الهجوم الحربي ]:**\n"
        "⚡ `!هجوم @الساحر` - الهجوم الأسطوري المدمر (الأساس!).\n"
        "🏥 `!مصابين` - لعرض قائمة المصابين النشطين.\n"
        "🩹 `!علاج @الساحر` - لعلاج المصاب حربياً.\n\n"
        "☣️ **[ الخدمات والأرشيف الطبي ]:**\n"
        "🦠 `!مرض @الساحر` - نشر وباء جانبي.\n"
        "📋 `!مرضى` - قائمة المرضى بالحجر.\n"
        "🧪 `!ترياق @الساحر` - صنع المضاد للمريض.\n"
        "📜 `!تاريخ_مرضي @الساحر` - لعرض السجل والأرشيف الطبي الكامل للعضو!\n\n"
        "ℹ️ `!about` | ❓ `!اوامر`\n"
        f"المعركة تستعر والأرشيف يسجل يا أبطال!{AUTHOR_SIGNATURE}"
    )

# تشغيل البوت بالتوكن الآمن
bot.run(os.getenv("BOT_TOKEN"))
