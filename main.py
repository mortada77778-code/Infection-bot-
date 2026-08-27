import os
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

# ============================================================
# CONFIG
# ============================================================

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


# ============================================================
# DISCORD AUTH & HOME
# ============================================================

@app.get("/")
async def home():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>الوزارة السحرية</title>

<script src="https://cdn.tailwindcss.com"></script>

<style>
body {
    background:
        radial-gradient(circle at 20% 20%, #3b1c55, transparent 35%),
        radial-gradient(circle at 80% 80%, #172044, transparent 35%),
        #08060d;
}

.magic-card {
    background: rgba(22,16,31,.82);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(212,175,55,.25);
}

.gold {
    color:#d4af37;
}

.magic-glow {
    box-shadow:
        0 0 40px rgba(212,175,55,.08),
        inset 0 0 30px rgba(255,255,255,.015);
}
</style>

</head>

<body class="text-white min-h-screen flex items-center justify-center px-5">

<div class="magic-card magic-glow rounded-3xl p-10 max-w-lg w-full text-center">

    <div class="text-7xl mb-5">🪄</div>

    <h1 class="text-4xl font-bold gold mb-3">
        الإدارة السحرية
    </h1>

    <p class="text-gray-400 leading-8 mb-8">
        لوحة التحكم الرسمية لإدارة المملكة السحرية
        والطلاب والفعاليات والمبارزات.
    </p>

    <a href="/login"
       class="block bg-[#5865F2] hover:bg-[#4752C4]
              transition-all duration-300
              rounded-xl py-4 font-bold shadow-lg">

        الدخول بواسطة Discord
        ✨

    </a>

    <p class="text-gray-600 text-xs mt-8">
        """ + AUTHOR_SIGNATURE + """
    </p>

</div>

</body>
</html>
""")


# ============================================================
# LOGIN
# ============================================================

@app.get("/login")
async def login():
    if not CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="DISCORD_CLIENT_ID غير موجود في Railway"
        )

    url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        "&scope=identify%20guilds"
    )

    return RedirectResponse(url)


# ============================================================
# CALLBACK
# ============================================================

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str):
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="إعدادات Discord OAuth2 غير مكتملة"
        )

    async with aiohttp.ClientSession() as session:
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        }

        headers = {
            "Content-Type":
            "application/x-www-form-urlencoded"
        }

        async with session.post(
            f"{API_ENDPOINT}/oauth2/token",
            data=payload,
            headers=headers
        ) as response:

            if response.status != 200:
                raise HTTPException(
                    status_code=400,
                    detail="فشل تسجيل الدخول بواسطة Discord"
                )

            token_data = await response.json()

    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="لم يتم استلام Access Token"
        )

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        async with session.get(
            f"{API_ENDPOINT}/users/@me",
            headers=headers
        ) as response:

            if response.status != 200:
                raise HTTPException(
                    status_code=400,
                    detail="تعذر الحصول على بيانات حساب Discord"
                )

            user = await response.json()

    request.session["user"] = {
        "id": user.get("id"),
        "username": user.get("username"),
        "global_name": user.get("global_name"),
        "avatar": user.get("avatar")
    }

    return RedirectResponse("/dashboard")


# ============================================================
# LOGOUT
# ============================================================

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")

    if not user:
        return RedirectResponse("/login")

    username = (
        user.get("global_name")
        or user.get("username")
        or "ساحر"
    )

    avatar = user.get("avatar")
    user_id = user.get("id")

    if avatar:
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/"
            f"{user_id}/{avatar}.png?size=256"
        )
    else:
        avatar_url = (
            "https://cdn.discordapp.com/embed/avatars/0.png"
        )

    return HTMLResponse(f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>لوحة الإدارة السحرية</title>
<script src="https://cdn.tailwindcss.com"></script>

<style>
* {{ box-sizing:border-box; }}
body {{
    margin:0;
    background:
        radial-gradient(circle at 10% 10%, #402050, transparent 30%),
        radial-gradient(circle at 90% 80%, #18254d, transparent 35%),
        #08060d;
    color:#eee;
    min-height:100vh;
    font-family: "Segoe UI", Tahoma, Arial, sans-serif;
}}
.sidebar {{
    position:fixed; right:0; top:0; bottom:0; width:270px;
    background: linear-gradient(180deg, rgba(24,16,34,.97), rgba(7,5,10,.99));
    border-left: 1px solid rgba(212,175,55,.2);
    padding:28px 18px; z-index:10;
}}
.logo {{
    text-align:center; padding-bottom:25px;
    border-bottom: 1px solid rgba(255,255,255,.06); margin-bottom:25px;
}}
.logo-icon {{ font-size:46px; }}
.logo h1 {{ color:#d4af37; font-family:Georgia,serif; font-size:21px; margin:8px 0 3px; }}
.logo p {{ color:#756b7d; font-size:11px; }}
.nav a {{
    display:flex; align-items:center; gap:13px; padding:14px; margin:7px 0;
    border-radius:12px; color:#aaa1b3; text-decoration:none; transition:.25s;
}}
.nav a:hover {{ background: rgba(212,175,55,.08); color:#fff; transform:translateX(-3px); }}
.main {{ margin-right:270px; padding:32px; }}
.topbar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:30px; }}
.profile {{ display:flex; align-items:center; gap:12px; }}
.profile img {{ width:45px; height:45px; border-radius:50%; border: 2px solid #d4af37; }}
.card {{
    background: linear-gradient(145deg, rgba(255,255,255,.055), rgba(255,255,255,.015));
    border: 1px solid rgba(255,255,255,.07); border-radius:20px; padding:22px;
    box-shadow: 0 15px 45px rgba(0,0,0,.25); backdrop-filter:blur(15px);
}}
.gold {{ color:#d4af37; }}
.stats {{ display:grid; grid-template-columns: repeat(4,1fr); gap:18px; margin-bottom:22px; }}
.stat-number {{ font-size:30px; font-weight:bold; color:#e4c765; }}
.stat-label {{ color:#82798b; font-size:12px; margin-top:5px; }}
.grid {{ display:grid; grid-template-columns: 1.5fr 1fr; gap:20px; }}
.section-title {{ color:#e0c461; font-family:Georgia,serif; font-size:18px; margin-bottom:18px; }}
.house {{ display:flex; align-items:center; justify-content:space-between; padding:15px; margin:9px 0; background: rgba(255,255,255,.025); border-radius:12px; }}
.quick-grid {{ display:grid; grid-template-columns: repeat(2,1fr); gap:12px; }}
.quick {{
    padding:18px; border-radius:14px; background: rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.05); text-decoration:none; color:#ddd; transition:.2s;
}}
.quick:hover {{ border-color: rgba(212,175,55,.4); transform:translateY(-2px); }}
.logout {{ color:#ef7777 !important; }}
@media(max-width:1000px) {{
    .sidebar {{ width:220px; }}
    .main {{ margin-right:220px; }}
    .stats {{ grid-template-columns: repeat(2,1fr); }}
    .grid {{ grid-template-columns:1fr; }}
}}
@media(max-width:700px) {{
    .sidebar {{ position:relative; width:100%; height:auto; border-left:0; border-bottom: 1px solid rgba(212,175,55,.2); }}
    .main {{ margin-right:0; padding:18px; }}
    .stats {{ grid-template-columns:1fr; }}
    .topbar {{ align-items:flex-start; gap:15px; flex-direction:column; }}
}}
</style>
</head>

<body>

<aside class="sidebar">
<div class="logo">
<div class="logo-icon">🪄</div>
<h1>الإدارة السحرية</h1>
<p>MAGICAL ADMINISTRATION</p>
</div>

<nav class="nav">
<a href="/dashboard">🏰<span>الرئيسية</span></a>
<a href="#">⚔️<span>المبارزات</span></a>
<a href="#">🏆<span>صدارة المبارزين</span></a>
<a href="#">📚<span>سجل الطلاب</span></a>
<a href="#">🪄<span>الفعاليات السحرية</span></a>
<a href="#">🛡️<span>الغارات</span></a>
<a href="#">🏥<span>المستشفى السحري</span></a>
<a href="/logout" class="logout">🚪<span>تسجيل الخروج</span></a>
</nav>
</aside>

<main class="main">
<div class="topbar">
<div>
<h2 class="text-3xl font-bold gold">مرحباً بك يا {username}</h2>
<p class="text-gray-500 text-sm mt-2">مجلس الإدارة السحرية • لوحة التحكم الرئيسية</p>
</div>
<div class="profile">
<img src="{avatar_url}">
<div>
<div class="font-bold">{username}</div>
<div class="text-xs text-green-400">● متصل</div>
</div>
</div>
</div>

<section class="stats">
<div class="card">
<div class="text-3xl mb-3">⚡</div>
<div class="stat-number">متصل</div>
<div class="stat-label">حالة البوت</div>
</div>
<div class="card">
<div class="text-3xl mb-3">⚔️</div>
<div class="stat-number">نشطة</div>
<div class="stat-label">حالة المبارزات</div>
</div>
<div class="card">
<div class="text-3xl mb-3">📚</div>
<div class="stat-number">جاهز</div>
<div class="stat-label">سجل الطلاب</div>
</div>
<div class="card">
<div class="text-3xl mb-3">🪄</div>
<div class="stat-number">جاهزة</div>
<div class="stat-label">الفعاليات</div>
</div>
</section>

<div class="grid">
<div class="card">
<div class="section-title">✨ مركز الإدارة السحرية</div>
<p class="text-gray-400 leading-8">
مرحباً بك في مركز التحكم. من هنا يمكن إدارة أنظمة المملكة السحرية ومتابعة المبارزات والفعاليات وسجلات الطلاب.
</p>
<div class="quick-grid mt-6">
<a href="#" class="quick">⚔️<div class="font-bold mt-2">حلبة المبارزات</div><div class="text-xs text-gray-500 mt-1">إدارة المبارزات</div></a>
<a href="#" class="quick">🪄<div class="font-bold mt-2">الفعاليات</div><div class="text-xs text-gray-500 mt-1">إدارة الفعاليات السحرية</div></a>
<a href="#" class="quick">📚<div class="font-bold mt-2">الطلاب</div><div class="text-xs text-gray-500 mt-1">سجل البيوت والطلاب</div></a>
<a href="#" class="quick">🏆<div class="font-bold mt-2">لوحة الشرف</div><div class="text-xs text-gray-500 mt-1">صدارة المبارزين</div></a>
</div>
</div>

<div class="card">
<div class="section-title">🏰 البيوت الأربعة</div>
<div class="house"><span>🦁 جريفندور</span><span class="text-gray-500">—</span></div>
<div class="house"><span>🐍 سليذيرين</span><span class="text-gray-500">—</span></div>
<div class="house"><span>🦅 رافينكلو</span><span class="text-gray-500">—</span></div>
<div class="house"><span>🦡 هافلباف</span><span class="text-gray-500">—</span></div>
</div>
</div>

<footer class="text-center text-gray-600 text-xs mt-10">
{AUTHOR_SIGNATURE}
</footer>
</main>

</body>
</html>
""")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
