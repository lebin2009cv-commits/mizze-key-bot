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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9120368691:AAE9J5NtmXqYBPiKmC7pJq_UKmjwlwny2sw")
BOT_USERNAME = "GetkeyMizzebot"
ADMIN_ID = 7976468365

USER_SIGNATURE = "\n\n────────────────────\n🤖 <i>Powered by Mizze Key Bot</i>"

BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/lebind"
SUPPORT_CONTACT = "https://t.me/NTH_VIP"

LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")
YEUMONEY_API_KEY = os.environ.get("YEUMONEY_API_KEY", "316b5434e78e4ffe8475d87e407754f0ab92a4b85055a7ecd19c86a196cd702a")
SHRINKME_API_KEY = os.environ.get("SHRINKME_API_KEY", "cbf0c1f1343fbb4755913212000f0ad1178e3a46")

BANK_ID = "VPBANK"
ACCOUNT_NO = "0382570538"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_API_KEY = os.environ.get("SEPAY_API_KEY", "botgetkey_sepay")

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
kho_shop_1h, kho_shop_12h, kho_shop_1d, kho_shop_1m = [], [], [], []

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