import os
import time
from datetime import datetime
from config import KEYS_FILE, COOLDOWN_GETKEY, MAX_KEY_PER_DAY, ADMIN_IDS

# Bộ nhớ tạm
pending = {}
user_keys = {}
user_cooldown = {}
user_daily = {}

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return []
    with open(KEYS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def save_keys(keys):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        for k in keys:
            f.write(k + "\n")

def get_one_key():
    keys = load_keys()
    if not keys:
        return None
    key = keys.pop(0)
    save_keys(keys)
    return key

def add_keys(new_keys):
    keys = load_keys()
    keys.extend(new_keys)
    save_keys(keys)
    return len(new_keys)

def count_keys():
    return len(load_keys())

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def save_user_key(user_id, key, days=1):
    expire = time.time() + days * 86400
    user_keys[user_id] = {"key": key, "expire": expire}

def get_user_key(user_id):
    data = user_keys.get(user_id)
    if not data:
        return None
    if time.time() > data["expire"]:
        del user_keys[user_id]
        return None
    return data

def can_get_key(user_id: int):
    now = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    last = user_cooldown.get(user_id, 0)
    if now - last < COOLDOWN_GETKEY:
        remain = int(COOLDOWN_GETKEY - (now - last))
        return False, f"⏳ Vui lòng chờ {remain} giây nữa mới được lấy key tiếp."

    daily = user_daily.get(user_id, {"count": 0, "date": today})
    if daily["date"] != today:
        daily = {"count": 0, "date": today}
        user_daily[user_id] = daily

    if daily["count"] >= MAX_KEY_PER_DAY:
        return False, f"❌ Bạn đã lấy đủ {MAX_KEY_PER_DAY} key hôm nay. Mai hãy quay lại."

    return True, ""

def increase_daily(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    daily = user_daily.get(user_id, {"count": 0, "date": today})
    if daily["date"] != today:
        daily = {"count": 0, "date": today}
    daily["count"] += 1
    user_daily[user_id] = daily
    user_cooldown[user_id] = time.time()