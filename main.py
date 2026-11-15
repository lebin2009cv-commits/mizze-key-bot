import os, logging, threading, httpx, re, time, datetime, json, asyncio, gc
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

LOG_GROUP_ID = -1003912025872
CLIENT_GROUP_LINK = "https://t.me/mizze_lebin"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/lebindz"
SUPPORT_CONTACT = "https://t.me/lebindz"

BANK_ID = "VPBank"
ACCOUNT_NO = "AGBSP4LRK4B099"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_KEY = os.environ.get("SEPAY_API_KEY", "botgetkey_sepay")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
DB_FILE = "database.json"

buy_lock = threading.Lock()
admin_state = {}
cooldown_cache = {}
admin_view_mode = {}

def load_data():
    default_data = {
        "users": {}, "user_data": {}, "sellers": {},
        "s_1h": [], "s_3d": [], "s_1d": [], "s_7d": [], "s_30d": [], "s_1y": [],
        "prices": {"1h": 5000, "3d": 12000, "1d": 20000, "7d": 70000, "30d": 150000, "1y": 800000},
        "seller_prices": {"1h": 5000, "3d": 10000, "1d": 10000, "7d": 45000, "30d": 70000, "1y": 500000},
        "total_rev": 2905000, "bot_active": True,
        "last_reset_date": datetime.datetime.now().strftime("%Y-%m-%d")
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception: pass
    return default_data

db = load_data()

def save_data():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if db.get("last_reset_date") != today_str:
            for s_info in db["sellers"].values():
                s_info["daily_rev"] = 0
            db["last_reset_date"] = today_str
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
        gc.collect()
    except Exception: pass

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {'balance': 0, 'total_deposit': 0, 'month_deposit': 0, 'deposit_history': [], 'buy_history': [], 'my_keys': []}
        save_data()
    u = db["user_data"][uid_str]
    for key in ['month_deposit', 'deposit_history', 'buy_history', 'my_keys']:
        if key not in u: u[key] = 0 if key == 'month_deposit' else []
    return u

def is_admin(uid): return uid in admin_list
def is_seller(uid):
    if is_admin(uid): return admin_view_mode.get(uid, 'seller') == 'seller'
    return str(uid) in db["sellers"]

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 0.4: return True
    if len(cooldown_cache) > 500: cooldown_cache.clear()
    cooldown_cache[uid] = now
    return False

async def edit_or_send(query, text, reply_markup=None):
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        try: await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
        except Exception: pass

def build_main_menu_content(uid):
    u = get_u(uid)
    mode_tag = f"\n⚡ <b>Kho xem:</b> <code>{admin_view_mode.get(uid, 'seller').upper()}</code>" if is_admin(uid) else ""
    text = (
        f"✨ <b>CHÀO MỪNG BẠN ĐẾN VỚI HỆ THỐNG STORE HACK</b> 💫\n\n"
        f"<blockquote>"
        f"🔔 <b>Kênh thông báo:</b> <a href='{CHANNEL_URL}'>Mizze Store</a>\n"
        f"☑️ <b>Admin:</b> <a href='{ADMIN_CONTACT}'>Le Bin</a>\n"
        f"➖ ➖ ➖ ➖ ➖ ➖ ➖ ➖\n"
        f"⏱️ <b>Tổng nạp:</b> <code>{u['total_deposit']:,}đ</code>\n"
        f"📊 <b>Tổng nạp tháng:</b> <code>{u['month_deposit']:,}đ</code>\n"
        f"💳 <b>Số dư:</b> <code>{u['balance']:,}đ</code>"
        f"{mode_tag}"
        f"</blockquote>"
    )
    kb = [
        [InlineKeyboardButton("👤 TÀI KHOẢN", callback_data='menu_account'), InlineKeyboardButton("🛒 CỬA HÀNG", callback_data='menu_shop')],
        [InlineKeyboardButton("💰 NẠP TIỀN", callback_data='menu_deposit'), InlineKeyboardButton("📊 LỊCH SỬ", callback_data='menu_history_hub')],
        [InlineKeyboardButton("🔑 KHO KEY CŨ", callback_data='my_keys'), InlineKeyboardButton("📥 TẢI FILE", url=CLIENT_GROUP_LINK)],
        [InlineKeyboardButton("💬 HỖ TRỢ / LIÊN HỆ", url=SUPPORT_CONTACT)]
    ]
    if is_seller(uid) and not is_admin(uid):
        kb.insert(3, [InlineKeyboardButton("📈 DOANH THU SELLER", callback_data='seller_stats')])
    if is_admin(uid):
        kb.append([InlineKeyboardButton("⚙️ QUẢN TRỊ ADMIN", callback_data='admin_panel')])
    return text, InlineKeyboardMarkup(kb)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_start=False):
    uid = update.effective_user.id
    save_data()
    if not db["bot_active"] and not is_admin(uid):
        msg = "🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ</b>\n<blockquote>Vui lòng quay lại sau!</blockquote>"
        if update.message: await update.message.reply_text(msg, parse_mode="HTML")
        elif update.callback_query: await edit_or_send(update.callback_query, msg)
        return

    text, kb = build_main_menu_content(uid)
    if is_start and update.message:
        l_msg = await update.message.reply_text("✨ <i>Đang tải giao diện động...</i>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        try: await l_msg.delete()
        except Exception: pass
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif update.message: await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=