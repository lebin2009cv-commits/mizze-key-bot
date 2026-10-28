import os
import threading
from flask import Flask
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

from config import BOT_TOKEN, KEYS_FILE
from database import load_keys
from handlers import start, upkey, listkey, menu_handler, receive_keys

# ================== FLASK SERVER ==================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is alive!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

# ================== MAIN ==================
def main():
    if not os.path.exists(KEYS_FILE):
        open(KEYS_FILE, "w").close()

    # Chạy Flask ở luồng phụ (cho Render)
    threading.Thread(target=run_web, daemon=True).start()

    # Khởi tạo Telegram Bot
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("upkey", upkey))
    application.add_handler(CommandHandler("listkey", listkey))
    application.add_handler(CallbackQueryHandler(menu_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_keys))

    print("🤖 Bot đang chạy...")
    application.run_polling()

if __name__ == "__main__":
    main()