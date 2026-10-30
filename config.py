# config.py
import os

# ==================== BOT ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9120368691:AAE9J5NtmXqYBPiKmC7pJq_UKmjwlwny2sw")
BOT_USERNAME = "GetkeyMizzebot"          # Không có @
ADMIN_ID = 7976468365                     # ID Telegram của bạn

# ==================== GIAO DIỆN ====================
BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/lebind"
SUPPORT_CONTACT = "https://t.me/NTH_VIP"

# ==================== API RÚT GỌN LINK ====================
LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")
YEUMONEY_API_KEY = os.environ.get("YEUMONEY_API_KEY", "316b5434e78e4ffe8475d87e407754f0ab92a4b85055a7ecd19c86a196cd702a")
SHRINKME_API_KEY = os.environ.get("SHRINKME_API_KEY", "cbf0c1f1343fbb4755913212000f0ad1178e3a46")

# ==================== NGÂN HÀNG & SEPAY ====================
BANK_ID = "VPBANK"
ACCOUNT_NO = "0382570538"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_API_KEY = os.environ.get("SEPAY_API_KEY", "botgetkey_sepay")

# ==================== GIÁ BÁN ====================
PRICE_SHOP_1H = 10000
PRICE_SHOP_12H = 20000
PRICE_SHOP_1D = 70000
PRICE_SHOP_1M = 150000

# ==================== GIỚI HẠN ====================
DAILY_FREE_LIMIT = 3          # Số lần lấy key free tối đa mỗi ngày