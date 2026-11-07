import os, logging, threading, httpx, re, secrets, time, html, datetime, json
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
BOT_USERNAME = "GetkeyMizzebot"

ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

# Cấu hình nhóm nhận file & link nhóm khách hàng
LOG_GROUP_ID = -1003912025872
CLIENT_GROUP_LINK = "https://t.me/mizze_lebin" 

SIGNATURE = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚡ 🔮 **MIZZE CYBERPUNK STORE** 🔮 ⚡"
BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
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

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {
        "users": {}, "user_data": {}, "sellers": {},
        "s_1h": [], "s_1d": [], "s_7d": [], "s_30d": [], 
        "prices": {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000},
        "seller_prices": {"1h": 5000, "1d": 15000, "7d": 60000, "30d": 120000},
        "seller_targets": {}, 
        "total_rev": 0, "bot_active": True, "last_reset_date": datetime.datetime.now().strftime("%Y-%m-%d")
    }

db = load_data()
if "prices" not in db:
    db["prices"] = {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000}
if "seller_prices" not in db:
    db["seller_prices"] = {"1h": 5000, "1d": 15000, "7d": 60000, "30d": 120000}
if "sellers" not in db:
    db["sellers"] = {}

def save_data():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if db.get("last_reset_date") != today_str:
            for s_id, s_info in db["sellers"].items():
                s_info["daily_rev"] = 0
            db["last_reset_date"] = today_str

        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
    except: pass

async def auto_backup_to_admin(context):
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                for adm in admin_list:
                    await context.bot.send_document(
                        chat_id=adm,
                        document=f,
                        filename="database_backup.json",
                        caption="🛡️ **[AUTO BACKUP SYSTEM]**\nFile dữ liệu database mới nhất của bot được sao lưu tự động an toàn tuyệt đối!"
                    )
    except Exception as e:
        logger.error(f"Lỗi backup tự động: {e}")

admin_state = {}
cooldown_cache = {}

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {
            'balance': 0, 'total_deposit': 0, 
            'deposit_history': [], 'buy_history': [], 'my_keys': []
        }
        save_data()
    return db["user_data"][uid_str]

def is_admin(uid):
    return uid in admin_list

def is_seller(uid):
    return str(uid) in db["sellers"] or uid in admin_list

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 1.5:
        return True
    if len(cooldown_cache) > 1000:
        cooldown_cache.clear()
    cooldown_cache[uid] = now
    return False

async def edit_or_send(query, text, reply_markup=None):
    try:
        if query.message.photo:
            await query.message.delete()
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except:
        try: await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except: pass

async def notify_all_admins(context, msg):
    for adm in list(admin_list):
        try:
            await context.bot.send_message(chat_id=adm, text="⚡ **[SYSTEM ALERT]**\n\n" + msg + SIGNATURE, parse_mode="HTML")
        except:
            pass

async def show_main_menu(update, context):
    uid = update.effective_user.id
    save_data() 
    
    if not db["bot_active"] and not is_admin(uid):
        maint_text = (
            f"🚧 **HỆ THỐNG ĐANG BẢO TRÌ NÂNG CẤP** 🚧\n\n"
            f"<i>Bot hiện đang tạm dừng hoạt động để bảo trì hệ thống. Vui lòng quay lại sau ít phút khi Admin mở lại nhé!</i>"
            f"{SIGNATURE}"
        )
        if update.message: await update.message.reply_text(maint_text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.reply_text(maint_text, parse_mode="HTML")
        return

    u = get_u(uid)
    role_badge = "👑 [ADMIN / VIP SELLER]" if is_admin(uid) else ("💎 [SELLER PARTNER]" if is_seller(uid) else "🛡️ [MEMBER]")
    
    text = (
        f"🌌 🔮 **MIZZE CYBERPUNK - ULTIMATE STORE** 🔮 🌌\n"
        f"✨ Cấp bậc: {role_badge}\n\n"
        f"📢 **Kênh Thông Báo:** <a href='{CHANNEL_URL}'>🔗 Tham Gia Kênh</a>\n"
        f"👑 **Admin Hỗ Trợ:** <a href='{ADMIN_CONTACT}'>💬 Liên Hệ Ngay</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 **Tổng Nạp:** <code>{u['total_deposit']:,}đ</code> | 💎 **Số Dư Ví:** <b>{u['balance']:,}đ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **📊 KHO HÀNG REAL-TIME:**\n"
        f"  • ⚡ **1H:** <code>[{len(db['s_1h'])}]</code> | 💎 **1D:** <code>[{len(db['s_1d'])}]</code>\n"
        f"  • 👑 **7D:** <code>[{len(db['s_7d'])}]</code> | 🚀 **30D:** <code>[{len(db['s_30d'])}]</code>"
        f"{SIGNATURE}"
    )
    
    kb_buttons = [
        [InlineKeyboardButton("🛒 CỬA HÀNG MUA KEY", callback_data='menu_shop'), InlineKeyboardButton("💳 NẠP TIỀN TỰ ĐỘNG", callback_data='menu_deposit')],
        [InlineKeyboardButton("🔑 KHO KEY CỦA TÔI", callback_data='my_keys'), InlineKeyboardButton("👤 TÀI KHOẢN CÁ NHÂN", callback_data='menu_account')],
        [InlineKeyboardButton("🧾 LỊCH SỬ NẠP", callback_data='hist_deposit'), InlineKeyboardButton("🛍️ LỊCH SỬ MUA HÀNG", callback_data='hist_buy')],
    ]
    
    if is_seller(uid) and not is_admin(uid):
        kb_buttons.append([InlineKeyboardButton("📊 THỐNG KÊ DOANH THU SELLER", callback_data='seller_stats')])
    
    if is_admin(uid):
        kb_buttons.append([InlineKeyboardButton("⚙️ B