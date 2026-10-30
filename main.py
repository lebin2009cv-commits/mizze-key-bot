import os
import logging
import threading
import httpx
import re
import secrets
import string
import time
import asyncio
import html
import datetime
from urllib.parse import quote
from flask import Flask, request, jsonify

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AFpXd6iMrdPBaAM")
BOT_USERNAME = "GetkeyMizzebot"
ADMIN_ID = 7976468365

USER_SIGNATURE = "\n\n────────────────────\n🤖 <i>Powered by Mizze Key Bot</i>"

BANNER_URL = "https://i.imgur.com/your_banner_image.jpg"
CHANNEL_URL = "https://t.me/minhanhmodz"
ADMIN_CONTACT = "https://t.me/bbiztrmy"
SUPPORT_CONTACT = "https://t.me/bbiztrmy"

LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")
YEUMONEY_API_KEY = os.environ.get("YEUMONEY_API_KEY", "ĐIỀN_API_YEUMONEY")
SHRINKME_API_KEY = os.environ.get("SHRINKME_API_KEY", "ĐIỀN_API_SHRINKME")

BANK_ID = "VPBANK"
ACCOUNT_NO = "0382570538"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_API_KEY = os.environ.get("SEPAY_API_KEY", "MẬT_KHẨU_BẢO_MẬT_SEPAY")

PRICE_SHOP_1H = 10000
PRICE_SHOP_12H = 20000
PRICE_SHOP_1D = 70000
PRICE_SHOP_1M = 150000

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 2. CƠ SỞ DỮ LIỆU TẠM THỜI (RAM)
# ==========================================
kho_free_1h, kho_free_3h = [], []
kho_shop_1h, kho_shop_12h, kho_shop_1d, kho_shop_1m = [], [], [], [], []

user_states = {}
cooldowns = {}
admin_adding_state = {}
all_users = set()
bot_status = {"active": True}
user_data = {}
daily_limits = {}
total_revenue = 0

def get_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {'balance': 0, 'total_deposit': 0, 'history': []}
    return user_data[user_id]

def check_daily_limit(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if user_id not in daily_limits or daily_limits[user_id]['date'] != today:
        daily_limits[user_id] = {'date': today, 'count': 0}
    if daily_limits[user_id]['count'] >= 3:
        return False, 0
    return True, 3 - daily_limits[user_id]['count']

def add_daily_usage(user_id):
    if user_id in daily_limits:
        daily_limits[user_id]['count'] += 1

# ==========================================
# 3. HÀM GỌI API RÚT GỌN LINK
# ==========================================
async def shorten_link4m(long_url: str) -> str:
    api_endpoint = "https://link4m.co/api-shorten/v2"
    full_api_url = f"{api_endpoint}?api={LINK4M_API_KEY}&url={quote(long_url, safe='')}"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(full_api_url, timeout=10.0)
            if res.json().get("status") == "success": 
                return res.json().get("shortenedUrl").strip()
    except Exception as e: 
        logger.error(f"Lỗi Link4m: {e}")
    return None

async def shorten_yeumoney(long_url: str) -> str:
    api_endpoint = "https://yeumoney.com/QL_api.php"
    full_api_url = f"{api_endpoint}?token={YEUMONEY_API_KEY}&url={quote(long_url, safe='')}&format=json"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(full_api_url, timeout=10.0)
            if res.json().get("status") == "success": 
                return res.json().get("shortenedUrl").strip()
    except Exception as e: 
        logger.error(f"Lỗi YeuMoney: {e}")
    return None

async def shorten_shrinkme(long_url: str) -> str:
    api_endpoint = "https://shrinkme.io/api"
    full_api_url = f"{api_endpoint}?api={SHRINKME_API_KEY}&url={quote(long_url, safe='')}"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(full_api_url, timeout=10.0)
            if res.json().get("status") == "success": 
                return res.json().get("shortenedUrl").strip()
    except Exception as e: 
        logger.error(f"Lỗi ShrinkMe: {e}")
    return None

# ==========================================
# 4. HÀM HỖ TRỢ KHÁC
# ==========================================
def generate_token(): 
    return secrets.token_hex(4)

def generate_random_key(key_len=15):
    alphabet = string.ascii_uppercase + string.digits
    k = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    p = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    return f"<b>🔑 Key:</b> <code>{k}</code>\n<b>🔒 Mật khẩu:</b> <code>{p}</code>"

def check_cooldown(user_id, key_type):
    if user_id not in cooldowns or key_type not in cooldowns[user_id]: 
        return True, 0
    rem = int(cooldowns[user_id][key_type] - time.time())
    if rem > 0: 
        return False, f"{rem // 3600}h {(rem % 3600) // 60}p"
    return True, 0

def set_cooldown(user_id, key_type):
    if user_id not in cooldowns: 
        cooldowns[user_id] = {}
    if key_type == '1h': 
        cooldowns[user_id]['1h'] = time.time() + 3600
    elif key_type == '3h': 
        cooldowns[user_id]['3h'] = time.time() + 10800

async def notify_admin(context, message):
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 <b>THÔNG BÁO ADMIN</b>\n\n{message}" + USER_SIGNATURE, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Không thể gửi tin nhắn cho Admin: {e}")

# ==========================================
# 5. GIAO DIỆN MENU CHÍNH
# ==========================================
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not bot_status["active"] and user_id != ADMIN_ID:
        text = "🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ</b> 🚧\nVui lòng quay lại sau ít phút!" + USER_SIGNATURE
        if update.message: await update.message.reply_text(text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML")
        return

    u = get_user(user_id)
    can_get, remaining = check_daily_limit(user_id)
    text = (
        "🏪 <b>CHÀO MỪNG ĐẾN VỚI HỆ THỐNG MIZZE KEY VIP</b> 🏪\n\n"
        f"📢 <b>Kênh Thông Báo:</b> {CHANNEL_URL}\n"
        f"👮‍♂️ <b>Admin:</b> {ADMIN_CONTACT}\n"
        "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"💸 <b>Tổng nạp:</b> {u['total_deposit']:,}đ\n"
        f"💰 <b>Số dư:</b> {u['balance']:,}đ\n"
        f"🎁 <b>Lượt lấy Key Free hôm nay:</b> {remaining}/3\n"
    ) + USER_SIGNATURE

    keyboard = [
        [InlineKeyboardButton("🔑 LẤY KEY (MIỄN PHÍ)", callback_data='menu_getkey')],
        [InlineKeyboardButton("🛒 Cửa hàng mua Key", callback_data='menu_shop'),
         InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit')],
        [InlineKeyboardButton("📖 Hướng dẫn sử dụng", callback_data='menu_guide')],
        [InlineKeyboardButton("👤 Tài khoản & Số dư", callback_data='menu_account'),
         InlineKeyboardButton("🧾 Lịch sử", callback_data='menu_history')],
        [InlineKeyboardButton("🐸 Hỗ trợ / Liên hệ Admin", url=SUPPORT_CONTACT)],
        [InlineKeyboardButton("🛡️ ADMIN PANEL", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if update.message:
            await update.message.reply_photo(photo=BANNER_URL, caption=text, reply_markup=reply_markup, parse_mode="HTML")
        elif update.callback_query:
            await update.callback_query.message.delete()
            await context.bot.send_photo(chat_id=user_id, photo=BANNER_URL, caption=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        if update.message: await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

# ==========================================
# 6. XỬ LÝ LỆNH /start & DEEP LINK
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)
    get_user(user_id)
    
    if user_id not in user_states: 
        user_states[user_id] = {'type': None, 'step': 0, 'token': None}

    if context.args:
        arg = context.args[0]
        try:
            parts = arg.split("_")
            key_type, step_num = parts[0], int(parts[1].replace("step", ""))
            received_token = parts[2] if len(parts) > 2 else None
            current_state = user_states[user_id]
            
            if current_state['type'] == key_type and current_state['step'] == step_num - 1:
                if received_token != current_state['token']:
                    await update.message.reply_text("⚠️ <b>PHÁT HIỆN GIAN LẬN HOẶC LINK CŨ!</b>" + USER_SIGNATURE, parse_mode="HTML")
                    user_states[user_id] = {'type': None, 'step': 0, 'token': None}
                    return
                
            user_states[user_id]['step'] = step_num
            
            if key_type == "1h":
                if step_num == 1: await process_step(update, key_type, 2, 2, 'yeumoney')
                elif step_num == 2: await deliver_free_key(update, context, '1h', kho_free_1h)
            
            elif key_type == "3h":
                if step_num == 1: await process_step(update, key_type, 2, 4, 'shrinkme')
                elif step_num == 2: await process_step(update, key_type, 3, 4, 'link4m')
                elif step_num == 3: await process_step(update, key_type, 4, 4, 'shrinkme')
                elif step_num == 4: await deliver_free_key(update, context, '3h', kho_free_3h)
            return
        except Exception as e:
            logger.error(f"Lỗi start deep-link: {e}")

    await show_main_menu(update, context)

async def process_step(update, key_type, current_step, total_steps, provider):
    new_token = generate_token()
    user_states[update.effective_user.id]['token'] = new_token
    target_url = f"https://t.me/{BOT_USERNAME}?start={key_type}_step{current_step}_{new_token}"
    
    if provider == 'link4m': short_url, p_name = await shorten_link4m(target_url), "Link4m"
    elif provider == 'yeumoney': short_url, p_name = await shorten_yeumoney(target_url), "YeuMoney"
    else: short_url, p_name = await shorten_shrinkme(target_url), "ShrinkMe"
        
    if short_url:
        keyboard = [[InlineKeyboardButton(f"🚀 VƯỢT LINK {current_step}/{total_steps} ({p_name})", url=short_url)]]
        text = f"🔄 <b>TIẾN TRÌNH: {current_step}/{total_steps}</b>\nNhà tài trợ: <b>{p_name}</b>\n\n👉 Bấm nút bên dưới để tiếp tục." + USER_SIGNATURE
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Lỗi kết nối API {p_name}. Vui lòng thử lại sau!", parse_mode="HTML")

async def deliver_free_key(update: Update, context: ContextTypes.DEFAULT_TYPE, key_type: str, kho: list):
    user_id = update.effective_user.id
    if not kho:
        await update.message.reply_text(f"❌ <b>KHO KEY FREE {key_type.upper()} ĐÃ CẠN!</b> Vui lòng mua Key tại cửa hàng." + USER_SIGNATURE, parse_mode="HTML")
    else:
        key_nhan = kho.pop(0)
        set_cooldown(user_id, key_type)
        add_daily_usage(user_id)
        
        text = f"🎉 <b>VƯỢT LINK THÀNH CÔNG!</b> 🎉\n〰️〰️〰️〰️〰️〰️〰️〰️\n{key_nhan}\n〰️〰️〰️〰️〰️〰️〰️〰️\n⏳ <i>Chờ {key_type.upper()} để lấy tiếp.</i>" + USER_SIGNATURE
        keyboard = [[InlineKeyboardButton("🛒 Mua thêm Key", callback_data='menu_shop'), InlineKeyboardButton("⬅️ Về Menu", callback_data='back_menu')]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    user_states[user_id] = {'type': None, 'step': 0, 'token': None}

# ==========================================
# 7. XỬ LÝ NÚT BẤM (CALLBACK MENU)
# ==========================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global total_revenue
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    u = get_user(user_id)

    if query.data == 'back_menu': 
        await show_main_menu(update, context)

    elif query.data == 'menu_guide':
        text = (
            "📖 <b>HƯỚNG DẪN SỬ DỤNG BOT</b> 📖\n"
            "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n\n"
            "1️⃣ <b>LẤY KEY MIỄN PHÍ:</b>\n"
            "👉 Bấm nút <b>'🔑 LẤY KEY'</b> -> Chọn 1H hoặc 3H -> Vượt qua các link được cung cấp để nhận Key.\n"
            "⚠️ <i>Mỗi ngày chỉ được lấy tối đa 3 lần.</i>\n\n"
            "2️⃣ <b>MUA KEY BẰNG SỐ DƯ:</b>\n"
            "👉 Bấm <b>'💳 Nạp tiền'</b>, quét mã QR để nạp tiền vào ví.\n"
            "👉 Bấm <b>'🛒 Cửa hàng mua Key'</b>, chọn loại Key muốn mua.\n\n"
            "3️⃣ <b>LIÊN HỆ:</b> Nếu có lỗi, bấm nút <b>'🐸 Hỗ trợ'</b> để gặp Admin."
        ) + USER_SIGNATURE
        keyboard = [[InlineKeyboardButton("⬅️ Quay lại Menu", callback_data='back_menu')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'menu_getkey':
        can_get, remaining = check_daily_limit(user_id)
        if not can_get:
            await query.message.edit_text("🚫 <b>BẠN ĐÃ HẾT 3 LƯỢT LẤY KEY MIỄN PHÍ HÔM NAY!</b>", parse_mode="HTML")
            return
        keyboard = [
            [InlineKeyboardButton("🔑 KEY 1H (2 LINK)", callback_data='get_1h')],
            [InlineKeyboardButton("💎 KEY 3H (4 LINK)", callback_data='get_3h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]
        await query.message.edit_text(f"👇 Bạn còn <b>{remaining}/3</b> lượt lấy Key miễn phí hôm nay.\nChọn loại Key muốn lấy:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data.startswith('get_'):
        can_get, remaining = check_daily_limit(user_id)
        if not can_get:
            await query.message.edit_text("🚫 <b>BẠN ĐÃ HẾT LƯỢT HÔM NAY!</b>", parse_mode="HTML")
            return
        key_type = query.data.split('_')[1]
        can_get_cd, time_left = check_cooldown(user_id, key_type)
        if not can_get_cd:
            await query.message.edit_text(f"🚫 <b>ĐANG TRONG THỜI GIAN CHỜ!</b>\nVui lòng quay lại sau: <b>{time_left}</b>", parse_mode="HTML")
            return
        
        token = generate_token()
        user_states[user_id] = {'type': key_type, 'step': 0, 'token': token}
        
        if key_type == '1h':
            url = await shorten_yeumoney(f"https://t.me/{BOT_USERNAME}?start=1h_step1_{token}")
            if url: await query.message.edit_text("🔄 <b>TIẾN TRÌNH 1/2 (YeuMoney)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK", url=url)]]), parse_mode="HTML")
        elif key_type == '3h':
            url = await shorten_link4m(f"https://t.me/{BOT_USERNAME}?start=3h_step1_{token}")
            if url: await query.message.edit_text("🔄 <b>TIẾN TRÌNH 1/4 (Link4m)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK", url=url)]]), parse_mode="HTML")

    elif query.data == 'menu_shop':
        text = (
            "🛒 <b>CỬA HÀNG BÁN KEY</b> 🛒\n"
            f"💰 Số dư của bạn: <b>{u['balance']:,}đ</b>\n"
            "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"
            f"🔑 Key 1H: <b>{PRICE_SHOP_1H:,}đ</b>\n"
            f"⏳ Key 12H: <b>{PRICE_SHOP_12H:,}đ</b>\n"
            f"📅 Key 1 Ngày: <b>{PRICE_SHOP_1D:,}đ</b>\n"
            f"📆 Key 1 Tháng: <b>{PRICE_SHOP_1M:,}đ</b>"
        )
        keyboard = [
            [InlineKeyboardButton("Mua 1H", callback_data='buy_1h'), InlineKeyboardButton("Mua 12H", callback_data='buy_12h')],
            [InlineKeyboardButton("Mua 1 Ngày", callback_data='buy_1d'), InlineKeyboardButton("Mua 1 Tháng", callback_data='buy_1m')],
            [InlineKeyboardButton("💳 Nạp thêm tiền", callback_data='menu_deposit')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data.startswith('buy_'):
        key_type = query.data.split('_')[1]
        price, kho = 0, []
        if key_type == '1h': price, kho = PRICE_SHOP_1H, kho_shop_1h
        elif key_type == '12h': price, kho = PRICE_SHOP_12H, kho_shop_12h
        elif key_type == '1d': price, kho = PRICE_SHOP_1D, kho_shop_1d
        elif key_type == '1m': price, kho = PRICE_SHOP_1M, kho_shop_1m
        
        if u['balance'] < price:
            await query.message.edit_text("❌ <b>SỐ DƯ KHÔNG ĐỦ!</b> Vui lòng nạp thêm tiền.", parse_mode="HTML")
            return
        if not kho:
            await query.message.edit_text(f"❌ <b>KHO KEY {key_type.upper()} ĐÃ HẾT HÀNG!</b>", parse_mode="HTML")
            return
        
        u['balance'] -= price
        total_revenue += price
        key_nhan = kho.pop(0)
        time_now = datetime.datetime.now().strftime("%H:%M %d/%m")
        u['history'].append(f"[{time_now}] Mua Key {key_type.upper()} (-{price:,}đ)")
        
        await notify_admin(context, f"User ID: <code>{user_id}</code> vừa mua <b>Key {key_type.upper()}</b>.\nSố tiền: <b>+{price:,}đ</b>")
        text = f"✅ <b>MUA THÀNH CÔNG!</b>\n〰️〰️〰️〰️〰️〰️〰️〰️\n{key_nhan}\n〰️〰️〰️〰️〰️〰️〰️〰️\n💰 Số dư còn: <b>{u['balance']:,}đ</b>" + USER_SIGNATURE
        keyboard = [[InlineKeyboardButton("🛒 Mua Tiếp", callback_data='menu_shop'), InlineKeyboardButton("⬅️ Về Menu", callback_data='back_menu')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'menu_deposit':
        add_info = f"NAP {user_id}"
        qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?addInfo={add_info.replace(' ', '%20')}&accountName={ACCOUNT_NAME.replace(' ', '%20')}"
        text = (
            "💳 <b>NẠP TIỀN TỰ ĐỘNG</b> 💳\n"
            "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"
            f"🏦 <b>Ngân hàng:</b> {BANK_ID}\n"
            f"🔢 <b>STK:</b> <code>{ACCOUNT_NO}</code>\n"
            f"👤 <b>Chủ TK:</b> {ACCOUNT_NAME}\n"
            f"📝 <b>Nội dung CK:</b> <code>{add_info}</code>\n\n"
            "👉 <i>Quét mã QR để nạp tự động (Hệ thống tự điền nội dung).</i>"
        )
        keyboard = [[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]
        try:
            await query.message.delete()
            await context.bot.send_photo(chat_id=user_id, photo=qr_url, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except Exception:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'menu_account':
        can_get, remaining = check_daily_limit(user_id)
        text = f"👤 <b>TÀI KHOẢN</b>\nID: <code>{user_id}</code>\nSố dư: <b>{u['balance']:,}đ</b>\nTổng nạp: <b>{u['total_deposit']:,}đ</b>\nLượt Free còn lại: <b>{remaining}/3</b>" + USER_SIGNATURE
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]), parse_mode="HTML")

    elif query.data == 'menu_history':
        hist = "\n".join(u['history'][-10:]) if u['history'] else "Chưa có giao dịch nào."
        text = f"🧾 <b>LỊCH SỬ GIAO DỊCH</b>\n{hist}" + USER_SIGNATURE
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]), parse_mode="HTML")

    # ADMIN PANEL
    elif query.data == 'admin_panel':
        if user_id != ADMIN_ID: return
        status = "🟢 ONLINE" if bot_status["active"] else "🔴 MAINTENANCE"
        keyboard = [
            [InlineKeyboardButton(f"⚙️ BOT: {status}", callback_data='admin_toggle')],
            [InlineKeyboardButton("📊 Thống kê Bot", callback_data='admin_stats')],
            [InlineKeyboardButton("➕ Thêm Key FREE", callback_data='admin_add_free_menu'), InlineKeyboardButton("🛒 Thêm Key SHOP", callback_data='admin_add_shop_menu')],
            [InlineKeyboardButton("🎲 Tạo Key Random (Free)", callback_data='admin_rand_menu')],
            [InlineKeyboardButton("💸 Cộng tiền cho User", callback_data='admin_add_balance')],
            [InlineKeyboardButton("📢 Gửi thông báo", callback_data='admin_broadcast')],
            [InlineKeyboardButton("⬅️ Về Menu", callback_data='back_menu')]
        ]
        await query.message.edit_text("🛡️ <b>BẢNG ĐIỀU KHIỂN ADMIN</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'admin_stats':
        if user_id != ADMIN_ID: return
        text = (
            "📊 <b>THỐNG KÊ HỆ THỐNG</b>\n"
            "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"
            f"👥 Tổng người dùng: <b>{len(all_users)}</b>\n"
            f"💵 Tổng doanh thu: <b>{total_revenue:,}đ</b>\n\n"
            f"<b>KHO FREE:</b> 1H: <code>{len(kho_free_1h)}</code> | 3H: <code>{len(kho_free_3h)}</code>\n"
            f"<b>KHO SHOP:</b> 1H: <code>{len(kho_shop_1h)}</code> | 12H: <code>{len(kho_shop_12h)}</code> | 1D: <code>{len(kho_shop_1d)}</code> | 1M: <code>{len(kho_shop_1m)}</code>"
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]]), parse_mode="HTML")

    elif query.data == 'admin_toggle':
        if user_id != ADMIN_ID: return
        bot_status["active"] = not bot_status["active"]
        await button_handler(update, context)

    elif query.data == 'admin_add_balance':
        if user_id != ADMIN_ID: return
        admin_adding_state[user_id] = 'add_balance'
        await query.message.edit_text("Nhập ID và Số tiền (VD: `7976468365 50000`):")

    elif query.data == 'admin_broadcast':
        if user_id != ADMIN_ID: return
        admin_adding_state[user_id] = 'broadcast'
        await query.message.edit_text("Nhập nội dung thông báo gửi đến toàn bộ người dùng:")

    elif query.data == 'admin_add_free_menu':
        if user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("Thêm Kho Free 1H", callback_data='add_free_1h')],
            [InlineKeyboardButton("Thêm Kho Free 3H", callback_data='add_free_3h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho Free để thêm Key:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'admin_add_shop_menu':
        if user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("Thêm Kho Shop 1H", callback_data='add_shop_1h')],
            [InlineKeyboardButton("Thêm Kho Shop 12H", callback_data='add_shop_12h')],
            [InlineKeyboardButton("Thêm Kho Shop 1 Ngày", callback_data='add_shop_1d')],
            [InlineKeyboardButton("Thêm Kho Shop 1 Tháng", callback_data='add_shop_1m')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho Shop để thêm Key:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('add_free_') or query.data.startswith('add_shop_'):
        if user_id != ADMIN_ID: return
        k_type = query.data.replace('add_', '')
        admin_adding_state[user_id] = f'add_{k_type}'
        await query.message.edit_text(f"📝 Hãy dán danh sách Key vào chat:")

    elif query.data == 'admin_rand_menu':
        if user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("Tạo Random Free 1H", callback_data='rand_free_1h')],
            [InlineKeyboardButton("Tạo Random Free 3H", callback_data='rand_free_3h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho để tạo Key tự động:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('rand_'):
        if user_id != ADMIN_ID: return
        k_type = query.data.replace('rand_', '')
        admin_adding_state[user_id] = f'rand_{k_type}'
        await query.message.edit_text(f"🎲 Nhập số lượng Key muốn tạo:")

# ==========================================
# 8. XỬ LÝ TIN NHẮN TEXT (ADMIN)
# ==========================================
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID or user_id not in admin_adding_state: return
    state = admin_adding_state[user_id]
    text = update.message.text

    if state == 'add_balance':
        try:
            target_id, amount = text.split()
            amount, target_id = int(amount), int(target_id)
            u = get_user(target_id)
            u['balance'] += amount
            u['total_deposit'] += amount
            time_now = datetime.datetime.now().strftime("%H:%M %d/%m")
            u['history'].append(f"[{time_now}] Admin nạp (+{amount:,}đ)")
            await update.message.reply_text(f"✅ Đã cộng {amount:,}đ cho ID {target_id}.")
            try: await context.bot.send_message(target_id, f"💰 Bạn vừa được Admin cộng {amount:,}đ vào số dư!")
            except: pass
        except: await update.message.reply_text("❌ Sai cú pháp.")
        del admin_adding_state[user_id]

    elif state == 'broadcast':
        await update.message.reply_text("⏳ Đang gửi thông báo...")
        success = 0
        for uid in list(all_users):
            try:
                await context.bot.send_message(uid, f"📢 <b>THÔNG BÁO TỪ ADMIN</b>\n\n{html.escape(text)}", parse_mode="HTML")
                success += 1
                await asyncio.sleep(0.05)
            except: pass
        await update.message.reply_text(f"✅ Đã gửi đến {success} người dùng.")
        del admin_adding_state[user_id]

    elif state.startswith('add_'):
        target_list = None
        if state == 'add_free_1h': target_list = kho_free_1h
        elif state == 'add_free_3h': target_list = kho_free_3h
        elif state == 'add_shop_1h': target_list = kho_shop_1h
        elif state == 'add_shop_12h': target_list = kho_shop_12h
        elif state == 'add_shop_1d': target_list = kho_shop_1d
        elif state == 'add_shop_1m': target_list = kho_shop_1m

        if not target_list: return
        matches = re.findall(r"Key:\s*([^\n]+)\s*\n.*?Mật khẩu:\s*([^\n]+)", text, re.IGNORECASE)
        added = 0
        if matches:
            for k, p in matches:
                target_list.append(f"<b>🔑 Key:</b> <code>{html.escape(k.strip())}</code>\n<b>🔒 Mật khẩu:</b> <span class='tg-spoiler'>{html.escape(p.strip())}</span>")
                added += 1
        else:
            for block in text.split('\n\n'):
                if block.strip():
                    target_list.append(html.escape(block.strip()))
                    added += 1
        await update.message.reply_text(f"✅ Đã thêm {added} Key vào kho!")
        del admin_adding_state[user_id]

    elif state.startswith('rand_'):
        target_list = kho_free_1h if state == 'rand_free_1h' else kho_free_3h
        try:
            sl = int(text.strip())
            for _ in range(sl): target_list.append(generate_random_key())
            await update.message.reply_text(f"✅ Đã tạo {sl} Key Random thành công!")
        except: await update.message.reply_text("❌ Vui lòng nhập số hợp lệ.")
        del admin_adding_state[user_id]

# ==========================================
# 9. FLASK SERVER & SEPAY WEBHOOK
# ==========================================
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check(): return "Bot is running!", 200

@flask_app.route('/sepay_webhook', methods=['POST'])
def sepay_webhook():
    auth_header = request.headers.get('Authorization')
    if auth_header != f"Apikey {SEPAY_API_KEY}":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json
    if not data or data.get("transferType") != "in":
        return jsonify({"success": True}), 200

    content = data.get("content", "")
    amount = int(data.get("transferAmount", 0))

    match = re.search(r"NAP\s+(\d+)", content, re.IGNORECASE)
    if match:
        target_id = int(match.group(1))
        u = get_user(target_id)
        u['balance'] += amount
        u['total_deposit'] += amount
        time_now = datetime.datetime.now().strftime("%H:%M %d/%m")
        u['history'].append(f"[{time_now}] SePay Auto (+{amount:,}đ)")
        
        try:
            msg = f"✅ <b>NẠP TIỀN THÀNH CÔNG!</b>\nSố tiền: <b>+{amount:,}đ</b>\nSố dư mới: <b>{u['balance']:,}đ</b>"
            httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": target_id, "text": msg, "parse_mode": "HTML"})
        except Exception as e:
            logger.error(f"Lỗi gửi tin nhắn webhook: {e}")

    return jsonify({"success": True}), 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ==========================================
# 10. KHỞI CHẠY BOT & BẮT LỖI TOÀN CỤC
# ==========================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    try:
        error_msg = str(context.error)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ <b>LỖI HỆ THỐNG BOT</b>\n\n<code>{html.escape(error_msg[:3500])}</code>",
            parse_mode="HTML"
        )
    except:
        pass

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    
    app.add_error_handler(error_handler)
    
    logger.info("Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()