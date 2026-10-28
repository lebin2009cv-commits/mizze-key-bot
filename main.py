import os
import logging
import threading
from urllib.parse import quote
import httpx
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CẤU HÌNH ---
# Lấy các biến môi trường từ Render (hoặc file .env nếu chạy local)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9120368691:AAE9J5NtmXqYBPiKmC7pJq_UKmjwlwny2sw")
LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")

# Cấu hình logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. HÀM XỬ LÝ LINK4M (Dùng Async) ---
async def shorten_link_async(long_url: str) -> str:
    """Gọi API Link4m bất đồng bộ để không làm treo Bot."""
    api_endpoint = "https://link4m.co/api-shorten/v2"
    encoded_url = quote(long_url, safe='')
    full_api_url = f"{api_endpoint}?api={LINK4M_API_KEY}&url={encoded_url}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(full_api_url, timeout=15.0)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data.get("shortenedUrl")
            else:
                logger.error(f"Link4m báo lỗi: {data.get('message', 'Không rõ nguyên nhân')}")
                return None
    except Exception as e:
        logger.error(f"Lỗi kết nối tới Link4m: {e}")
        return None

# --- 2. CÁC LỆNH CỦA TELEGRAM BOT ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start"""
    welcome_text = (
        "👋 Chào bạn! Mình là Bot rút gọn link.\n\n"
        "Để rút gọn link, hãy sử dụng cú pháp:\n"
        "👉 `/shorten <link_can_rut_gon>`\n\n"
        "Ví dụ: `/shorten https://google.com`"
    )
    await update.message.reply_text(welcome_text)

async def shorten_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /shorten <url>"""
    # Kiểm tra xem người dùng có nhập link không
    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập link cần rút gọn.\nVí dụ: `/shorten https://google.com`")
        return

    original_url = context.args[0]
    
    # Kiểm tra sơ bộ định dạng link
    if not original_url.startswith(("http://", "https://")):
        await update.message.reply_text("⚠️ Link không hợp lệ. Link phải bắt đầu bằng http:// hoặc https://")
        return

    msg = await update.message.reply_text("⏳ Đang tạo link rút gọn, vui lòng chờ...")

    # Gọi hàm rút gọn link
    short_url = await shorten_link_async(original_url)

    if short_url:
        await msg.edit_text(f"✅ Rút gọn thành công!\n\n🔗 Link của bạn: {short_url}")
    else:
        await msg.edit_text("❌ Không tạo được link Link4m. Vui lòng thử lại sau hoặc kiểm tra lại API Key.")

# --- 3. CẤU HÌNH FLASK ĐỂ GIỮ RENDER LUÔN CHẠY ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    # Chạy Flask ở port 10000 (Render mặc định) hoặc port do Render cấp
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# --- 4. HÀM MAIN KHỞI CHẠY BOT ---
def main():
    # Chạy Flask trên một luồng (thread) riêng để không chặn Bot
    threading.Thread(target=run_flask, daemon=True).start()

    # Khởi tạo Bot
    application = Application.builder().token(BOT_TOKEN).build()

    # Đăng ký các lệnh
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("shorten", shorten_command))

    # Bắt đầu chạy Bot
    logger.info("Bot đang khởi động...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()