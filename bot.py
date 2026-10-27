import os
import asyncio
import sqlite3
import secrets
import string
import uuid
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBAPP_URL = "https://mizze-key-storez.vercel.app/" # Link Vercel của bạn

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===== KHỞI TẠO DATABASE =====
def init_db():
    conn = sqlite3.connect("keys.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS key_prices (id INTEGER PRIMARY KEY, name TEXT, duration_hours INTEGER, price_vnd INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keys (id INTEGER PRIMARY KEY, key_code TEXT UNIQUE, user_id INTEGER, plan_id INTEGER, expires_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS claim_logs (id INTEGER PRIMARY KEY, ip TEXT, user_id INTEGER, claimed_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS links_4m (id INTEGER PRIMARY KEY, url TEXT, active BOOLEAN DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_tasks (user_id INTEGER, link_id INTEGER, task_token TEXT, is_completed BOOLEAN DEFAULT 0, created_at TIMESTAMP)''')

    c.execute("INSERT OR IGNORE INTO key_prices VALUES (1, 'Key 1 Ngày', 24, 20000)")
    c.execute("INSERT OR IGNORE INTO key_prices VALUES (2, 'Key 7 Ngày', 168, 70000)")
    c.execute("INSERT OR IGNORE INTO key_prices VALUES (3, 'Key 6 Giờ', 6, 0)")
    c.execute("INSERT OR IGNORE INTO key_prices VALUES (4, 'Key 3 Giờ', 3, 0)")
    
    if not c.execute("SELECT * FROM links_4m").fetchall():
        for i in range(1, 5):
            c.execute("INSERT INTO links_4m (url) VALUES (?)", (f"https://link4m.com/test{i}",))
    conn.commit()
    conn.close()

def gen_key():
    return "-".join("".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)) for _ in range(3))

# ===== API CHO MINI APP =====

# API 1: Lấy link (Tạo mã token riêng cho từng user để chống gian lận)
async def api_links(request):
    user_id = request.query.get("user_id")
    if not user_id: return web.json_response({"error": "Thiếu user_id"})
    
    conn = sqlite3.connect("keys.db")
    c = conn.cursor()
    links = c.execute("SELECT id, url FROM links_4m WHERE active=1").fetchall()
    c.execute("DELETE FROM user_tasks WHERE user_id=?", (user_id,))
    
    result = []
    for link in links:
        link_id, url = link
        token = str(uuid.uuid4())
        c.execute("INSERT INTO user_tasks (user_id, link_id, task_token, is_completed, created_at) VALUES (?, ?, ?, 0, ?)", 
                  (user_id, link_id, token, datetime.now()))
        result.append({"url": f"{url}?sub_id={token}"}) 
    conn.commit()
    conn.close()
    return web.json_response({"links": result})

# API 2: Callback từ Link4m báo vượt link thành công
async def api_callback(request):
    token = request.query.get("sub_id")
    if not token: return web.Response(text="Error: No token")
    conn = sqlite3.connect("keys.db")
    conn.execute("UPDATE user_tasks SET is_completed=1 WHERE task_token=?", (token,))
    conn.commit(); conn.close()
    return web.Response(text="Success")

# API 3: Nhận Key (Kiểm tra spam 5 phút, 50 lần/ngày + 4 link)
async def api_claim(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id"))
        ip = request.remote
        conn = sqlite3.connect("keys.db")
        c = conn.cursor()
        now = datetime.now()

        # 1. Kiểm tra đủ 4 link chưa
        c.execute("SELECT COUNT(*) FROM user_tasks WHERE user_id=? AND is_completed=1", (user_id,))
        if c.fetchone()[0] < 4:
            conn.close()
            return web.json_response({"ok": False, "error": "Bạn chưa vượt đủ 4 link!"})

        # 2. Kiểm tra chống spam 5 phút/lần
        c.execute("SELECT claimed_at FROM claim_logs WHERE ip=? ORDER BY id DESC LIMIT 1", (ip,))
        last_claim = c.fetchone()
        if last_claim and now - datetime.fromisoformat(last_claim[0]) < timedelta(minutes=5):
            conn.close()
            return web.json_response({"ok": False, "error": "Chờ 5 phút mới được lấy key tiếp!"})

        # 3. Kiểm tra chống spam 50 lần/ngày (ĐÃ CẬP NHẬT)
        today_start = now.strftime("%Y-%m-%d 00:00:00")
        c.execute("SELECT COUNT(*) FROM claim_logs WHERE ip=? AND claimed_at >= ?", (ip, today_start))
        if c.fetchone()[0] >= 50:
            conn.close()
            return web.json_response({"ok": False, "error": "Bạn đã hết 50 lượt hôm nay. Mai quay lại!"})

        # 4. Tạo key và lưu log
        code = gen_key()
        expires = now + timedelta(hours=24)
        c.execute("INSERT INTO keys (key_code, user_id, plan_id, expires_at) VALUES (?, ?, ?, ?)", (code, user_id, 1, expires))
        c.execute("INSERT INTO claim_logs (ip, user_id, claimed_at) VALUES (?, ?, ?)", (ip, user_id, now.isoformat()))
        
        # Xóa task sau khi lấy key để tránh bị gọi lại
        c.execute("DELETE FROM user_tasks WHERE user_id=?", (user_id,))
        
        conn.commit()
        conn.close()
        return web.json_response({"ok": True, "key": code, "expires": expires.strftime("%d/%m/%Y %H:%M")})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

# API 4: Kiểm tra trạng thái vượt link của Mini App
async def api_check_status(request):
    user_id = request.query.get("user_id")
    conn = sqlite3.connect("keys.db")
    rows = conn.execute("SELECT link_id FROM user_tasks WHERE user_id=? AND is_completed=1", (user_id,)).fetchall()
    conn.close()
    # Trả về danh sách vị trí các link đã hoàn thành (0, 1, 2, 3)
    completed_indices = [r[0] - 1 for r in rows] 
    return web.json_response({"completed_indices": completed_indices})

# ===== LỆNH BOT TELEGRAM =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Mở Key Store", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(f"👋 Chào {message.from_user.first_name}!\n👇 Bấm nút bên dưới:", reply_markup=kb)

# ===== ADMIN =====
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    text = (
        "🛠 **BẢNG QUẢN LÝ ADMIN**\n\n"
        "`/listkeys` - Xem 15 key gần nhất\n"
        "`/givekey <user_id> <gói>` - Tặng key\n"
        "`/upkey <key> <số_giờ>` - Cộng thêm giờ\n"
        "`/addlink <url>` - Thêm link 4m\n"
        "`/listlinks` - Xem link 4m\n"
        "`/dellink <id>` - Xóa link 4m\n"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("givekey"))
async def cmd_givekey(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, uid, pid = message.text.split()
        conn = sqlite3.connect("keys.db")
        code = gen_key()
        expires = datetime.now() + timedelta(hours=24)
        conn.execute("INSERT INTO keys (key_code, user_id, plan_id, expires_at) VALUES (?, ?, ?, ?)", (code, int(uid), int(pid), expires))
        conn.commit(); conn.close()
        await bot.send_message(int(uid), f"🎁 Bạn nhận được Key: `{code}`\nHết hạn: {expires.strftime('%d/%m/%Y %H:%M')}", parse_mode="Markdown")
        await message.answer(f"✅ Đã gửi key cho {uid}")
    except Exception as e:
        await message.answer(f"❌ Lỗi: {e}")

@dp.message(Command("addlink"))
async def cmd_addlink(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        conn = sqlite3.connect("keys.db")
        conn.execute("INSERT INTO links_4m (url) VALUES (?)", (url,))
        conn.commit(); conn.close()
        await message.answer(f"✅ Đã thêm link: {url}")
    except Exception as e:
        await message.answer("❌ Sai cú pháp: /addlink <url>")

@dp.message(Command("listlinks"))
async def cmd_listlinks(message: Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect("keys.db")
    rows = conn.execute("SELECT id, url FROM links_4m WHERE active=1").fetchall()
    conn.close()
    text = "🔗 **DANH SÁCH LINK 4M**\n\n" + "\n".join([f"`#{r[0]}` - {r[1]}" for r in rows])
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("dellink"))
async def cmd_dellink(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, lid = message.text.split()
        conn = sqlite3.connect("keys.db")
        conn.execute("DELETE FROM links_4m WHERE id=?", (int(lid),))
        conn.commit(); conn.close()
        await message.answer(f"✅ Đã xóa link #{lid}")
    except Exception as e:
        await message.answer("❌ Sai cú pháp: /dellink <id>")

# ===== CHẠY WEB SERVER + BOT =====
async def main():
    init_db()
    app = web.Application()
    app.router.add_post('/api/claim', api_claim)
    app.router.add_get('/api/links', api_links)
    app.router.add_get('/api/callback', api_callback)
    app.router.add_get('/api/check_status', api_check_status)
    app.router.add_get('/', lambda r: web.Response(text="Bot is running!"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    await site.start()
    
    print("🤖 Bot & Web Server đang chạy...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())