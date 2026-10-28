import os
import asyncio
import sqlite3
import uuid
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.client.default import DefaultBotProperties

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://mizze-store-24-7.vercel.app")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()
app = FastAPI(title="Mizze Key Store Master Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    return sqlite3.connect("keys.db")

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        # Bảng gói key
        c.execute('''CREATE TABLE IF NOT EXISTS key_prices (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        duration_hours INTEGER,
                        required_links INTEGER DEFAULT 3,
                        active BOOLEAN DEFAULT 1)''')
        
        # Bảng kho key nhập sẵn
        c.execute('''CREATE TABLE IF NOT EXISTS key_stock (
                        id INTEGER PRIMARY KEY,
                        key_code TEXT UNIQUE,
                        plan_id INTEGER,
                        is_used BOOLEAN DEFAULT 0)''')
        
        # Bảng danh sách link rút gọn (Link4m) quản lý bởi Admin
        c.execute('''CREATE TABLE IF NOT EXISTS short_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        link_url TEXT)''')
        
        # Bảng lịch sử cấp key
        c.execute('''CREATE TABLE IF NOT EXISTS keys (
                        id INTEGER PRIMARY KEY,
                        key_code TEXT UNIQUE,
                        user_id INTEGER,
                        plan_id INTEGER,
                        expires_at TIMESTAMP)''')
        
        # Bảng chống spam pass token vượt link
        c.execute('''CREATE TABLE IF NOT EXISTS user_passes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        pass_token TEXT UNIQUE,
                        created_at TIMESTAMP)''')
        
        # Bảng quản lý cooldown chống spam (cách 5 phút) & giới hạn ngày
        c.execute('''CREATE TABLE IF NOT EXISTS user_limits (
                        user_id INTEGER PRIMARY KEY,
                        last_claim_time TIMESTAMP)''')
        
        # Khởi tạo mặc định gói
        c.execute("INSERT OR REPLACE INTO key_prices (id, name, duration_hours, required_links) VALUES (1, 'Key 6 Giờ', 6, 4)")
        c.execute("INSERT OR REPLACE INTO key_prices (id, name, duration_hours, required_links) VALUES (2, 'Key 3 Giờ', 3, 3)")
        
        # Thêm 3-4 link mẫu nếu bảng trống
        if c.execute("SELECT COUNT(*) FROM short_links").fetchone()[0] == 0:
            c.execute("INSERT INTO short_links (link_url) VALUES ('https://link4m.net/go/HEDP6k5i')")
            c.execute("INSERT INTO short_links (link_url) VALUES ('https://link4m.net/go/djYtu')")
            c.execute("INSERT INTO short_links (link_url) VALUES ('https://link4m.org/go/hWucf')")
            c.execute("INSERT INTO short_links (link_url) VALUES ('https://link4m.org/go/lgoZEE')")
            
        conn.commit()

init_db()

# --- API CHO MINI APP ---

@app.get("/")
async def root():
    return {"status": "Mizze Backend & Bot is running 24/7!"}

@app.get("/api/get_links")
async def get_links():
    with get_db() as conn:
        links = [row[0] for row in conn.execute("SELECT link_url FROM short_links").fetchall()]
    return {"status": "success", "links": links}

@app.get("/get_pass")
async def get_pass(user_id: int):
    token = str(uuid.uuid4())
    now = datetime.now()
    with get_db() as conn:
        conn.execute("INSERT INTO user_passes (user_id, pass_token, created_at) VALUES (?, ?, ?)", (user_id, token, now))
        conn.commit()
    return {"status": "success", "pass_token": token}

@app.post("/claim_key")
async def claim_key(user_id: int, plan: str, tokens: str = Query("")):
    token_list = [t.strip() for t in tokens.split(",") if t.strip()]
    plan_mapping = {"6h": ("Key 6 Giờ", 4), "3h": ("Key 3 Giờ", 3)}
    
    if plan not in plan_mapping:
        raise HTTPException(status_code=400, detail="Gói không hợp lệ.")
        
    plan_name, required_tokens = plan_mapping[plan]

    if len(token_list) < required_tokens:
        raise HTTPException(status_code=400, detail=f"Bạn chưa hoàn thành đủ {required_tokens} lượt vượt link hợp lệ!")

    now = datetime.now()

    with get_db() as conn:
        # Kiểm tra Cooldown chống spam 5 phút
        limit_row = conn.execute("SELECT last_claim_time FROM user_limits WHERE user_id=?", (user_id,)).fetchone()
        if limit_row and limit_row[0]:
            last_time = datetime.strptime(limit_row[0], '%Y-%m-%d %H:%M:%S')
            diff_minutes = (now - last_time).total_seconds() / 60
            if diff_minutes < 5:
                wait_time = int(5 - diff_minutes)
                raise HTTPException(status_code=400, detail=f"Chống spam: Vui lòng đợi thêm {wait_time} phút nữa mới được lấy key tiếp theo!")

        # Kiểm tra token vượt link hợp lệ
        for token in token_list:
            row = conn.execute("SELECT id FROM user_passes WHERE user_id=? AND pass_token=?", (user_id, token)).fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Phát hiện lượt vượt link không hợp lệ hoặc đã hết hạn.")
        
        # Xóa các token đã dùng để tính là hoàn thành hợp lệ
        for token in token_list:
            conn.execute("DELETE FROM user_passes WHERE pass_token=?", (token,))

        # Lấy kho key
        db_plan = conn.execute("SELECT id, name, duration_hours FROM key_prices WHERE name=?", (plan_name,)).fetchone()
        if not db_plan:
            raise HTTPException(status_code=400, detail="Gói key không tồn tại.")
        
        plan_id, name_p, duration_h = db_plan
        stock_item = conn.execute("SELECT id, key_code FROM key_stock WHERE plan_id=? AND is_used=0 LIMIT 1", (plan_id,)).fetchone()
        if not stock_item:
            raise HTTPException(status_code=400, detail=f"Kho key gói {name_p} đã hết! Vui lòng báo Admin nạp thêm.")
        
        stock_id, code = stock_item
        conn.execute("UPDATE key_stock SET is_used=1 WHERE id=?", (stock_id,))
        
        expires = now + timedelta(hours=duration_h)
        conn.execute("INSERT INTO keys (key_code, user_id, plan_id, expires_at) VALUES (?, ?, ?, ?)", (code, user_id, plan_id, expires))
        
        # Cập nhật thời điểm claim gần nhất cho user (Cooldown 5p)
        conn.execute("""INSERT INTO user_limits (user_id, last_claim_time) VALUES (?, ?) 
                        ON CONFLICT(user_id) DO UPDATE SET last_claim_time=excluded.last_claim_time""",
                     (user_id, now.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

        return {
            "status": "success",
            "key": code,
            "expires": expires.strftime('%d/%m/%Y %H:%M')
        }

# --- TELEGRAM BOT QUẢN LÝ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Mở Mizze Store (Mini App)", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(
        f"👋 Chào {message.from_user.first_name}!\n"
        f"Chào mừng bạn đến với **Mizze Key Store**.\n\n"
        f"👇 Bấm nút bên dưới để mở cửa hàng nhận Key tự động 24/7.",
        reply_markup=kb
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    with get_db() as conn:
        prices = conn.execute("SELECT id, name FROM key_prices WHERE active=1").fetchall()
        counts = conn.execute("SELECT plan_id, COUNT(*) FROM key_stock WHERE is_used=0 GROUP BY plan_id").fetchall()
        stock_map = {r[0]: r[1] for r in counts}
        links_count = conn.execute("SELECT COUNT(*) FROM short_links").fetchone()[0]

    text = "🛠 **BẢNG QUẢN TRỊ HỆ THỐNG (ADMIN)**\n\n"
    text += f"🔗 **Số lượng link 4m hiện có:** {links_count} link\n\n**Kho key hiện tại:**\n"
    for p in prices:
        text += f"- ID `{p[0]}` ({p[1]}): **{stock_map.get(p[0], 0)}** key\n"
    text += "\n**📌 Danh sách lệnh quản lý:**\n"
    text += "📥 Nạp key: `/addkey <ID_gói> <key1,key2,...>`\n"
    text += "📋 Xem kho key: `/listkey <ID_gói>`\n"
    text += "➕ Thêm link 4m: `/addlink <URL_link>`\n"
    text += "📋 Xem danh sách link: `/listlink`"
    await message.answer(text)

@dp.message(Command("addkey"))
async def cmd_addkey(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(maxsplit=2)
        pid = int(parts[1])
        key_list = [k.strip() for k in parts[2].replace("\n", ",").split(",") if k.strip()]
        added = 0
        with get_db() as conn:
            for k in key_list:
                try:
                    conn.execute("INSERT INTO key_stock (key_code, plan_id, is_used) VALUES (?, ?, 0)", (k, pid))
                    added += 1
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
        await message.answer(f"✅ Đã nạp thành công **{added}** key vào kho ID `{pid}`!")
    except Exception as e:
        await message.answer(f"❌ Sai cú pháp! VD: `/addkey 1 KEY1,KEY2`")

@dp.message(Command("listkey"))
async def cmd_listkey(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        pid = int(message.text.split()[1])
        with get_db() as conn:
            keys = conn.execute("SELECT key_code FROM key_stock WHERE plan_id=? AND is_used=0 LIMIT 20", (pid,)).fetchall()
        if not keys:
            await message.answer(f"📭 Kho key ID `{pid}` đang trống.")
            return
        txt = f"🔑 **20 Key chưa dùng của gói ID {pid}:**\n" + "\n".join([f"- `{r[0]}`" for r in keys])
        await message.answer(txt)
    except:
        await message.answer("❌ Sai cú pháp! VD: `/listkey 1`")

@dp.message(Command("addlink"))
async def cmd_addlink(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        link_url = message.text.split(maxsplit=1)[1].strip()
        with get_db() as conn:
            conn.execute("INSERT INTO short_links (link_url) VALUES (?)", (link_url,))
            conn.commit()
        await message.answer(f"✅ Đã thêm link rút gọn mới thành công:\n`{link_url}`")
    except:
        await message.answer("❌ Sai cú pháp! VD: `/addlink https://link4m.co/abc`")

@dp.message(Command("listlink"))
async def cmd_listlink(message: Message):
    if message.from_user.id != ADMIN_ID: return
    with get_db() as conn:
        links = conn.execute("SELECT id, link_url FROM short_links").fetchall()
    if not links:
        await message.answer("📭 Chưa có link rút gọn nào trong hệ thống.")
        return
    txt = "🔗 **Danh sách Link 4m hiện tại:**\n" + "\n".join([f"{r[0]}. `{r[1]}`" for r in links])
    await message.answer(txt)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(dp.start_polling(bot))