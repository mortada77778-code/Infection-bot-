import discord
from discord.ext import commands
import os

AUTHOR_SIGNATURE = "— تم الصناعة بواسطة سيدريك 🪄"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قائمة أقسام الـ Cogs المعرفة يدوياً
INITIAL_EXTENSIONS = [
    "cogs.sorting",
    "cogs.forest_attack",
    "cogs.events_manager",
    "cogs.duel"
]

@bot.event
async def on_ready():
    print(f"البوت جاهز ويعمل باسم: {bot.user.name} (ID: {bot.user.id})")
    print(AUTHOR_SIGNATURE)
    
    # تحميل الأقسام يدوياً واحدة تلو الأخرى
    for extension in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(extension)
            print(f"تم تحميل القسم بنجاح: {extension}")
        except Exception as e:
            print(f"فشل تحميل القسم {extension}: {e}")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
