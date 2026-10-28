import uuid
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import MIN_TIME_BETWEEN_STEPS
from utils import create_link4m
from database import (
    pending, user_keys, is_admin, load_keys, get_one_key, 
    add_keys, count_keys, save_user_key, get_user_key, 
    can_get_key, increase_daily
)

# ================== MENU ==================
def main_menu(user_id: int):
    keyboard = [
        [InlineKeyboardButton("🔑 Lấy Key", callback_data="menu_getkey")],
        [
            InlineKeyboardButton("🔍 Kiểm tra Key", callback_data="menu_checkkey"),
            InlineKeyboardButton("🔗 Kiểm tra Link", callback_data="menu_checklink")
        ],
        [
            InlineKeyboardButton("⏰ Thời gian", callback_data="menu_time"),
            InlineKeyboardButton("🗑️ Xóa Key", callback_data="menu_delkey")
        ],
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="menu_admin")])
    return InlineKeyboardMarkup(keyboard)

def admin_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Thêm Key", callback_data="admin_addkey")],
        [InlineKeyboardButton("📦 Kho Key", callback_data="admin_stock")],
        [InlineKeyboardButton("📊 Thống kê", callback_data="admin_stats")],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"Xin chào <b>{user.first_name}</b>!\n\n"
        f"Chào mừng bạn đến với hệ thống lấy Key tự động.\n"
        f"Chọn chức năng bên dưới:"
    )
    await update.message.reply_text(text, reply_markup=main_menu(user.id), parse_mode="HTML")

# ================== CALLBACK ==================
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "menu_back":
        await query.edit_message_text("Chọn chức năng:", reply_markup=main_menu(user_id))
        return

    if data == "menu_getkey":
        ok, msg = can_get_key(user_id)
        if not ok:
            await query.edit_message_text(msg, reply_markup=main_menu(user_id))
            return
        await start_getkey(query, user_id)
        return

    if data == "menu_checkkey":
        info = get_user_key(user_id)
        if info:
            remain = int((info["expire"] - time.time()) / 3600)
            text = f"🔑 <b>Key của bạn:</b>\n<code>{info['key']}</code>\n\n⏰ Còn lại khoảng <b>{remain} giờ</b>"
        else:
            text = "❌ Bạn chưa có key hoặc key đã hết hạn."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_checklink":
        if user_id in pending:
            text = f"🔗 Bạn đang vượt link\nBước hiện tại: <b>{pending[user_id]['step']}/2</b>"
        else:
            text = "❌ Bạn chưa có phiên vượt link."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_time":
        info = get_user_key(user_id)
        if info:
            expire_str = datetime.fromtimestamp(info["expire"]).strftime("%H:%M %d/%m/%Y")
            text = f"⏰ Key hết hạn lúc:\n<b>{expire_str}</b>"
        else:
            text = "❌ Bạn chưa có key."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_delkey":
        if user_id in user_keys:
            del user_keys[user_id]
            text = "✅ Đã xóa key của bạn."
        else:
            text = "❌ Bạn không có key để xóa."
        await query.edit_message_text(text, reply_markup=main_menu(user_id), parse_mode="HTML")
        return

    if data == "menu_admin":
        if not is_admin(user_id):
            await query.answer("Không có quyền!", show_alert=True)
            return
        await query.edit_message_text("👑 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")
        return

    if data == "admin_stock":
        keys = load_keys()
        text = f"📦 Hiện còn <b>{len(keys)}</b> key."
        if keys:
            text += "\n\n" + "\n".join(f"<code>{k}</code>" for k in keys[:8])
        await query.edit_message_text(text, reply_markup=admin_menu(), parse_mode="HTML")
        return

    if data == "admin_stats":
        text = (
            f"📊 <b>Thống kê</b>\n\n"
            f"• Key trong kho: <b>{count_keys()}</b>\n"
            f"• User đang có key: <b>{len(user_keys)}</b>\n"
            f"• Phiên đang vượt: <b>{len(pending)}</b>"
        )
        await query.edit_message_text(text, reply_markup=admin_menu(), parse_mode="HTML")
        return

    if data == "admin_addkey":
        await query.edit_message_text(
            "Gửi danh sách key (mỗi key 1 dòng)\nhoặc dùng lệnh:\n<code>/upkey KEY1 KEY2</code>",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )
        return

    if data.startswith("step1_"):
        await handle_step1(query, user_id, data)
        return

    if data.startswith("step2_"):
        await handle_step2(query, user_id, data)
        return

# ================== LẤY KEY ==================
async def start_getkey(query, user_id):
    code1 = str(uuid.uuid4())[:8]
    code2 = str(uuid.uuid4())[:8]

    dest1 = f"https://example.com/ok1?c={code1}"
    dest2 = f"https://example.com/ok2?c={code2}"

    link1 = create_link4m(dest1)
    link2 = create_link4m(dest2)

    if not link1 or not link2:
        await query.edit_message_text("❌ Không tạo được link Link4m. Thử lại sau.")
        return

    pending[user_id] = {
        "step": 1,
        "code1": code1,
        "code2": code2,
        "link1": link1,
        "link2": link2,
        "time": time.time(),
        "step1_time": None
    }

    keyboard = [[InlineKeyboardButton("✅ Tôi đã vượt lần 1", callback_data=f"step1_{code1}")]]
    await query.edit_message_text(
        f"🔗 <b>Bước 1/2</b>\n\nVượt link sau:\n{link1}\n\n"
        f"⚠️ Phải vượt thật + chờ đủ thời gian mới được nhấn nút.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def handle_step1(query, user_id, data):
    if user_id not in pending:
        await query.edit_message_text("❌ Phiên hết hạn.")
        return
    info = pending[user_id]
    code = data.replace("step1_", "")
    if info["code1"] != code or info["step"] != 1:
        await query.edit_message_text("❌ Mã không hợp lệ.")
        return

    info["step"] = 2
    info["step1_time"] = time.time()

    keyboard = [[InlineKeyboardButton("✅ Tôi đã vượt lần 2", callback_data=f"step2_{info['code2']}")]]
    await query.edit_message_text(
        f"✅ Đã vượt lần 1!\n\n🔗 <b>Bước 2/2</b>\n\nVượt link sau:\n{info['link2']}\n\n"
        f"⚠️ Phải chờ ít nhất {MIN_TIME_BETWEEN_STEPS} giây sau khi vượt lần 1.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def handle_step2(query, user_id, data):
    if user_id not in pending:
        await query.edit_message_text("❌ Phiên hết hạn.")
        return
    info = pending[user_id]
    code = data.replace("step2_", "")
    if info["code2"] != code or info["step"] != 2:
        await query.edit_message_text("❌ Mã không hợp lệ.")
        return

    if info.get("step1_time"):
        elapsed = time.time() - info["step1_time"]
        if elapsed < MIN_TIME_BETWEEN_STEPS:
            remain = int(MIN_TIME_BETWEEN_STEPS - elapsed)
            await query.answer(f"Vui lòng chờ thêm {remain} giây!", show_alert=True)
            return

    key = get_one_key()
    del pending[user_id]

    if key:
        save_user_key(user_id, key, days=1)
        increase_daily(user_id)
        await query.edit_message_text(
            f"🎉 <b>Thành công!</b>\n\n🔑 Key của bạn:\n<code>{key}</code>\n\n⏰ Thời hạn: <b>1 ngày</b>",
            reply_markup=main_menu(user_id),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text("⚠️ Hiện đã hết key.", reply_markup=main_menu(user_id))

# ================== LỆNH ADMIN ==================
async def upkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Dùng: /upkey KEY1 KEY2 KEY3")
        return
    added = add_keys([k.strip() for k in context.args if k.strip()])
    await update.message.reply_text(f"✅ Đã thêm {added} key.\nHiện còn {count_keys()} key.")

async def listkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    keys = load_keys()
    text = f"📦 Còn {len(keys)} key"
    if keys:
        text += "\n\n" + "\n".join(keys[:15])
    await update.message.reply_text(text)

async def receive_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    lines = [l.strip() for l in update.message.text.split("\n") if l.strip() and len(l.strip()) > 5]
    if lines:
        added = add_keys(lines)
        await update.message.reply_text(f"✅ Đã thêm {added} key. Hiện còn {count_keys()} key.")