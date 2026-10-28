import os
import logging
import threading
import httpx
import re
import secrets
import string
from urllib.parse import quote
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

# ==========================================
# 1. CẤU HÌNH
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9120368691:AAE9J5NtmXqYBPiKmC7pJq_UKmjwlwny2sw")
LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")

# ⚠️ QUAN TRỌNG: SỬA 2 DÒNG DƯỚI ĐÂY
BOT_USERNAME = "GetkeyMizze_bot" # Tên bot của bạn (GetkeyMizze_bot)
ADMIN_ID = 7976468365              # ID Telegram của bạn (7976468365)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 2. CƠ SỞ DỮ LIỆU TẠM THỜI
# ==========================================
kho_key_1h = []   # Chứa key 1 giờ (vượt 2 link)
kho_key_3h = []   # Chứa key 3 giờ (vượt 3 link)

# Lưu trạng thái: {user_id: {'type': '1h' hoặc '3h', 'step': 0, 1, 2, 3}}
user_states = {}  
# Lưu trạng thái Admin đang thêm key vào kho nào: {admin_id: '1h' hoặc '3h'}
admin_adding_state = {} 

# ==========================================
# 3. HÀM TẠO LINK4M
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
# 4. XỬ LÝ TIN NHẮN TỪ ADMIN (DÙNG REGEX)
# ==========================================
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    # Chỉ xử lý nếu là Admin và Admin đang trong trạng thái chờ nhập Key
    if user_id != ADMIN_ID or user_id not in admin_adding_state:
        return 
    
    kho_loai = admin_adding_state[user_id]
    text = update.message.text
    
    # Regex tìm cặp "Key: xxx" và "Mật khẩu: yyy"
    matches = re.findall(r"Key:\s*(.*?)\s*\n.*?Mật khẩu:\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    
    added_count = 0
    if matches:
        for k, p in matches:
            # Gộp lại thành 1 khối định dạng chuẩn
            formatted_key = f"🔑 Key: {k.strip()}\n🔒 Mật khẩu: {p.strip()}"
            if kho_loai == '1h': kho_key_1h.append(formatted_key)
            else: kho_key_3h.append(formatted_key)
            added_count += 1
    else:
        # Fallback: Nếu text không có chữ "Key:" và "Mật khẩu:", chia khối bằng dấu xuống dòng kép
        blocks = text.split('\n\n')
        for block in blocks:
            if block.strip():
                if kho_loai == '1h': kho_key_1h.append(block.strip())
                else: kho_key_3h.append(block.strip())
                added_count += 1
                
    if added_count > 0:
        await update.message.reply_text(f"✅ Đã trích xuất và thêm {added_count} Key vào kho **{kho_loai.upper()}** thành công!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Không tìm thấy Key hợp lệ trong tin nhắn.")
    
    # Xoá trạng thái chờ thêm key
    del admin_adding_state[user_id]

# ==========================================
# 5. HÀM TẠO KEY RANDOM (Dùng cho lệnh /rangex)
# ==========================================
def generate_random_key(key_len=15):
    alphabet = string.ascii_uppercase + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    password = ''.join(secrets.choice(alphabet) for _ in range(key_len))
    return f"🔑 Key: {key}\n🔒 Mật khẩu: {password}"

# ==========================================
# 6. GIAO DIỆN & XỬ LÝ CHÍNH
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        user_states[user_id] = {'type': None, 'step': 0}

    # Bắt tín hiệu vượt link thành công (Deep link)
    if context.args:
        arg = context.args[0] # Ví dụ: "1h_step1" hoặc "3h_step2"
        try:
            key_type, step_str = arg.split("_")
            step_num = int(step_str.replace("step", ""))
            user_states[user_id]['type'] = key_type
            user_states[user_id]['step'] = step_num
            
            if key_type == "1h":
                if step_num == 1: await update.message.reply_text("✅ Đã xong link 1/2. Bấm 'Lấy Key 1H' để tiếp tục.")
                elif step_num == 2: await update.message.reply_text("✅ Đã xong link 2/2. Bấm 'Lấy Key 1H' để nhận thưởng!")
            elif key_type == "3h":
                if step_num == 1: await update.message.reply_text("✅ Đã xong link 1/3. Bấm 'Lấy Key 3H' để tiếp tục.")
                elif step_num == 2: await update.message.reply_text("✅ Đã xong link 2/3. Bấm 'Lấy Key 3H' để tiếp tục.")
                elif step_num == 3: await update.message.reply_text("✅ Đã xong link 3/3. Bấm 'Lấy Key 3H' để nhận thưởng!")
        except Exception:
            pass

    keyboard = [
        [InlineKeyboardButton("🔑 Vượt 2 link - Lấy Key 1H", callback_data='get_1h')],
        [InlineKeyboardButton("🔥 Vượt 3 link - Lấy Key 3H", callback_data='get_3h')],
        [InlineKeyboardButton("📦 Kho Key (Admin)", callback_data='admin_kho')],
        [InlineKeyboardButton("➕ Thêm Key (Admin)", callback_data='admin_add')]
    ]
    text = "👋 Chào bạn! Vui lòng chọn loại Key bạn muốn lấy:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id, {'type': None, 'step': 0})

    # --- XỬ LÝ LẤY KEY 1H ---
    if query.data == 'get_1h':
        if state['type'] != '1h':
            state = {'type': '1h', 'step': 0}
            user_states[user_id] = state

        if state['step'] == 0:
            target_url = f"https://t.me/{BOT_USERNAME}?start=1h_step1"
            short_url = await shorten_link_async(target_url)
            if short_url:
                keyboard = [[InlineKeyboardButton("🔗 Vượt Link 1/2", url=short_url)]]
                await query.message.edit_text("Bấm nút dưới để vượt Link 1:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.edit_text("❌ Lỗi tạo link. Thử lại sau.")
                
        elif state['step'] == 1:
            target_url = f"https://t.me/{BOT_USERNAME}?start=1h_step2"
            short_url = await shorten_link_async(target_url)
            if short_url:
                keyboard = [[InlineKeyboardButton("🔗 Vượt Link 2/2", url=short_url)]]
                await query.message.edit_text("Bấm nút dưới để vượt Link 2:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.edit_text("❌ Lỗi tạo link. Thử lại sau.")
                
        elif state['step'] >= 2:
            if not kho_key_1h:
                await query.message.edit_text("📦 Kho Key 1H đã hết sạch! Vui lòng báo Admin.")
                return
            key_nhan = kho_key_1h.pop(0)
            user_states[user_id] = {'type': None, 'step': 0} # Reset
            await query.message.edit_text(f"🎁 Chúc mừng! Bạn đã vượt thành công.\n\n{key_nhan}", parse_mode="Markdown")

    # --- XỬ LÝ LẤY KEY 3H ---
    elif query.data == 'get_3h':
        if state['type'] != '3h':
            state = {'type': '3h', 'step': 0}
            user_states[user_id] = state

        if state['step'] == 0:
            target_url = f"https://t.me/{BOT_USERNAME}?start=3h_step1"
            short_url = await shorten_link_async(target_url)
            if short_url:
                keyboard = [[InlineKeyboardButton("🔗 Vượt Link 1/3", url=short_url)]]
                await query.message.edit_text("Bấm nút dưới để vượt Link 1:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.edit_text("❌ Lỗi tạo link. Thử lại sau.")
                
        elif state['step'] == 1:
            target_url = f"https://t.me/{BOT_USERNAME}?start=3h_step2"
            short_url = await shorten_link_async(target_url)
            if short_url:
                keyboard = [[InlineKeyboardButton("🔗 Vượt Link 2/3", url=short_url)]]
                await query.message.edit_text("Bấm nút dưới để vượt Link 2:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.edit_text("❌ Lỗi tạo link. Thử lại sau.")
                
        elif state['step'] == 2:
            target_url = f"https://t.me/{BOT_USERNAME}?start=3h_step3"
            short_url = await shorten_link_async(target_url)
            if short_url:
                keyboard = [[InlineKeyboardButton("🔗 Vượt Link 3/3", url=short_url)]]
                await query.message.edit_text("Sắp xong rồi! Bấm nút dưới để vượt Link 3:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.edit_text("❌ Lỗi tạo link. Thử lại sau.")
                
        elif state['step'] >= 3:
            if not kho_key_3h:
                await query.message.edit_text("📦 Kho Key 3H đã hết sạch! Vui lòng báo Admin.")
                return
            key_nhan = kho_key_3h.pop(0)
            user_states[user_id] = {'type': None, 'step': 0} # Reset
            await query.message.edit_text(f"🎁 Chúc mừng! Bạn đã vượt thành công.\n\n{key_nhan}", parse_mode="Markdown")

    # --- ADMIN: XEM KHO ---
    elif query.data == 'admin_kho':
        if user_id != ADMIN_ID: return
        text = f"📦 **THỐNG KÊ KHO KEY**\n\n- Key 1H còn lại: `{len(kho_key_1h)}`\n- Key 3H còn lại: `{len(kho_key_3h)}`"
        await query.message.edit_text(text, parse_mode="Markdown")

    # --- ADMIN: CHỌN KHO ĐỂ THÊM ---
    elif query.data == 'admin_add':
        if user_id != ADMIN_ID: return
        keyboard = [
            [InlineKeyboardButton("Thêm vào kho 1H", callback_data='add_to_1h')],
            [InlineKeyboardButton("Thêm vào kho 3H", callback_data='add_to_3h')],
        ]
        await query.message.edit_text("Bạn muốn thêm Key vào kho nào?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'add_to_1h':
        if user_id != ADMIN_ID: return
        admin_adding_state[user_id] = '1h'
        await query.message.edit_text("📝 Hãy gửi danh sách Key 1H (mỗi key 1 khối) vào chat ngay bây giờ:")

    elif query.data == 'add_to_3h':
        if user_id != ADMIN_ID: return
        admin_adding_state[user_id] = '3h'
        await query.message.edit_text("📝 Hãy gửi danh sách Key 3H (mỗi key 1 khối) vào chat ngay bây giờ:")

# ==========================================
# 7. CÁC LỆNH ADMIN (XEM, XOÁ, RANGEX)
# ==========================================
async def cmd_kho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text(
        f"📦 **KHO KEY HIỆN TẠI**\n\n"
        f"🕒 Key 1H: `{len(kho_key_1h)}`\n"
        f"🔥 Key 3H: `{len(kho_key_3h)}`", 
        parse_mode="Markdown"
    )

async def cmd_xoa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Cú pháp: `/xoa 1h <từ_khoá>` hoặc `/xoa 3h <từ_khoá>`\nVí dụ: `/xoa 1h KEY1`", parse_mode="Markdown")
        return
    
    kho_loai = context.args[0].lower()
    keyword = " ".join(context.args[1:])
    
    global kho_key_1h, kho_key_3h
    target_list = kho_key_1h if kho_loai == '1h' else kho_key_3h if kho_loai == '3h' else None
    
    if not target_list:
        await update.message.reply_text("❌ Sai cú pháp. Chỉ chọn `1h` hoặc `3h`.", parse_mode="Markdown")
        return

    found = False
    for i, k in enumerate(target_list):
        if keyword in k:
            target_list.pop(i)
            found = True
            break
            
    if found:
        await update.message.reply_text(f"✅ Đã xoá key chứa `{keyword}` khỏi kho {kho_loai.upper()}.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Không tìm thấy key nào chứa từ khoá đó.")

async def cmd_rangex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh tự động tạo Key random: /rangex <1h|3h> <số_lượng>"""
    if update.message.from_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Cú pháp: `/rangex <1h|3h> <số_lượng>`\nVí dụ: `/rangex 1h 50` (Tạo 50 key 1H)", parse_mode="Markdown")
        return
    
    kho_loai = context.args[0].lower()
    try:
        so_luong = int(context.args[1])
    except:
        await update.message.reply_text("❌ Số lượng phải là chữ số.")
        return

    if kho_loai == '1h':
        for _ in range(so_luong):
            kho_key_1h.append(generate_random_key())
        await update.message.reply_text(f"✅ Đã tạo và thêm thành công {so_luong} Key vào kho 1H!")
    elif kho_loai == '3h':
        for _ in range(so_luong):
            kho_key_3h.append(generate_random_key())
        await update.message.reply_text(f"✅ Đã tạo và thêm thành công {so_luong} Key vào kho 3H!")
    else:
        await update.message.reply_text("❌ Sai cú pháp. Chỉ chọn `1h` hoặc `3h`.", parse_mode="Markdown")

# ==========================================
# 8. FLASK & KHỞI CHẠY
# ==========================================
flask_app = Flask(__name__)
@flask_app.route('/')
def health_check(): return "Bot is running!", 200
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Lệnh cơ bản
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Các lệnh Admin
    app.add_handler(CommandHandler("kho", cmd_kho))
    app.add_handler(CommandHandler("xoa", cmd_xoa))
    app.add_handler(CommandHandler("rangex", cmd_rangex))
    
    # Bắt text (dành cho Admin thêm key)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    
    logger.info("Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()