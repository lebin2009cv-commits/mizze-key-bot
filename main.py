# main.py
import os
import logging
import threading
import asyncio
from flask import Flask, request, jsonify
import httpx
import re

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import BOT_TOKEN, SEPAY_API_KEY, ADMIN_ID
from database import init_db, update_balance
from handlers import start, button_handler, handle_admin_text

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== FLASK + SEPAY WEBHOOK ====================
flask_app = Flask(__name__)


@flask_app.route('/')
def health_check():
    return "Bot is running!", 200


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

        async def process_deposit():
            await update_balance(target_id, amount, "deposit", "SePay Auto")
            try:
                msg = (
                    f"✅ <b>NẠP TIỀN THÀNH CÔNG!</b>\n"
                    f"Số tiền: <b>+{amount:,}đ</b>"
                )
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": target_id, "text": msg, "parse_mode": "HTML"}
                    )
            except Exception as e:
                logger.error(f"Lỗi gửi tin nhắn webhook: {e}")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_deposit())
            loop.close()
        except Exception as e:
            logger.error(f"Lỗi xử lý deposit: {e}")

    return jsonify({"success": True}), 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)


# ==================== ERROR HANDLER ====================
async def error_handler(update, context):
    logger.error("Exception while handling an update:", exc_info=context.error)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Đã xảy ra lỗi hệ thống. Admin đã được thông báo.")
        except:
            pass


# ==================== MAIN ====================
async def post_init(application):
    await init_db()
    logger.info("✅ Database initialized")


def main():
    # Chạy Flask song song
    threading.Thread(target=run_flask, daemon=True).start()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    app.add_error_handler(error_handler)

    logger.info("Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()