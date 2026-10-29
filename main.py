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
from urllib.parse import quote
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

# ==========================================
# 1. CẤU HÌNH (Sửa thông tin của bạn ở đây)
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFbhh-nluyw0QkW8nDSH9hW_qOzxfukKD4")
LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")

# ⚠️ QUAN TRỌNG: SỬA 2 DÒNG DƯỚI ĐÂY
BOT_USERNAME = "GetkeyMizze_bot" # Tên bot của bạn (GetkeyMizzebot)
ADMIN_ID = 7976468365              # ID Telegram của bạn (7976468365)

# ✍️ CHỮ KÝ MẪU (Hiển thị cuối mỗi tin nhắn nhận key hoặc thông báo)
USER_SIGNATURE = "\n\n────────────────────\n🤖 <i>Powered by Mizze Key Bot</i>"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 2. CƠ SỞ DỮ LIỆU TẠM THỜI (RAM)
# ==========================================
kho_key_1h = []
kho_key_3h = []
kho_key_6h = []

user_states = {}
cooldowns = {}
admin_adding_state = {}
all_users = set() # Lưu ID người dùng
bot_status = {"active": True}

# ==========================================
# 3. HÀM HỖ TRỢ
# ==========================================
async def shorten_link_async(long_url: str) -> str:
    api_endpoint = "https://link4m.co/api-shorten/v2"
    encoded_url = quote(long_url.strip(), safe='')
    full_api_url = f"{api_endpoint}?api={LINK4M_API_KEY.strip()}&url={encoded_url}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(full_api_url, timeout=15.0)
            data = response.json()
            if data.get("status") == "success":
                return data.get("shortenedUrl").strip()
            return None
    except Exception as e:
        logger.error(f"Lỗi kết nối Link4m: {e}")
        return None

def generate_random_key(key_len=15):
    alphabet = string.ascii_uppercase + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    password = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    return f"<b>🔑 Key:</b> <code>{key}</code>\n<b>🔒 Mật khẩu:</b> <code>{password}</code>"

def check_cooldown(user_id, key_type):
    if user_id not in cooldowns or key_type not in cooldowns[user_id]:
        return True, 0
    expire_time = cooldowns[user_id][key_type]
    now = time.time()
    if now < expire_time:
        remaining = int(expire_time - now)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        return False, f"{hours} giờ {minutes} phút"
    return True, 0

def set_cooldown(user_id, key_type):
    if user_id not in cooldowns: cooldowns[user_id] = {}
    if key_type == '1h': cooldowns[user_id]['1h'] = time.time() + (1 * 3600)
    elif key_type == '3h': cooldowns[user_id]['3h'] = time.time() + (3 * 3600)
    elif key_type == '6h': cooldowns[user_id]['6h'] = time.time() + (6 * 3600)

async def broadcast(context, text):
    success = 0
    full_text = text + USER_SIGNATURE
    for uid in list(all_users):
        try:
            await context.bot.send_message(chat_id=uid, text=full_text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    return success

# ==========================================
# 4. GIAO DIỆN NGƯỜI DÙNG (HTML MODERN UI)
# ==========================================
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not bot_status["active"] and user_id != ADMIN_ID:
        text = (
            "🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ</b> 🚧\n\n"
            "⏳ Admin đang nâng cấp hệ thống để phục vụ bạn tốt hơn.\n"
            "Vui lòng quay lại sau ít phút!"
        ) + USER_SIGNATURE
        if update.message: await update.message.reply_text(text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML")
        return

    keyboard = [
        [InlineKeyboardButton("🔑 KEY 1 GIỜ (2 LINK)", callback_data='get_1h')],
        [InlineKeyboardButton("🔥 KEY 3 GIỜ (3 LINK)", callback_data='get_3h')],
        [InlineKeyboardButton("💎 KEY 6 GIỜ (6 LINK)", callback_data='get_6h')],
        [InlineKeyboardButton("📦 KHO KEY", callback_data='view_kho'),
         InlineKeyboardButton("📊 TRẠNG THÁI", callback_data='check_status')],
        [InlineKeyboardButton("🛡️ QUẢN TRỊ VIÊN", callback_data='admin_panel')]
    ]

    text = (
        "╭───────────────────╮\n"
        " 🤖 <b>BOT GET KEY VIP</b> 🤖\n"
        "╰───────────────────╯\n\n"
        "✨ Chào mừng bạn đến với hệ thống lấy Key tự động!\n\n"
        "🔹 <b>Hướng dẫn:</b>\n"
        "Nhấn vào các nút bên dưới để chọn loại Key bạn muốn lấy.\n\n"
        "⚠️ <i>Hệ thống có thời gian chờ (Cooldown) để chống lạm phát. Vui lòng đọc kỹ trước khi lấy!</i>"
    ) + USER_SIGNATURE

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message: await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query: await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)
    if user_id not in user_states: user_states[user_id] = {'type': None, 'step': 0}

    if context.args:
        arg = context.args[0].strip()
        try:
            key_type, step_str = arg.split("_")
            step_num = int(step_str.replace("step", ""))
            current_state = user_states[user_id]

            if current_state['type'] == key_type and current_state['step'] == step_num - 1:
                user_states[user_id]['step'] = step_num

            if key_type == "1h":
                if step_num == 1: await handle_step(update, key_type, 2, 2)
                elif step_num == 2: await deliver_key(update, context, '1h', kho_key_1h)
            elif key_type == "3h":
                if step_num == 1: await handle_step(update, key_type, 2, 3)
                elif step_num == 2: await handle_step(update, key_type, 3, 3)
                elif step_num == 3: await deliver_key(update, context, '3h', kho_key_3h)
            elif key_type == "6h":
                if step_num == 1: await handle_step(update, key_type, 2, 6)
                elif step_num == 2: await handle_step(update, key_type, 3, 6)
                elif step_num == 3: await handle_step(update, key_type, 4, 6)
                elif step_num == 4: await handle_step(update, key_type, 5, 6)
                elif step_num == 5: await handle_step(update, key_type, 6, 6)
                elif step_num == 6: await deliver_key(update, context, '6h', kho_key_6h)
            return
        except Exception:
            pass
    await show_main_menu(update, context)

async def handle_step(update, key_type, current_step, total_steps):
    target_link = f"https://t.me/{BOT_USERNAME}?start={key_type}_step{current_step}"
    short_url = await shorten_link_async(target_link)
    if short_url:
        keyboard = [[InlineKeyboardButton(f"🚀 VƯỢT LINK {current_step}/{total_steps}", url=short_url)]]
        text = f"🔄 <b>TIẾN TRÌNH: {current_step}/{total_steps}</b>\n\nVui lòng bấm nút bên dưới để vượt link và tiếp tục." + USER_SIGNATURE
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Lỗi tạo link rút gọn từ hệ thống Link4m. Vui lòng thử lại sau!", parse_mode="HTML")

async def deliver_key(update: Update, context: ContextTypes.DEFAULT_TYPE, key_type: str, kho: list):
    user_id = update.effective_user.id
    if not kho:
        await update.message.reply_text(f"❌ <b>RẤT TIẾC!</b>\nKho Key {key_type.upper()} đã hết sạch. Vui lòng quay lại sau hoặc báo Admin!" + USER_SIGNATURE, parse_mode="HTML")
        user_states[user_id] = {'type': None, 'step': 0}
        return

    key_nhan = kho.pop(0)
    set_cooldown(user_id, key_type)
    user_states[user_id] = {'type': None, 'step': 0}

    text = (
        "🎉 <b>CHÚC MỪNG BẠN ĐÃ VƯỢT LINK THÀNH CÔNG!</b> 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{key_nhan}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ <i>Bạn cần chờ <b>{key_type.upper()}</b> để có thể lấy key tiếp theo.</i>"
    ) + USER_SIGNATURE
    await update.message.reply_text(text, parse_mode="HTML")

# ==========================================
# 5. XỬ LÝ NÚT BẤM (CALLBACK)
# ==========================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if not bot_status["active"] and user_id != ADMIN_ID:
        await query.answer("🛠️ Hệ thống đang bảo trì, vui lòng quay lại sau!", show_alert=True)
        return

    if query.data.startswith('get_'):
        key_type = query.data.split('_')[1]
        can_get, time_left = check_cooldown(user_id, key_type)
        if not can_get:
            await query.message.edit_text(
                f"🚫 <b>BẠN ĐANG TRONG THỜI GIAN CHỜ!</b>\n\n"
                f"Vui lòng quay lại sau: <b>{time_left}</b>" + USER_SIGNATURE,
                parse_mode="HTML"
            )
            return
        user_states[user_id] = {'type': key_type, 'step': 0}
        target_url = f"https://t.me/{BOT_USERNAME}?start={key_type}_step1"
        short_url = await shorten_link_async(target_url)
        if short_url:
            total = "2" if key_type == "1h" else "3" if key_type == "3h" else "6"
            keyboard = [[InlineKeyboardButton(f"🚀 VƯỢT LINK 1/{total}", url=short_url)]]
            await query.message.edit_text(
                f"🔄 <b>TIẾN TRÌNH: 1/{total}</b>\n\nVui lòng bấm nút bên dưới để vượt link và tiếp tục." + USER_SIGNATURE,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
            )
        else:
            await query.message.edit_text("❌ Lỗi tạo link rút gọn từ hệ thống Link4m. Vui lòng thử lại sau.", parse_mode="HTML")

    elif query.data == 'view_kho':
        text = (
            "📦 <b>KHO KEY HIỆN TẠI</b> 📦\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 Key 1H: <code>{len(kho_key_1h)}</code>\n"
            f"🔥 Key 3H: <code>{len(kho_key_3h)}</code>\n"
            f"💎 Key 6H: <code>{len(kho_key_6h)}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Số lượng key sẽ được cập nhật liên tục khi Admin thêm vào.</i>"
        ) + USER_SIGNATURE
        keyboard = [[InlineKeyboardButton("⬅️ QUAY LẠI", callback_data='back_menu')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'check_status':
        text = "📊 <b>TRẠNG THÁI COOLDOWN CỦA BẠN</b> 📊\n━━━━━━━━━━━━━━━━━━━━\n"
        for kt in ['1h', '3h', '6h']:
            can_get, time_left = check_cooldown(user_id, kt)
            if can_get: text += f"✅ Key {kt.upper()}: <b>Sẵn sàng lấy</b>\n"
            else: text += f"⏳ Key {kt.upper()}: Chờ <b>{time_left}</b>\n"
        text += USER_SIGNATURE

        keyboard = [[InlineKeyboardButton("⬅️ QUAY LẠI", callback_data='back_menu')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'back_menu':
        await show_main_menu(update, context)

    # --- MENU ADMIN ---
    elif query.data == 'admin_panel':
        if user_id != ADMIN_ID: return
        status_text = "🟢 ĐANG HOẠT ĐỘNG" if bot_status["active"] else "🔴 Đang bảo trì"
        keyboard = [
            [InlineKeyboardButton("👥 THỐNG KÊ NGƯỜI DÙNG", callback_data='admin_users')],
            [InlineKeyboardButton("📦 Xem Kho Key", callback_data='admin_kho')],
            [InlineKeyboardButton("➕ Thêm Key", callback_data='admin_add_menu')],
            [InlineKeyboardButton("🗑 Xoá Key", callback_data='admin_del_menu')],
            [InlineKeyboardButton("🎲 Tạo Key Random", callback_data='admin_rand_menu')],
            [InlineKeyboardButton(f"⚙️ Bot: {status_text}", callback_data='admin_toggle')],
            [InlineKeyboardButton("📢 Gửi thông báo chung", callback_data='admin_broadcast')],
            [InlineKeyboardButton("⬅️ Quay lại Menu", callback_data='back_menu')]
        ]
        await query.message.edit_text(
            "🛡️ <b>BẢNG ĐIỀU KHIỂN ADMIN</b> 🛡️\n<i>Chọn chức năng bên dưới:</i>" + USER_SIGNATURE,
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )

    elif query.data == 'admin_users':
        if user_id != ADMIN_ID: return
        total_users = len(all_users)
        user_list = list(all_users)[-20:]
        ids_text = "\n".join([f"• <code>{uid}</code>" for uid in user_list])

        text = (
            "👥 <b>THỐNG KÊ NGƯỜI DÙNG</b> 👥\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Tổng số người đã dùng bot: <b>{total_users}</b>\n\n"
            f"<b>Danh sách 20 ID mới nhất:</b>\n{ids_text}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<i>*Lưu ý: Danh sách sẽ reset nếu Render khởi động lại.</i>"
        ) + USER_SIGNATURE
        keyboard = [[InlineKeyboardButton("⬅️ QUAY LẠI", callback_data='admin_panel')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'admin_toggle':
        if user_id != ADMIN_ID: return
        bot_status["active"] = not bot_status["active"]
        status_msg = "BẬT" if bot_status["active"] else "TẮT"
        await query.answer(f"Đã {status_msg} bot!", show_alert=True)
        await query.message.edit_text(f"⚙️ Đã chuyển trạng thái Bot thành: <b>{status_msg}</b>\nBấm vào Quản trị viên để xem lại." + USER_SIGNATURE, parse_mode="HTML")

    elif query.data == 'admin_broadcast':
        if user_id != ADMIN_ID: return
        admin_adding_state[user_id] = 'broadcast'
        await query.message.edit_text("📢 Hãy nhập nội dung thông báo gửi đến toàn bộ người dùng:")

    elif query.data == 'admin_kho':
        if user_id != ADMIN_ID: return
        text = (
            "📦 <b>THỐNG KÊ KHO KEY (ADMIN)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 Key 1H: <code>{len(kho_key_1h)}</code>\n"
            f"🔥 Key 3H: <code>{len(kho_key_3h)}</code>\n"
            f"💎 Key 6H: <code>{len(kho_key_6h)}</code>"
        ) + USER_SIGNATURE
        keyboard = [[InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'admin_add_menu':
        if user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("Thêm Kho 1H", callback_data='add_key_1h'), InlineKeyboardButton("Thêm Kho 3H", callback_data='add_key_3h'), InlineKeyboardButton("Thêm Kho 6H", callback_data='add_key_6h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho để thêm Key:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'admin_del_menu':
        if user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("Xoá Kho 1H", callback_data='del_key_1h'), InlineKeyboardButton("Xoá Kho 3H", callback_data='del_key_3h'), InlineKeyboardButton("Xoá Kho 6H", callback_data='del_key_6h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho để xoá Key:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'admin_rand_menu':
        if user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("Tạo Random 1H", callback_data='rand_key_1h'), InlineKeyboardButton("Tạo Random 3H", callback_data='rand_key_3h'), InlineKeyboardButton("Tạo Random 6H", callback_data='rand_key_6h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho để tạo Key tự động:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith(('add_key_', 'del_key_', 'rand_key_')):
        if user_id != ADMIN_ID: return
        action, k_type = query.data.split('_')[1], query.data.split('_')[2]

        if action == 'add':
            admin_adding_state[user_id] = f'add_{k_type}'
            await query.message.edit_