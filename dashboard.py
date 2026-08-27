import os
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

app = FastAPI(title="Magic Bot Dashboard")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://Infection-bot-production.up.railway.app/auth/callback")
API_ENDPOINT = "https://discord.com/api/v10"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>لوحة تحكم بوت السحر</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#0f0a1a] text-white font-sans flex items-center justify-center h-screen">
        <div class="bg-[#1e1128] border border-[#d4af37] p-8 rounded-2xl shadow-2xl text-center max-w-md w-full">
            <h1 class="text-3xl font-bold text-[#d4af37] mb-4">🪄 لوحة تحكم السحر</h1>
            <p class="text-gray-300 mb-6">تحكم بإدارة البوت، الفعاليات، وسجلات الطلاب بكل سهولة.</p>
            <a href="/login" class="inline-block bg-[#5865F2] hover:bg-[#4752C4] text-white font-bold py-3 px-6 rounded-xl transition duration-300 shadow-lg">
                تسجيل الدخول بواسطة Discord 🚀
            </a>
            <div class="mt-8 text-xs text-gray-500">_— تم الصناعة بواسطة سيدريك 🪄_</div>
        </div>
    </body>
    </html>
    """

@app.get("/login")
async def login():
    discord_login_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return RedirectResponse(discord_login_url)

@app.get("/auth/callback")
async def auth_callback(code: str):
    async with aiohttp.ClientSession() as session:
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with session.post(f"{API_ENDPOINT}/oauth2/token", data=payload, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=400, detail="فشل المصادقة مع ديسكورد")
            token_data = await resp.json()
            access_token = token_data.get("access_token")

        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.get(f"{API_ENDPOINT}/users/@me", headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=400, detail="فشل جلب بيانات المستخدم")
            user_data = await resp.json()

    return RedirectResponse(f"/dashboard?user={user_data.get('username')}")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(user: str = "مشرف"):
    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>الداشبورد الرئيسية</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#0f0a1a] text-white p-8">
        <div class="max-w-4xl mx-auto">
            <div class="flex justify-between items-center bg-[#1e1128] border border-[#d4af37] p-6 rounded-2xl shadow-xl mb-8">
                <h1 class="text-2xl font-bold text-[#d4af37]">🪄 مرحباً بك يا {user}</h1>
                <a href="/" class="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg text-sm font-bold">تسجيل الخروج</a>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-[#1e1128] border border-purple-500 p-6 rounded-xl text-center shadow-lg">
                    <h3 class="text-gray-400">حالة البوت</h3>
                    <p class="text-xl font-bold text-green-400 mt-2">متصل ونشط 🟢</p>
                </div>
                <div class="bg-[#1e1128] border border-purple-500 p-6 rounded-xl text-center shadow-lg">
                    <h3 class="text-gray-400">إدارة الفعاليات</h3>
                    <p class="text-xl font-bold text-[#00ffcc] mt-2">متاح للتحكم</p>
                </div>
                <div class="bg-[#1e1128] border border-purple-500 p-6 rounded-xl text-center shadow-lg">
                    <h3 class="text-gray-400">سجلات الطلاب</h3>
                    <p class="text-xl font-bold text-yellow-400 mt-2">نشطة</p>
                </div>
            </div>
            <div class="text-center mt-12 text-gray-500">_— تم الصناعة بواسطة سيدريك 🪄_</div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
