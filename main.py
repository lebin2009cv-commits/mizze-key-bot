import os
import logging
import threading
import httpx
from urllib.parse import quote
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

# ==========================================
# 1. CẤU HÌNH (Bạn có thể sửa trực tiếp ở đây)
# ==========================================
# Lấy Token và API Key từ biến môi trường trên Render
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9120368691:AAE9J5NtmXqYBPiKmC7pJq_UKmjwlwny2sw")
LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")

# ⚠️ QUAN TRỌNG: SỬA 2 DÒNG DƯỚI ĐÂY
BOT_USERNAME = "GetkeyMizze_bot" # Tên bot của bạn (GetkeyMizze_bot)
ADMIN_ID = 7976468365             # ID Telegram của bạn (7976468365)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 2. CƠ SỞ DỮ LIỆU TẠM THỜI (Lưu trên RAM)
# ==========================================
kho_key = []      # Nơi chứa key
user_states = {}  # Lưu tiến trình vượt link: {user_id: 0, 1, 2}

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
            else:
                logger.error(f"Link4m báo lỗi: {data.get('message')}")
                return None
    except Exception as e:
        logger.error(f"Lỗi kết nối Link4m: {e}")
        return None

# ==========================================
# 4. GIAO DIỆN & XỬ LÝ CHÍNH
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        user_states[user_id] = 0

    # Bắt tín hiệu khi người dùng vượt link xong và quay lại bot
    if context.args:
        step = context.args[0]
        if step == "step1":
            user_states[user_id] = 1
            await update.message.reply_text("✅ Đã xong link 1/2.\nBấm 'Lấy Key' để tiếp tục vượt link 2.")
        elif step == "step2":
            user_states[user_id] = 2
            await update.message.reply_text("✅ Đã xong link 2/2.\nBấm 'Lấy Key' để nhận phần thưởng!")

    keyboard = [
        [InlineKeyboardButton("🔑 Lấy Key", callback_data='get_key')],
        [InlineKeyboardButton("📦 Kho Key", callback_data='warehouse')],
        [InlineKeyboardButton("📊 Thống kê", callback_data='stats')],
        [InlineKeyboardButton("➕ Thêm Key (Admin)", callback_data='add_key')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "👋 Chào bạn! Vượt 2 link để nhận 1 Key."
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id, 0)

    if query.data == 'get_key':
        if state == 0:
            await query.message.edit_text("⏳ Đang tạo link vượt (1/2)...")
            target_url = f"https://t.me/{BOT_USERNAME}?start=step1"
            short_url = await shorten_link_async(target_url)
            
            if short_url:
                keyboard = [[InlineKeyboardButton("🔗 Vượt Link 1/2", url=short_url)]]
                await query.message.edit_text("Bấm nút dưới để vượt Link 1:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.edit_text("❌ Lỗi tạo link Link4m. Thử lại sau.")

        elif state == 1:
            await query.message.edit_text("⏳ Đang tạo link vượt (2/2)...")
            target_url = f"https://t.me/{BOT_USERNAME}?start=step2"
            short_url = await shorten_link_async(target_url)
            
            if short_url:
                keyboard = [[InlineKeyboardButton("🔗 Vượt Link 2/2", url=short_url)]]
                await query.message.edit_text("Sắp xong rồi! Bấm nút dưới để vượt Link 2:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.edit_text("❌ Lỗi tạo link Link4m. Thử lại sau.")

        elif state >= 2:
            if not kho_key:
                await query.message.edit_text("📦 Kho Key đã hết sạch! Vui lòng báo Admin.")
                return
            
            key_nhan_duoc = kho_key.pop(0)
            user_states[user_id] = 0 # Reset trạng thái
            await query.message.edit_text(f"🎁 Chúc mừng! Bạn đã vượt thành công.\n\nKey của bạn là:\n`{key_nhan_duoc}`", parse_mode="Markdown")

    elif query.data == 'warehouse':
        await query.message.edit_text(f"📦 Trong kho hiện còn {len(kho_key)} key.")

    elif query.data == 'stats':
        await query.message.edit_text(f"📊 Thống kê:\n- Key còn lại: {len(kho_key)}\n- Tiến trình của bạn: Bước {state}/2")

    elif query.data == 'add_key':
        if user_id != ADMIN_ID:
            await query.message.edit_text("⚠️ Bạn không phải Admin!")
            return
        await query.message.edit_text("📝 Hãy gửi danh sách key (mỗi key 1 dòng) vào chat để thêm vào kho.")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi Admin gửi danh sách key"""
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return 
    
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if len(lines) > 0:
        kho_key.extend(lines)
        await update.message.reply_text(f"✅ Đã thêm {len(lines)} key vào kho!")

# ==========================================
# 5. CẤU HÌNH FLASK (Giữ Render chạy 24/7)
# ==========================================
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# ==========================================
# 6. KHỞI CHẠY
# ==========================================
def main():
    # Chạy Flask ngầm
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Khởi chạy Bot
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    
    logger.info("Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()