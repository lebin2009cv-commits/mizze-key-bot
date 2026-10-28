import logging
import uuid
import time
import os
import requests
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ================== CẤU HÌNH ==================
BOT_TOKEN = "9120368691:AAE9J5NtmXqYBPiKmC7pJq_UKmjwlwny2sw"
ADMIN_IDS = [7976468365]
LINK4M_API_TOKEN = "6a38ad422de39b3f34159f96"

KEYS_FILE = "keys.txt"

# Chống spam
COOLDOWN_GETKEY = 120         # 2 phút mới được lấy key tiếp
MIN_TIME_BETWEEN_STEPS = 45    # Phải cách ít nhất 45 giây giữa lần 1 và lần 2
MAX_KEY_PER_DAY = 3            # Mỗi user tối đa 3 key/ngày

pending = {}
user_keys = {}
user_cooldown = {}             # {user_id: last_getkey_time}
user_daily = {}                # {user_id: {"count": x, "date": "2026-10-28"}}

logging.basicConfig(level=logging.INFO)

# ================== FLASK (để Render không tắt) ==================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is alive!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

# ================== XỬ LÝ FILE ==================
def load_keys():
    if not os.path.exists(KEYS_FILE):
        return []
    with open(KEYS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def save_keys(keys):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        for k in keys:
            f.write(k + "\n")

def get_one_key():
    keys = load_keys()
    if not keys:
        return None
    key = keys.pop(0)
    save_keys(keys)
    return key

def add_keys(new_keys):
    keys = load_keys()
    keys.extend(new_keys)
    save_keys(keys)
    return len(new_keys)

def count_keys():
    return len(load_keys())

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def save_user_key(user_id, key, days=1):
    expire = time.time() + days * 86400
    user_keys[user_id] = {"key": key, "expire": expire}

def get_user_key(user_id):
    data = user_keys.get(user_id)
    if not data:
        return None
    if time.time() > data["expire"]:
        del user_keys[user_id]
        return None
    return data

def can_get_key(user_id: int):
    now = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    # Kiểm tra cooldown
    last = user_cooldown.get(user_id, 0)
    if now - last < COOLDOWN_GETKEY:
        remain = int(COOLDOWN_GETKEY - (now - last))
        return False, f"⏳ Vui lòng chờ {remain} giây nữa mới được lấy key tiếp."

    # Kiểm tra giới hạn ngày
    daily = user_daily.get(user_id, {"count": 0, "date": today})
    if daily["date"] != today:
        daily = {"count": 0, "date": today}
        user_daily[user_id] = daily

    if daily["count"] >= MAX_KEY_PER_DAY:
        return False, f"❌ Bạn đã lấy đủ {MAX_KEY_PER_DAY} key hôm nay. Mai hãy quay lại."

    return True, ""

def increase_daily(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    daily = user_daily.get(user_id, {"count": 0, "date": today})
    if daily["date"] != today:
        daily = {"count": 0, "date": today}
    daily["count"] += 1
    user_daily[user_id] = daily
    user_cooldown[user_id] = time.time()

# ================== TẠO LINK LINK4M ==================
def create_link4m(destination_url: str) -> str | None:
    try:
        api_url = "https://link4m.co/api-shorten/v2"
        params = {"api": LINK4M_API_TOKEN, "url": destination_url}
        res = requests.get(api_url, params=params, timeout=15)
        data = res.json()
        if data.get("status") == "success":
            return data.get("shortenedUrl")
        print("Link4m lỗi:", data)
        return None
    except Exception as e:
        print("Lỗi tạo link:", e)
        return None

# ================== MENU ==================
def main_menu(user_id: int):
    keyboard = [
        [InlineKeyboardButton("🔑 Lấy Key", callback_data="menu_getkey")],
        [
            InlineKeyboardButton("🔍 Kiểm tra Key", callback_data="menu_checkkey"),
            InlineKeyboardButton("🔗 Kiểm tra Link", callback_data="menu_checklink")
        ],
        [
            InlineKeyboardButton("⏰ Thời gian", callback_data="menu_time"),
            InlineKeyboardButton("🗑️ Xóa Key", callback_data="menu_delkey")
        ],
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="menu_admin")])
    return InlineKeyboardMarkup(keyboard)

def admin_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Thêm Key", callback_data="admin_addkey")],
        [InlineKeyboardButton("📦 Kho Key", callback_data="admin_stock")],
        [InlineKeyboardButton("📊 Thống kê", callback_data="admin_stats")],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"Xin chào <b>{user.first_name}</b>!\n\n"
        f"Chào mừng bạn đến với hệ thống lấy Key tự động.\n"
        f"Chọn chức năng bên dưới:"
    )
    await update.message.reply_text(text, reply_markup=main_menu(user.id), parse_mode="HTML")

# ================== CALLBACK ==================
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "menu_back":
        await query.edit_message_text("Chọn chức năng:", reply_markup=main_menu(user_id))
        return

    if data == "menu_getkey":
        ok, msg = can_get_key(user_id)
        if not ok:
            await query.edit_message_text(msg, reply_markup=main_menu(user_id))
            return
        await start_getkey(query, user_id)
        return

    if data == "menu_checkkey":
        info = get_user_key(user_id)
        if info:
            remain = int((info["expire"] - time.time()) / 3600)
            text = f"🔑 <b>Key của bạn:</b>\n<code>{info['key']}</code>\n\n⏰ Còn lại khoảng <b>{remain} giờ</b>"
        else:
            text = "❌ Bạn chưa có key hoặc key đã hết hạn."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_checklink":
        if user_id in pending:
            text = f"🔗 Bạn đang vượt link\nBước hiện tại: <b>{pending[user_id]['step']}/2</b>"
        else:
            text = "❌ Bạn chưa có phiên vượt link."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_time":
        info = get_user_key(user_id)
        if info:
            expire_str = datetime.fromtimestamp(info["expire"]).strftime("%H:%M %d/%m/%Y")
            text = f"⏰ Key hết hạn lúc:\n<b>{expire_str}</b>"
        else:
            text = "❌ Bạn chưa có key."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_delkey":
        if user_id in user_keys:
            del user_keys[user_id]
            text = "✅ Đã xóa key của bạn."
        else:
            text = "❌ Bạn không có key để xóa."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_admin":
        if not is_admin(user_id):
            await query.answer("Không có quyền!", show_alert=True)
            return
        await query.edit_message_text("👑 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")
        return

    if data == "admin_stock":
        keys = load_keys()
        text = f"📦 Hiện còn <b>{len(keys)}</b> key."
        if keys:
            text += "\n\n" + "\n".join(f"<code>{k}</code>" for k in keys[:8])
        await query.edit_message_text(text, reply_markup=admin_menu(), parse_mode="HTML")
        return

    if data == "admin_stats":
        text = (
            f"📊 <b>Thống kê</b>\n\n"
            f"• Key trong kho: <b>{count_keys()}</b>\n"
            f"• User đang có key: <b>{len(user_keys)}</b>\n"
            f"• Phiên đang vượt: <b>{len(pending)}</b>"
        )
        await query.edit_message_text(text, reply_markup=admin_menu(), parse_mode="HTML")
        return

    if data == "admin_addkey":
        await query.edit_message_text(
            "Gửi danh sách key (mỗi key 1 dòng)\nhoặc dùng lệnh:\n<code>/upkey KEY1 KEY2</code>",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )
        return

    if data.startswith("step1_"):
        await handle_step1(query, user_id, data)
        return

    if data.startswith("step2_"):
        await handle_step2(query, user_id, data)
        return

# ================== LẤY KEY ==================
async def start_getkey(query, user_id):
    code1 = str(uuid.uuid4())[:8]
    code2 = str(uuid.uuid4