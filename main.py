import os
import logging
import threading
import httpx
import re
import secrets
import string
import time
from urllib.parse import quote
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9120368691:AAE9J5NtmXqYBPiKmC7pJq_UKmjwlwny2sw")
LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")

# ⚠️ QUAN TRỌNG: SỬA 2 DÒNG DƯỚI ĐÂY
BOT_USERNAME = "GetkeyMizze_bot" # Tên bot của bạn (GetkeyMizze_bot)
ADMIN_ID = 7976468365              # ID Telegram của bạn (7976468365)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 2. CƠ SỞ DỮ LIỆU TẠM THỜI (LƯU TRÊN RAM)
# ==========================================
kho_key_1h = []
kho_key_3h = []
kho_key_6h = []

# Lưu tiến trình vượt link của user: {user_id: {'type': '1h'/'3h'/'6h', 'step': x}}
user_states = {}

# Lưu thời gian cooldown của từng user theo gói: {user_id: {'1h': timestamp, '3h': timestamp, '6h': timestamp}}
user_cooldowns = {}

# Trạng thái chờ thêm key của Admin: {admin_id: '1h'/'3h'/'6h'}
admin_adding_state = {}

# ==========================================
# 3. HÀM TẠO LINK4M BẤT ĐỒNG BỘ
# ==========================================
async def shorten_link_async(long_url: str) -> str:
    api_endpoint = "https://link4m.co/api-shorten/v2"
    encoded_url = quote(long_url, safe='')
    full_api_url = f"{api_endpoint}?api={LINK4M_API_KEY}&url={encoded_url}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(full_api_url, timeout=15.0)
            data = response.json()
            if data.get("status") == "success":
                return data.get("shortenedUrl")
            return None
    except Exception as e:
        logger.error(f"Lỗi kết nối Link4m: {e}")
        return None

# ==========================================
# 4. HÀM SINH KEY NGẪU NHÂN CHO ADMIN (/rangex)
# ==========================================
def generate_random_key(key_len=16):
    alphabet = string.ascii_uppercase + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    password = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    return f"🔑 Key: {key}\n🔒 Mật khẩu: {password}"

# ==========================================
# 5. GIAO DIỆN CHÍNH (MENU & BUTTON)
# ==========================================
def get_main_menu_keyboard(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("🕒 Nhận Key 1 Giờ (Vượt 2 Link)", callback_data='menu_1h')],
        [InlineKeyboardButton("🔥 Nhận Key 3 Giờ (Vượt 3 Link)", callback_data='menu_3h')],
        [InlineKeyboardButton("⚡ Nhận Key 6 Giờ (Vượt 6 Link)", callback_data='menu_6h')],
        [InlineKeyboardButton("📊 Trạng thái & Cooldown", callback_data='menu_status')],
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 Bảng Điều Khiển Admin", callback_data='admin_panel')])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        user_states[user_id] = {'type': None, 'step': 0}

    # Bắt tín hiệu Deep Link sau khi người dùng vượt link xong quay lại bot
    if context.args:
        arg = context.args[0] # Ví dụ: "1h_step1", "3h_step2", "6h_step5"...
        try:
            key_type, step_str = arg.split("_")
            step_num = int(step_str.replace("step", ""))
            user_states[user_id]['type'] = key_type
            user_states[user_id]['step'] = step_num
            
            total_steps = 2 if key_type == "1h" else (3 if key_type == "3h" else 6)
            if step_num < total_steps:
                await update.message.reply_text(f"✅ Hoàn thành link {step_num}/{total_steps}!\nBấm vào nút tương ứng bên dưới để tiếp tục.")
            else:
                await update.message.reply_text(f"✅ Hoàn thành tất cả {total_steps} link!\nBấm vào nút tương ứng để nhận phần thưởng.")
        except Exception:
            pass

    text = (
        "🤖 **HỆ THỐNG LẤY KEY TỰ ĐỘNG MIZZE**\n\n"
        "Chào mừng bạn đến với bot cấp key tự động cao cấp.\n"
        "Vui lòng chọn các mục bên dưới để bắt đầu vượt link nhận thưởng:"
    )
    is_admin = (user_id == ADMIN_ID)
    markup = get_main_menu_keyboard(is_admin)

    if update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# 6. XỬ LÝ SỰ KIỆN CALLBACK BUTTON
# ==========================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # Quay lại menu chính
    if data == 'main_menu':
        is_admin = (user_id == ADMIN_ID)
        await query.message.edit_text(
            "🏠 **MENU CHÍNH**\nVui lòng lựa chọn dịch vụ:",
            reply_markup=get_main_menu_keyboard(is_admin),
            parse_mode="Markdown"
        )
        return

    # --- KIỂM TRA COOLDOWN (CHỐNG LẠM PHÁT / SPAM) ---
    now = time.time()
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = {'1h': 0, '3h': 0, '6h': 0}

    # --- XỬ LÝ GÓI KEY 1H (2 Link) ---
    if data in ['menu_1h', 'get_1h_next']:
        cooldown_time = 3600 # 1 tiếng = 3600 giây
        time_left = user_cooldowns[user_id]['1h'] - now
        if time_left > 0:
            mins = int(time_left // 60)
            await query.message.edit_text(
                f"⏳ **Bạn đang trong thời gian chờ (Cooldown)!**\nVui lòng đợi thêm `{mins} phút` nữa mới được lấy Key 1H tiếp theo.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại Menu", callback_data='main_menu')]]),
                parse_mode="Markdown"
            )
            return

        state = user_states.setdefault(user_id, {'type': None, 'step': 0})
        if state['type'] != '1h':
            state = {'type': '1h', 'step': 0}
            user_states[user_id] = state

        if state['step'] == 0:
            target_url = f"https://t.me/{BOT_USERNAME}?start=1h_step1"
            short_url = await shorten_link_async(target_url)
            if short_url:
                kb = [[InlineKeyboardButton("🔗 Vượt Link 1/2", url=short_url)],
                      [InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]
                await query.message.edit_text("🕒 **Gói 1 Giờ - Link 1/2**\nBấm nút bên dưới để vượt link:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                await query.message.edit_text("❌ Lỗi hệ thống tạo link rút gọn. Vui lòng thử lại sau.")

        elif state['step'] == 1:
            target_url = f"https://t.me/{BOT_USERNAME}?start=1h_step2"
            short_url = await shorten_link_async(target_url)
            if short_url:
                kb = [[InlineKeyboardButton("🔗 Vượt Link 2/2", url=short_url)],
                      [InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]
                await query.message.edit_text("🕒 **Gói 1 Giờ - Link 2/2 (Cuối cùng)**\nBấm nút bên dưới để hoàn tất:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                await query.message.edit_text("❌ Lỗi hệ thống tạo link rút gọn. Vui lòng thử lại sau.")

        elif state['step'] >= 2:
            if not kho_key_1h:
                await query.message.edit_text("📦 Kho Key 1H hiện đang trống! Vui lòng báo Admin bổ sung.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]))
                return
            key_nhan = kho_key_1h.pop(0)
            user_states[user_id] = {'type': None, 'step': 0}
            user_cooldowns[user_id]['1h'] = now + cooldown_time # Kích hoạt cooldown 1 tiếng
            await query.message.edit_text(
                f"🎉 **Nhận Key 1H Thành Công!**\n\n{key_nhan}\n\n⏱️ *Bạn đã bị khóa cooldown gói này trong 1 giờ tới.*",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Về Menu Chính", callback_data='main_menu')]]),
                parse_mode="Markdown"
            )

    # --- XỬ LÝ GÓI KEY 3H (3 Link) ---
    elif data in ['menu_3h', 'get_3h_next']:
        cooldown_time = 10800 # 3 tiếng = 10800 giây
        time_left = user_cooldowns[user_id]['3h'] - now
        if time_left > 0:
            hours = int(time_left // 3600)
            mins = int((time_left % 3600) // 60)
            await query.message.edit_text(
                f"⏳ **Bạn đang trong thời gian chờ (Cooldown)!**\nVui lòng đợi thêm `{hours} giờ {mins} phút` nữa mới được lấy Key 3H tiếp theo.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại Menu", callback_data='main_menu')]]),
                parse_mode="Markdown"
            )
            return

        state = user_states.setdefault(user_id, {'type': None, 'step': 0})
        if state['type'] != '3h':
            state = {'type': '3h', 'step': 0}
            user_states[user_id] = state

        if state['step'] == 0:
            target_url = f"https://t.me/{BOT_USERNAME}?start=3h_step1"
            short_url = await shorten_link_async(target_url)
            if short_url:
                kb = [[InlineKeyboardButton("🔗 Vượt Link 1/3", url=short_url)], [InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]
                await query.message.edit_text("🔥 **Gói 3 Giờ - Link 1/3**\nBấm nút bên dưới:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                await query.message.edit_text("❌ Lỗi hệ thống tạo link.")

        elif state['step'] == 1:
            target_url = f"https://t.me/{BOT_USERNAME}?start=3h_step2"
            short_url = await shorten_link_async(target_url)
            if short_url:
                kb = [[InlineKeyboardButton("🔗 Vượt Link 2/3", url=short_url)], [InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]
                await query.message.edit_text("🔥 **Gói 3 Giờ - Link 2/3**\nBấm nút bên dưới:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                await query.message.edit_text("❌ Lỗi hệ thống tạo link.")

        elif state['step'] == 2:
            target_url = f"https://t.me/{BOT_USERNAME}?start=3h_step3"
            short_url = await shorten_link_async(target_url)
            if short_url:
                kb = [[InlineKeyboardButton("🔗 Vượt Link 3/3", url=short_url)], [InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]
                await query.message.edit_text("🔥 **Gói 3 Giờ - Link 3/3 (Cuối)**\nBấm nút bên dưới:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                await query.message.edit_text("❌ Lỗi hệ thống tạo link.")

        elif state['step'] >= 3:
            if not kho_key_3h:
                await query.message.edit_text("📦 Kho Key 3H hiện đang trống!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]))
                return
            key_nhan = kho_key_3h.pop(0)
            user_states[user_id] = {'type': None, 'step': 0}
            user_cooldowns[user_id]['3h'] = now + cooldown_time
            await query.message.edit_text(
                f"🎉 **Nhận Key 3H Thành Công!**\n\n{key_nhan}\n\n⏱️ *Cooldown: 3 giờ.*",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Về Menu Chính", callback_data='main_menu')]]),
                parse_mode="Markdown"
            )

    # --- XỬ LÝ GÓI KEY 6H (6 Link) ---
    elif data in ['menu_6h', 'get_6h_next']:
        cooldown_time = 21600 # 6 tiếng = 21600 giây
        time_left = user_cooldowns[user_id]['6h'] - now
        if time_left > 0:
            hours = int(time_left // 3600)
            mins = int((time_left % 3600) // 60)
            await query.message.edit_text(
                f"⏳ **Bạn đang trong thời gian chờ (Cooldown)!**\nVui lòng đợi thêm `{hours} giờ {mins} phút` nữa mới được lấy Key 6H tiếp theo.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại Menu", callback_data='main_menu')]]),
                parse_mode="Markdown"
            )
            return

        state = user_states.setdefault(user_id, {'type': None, 'step': 0})
        if state['type'] != '6h':
            state = {'type': '6h', 'step': 0}
            user_states[user_id] = state

        step = state['step']
        if step < 6:
            target_url = f"https://t.me/{BOT_USERNAME}?start=6h_step{step+1}"
            short_url = await shorten_link_async(target_url)
            if short_url:
                kb = [[InlineKeyboardButton(f"🔗 Vượt Link {step+1}/6", url=short_url)], [InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]
                await query.message.edit_text(f"⚡ **Gói 6 Giờ - Link {step+1}/6**\nBấm nút bên dưới để tiếp tục:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                await query.message.edit_text("❌ Lỗi hệ thống tạo link.")
        else:
            if not kho_key_6h:
                await query.message.edit_text("📦 Kho Key 6H hiện đang trống!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='main_menu')]]))
                return
            key_nhan = kho_key_6h.pop(0)
            user_states[user_id] = {'type': None, 'step': 0}
            user_cooldowns[user_id]['6h'] = now + cooldown_time
            await query.message.edit_text(
                f"🎉 **Nhận Key 6H Thành Công!**\n\n{key_nhan}\n\n⏱️ *Cooldown: 6 giờ.*",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Về Menu Chính", callback_data='main_menu')]]),
                parse_mode="Markdown"
            )

    # --- MENU TRẠNG THÁI & COOLDOWN CỦA USER ---
    elif data == 'menu_status':
        cd = user_cooldowns.get(user_id, {'1h': 0, '3h': 0, '6h': 0})
        
        def fmt_cd(exp):
            rem = exp - now
            if rem <= 0: return "🟢 Sẵn sàng"
            h = int(rem // 3600)
            m = int((rem % 3600) // 60)
            return f"⏳ Còn chờ {h}h {m}p"

        st_text = (
            f"📊 **TRẠNG THÁI TÀI KHOẢN CỦA BẠN**\n\n"
            f"• Gói 1H: {fmt_cd(cd['1h'])}\n"
            f"• Gói 3H: {fmt_cd(cd['3h'])}\n"
            f"• Gói 6H: {fmt_cd(cd['6h'])}\n"
        )
        kb = [[InlineKeyboardButton("⬅️ Quay lại Menu", callback_data='main_menu')]]
        await query.message.edit_text(st_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    # ==========================================
    # 7. ADMIN PANEL (GIAO DIỆN QUẢN TRỊ)
    # ==========================================
    elif data == 'admin_panel':
        if user_id != ADMIN_ID: return
        adm_text = (
            f"👑 **BẢNG ĐIỀU KHIỂN ADMIN**\n\n"
            f"📦 **Kho hiện tại:**\n"
            f"- Key 1H: `{len(kho_key_1h)}` bộ\n"
            f"- Key 3H: `{len(kho_key_3h)}` bộ\n"
            f"- Key 6H: `{len(kho_key_6h)}` bộ\n"
        )
        kb = [
            [InlineKeyboardButton("➕ Thêm Key 1H", callback_data='add_to_1h'), InlineKeyboardButton("➕ Thêm Key 3H", callback_data='add_to_3h')],
            [InlineKeyboardButton("➕ Thêm Key 6H", callback_data='add_to_6h')],
            [InlineKeyboardButton("🏠 Về Menu Chính", callback_data='main_menu')]
        ]
        await query.message.edit_text(adm_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data in ['add_to_1h', 'add_to_3h', 'add_to_6h']:
        if user_id != ADMIN_ID: return
        kho_type = data.replace('add_to_', '')
        admin_adding_state[user_id] = kho_type
        await query.message.edit_text(
            f"📝 **THÊM KEY VÀO KHO {kho_type.upper()}**\n\n"
            f"Hãy gửi danh sách Key kèm Mật khẩu vào đây (hỗ trợ tự động nhận diện Key/Mật khẩu hoặc phân cách bằng dòng trống).",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy bỏ", callback_data='admin_panel')]]),
            parse_mode="Markdown"
        )

# ==========================================
# 8. XỬ LÝ NHẬP LIỆU CỦA ADMIN (THÊM KEY)
# ==========================================
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID or user_id not in admin_adding_state:
        return 
    
    kho_loai = admin_adding_state[user_id]
    text = update.message.text
    
    # Dùng Regex nhận diện cặp Key - Mật khẩu
    matches = re.findall(r"Key:\s*(.*?)\s*\n.*?Mật khẩu:\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    
    added_count = 0
    target_list = kho_key_1h if kho_loai == '1h' else (kho_key_3h if kho_loai == '3h' else kho_key_6h)

    if matches:
        for k, p in matches:
            formatted_key = f"🔑 Key: {k.strip()}\n🔒 Mật khẩu: {p.strip()}"
            target_list.append(formatted_key)
            added_count += 1
    else:
        blocks = text.split('\n\n')
        for block in blocks:
            if block.strip():
                target_list.append(block.strip())
                added_count += 1
                
    if added_count > 0:
        await update.message.reply_text(f"✅ Đã thêm thành công `{added_count}` bộ Key vào kho **{kho_loai.upper()}**!\n📦 Tổng kho hiện tại: `{len(target_list)}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Không tìm thấy định dạng Key hợp lệ.")
    
    del admin_adding_state[user_id]

# ==========================================
# 9. CÁC LỆNH QUẢN TRỊ VIÊN (COMMANDS)
# ==========================================
async def cmd_kho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text(
        f"📦 **THỐNG KÊ KHO KEY**\n\n"
        f"🕒 Key 1H: `{len(kho_key_1h)}`\n"
        f"🔥 Key 3H: `{len(kho_key_3h)}`\n"
        f"⚡ Key 6H: `{len(kho_key_6h)}`", 
        parse_mode="Markdown"
    )

async def cmd_rangex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cú pháp: /rangex <1h|3h|6h> <số_lượng>"""
    if update.message.from_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Cú pháp: `/rangex <1h|3h|6h> <số_lượng>`\nVí dụ: `/rangex 6h 20`", parse_mode="Markdown")
        return
    
    kho_loai = context.args[0].lower()
    try:
        so_luong = int(context.args[1])
    except:
        await update.message.reply_text("❌ Số lượng phải là chữ số hợp lệ.")
        return

    target_list = kho_key_1h if kho_loai == '1h' else (kho_key_3h if kho_loai == '3h' else (kho_key_6h if kho_loai == '6h' else None))
    
    if target_list is None:
        await update.message.reply_text("❌ Loại kho không hợp lệ. Chỉ chọn: `1h`, `3h`, hoặc `6h`.", parse_mode="Markdown")
        return

    for _ in range(so_luong):
        target_list.append(generate_random_key())
    
    await update.message.reply_text(f"✅ Đã tự động tạo và thêm `{so_luong}` Key vào kho **{kho_loai.upper()}** thành công!", parse_mode="Markdown")

# ==========================================
# 10. FLASK SERVER & KHỞI CHẠY
# ==========================================
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is running perfectly!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

def main():
    # Khởi chạy luồng Flask ngầm phục vụ Render
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers cốt lõi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("kho", cmd_kho))
    app.add_handler(CommandHandler("rangex", cmd_rangex))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    
    logger.info("Bot đang khởi động hệ thống...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()