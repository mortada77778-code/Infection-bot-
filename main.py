import discord
from discord.ext import commands
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# سيرفر ويب وهمي عشان ريلواي يفضل مفكر إن البوت شغال وما يقفلوش
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# تشغيل السيرفر الوهمي في خيط منفصل
threading.Thread(target=run_web_server, daemon=True).start()

AUTHOR_SIGNATURE = "— تم الصناعة بواسطة سيدريك 🪄"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"البوت جاهز ويعمل باسم: {bot.user.name} (ID: {bot.user.id})")
    print(AUTHOR_SIGNATURE)
    
    if os.path.exists("./cogs"):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                cog_name = filename[:-3]
                try:
                    await bot.load_extension(f"cogs.{cog_name}")
                    print(f"تم تحميل القسم بنجاح: cogs.{cog_name}")
                except Exception as e:
                    print(f"فشل تحميل القسم {cog_name}: {e}")
    else:
        print("⚠️ تنبيه: مجلد cogs غير موجود في المسار الرئيسي!")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
