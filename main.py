import os
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

app = FastAPI(title="Hogwarts Magical Dashboard")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("DASHBOARD_SECRET", "change-this-secret-in-railway"),
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=True
)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://Infection-bot-production.up.railway.app/auth/callback"
)
API_ENDPOINT = "https://discord.com/api/v10"
AUTHOR_SIGNATURE = "✦ صُنع بعناية بواسطة سيدريك 🪄"

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>الوزارة السحرية</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#08060d] text-white min-h-screen flex items-center justify-center p-5">
<div class="bg-[#16101f] border border-yellow-500/30 rounded-3xl p-10 max-w-lg w-full text-center shadow-2xl">
<div class="text-6xl mb-4">🪄</div>
<h1 class="text-3xl font-bold text-yellow-500 mb-3">الإدارة السحرية</h1>
<p class="text-gray-400 mb-6">لوحة التحكم الرسمية لإدارة المملكة السحرية والطلاب والفعاليات.</p>
<a href="/login" class="block bg-[#5865F2] hover:bg-[#4752C4] py-3 rounded-xl font-bold transition-all shadow-lg">الدخول بواسطة Discord ✨</a>
<p class="text-gray-600 text-xs mt-6">{AUTHOR_SIGNATURE}</p>
</div>
</body>
</html>
""")

@app.get("/login")
async def login():
    if not CLIENT_ID:
        raise HTTPException(status_code=500, detail="CLIENT_ID غير موجود")
    return RedirectResponse(f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds")

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str):
    async with aiohttp.ClientSession() as session:
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with session.post(f"{API_ENDPOINT}/oauth2/token", data=payload, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=400, detail="فشل تسجيل الدخول")
            token_data = await resp.json()
            
        async with session.get(f"{API_ENDPOINT}/users/@me", headers={"Authorization": f"Bearer {token_data.get('access_token')}"}) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=400, detail="تعذر الحصول على بيانات المستخدم")
            user = await resp.json()
            
    request.session["user"] = {
        "id": user.get("id"),
        "username": user.get("username"),
        "global_name": user.get("global_name"),
        "avatar": user.get("avatar")
    }
    return RedirectResponse("/dashboard")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")
    name = user.get("global_name") or user.get("username")
    return HTMLResponse(f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>لوحة التحكم</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#08060d] text-white min-h-screen p-10">
<div class="max-w-4xl mx-auto bg-[#16101f] border border-white/10 rounded-3xl p-8 shadow-xl">
<h1 class="text-3xl font-bold text-yellow-500 mb-4">مرحباً بك يا {name} 🪄</h1>
<p class="text-gray-400 mb-6">تم تسجيل الدخول بنجاح إلى لوحة التحكم السحرية.</p>
<a href="/logout" class="bg-red-500 hover:bg-red-600 px-5 py-2.5 rounded-xl font-bold transition-all">تسجيل الخروج</a>
</div>
</body>
</html>
""")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)


