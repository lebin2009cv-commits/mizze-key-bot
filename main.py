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

# 1. CẤU HÌNH (BẠN CẦN SỬA 4 DÒNG DƯỚI ĐÂY)

# ==========================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFbhh-nluyw0QkW8nDSH9hW_qOzxfukKD4")
LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")

# ⚠️ QUAN TRỌNG: SỬA 2 DÒNG DƯỚI ĐÂY
BOT_USERNAME = "GetkeyMizze_bot" # Tên bot của bạn (GetkeyMizzebot)
ADMIN_ID = 7976468365              # ID Telegram của bạn (7976468365)



# Cấu hình hệ thống

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

logger = logging.getLogger(__name__)



# ==========================================

# 2. CƠ SỞ DỮ LIỆU TẠM THỜI (RAM)

# ==========================================

kho_key_1h = []

kho_key_3h = []

kho_key_6h = []



user_states = {} # Lưu tiến trình vượt link

cooldowns = {} # Lưu thời gian chờ (1h, 3h, 6h)

admin_adding_state = {} # Lưu trạng thái Admin đang thao tác

all_users = set() # Lưu ID người dùng để Broadcast

bot_status = {"active": True}



# ==========================================

# 3. CÁC HÀM HỖ TRỢ (LINK4M & RANDOM)

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



def generate_token():

"""Tạo mã xác thực ngẫu nhiên để chống gian lận (VD: a8f9c2)"""

return secrets.token_hex(4)



def generate_random_key(key_len=15):

alphabet = string.ascii_uppercase + string.digits

key = ''.join(secrets.choice(alphabet) for _ in range(key_len))

password = ''.join(secrets.choice(alphabet) for _ in range(key_len))

return f"🔑 <b>Key:</b> <code>{key}</code>\n🔒 <b>Pass:</b> <span class='tg-spoiler'>{password}</span>"



def check_cooldown(user_id, key_type):

if user_id not in cooldowns or key_type not in cooldowns[user_id]:

return True, 0

expire_time = cooldowns[user_id][key_type]

now = time.time()

if now < expire_time:

remaining = int(expire_time - now)

hours = remaining // 3600

minutes = (remaining % 3600) // 60

return False, f"{hours}h {minutes}p"

return True, 0



def set_cooldown(user_id, key_type):

if user_id not in cooldowns: cooldowns[user_id] = {}

if key_type == '1h': cooldowns[user_id]['1h'] = time.time() + 3600

elif key_type == '3h': cooldowns[user_id]['3h'] = time.time() + 10800

elif key_type == '6h': cooldowns[user_id]['6h'] = time.time() + 21600



async def broadcast(context, text):

success = 0

for uid in list(all_users):

try:

await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")

success += 1

await asyncio.sleep(0.05)

except Exception:

pass

return success



async def check_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:

user_id = update.effective_user.id if update.effective_user else 0

if not bot_status["active"] and user_id != ADMIN_ID:

text = (

"🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ</b> 🚧\n"

"━━━━━━━━━━━━━━━━━━━━\n"

"⏳ Admin đang nâng cấp máy chủ để phục vụ bạn tốt hơn.\n"

"🔄 Vui lòng quay lại sau ít phút!\n"

"💌 <i>Xin lỗi vì sự bất tiện này.</i>"

)

if update.message: await update.message.reply_text(text, parse_mode="HTML")

elif update.callback_query:

await update.callback_query.answer("🛠️ Hệ thống đang bảo trì!", show_alert=True)

await update.callback_query.message.edit_text(text, parse_mode="HTML")

return False

return True



# ==========================================

# 4. GIAO DIỆN NGƯỜI DÙNG (HTML UI)

# ==========================================

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

if not await check_maintenance(update, context): return



keyboard = [

[InlineKeyboardButton("🔑 KEY 1H (2 LINK)", callback_data='get_1h')],

[InlineKeyboardButton("💎 KEY 3H (3 LINK)", callback_data='get_3h')],

[InlineKeyboardButton("👑 KEY 6H (6 LINK)", callback_data='get_6h')],

[InlineKeyboardButton("📦 KHO KEY", callback_data='view_kho'),

InlineKeyboardButton("📊 TÌNH TRẠNG", callback_data='check_status')],

[InlineKeyboardButton("🛡️ ADMIN PANEL", callback_data='admin_panel')]

]



text = (

"✨ <b>WELCOME TO GET KEY BOT</b> ✨\n"

"▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"

"⚡ <b>Hệ thống lấy key tự động tốc độ cao</b>\n"

"🛡 <b>Bảo mật:</b> Anti-Spam & Anti-Cheat (Token)\n"

"🚀 <b>Trạng thái:</b> 🟢 Hoạt động ổn định\n"

"▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n\n"

"👇 <i>Vui lòng chọn loại Key bạn muốn sở hữu:</i>"

)



reply_markup = InlineKeyboardMarkup(keyboard)

if update.message: await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

elif update.callback_query: await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

if not await check_maintenance(update, context): return



user_id = update.effective_user.id

all_users.add(user_id)



if user_id not in user_states:

user_states[user_id] = {'type': None, 'step': 0, 'token': None}



if context.args:

arg = context.args[0]

try:

# Cấu trúc link: 1h_step2_a8f9c2

parts = arg.split("_")

key_type = parts[0]

step_num = int(parts[1].replace("step", ""))

received_token = parts[2] if len(parts) > 2 else None



current_state = user_states[user_id]



# KIỂM TRA TOKEN CHỐNG GIAN LẬN

if current_state['type'] == key_type and current_state['step'] == step_num - 1:

if received_token != current_state['token']:

await update.message.reply_text(

"⚠️ <b>PHÁT HIỆN GIAN LẬN!</b>\n"

"Mã xác thực (Token) không hợp lệ hoặc đã bị sửa.\n"

"Vui lòng bấm /start và làm lại từ đầu.",

parse_mode="HTML"

)

user_states[user_id] = {'type': None, 'step': 0, 'token': None}

return



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

except Exception as e:

logger.error(f"Lỗi Deep Link: {e}")

pass

await show_main_menu(update, context)



async def handle_step(update, key_type, current_step, total_steps):

new_token = generate_token()

user_states[update.effective_user.id]['token'] = new_token



short_url = await shorten_link_async(f"https://t.me/{BOT_USERNAME}?start={key_type}_step{current_step}_{new_token}")

if short_url:

keyboard = [[InlineKeyboardButton(f"🚀 VƯỢT LINK {current_step}/{total_steps}", url=short_url)]]

text = (

"🔄 <b>ĐANG XỬ LÝ...</b>\n"

f"Tiến trình: <b>{current_step}/{total_steps}</b>\n"

"👉 Bấm nút bên dưới để vượt link và tiếp tục."

)

await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")



async def deliver_key(update: Update, context: ContextTypes.DEFAULT_TYPE, key_type: str, kho: list):

user_id = update.effective_user.id

if not kho:

await update.message.reply_text(f"❌ <b>RẤT TIẾC!</b>\nKho Key {key_type.upper()} đã cạn. Vui lòng báo Admin!", parse_mode="HTML")

user_states[user_id] = {'type': None, 'step': 0, 'token': None}

return



key_nhan = kho.pop(0)

set_cooldown(user_id, key_type)

user_states[user_id] = {'type': None, 'step': 0, 'token': None}



text = (

"🎉 <b>CHÚC MỪNG BẠN ĐÃ VƯỢT LINK THÀNH CÔNG!</b> 🎉\n"

"▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"

f"{key_nhan}\n"

"▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"

f"⏳ <i>Bạn cần chờ <b>{key_type.upper()}</b> để lấy key tiếp theo.</i>\n"

"💡 <i>(Chạm vào mật khẩu để xem)</i>"

)

await update.message.reply_text(text, parse_mode="HTML")



# ==========================================

# 5. XỬ LÝ NÚT BẤM (CALLBACK)

# ==========================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

query = update.callback_query

user_id = query.from_user.id

await query.answer()



if not await check_maintenance(update, context): return



if user_id not in user_states:

user_states[user_id] = {'type': None, 'step': 0, 'token': None}



# --- MENU NGƯỜI DÙNG ---

if query.data.startswith('get_'):

key_type = query.data.split('_')[1]

can_get, time_left = check_cooldown(user_id, key_type)

if not can_get:

await query.message.edit_text(

f"🚫 <b>BẠN ĐANG TRONG THỜI GIAN CHỜ!</b>\n\n"

f"Vui lòng quay lại sau: <b>{time_left}</b>",

parse_mode="HTML"

)

return



initial_token = generate_token()

user_states[user_id] = {'type': key_type, 'step': 0, 'token': initial_token}



target_url = f"https://t.me/{BOT_USERNAME}?start={key_type}_step1_{initial_token}"

short_url = await shorten_link_async(target_url)



if short_url:

total = "2" if key_type == "1h" else "3" if key_type == "3h" else "6"

keyboard = [[InlineKeyboardButton(f"🚀 VƯỢT LINK 1/{total}", url=short_url)]]

await query.message.edit_text(

f"🔄 <b>TIẾN TRÌNH: 1/{total}</b>\n\nVui lòng bấm nút bên dưới để vượt link.",

reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"

)



elif query.data == 'view_kho':

text = (

"📦 <b>KHO KEY HIỆN TẠI</b> 📦\n"

"▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"

f"🕒 Key 1H: <code>{len(kho_key_1h)}</code>\n"

f"💎 Key 3H: <code>{len(kho_key_3h)}</code>\n"

f"👑 Key 6H: <code>{len(kho_key_6h)}</code>\n"

"▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"

"<i>Số lượng key sẽ được cập nhật liên tục.</i>"

)

keyboard = [[InlineKeyboardButton("⬅️ QUAY LẠI", callback_data='back_menu')]]

await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")



elif query.data == 'check_status':

text = "📊 <b>TRẠNG THÁI COOLDOWN</b> 📊\n▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"

for kt in ['1h', '3h', '6h']:

can_get, time_left = check_cooldown(user_id, kt)

if can_get: text += f"✅ Key {kt.upper()}: <b>Sẵn sàng</b>\n"

else: text += f"⏳ Key {kt.upper()}: Chờ <b>{time_left}</b>\n"



keyboard = [[InlineKeyboardButton("⬅️ QUAY LẠI", callback_data='back_menu')]]

await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")



elif query.data == 'back_menu':

await show_main_menu(update, context)



# --- MENU ADMIN ---

elif query.data == 'admin_panel':

if user_id != ADMIN_ID: return

status_text = "🟢 ONLINE" if bot_status["active"] else "🔴 MAINTENANCE"

keyboard = [

[InlineKeyboardButton(f"⚙️ BOT: {status_text} (Bấm để đổi)", callback_data='admin_toggle')],

[InlineKeyboardButton("👥 THỐNG KÊ NGƯỜI DÙNG", callback_data='admin_users')],

[InlineKeyboardButton("➕ THÊM KEY", callback_data='admin_add_menu')],

[InlineKeyboardButton("🗑 XOÁ KEY", callback_data='admin_del_menu')],

[InlineKeyboardButton("🎲 TẠO KEY RANDOM", callback_data='admin_rand_menu')],

[InlineKeyboardButton("📢 GỬI THÔNG BÁO", callback_data='admin_broadcast')],

[InlineKeyboardButton("⬅️ VỀ MENU CHÍNH", callback_data='back_menu')]

]

await query.message.edit_text(

"🛡️ <b>BẢNG ĐIỀU KHIỂN TỐI CAO</b> 🛡️\n▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰",

reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"

)



elif query.data == 'admin_toggle':

if user_id != ADMIN_ID: return

bot_status["active"] = not bot_status["active"]

status_msg = "🟢 BẬT (Hoạt động)" if bot_status["active"] else "🔴 TẮT (Bảo trì)"

await query.answer(f"Đã chuyển trạng thái: {status_msg}!", show_alert=True)

await button_handler(update, context)



elif query.data == 'admin_users':

if user_id != ADMIN_ID: return

total_users = len(all_users)

user_list = list(all_users)[-20:]

ids_text = "\n".join([f"• <code>{uid}</code>" for uid in user_list])

text = (

"👥 <b>THỐNG KÊ NGƯỜI DÙNG</b> 👥\n"

"▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"

f"📈 Tổng số người đã dùng: <b>{total_users}</b>\n\n"

f"<b>20 ID mới nhất:</b>\n{ids_text}"

)

keyboard = [[InlineKeyboardButton("⬅️ QUAY LẠI", callback_data='admin_panel')]]

await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")



elif query.data == 'admin_broadcast':

if user_id != ADMIN_ID: return

admin_adding_state[user_id] = 'broadcast'

await query.message.edit_text("📢 Nhập nội dung thông báo gửi đến toàn bộ người dùng (Hỗ trợ HTML):")



# MENU CON ADMIN

elif query.data == 'admin_add_menu':

if user_id != ADMIN_ID: return

keyboard = [

[InlineKeyboardButton("Thêm Kho 1H", callback_data='add_key_1h')],

[InlineKeyboardButton("Thêm Kho 3H", callback_data='add_key_3h')],

[InlineKeyboardButton("Thêm Kho 6H", callback_data='add_key_6h')],

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

await query.message.edit_text(f"📝 Hãy dán danh sách Key {k_type.upper()} vào chat:")

elif action == 'del':

admin_adding_state[user_id] = f'del_{k_type}'

await query.message.edit_text(f"🗑 Hãy dán <b>Key hoặc Mật khẩu</b> muốn xoá khỏi kho {k_type.upper()}:", parse_mode="HTML")

elif action == 'rand':

admin_adding_state[user_id] = f'rand_{k_type}'

await query.message.edit_text(f"🎲 Nhập <b>số lượng</b> Key {k_type.upper()} muốn tạo (VD: 10):", parse_mode="HTML")



# ==========================================

# 6. XỬ LÝ TEXT TỪ ADMIN (REGEX TỰ ĐỘNG NHẬN DIỆN)

# ==========================================

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

user_id = update.message.from_user.id

if user_id != ADMIN_ID or user_id not in admin_adding_state:

return



state = admin_adding_state[user_id]

text = update.message.text



# 1. Broadcast

if state == 'broadcast':

await update.message.reply_text("⏳ Đang gửi thông báo...")

success = await broadcast(context, f"📢 <b>THÔNG BÁO TỪ ADMIN</b>\n\n{text}")

await update.message.reply_text(f"✅ Đã gửi thành công đến {success} người dùng.")

del admin_adding_state[user_id]

return



action, k_type = state.split('_')

target_list = kho_key_1h if k_type == '1h' else kho_key_3h if k_type == '3h' else kho_key_6h



# 2. Thêm Key (Tự động Regex bắt Key/Pass bất chấp văn bản rác)

if action == 'add':

matches = re.findall(r"Key:\s*([^\n]+)\s*\n.*?Mật khẩu:\s*([^\n]+)", text, re.IGNORECASE)



added_count = 0

if matches:

for k, p in matches:

safe_key = html.escape(k.strip())

safe_pass = html.escape(p.strip())

formatted_key = f"🔑 <b>Key:</b> <code>{safe_key}</code>\n🔒 <b>Pass:</b> <span class='tg-spoiler'>{safe_pass}</span>"

target_list.append(formatted_key)

added_count += 1

else:

blocks = text.split('\n\n')

for block in blocks:

if block.strip():

target_list.append(html.escape(block.strip()))

added_count += 1



if added_count > 0:

await update.message.reply_text(f"✅ Đã tự động trích xuất và thêm <b>{added_count}</b> Key vào kho <b>{k_type.upper()}</b>!", parse_mode="HTML")

await broadcast(context, f"🎉 <b>CẬP NHẬT KHO KEY {k_type.upper()}!</b>\n\nAdmin vừa thêm <b>{added_count}</b> key mới. Nhanh tay vào lấy nhé! 🏃‍♂️💨")

else:

await update.message.reply_text("❌ Không tìm thấy Key hợp lệ. Vui lòng kiểm tra lại định dạng.", parse_mode="HTML")



del admin_adding_state[user_id]



# 3. Xoá Key

elif action == 'del':

found = False

for i, k in enumerate(target_list):

if text.strip() in k:

target_list.pop(i)

found = True

break

if found: await update.message.reply_text(f"✅ Đã xoá Key thành công khỏi kho {k_type.upper()}.", parse_mode="HTML")

else: await update.message.reply_text("❌ Không tìm thấy Key này.", parse_mode="HTML")

del admin_adding_state[user_id]



# 4. Tạo Random

elif action == 'rand':

try:

so_luong = int(text.strip())

for _ in range(so_luong):

target_list.append(generate_random_key())

await update.message.reply_text(f"✅ Đã tạo tự động {so_luong} Key vào kho {k_type.upper()}!", parse_mode="HTML")

except ValueError:

await update.message.reply_text("❌ Vui lòng chỉ nhập số.", parse_mode="HTML")

del admin_adding_state[user_id]



# ==========================================

# 7. KHỞI CHẠY

# ==========================================

flask_app = Flask(__name__)

@flask_app.route('/')

def health_check(): return "Bot is running!", 200

def run_flask():

flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))



def main():

threading.Thread(target=run_flask, daemon=True).start()

app = Application.builder().token(BOT_TOKEN).build()



app.add_handler(CommandHandler("start", start))

app.add_handler(CallbackQueryHandler(button_handler))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))



logger.info("Bot đang chạy...")

app.run_polling(drop_pending_updates=True)



if __name__ == '__main__':

main()