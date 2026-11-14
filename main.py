import os, logging, threading, httpx, re, time, html, datetime, json, asyncio
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    BotCommand, CopyTextButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

# ================= CẤU HÌNH HỆ THỐNG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

LOG_GROUP_ID = -1003912025872
CLIENT_GROUP_LINK = "https://t.me/mizze_lebin"
CHANNEL_USERNAME = "@mizze_store"
ADMIN_USERNAME = "@lebindz"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/lebindz"
SUPPORT_CONTACT = "https://t.me/lebindz"

BANK_ID = "VPBank"
ACCOUNT_NO = "AGBSP4LRK4B099"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_KEY = os.environ.get("SEPAY_API_KEY", "botgetkey_sepay")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
DB_FILE = "database.json"

buy_lock = threading.Lock()
admin_state = {}
cooldown_cache = {}
admin_view_mode = {}  # Lưu chế độ xem của Admin: 'member' hoặc 'seller'

# ================= QUẢN LÝ DATABASE =================
def load_data():
    default_data = {
        "users": {}, "user_data": {}, "sellers": {},
        "s_1h": [], "s_1d": [], "s_7d": [], "s_30d": [],
        "prices": {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000},
        "seller_prices": {"1h": 5000, "1d": 15000, "7d": 60000, "30d": 120000},
        "total_rev": 0, "bot_active": True,
        "last_reset_date": datetime.datetime.now().strftime("%Y-%m-%d")
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            logger.error(f"Lỗi đọc database: {e}")
    return default_data

db = load_data()

def save_data():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if db.get("last_reset_date") != today_str:
            expired_sellers = []
            for s_id, s_info in db["sellers"].items():
                rev = s_info.get("daily_rev", 0)
                target = s_info.get("target", 500000)
                if rev < target:
                    expired_sellers.append(s_id)
            db["_expired_sellers_yesterday"] = expired_sellers
            for s_info in db["sellers"].values():
                s_info["daily_rev"] = 0
            db["last_reset_date"] = today_str

        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Lỗi lưu database: {e}")

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {
            'balance': 0,
            'total_deposit': 0,
            'month_deposit': 0,
            'deposit_history': [],
            'buy_history': [],
            'balance_logs': [],
            'my_keys': []
        }
        save_data()
    u = db["user_data"][uid_str]
    for key in ['month_deposit', 'deposit_history', 'buy_history', 'balance_logs', 'my_keys']:
        if key not in u:
            u[key] = 0 if key == 'month_deposit' else []
    return u

def is_admin(uid):
    return uid in admin_list

def is_seller(uid):
    if is_admin(uid):
        return admin_view_mode.get(uid, 'seller') == 'seller'
    return str(uid) in db["sellers"]

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 0.8:
        return True
    if len(cooldown_cache) > 1000:
        cooldown_cache.clear()
    cooldown_cache[uid] = now
    return False

async def edit_or_send(query, text, reply_markup=None):
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        try:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass

# ================= GIAO DIỆN MENU CHÍNH CHUẨN MẪU =================
def build_main_menu_content(uid):
    u = get_u(uid)
    mode_tag = ""
    if is_admin(uid):
        cur_mode = admin_view_mode.get(uid, 'seller').upper()
        mode_tag = f"\n👑 <b>Chế độ Admin:</b> Đang xem kho <code>{cur_mode}</code>"

    text = (
        f"<b>CHÀO MỪNG BẠN ĐẾN VỚI BOT AUTO BÁN KEY VIP</b>\n\n"
        f"<blockquote>"
        f"🚨 <b>Kênh thông báo:</b> {CHANNEL_USERNAME}\n"
        f"⚜️ <b>Admin:</b> {ADMIN_USERNAME}\n"
        f"➖ ➖ ➖ ➖ ➖ ➖ ➖ ➖\n"
        f"💰 <b>Tổng nạp:</b> <code>{u['total_deposit']:,}đ</code>\n"
        f"📅 <b>Tổng nạp tháng:</b> <code>{u['month_deposit']:,}đ</code>\n"
        f"💎 <b>Số dư:</b> <code>{u['balance']:,}đ</code>"
        f"{mode_tag}"
        f"</blockquote>"
    )

    kb_buttons = [
        [
            InlineKeyboardButton("👤 Tài khoản", callback_data='menu_account'),
            InlineKeyboardButton("🛒 Cửa hàng", callback_data='menu_shop')
        ],
        [
            InlineKeyboardButton("💸 Nạp tiền", callback_data='menu_deposit'),
            InlineKeyboardButton("📊 Lịch sử & Kho Key", callback_data='menu_history_hub')
        ],
        [
            InlineKeyboardButton("🔑 Kho Key Đã Mua", callback_data='my_keys'),
            InlineKeyboardButton("📥 Tải File / Nhóm", url=CLIENT_GROUP_LINK)
        ],
        [
            InlineKeyboardButton("💬 Hỗ trợ / Liên hệ", url=SUPPORT_CONTACT)
        ]
    ]

    if is_seller(uid) and not is_admin(uid):
        kb_buttons.insert(3, [InlineKeyboardButton("📈 Doanh Thu & Chỉ Tiêu Seller", callback_data='seller_stats')])

    if is_admin(uid):
        kb_buttons.append([InlineKeyboardButton("⚙️ BẢNG ĐIỀU KHIỂN ADMIN", callback_data='admin_panel')])

    return text, InlineKeyboardMarkup(kb_buttons)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_start=False):
    uid = update.effective_user.id
    save_data()

    if not db["bot_active"] and not is_admin(uid):
        maint_text = (
            "🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ</b>\n"
            "<blockquote>Trạm dịch vụ đang tạm khóa để nâng cấp. Vui lòng quay lại sau!</blockquote>"
        )
        if update.message:
            await update.message.reply_text(maint_text, parse_mode="HTML")
        elif update.callback_query:
            await edit_or_send(update.callback_query, maint_text)
        return

    text, kb = build_main_menu_content(uid)

    if is_start and update.message:
        # Hiệu ứng làm mới giao diện giống ảnh mẫu
        loading_msg = await update.message.reply_text("✨ <i>Đang làm mới giao diện...</i>", parse_mode="HTML")
        await asyncio.sleep(0.5)
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif update.callback_query:
        await edit_or_send(update.callback_query, text, kb)

# ================= CÁC LỆNH SLASH COMMANDS (MENU GÓC TRÁI) =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db["users"][str(uid)] = True
    get_u(uid)
    save_data()
    await show_main_menu(update, context, is_start=True)

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_u(uid)
    is_s = is_seller(uid)
    p = db["seller_prices"] if is_s else db["prices"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ 1H: {p['1h']:,}đ [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 1D: {p['1d']:,}đ [{len(db['s_1d'])}]", callback_data='shop_1d')],
        [InlineKeyboardButton(f"👑 7D: {p['7d']:,}đ [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 30D: {p['30d']:,}đ [{len(db['s_30d'])}]", callback_data='shop_30d')],
        [InlineKeyboardButton("💸 Nạp Tiền", callback_data='menu_deposit'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ])
    text = (
        f"🛒 <b>CỬA HÀNG MUA KEY TỰ ĐỘNG</b>\n"
        f"<blockquote>"
        f"💎 Số dư hiện tại: <code>{u['balance']:,}đ</code>\n"
        f"🏷️ Bảng giá áp dụng: <b>{'SELLER VIP' if is_s else 'MEMBER'}</b>"
        f"</blockquote>"
    )
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 <b>HƯỚNG DẪN SỬ DỤNG HỆ THỐNG</b>\n"
        f"<blockquote>"
        f"1️⃣ Chọn <b>Nạp tiền</b> và quét mã QR (hệ thống tự cộng sau 5-15 giây).\n"
        f"2️⃣ Vào <b>Cửa hàng</b> chọn gói key cần mua.\n"
        f"3️⃣ Bấm nút <b>Copy Key</b> để sao chép tự động 1 chạm.\n"
        f"4️⃣ Mọi thắc mắc liên hệ Admin: {ADMIN_USERNAME}"
        f"</blockquote>"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]]), parse_mode="HTML")

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📋 Copy ID", copy_text=CopyTextButton(text=str(uid)))]])
    await update.message.reply_text(f"🆔 <b>Telegram ID của bạn:</b> <code>{uid}</code>", reply_markup=kb, parse_mode="HTML")

async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_u(uid)
    role = "👑 ADMIN" if is_admin(uid) else ("💎 SELLER" if is_seller(uid) else "🛡️ MEMBER")
    text = (
        f"👤 <b>THÔNG TIN TÀI KHOẢN</b>\n"
        f"<blockquote>"
        f"🆔 ID: <code>{uid}</code>\n"
        f"🎖️ Cấp bậc: <b>{role}</b>\n"
        f"💎 Số dư: <code>{u['balance']:,}đ</code>\n"
        f"💰 Tổng nạp: <code>{u['total_deposit']:,}đ</code>\n"
        f"🔑 Tổng key đã mua: <code>{len(u['my_keys'])}</code>"
        f"</blockquote>"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]]), parse_mode="HTML")

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    await show_admin_panel(update.message, uid, is_edit=False)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    tot_k = len(db['s_1h']) + len(db['s_1d']) + len(db['s_7d']) + len(db['s_30d'])
    text = (
        f"📊 <b>THỐNG KÊ DOANH THU SHOP</b>\n"
        f"<blockquote>"
        f"👥 Tổng người dùng: <code>{len(db['users'])}</code>\n"
        f"💎 Tổng Seller: <code>{len(db['sellers'])}</code>\n"
        f"💰 Tổng doanh thu: <code>{db['total_rev']:,}đ</code>\n"
        f"📦 Tồn kho key: <code>{tot_k}</code> (1H:{len(db['s_1h'])} | 1D:{len(db['s_1d'])} | 7D:{len(db['s_7d'])} | 30D:{len(db['s_30d'])})"
        f"</blockquote>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    await update.message.reply_text(f"👥 <b>Tổng số thành viên trong hệ thống:</b> <code>{len(db['users'])}</code> người dùng.", parse_mode="HTML")

async def cmd_thongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    admin_state[uid] = 'broadcast_msg'
    await update.message.reply_text(
        "📢 <b>GỬI THÔNG BÁO TOÀN HỆ THỐNG</b>\n"
        "<blockquote>Nhập nội dung thông báo bạn muốn gửi tới tất cả khách hàng (hỗ trợ định dạng HTML):</blockquote>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy bỏ", callback_data='cancel_state')]]),
        parse_mode="HTML"
    )

# ================= BẢNG ĐIỀU KHIỂN ADMIN =================
async def show_admin_panel(target_msg, uid, is_edit=True):
    st = "🟢 Hoạt Động" if db["bot_active"] else "🔴 Bảo Trì"
    cur_mode = admin_view_mode.get(uid, 'seller')
    switch_label = "🔄 Đang xem: KHO SELLER (Bấm đổi sang Member)" if cur_mode == 'seller' else "🔄 Đang xem: KHO MEMBER (Bấm đổi sang Seller)"

    text = (
        f"⚙️ <b>TRẠM QUẢN TRỊ MASTER ADMIN</b>\n"
        f"<blockquote>"
        f"• Trạng thái Bot: <b>{st}</b>\n"
        f"• Chế độ xem kho hiện tại: <b>{cur_mode.upper()}</b>\n"
        f"• Tồn kho: 1H[<code>{len(db['s_1h'])}</code>] | 1D[<code>{len(db['s_1d'])}</code>] | 7D[<code>{len(db['s_7d'])}</code>] | 30D[<code>{len(db['s_30d'])}</code>]"
        f"</blockquote>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(switch_label, callback_data='ad_switch_view')],
        [InlineKeyboardButton("📢 Gửi Thông Báo All", callback_data='ad_broadcast'), InlineKeyboardButton("🔴 Bật/Tắt Bảo Trì", callback_data='toggle_bot_status')],
        [InlineKeyboardButton("📦 Thêm Key Vào Kho", callback_data='ad_checkkey'), InlineKeyboardButton("💰 Sửa Bảng Giá", callback_data='ad_price_menu')],
        [InlineKeyboardButton("💸 Cộng Tiền", callback_data='ad_bal'), InlineKeyboardButton("📉 Trừ Tiền", callback_data='ad_subbal')],
        [InlineKeyboardButton("👥 Quản Lý Seller", callback_data='ad_manageseller'), InlineKeyboardButton("📊 Thống Kê", callback_data='ad_stats')],
        [InlineKeyboardButton("💾 Tải File Backup", callback_data='ad_get_backup'), InlineKeyboardButton("📥 Khôi Phục Backup", callback_data='ad_restore_prompt')],
        [InlineKeyboardButton("🏠 Quay Lại Trang Chủ", callback_data='back_menu')]
    ])
    if is_edit:
        await edit_or_send(target_msg, text, kb)
    else:
        await target_msg.reply_text(text, reply_markup=kb, parse_mode="HTML")

# ================= XỬ LÝ NÚT BẤM (CALLBACK) =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if check_spam(uid):
        await query.answer("⚠️ Thao tác quá nhanh!", show_alert=True)
        return
    await query.answer()

    u = get_u(uid)
    data = query.data
    is_s = is_seller(uid)
    p = db["seller_prices"] if is_s else db["prices"]

    if data == 'cancel_state':
        admin_state.pop(uid, None)
        await show_main_menu(update, context)

    elif data == 'back_menu':
        await show_main_menu(update, context)

    elif data == 'menu_account':
        role = "👑 ADMIN" if is_admin(uid) else ("💎 SELLER" if is_seller(uid) else "🛡️ MEMBER")
        text = (
            f"👤 <b>THÔNG TIN TÀI KHOẢN</b>\n"
            f"<blockquote>"
            f"🆔 ID: <code>{uid}</code>\n"
            f"🎖️ Cấp bậc: <b>{role}</b>\n"
            f"💎 Số dư khả dụng: <code>{u['balance']:,}đ</code>\n"
            f"💰 Tổng nạp tích lũy: <code>{u['total_deposit']:,}đ</code>\n"
            f"📅 Nạp trong tháng: <code>{u['month_deposit']:,}đ</code>\n"
            f"🔑 Key đang sở hữu: <code>{len(u['my_keys'])} key</code>"
            f"</blockquote>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy ID Tài Khoản", copy_text=CopyTextButton(text=str(uid)))],
            [InlineKeyboardButton("🔑 Kho Key Đã Mua", callback_data='my_keys'), InlineKeyboardButton("📊 Lịch Sử Giao Dịch", callback_data='menu_history_hub')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]
        ])
        await edit_or_send(query, text, kb)

    # KHO KEY ĐÃ MUA - FIX TRIỆT ĐỂ NÚT COPY BẰNG COPYTEXTBUTTON
    elif data == 'my_keys':
        kb_keys = []
        if u['my_keys']:
            recent_keys = u['my_keys'][-15:]
            key_lines = []
            for idx, item in enumerate(reversed(recent_keys), 1):
                clean_k = item.split('] ')[-1] if '] ' in item else item
                label = item.split('] ')[0] + ']' if '] ' in item else '[KEY]'
                short_disp = clean_k[:14] + "..." if len(clean_k) > 14 else clean_k
                key_lines.append(f"<b>{idx}.</b> {label} <code>{clean_k}</code>")
                # Nút bấm copy trực tiếp 1 chạm vào clipboard điện thoại!
                kb_keys.append([
                    InlineKeyboardButton(f"📋 Copy {label} {short_disp}", copy_text=CopyTextButton(text=clean_k))
                ])
            keys_block = "\n".join(key_lines)
        else:
            keys_block = "<i>Bạn chưa mua key nào. Hãy ghé cửa hàng ngay nhé!</i>"
            kb_keys.append([InlineKeyboardButton("🛒 Đi Tới Cửa Hàng", callback_data='menu_shop')])

        kb_keys.append([InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')])
        text = (
            f"🔑 <b>KHO KEY ĐÃ MUA (15 KEY GẦN NHẤT)</b>\n"
            f"<blockquote>{keys_block}</blockquote>\n"
            f"👉 <i>Bấm trực tiếp vào nút bên dưới để sao chép Key tự động:</i>"
        )
        await edit_or_send(query, text, InlineKeyboardMarkup(kb_keys))

    # DANH MỤC LỊCH SỬ & BIẾN ĐỘNG SỐ DƯ THỜI GIAN THỰC
    elif data == 'menu_history_hub':
        text = (
            f"📊 <b>TRUNG TÂM LỊCH SỬ & BIẾN ĐỘNG SỐ DƯ</b>\n"
            f"<blockquote>"
            f"💎 Số dư hiện tại: <code>{u['balance']:,}đ</code>\n"
            f"🛍️ Đơn hàng đã mua: <code>{len(u['buy_history'])} đơn</code>\n"
            f"💳 Giao dịch nạp tiền: <code>{len(u['deposit_history'])} lần</code>"
            f"</blockquote>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Lịch Sử Mua Key & Số Dư", callback_data='hist_buy')],
            [InlineKeyboardButton("💳 Lịch Sử Nạp Tiền", callback_data='hist_deposit')],
            [InlineKeyboardButton("🔑 Mở Kho Key (Copy Nhanh)", callback_data='my_keys')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]
        ])
        await edit_or_send(query, text, kb)

    elif data == 'hist_buy':
        if u['buy_history']:
            b_list = "\n".join(reversed(u['buy_history'][-12:]))
        else:
            b_list = "<i>Chưa có lịch sử mua hàng nào.</i>"
        text = (
            f"🛍️ <b>LỊCH SỬ MUA KEY & BIẾN ĐỘNG SỐ DƯ</b>\n"
            f"<blockquote>{b_list}</blockquote>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 Vào Kho Key Để Copy", callback_data='my_keys')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_history_hub')]
        ])
        await edit_or_send(query, text, kb)

    elif data == 'hist_deposit':
        if u['deposit_history']:
            h_list = "\n".join(reversed(u['deposit_history'][-12:]))
        else:
            h_list = "<i>Chưa có lịch sử nạp tiền nào.</i>"
        text = (
            f"💳 <b>LỊCH SỬ NẠP TIỀN REAL-TIME</b>\n"
            f"<blockquote>{h_list}</blockquote>"
        )
        await edit_or_send(query, text, InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_history_hub')]]))

    elif data == 'seller_stats':
        s_info = db["sellers"].get(str(uid), {"daily_rev": 0, "target": 500000})
        rev, target = s_info["daily_rev"], s_info.get("target", 500000)
        percent = min(100, int((rev / target) * 100)) if target > 0 else 100
        status = "🟢 ĐẠT CHỈ TIÊU" if rev >= target else "🔴 CHƯA ĐẠT"
        text = (
            f"📈 <b>DOANH THU & CHỈ TIÊU SELLER</b>\n"
            f"<blockquote>"
            f"• Doanh thu hôm nay: <code>{rev:,}đ</code>\n"
            f"• Chỉ tiêu ngày: <code>{target:,}đ</code> ({percent}%)\n"
            f"• Trạng thái: <b>{status}</b>"
            f"</blockquote>"
        )
        await edit_or_send(query, text, InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]]))

    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ 1H: {p['1h']:,}đ [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 1D: {p['1d']:,}đ [{len(db['s_1d'])}]", callback_data='shop_1d')],
            [InlineKeyboardButton(f"👑 7D: {p['7d']:,}đ [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 30D: {p['30d']:,}đ [{len(db['s_30d'])}]", callback_data='shop_30d')],
            [InlineKeyboardButton("💸 Nạp Tiền", callback_data='menu_deposit'), InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]
        ])
        text = (
            f"🛒 <b>CỬA HÀNG MUA KEY</b>\n"
            f"<blockquote>"
            f"💎 Số dư ví: <code>{u['balance']:,}đ</code>\n"
            f"🏷️ Phân khúc giá: <b>{'SELLER VIP' if is_s else 'MEMBER'}</b>"
            f"</blockquote>"
        )
        await edit_or_send(query, text, kb)

    elif data.startswith('shop_'):
        kt = data.split('_')[1]
        price, kho = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}[kt]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Mua 1 Key", callback_data=f"buyq_{kt}_1"), InlineKeyboardButton("Mua 2 Key", callback_data=f"buyq_{kt}_2")],
            [InlineKeyboardButton("Mua 5 Key", callback_data=f"buyq_{kt}_5"), InlineKeyboardButton("Mua 10 Key", callback_data=f"buyq_{kt}_10")],
            [InlineKeyboardButton("✏️ Nhập Số Lượng Tùy Ý", callback_data=f"buyq_custom_{kt}")],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_shop')]
        ])
        text = (
            f"📦 <b>CHI TIẾT GÓI {kt.upper()}</b>\n"
            f"<blockquote>"
            f"• Đơn giá: <code>{price:,}đ / key</code>\n"
            f"• Tồn kho: <code>{len(kho)} key</code>\n"
            f"• Số dư của bạn: <code>{u['balance']:,}đ</code>"
            f"</blockquote>"
        )
        await edit_or_send(query, text, kb)

    elif data.startswith('buyq_custom_'):
        kt = data.split('_')[2]
        admin_state[uid] = f"buy_custom_{kt}"
        await edit_or_send(query, f"💬 Nhập số lượng key gói <b>{kt.upper()}</b> cần mua vào khung chat:", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data=f"shop_{kt}")]]))

    elif data.startswith('buyq_'):
        _, kt, qty = data.split('_')
        await process_purchase(query, context, uid, kt, int(qty))

    elif data == 'menu_deposit':
        kb_dep = InlineKeyboardMarkup([
            [InlineKeyboardButton("10.000đ", callback_data='pre_qr_10000'), InlineKeyboardButton("50.000đ", callback_data='pre_qr_50000')],
            [InlineKeyboardButton("100.000đ", callback_data='pre_qr_100000'), InlineKeyboardButton("200.000đ", callback_data='pre_qr_200000')],
            [InlineKeyboardButton("✏️ Nhập Số Tiền Tùy Ý", callback_data='pre_qr_custom')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]
        ])
        text = (
            f"💸 <b>NẠP TIỀN TỰ ĐỘNG 24/7 (SEPAY)</b>\n"
            f"<blockquote>Chọn mệnh giá nạp nhanh bên dưới, hệ thống cộng tiền tự động ngay lập tức sau khi chuyển khoản:</blockquote>"
        )
        await edit_or_send(query, text, kb_dep)

    elif data.startswith('pre_qr_'):
        sub = data.replace('pre_qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, "💬 Nhập số tiền cần nạp (Ví dụ: <code>50000</code>):", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]]))
            return
        await send_qr_direct(query, context, uid, int(sub))

    # ================= ADMIN CALLBACKS =================
    elif data == 'admin_panel' and is_admin(uid):
        await show_admin_panel(query, uid, is_edit=True)

    elif data == 'ad_switch_view' and is_admin(uid):
        cur = admin_view_mode.get(uid, 'seller')
        admin_view_mode[uid] = 'member' if cur == 'seller' else 'seller'
        await query.answer(f"Đã chuyển sang chế độ xem: {admin_view_mode[uid].upper()}", show_alert=True)
        await show_admin_panel(query, uid, is_edit=True)

    elif data == 'ad_broadcast' and is_admin(uid):
        admin_state[uid] = 'broadcast_msg'
        await edit_or_send(query, "📢 <b>GỬI THÔNG BÁO TOÀN HỆ THỐNG</b>\n<blockquote>Nhập nội dung thông báo bạn muốn gửi tới toàn bộ user:</blockquote>", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data='admin_panel')]]))

    elif data == 'toggle_bot_status' and is_admin(uid):
        db["bot_active"] = not db["bot_active"]
        save_data()
        await query.answer("Đã đổi trạng thái hoạt động của Bot!", show_alert=True)
        await show_admin_panel(query, uid, is_edit=True)

    elif data == 'ad_price_menu' and is_admin(uid):
        await edit_or_send(query, "💰 <b>CHỈNH SỬA BẢNG GIÁ</b>\nChọn phân khúc cần sửa:", InlineKeyboardMarkup([
            [InlineKeyboardButton("🏷️ Giá Member", callback_data='set_type_mem'), InlineKeyboardButton("👑 Giá Seller", callback_data='set_type_sel')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))

    elif data == 'set_type_mem' and is_admin(uid):
        await edit_or_send(query, "🏷️ <b>GIÁ MEMBER:</b> Chọn gói cần sửa:", InlineKeyboardMarkup([
            [InlineKeyboardButton("1H", callback_data='pm_1h'), InlineKeyboardButton("1D", callback_data='pm_1d')],
            [InlineKeyboardButton("7D", callback_data='pm_7d'), InlineKeyboardButton("30D", callback_data='pm_30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_price_menu')]
        ]))

    elif data == 'set_type_sel' and is_admin(uid):
        await edit_or_send(query, "👑 <b>GIÁ SELLER:</b> Chọn gói cần sửa:", InlineKeyboardMarkup([
            [InlineKeyboardButton("1H", callback_data='ps_1h'), InlineKeyboardButton("1D", callback_data='ps_1d')],
            [InlineKeyboardButton("7D", callback_data='ps_7d'), InlineKeyboardButton("30D", callback_data='ps_30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_price_menu')]
        ]))

    elif data.startswith('pm_') and is_admin(uid):
        pk = data.replace('pm_', '')
        admin_state[uid] = f"setprice_mem_{pk}"
        await edit_or_send(query, f"💬 Nhập giá Member mới cho gói <b>{pk.upper()}</b>:")

    elif data.startswith('ps_') and is_admin(uid):
        pk = data.replace('ps_', '')
        admin_state[uid] = f"setprice_sel_{pk}"
        await edit_or_send(query, f"💬 Nhập giá Seller mới cho gói <b>{pk.upper()}</b>:")

    elif data == 'ad_stats' and is_admin(uid):
        tot_k = len(db['s_1h']) + len(db['s_1d']) + len(db['s_7d']) + len(db['s_30d'])
        text = (
            f"📊 <b>THỐNG KÊ HỆ THỐNG</b>\n"
            f"<blockquote>"
            f"• Tổng User: <code>{len(db['users'])}</code>\n"
            f"• Tổng Seller: <code>{len(db['sellers'])}</code>\n"
            f"• Tổng Doanh Thu: <code>{db['total_rev']:,}đ</code>\n"
            f"• Tồn Kho: <code>{tot_k} key</code>"
            f"</blockquote>"
        )
        await edit_or_send(query, text, InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]]))

    elif data == 'ad_get_backup' and is_admin(uid):
        save_data()
        try:
            if os.path.exists(DB_FILE):
                with open(DB_FILE, "rb") as f:
                    await context.bot.send_document(
                        chat_id=uid,
                        document=f,
                        filename=f"database_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
                        caption="🛡️ <b>[MANUAL BACKUP]</b>\nFile dữ liệu đầy đủ của hệ thống. Để khôi phục bất cứ lúc nào, chỉ cần gửi trực tiếp file này lại cho Bot!"
                    )
            await query.answer("Đã gửi file backup về chat riêng!", show_alert=True)
        except Exception:
            await query.answer("Lỗi xuất file backup!", show_alert=True)

    elif data == 'ad_restore_prompt' and is_admin(uid):
        await edit_or_send(
            query,
            "📥 <b>KHÔI PHỤC DỮ LIỆU TỪ FILE BACKUP</b>\n"
            "<blockquote>Anh chỉ cần gửi trực tiếp file <code>database.json</code> (hoặc file backup cũ) vào khung chat này, Bot sẽ tự động nạp lại toàn bộ số dư, kho key và danh sách Seller ngay lập tức!</blockquote>",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]])
        )

    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, "💬 Nhập cú pháp cộng tiền: <code>[ID] [Số_tiền]</code>\nVí dụ: <code>7976468365 50000</code>")

    elif data == 'ad_subbal' and is_admin(uid):
        admin_state[uid] = 'sub_bal'
        await edit_or_send(query, "💬 Nhập cú pháp trừ tiền: <code>[ID] [Số_tiền]</code>")

    elif data == 'ad_manageseller' and is_admin(uid):
        s_list_text = "👥 <b>DANH SÁCH SELLER & DOANH THU NGÀY:</b>\n<blockquote>"
        if db["sellers"]:
            for s_id, s_info in db["sellers"].items():
                rev = s_info.get("daily_rev", 0)
                target = s_info.get("target", 500000)
                s_list_text += f"• ID: <code>{s_id}</code> — <b>{rev:,}đ / {target:,}đ</b>\n"
        else:
            s_list_text += "<i>Chưa có Seller nào trong hệ thống.</i>"
        s_list_text += "</blockquote>"

        kb_sel = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Thêm / Sửa Chỉ Tiêu", callback_data='add_seller_prompt')],
            [InlineKeyboardButton("🗑️ Xóa Seller", callback_data='del_seller_prompt')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ])
        await edit_or_send(query, s_list_text, kb_sel)

    elif data == 'add_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'add_seller_id'
        await edit_or_send(query, "💬 Nhập: <code>[ID] [Chỉ_tiêu_ngày]</code>\nVí dụ: <code>7976468365 500000</code>")

    elif data == 'del_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'del_seller_id'
        await edit_or_send(query, "💬 Nhập ID Seller cần xóa:")

    elif data == 'ad_checkkey' and is_admin(uid):
        await edit_or_send(query, "📦 <b>QUẢN LÝ KHO KEY</b>\nChọn loại gói cần thêm key:", InlineKeyboardMarkup([
            [InlineKeyboardButton(f"1H [{len(db['s_1h'])}]", callback_data='k_s1h'), InlineKeyboardButton(f"1D [{len(db['s_1d'])}]", callback_data='k_s1d')],
            [InlineKeyboardButton(f"7D [{len(db['s_7d'])}]", callback_data='k_s7d'), InlineKeyboardButton(f"30D [{len(db['s_30d'])}]", callback_data='k_s30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))

    elif data.startswith('k_') and is_admin(uid):
        k_type = data.replace('k_', '')
        admin_state[uid] = f"addk_{k_type}"
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        cur_len = len(m_map.get(k_type, []))
        await edit_or_send(
            query,
            f"📦 <b>THÊM KEY VÀO KHO {k_type.upper()}</b>\nTồn kho hiện tại: <code>{cur_len} key</code>\n\n💬 Gửi danh sách key (mỗi key 1 dòng):",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_checkkey')]])
        )

# ================= XỬ LÝ NẠP QR & MUA HÀNG =================
async def send_qr_direct(query, context, uid, amount):
    memo = f"NAP {uid}"
    photo_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo={quote(memo)}&accountName={quote(ACCOUNT_NAME)}"

    text = (
        f"💳 <b>MÃ QR NẠP {amount:,}Đ</b>\n"
        f"<blockquote>"
        f"🏦 Ngân hàng: <b>{BANK_ID}</b>\n"
        f"🔢 Số tài khoản: <code>{ACCOUNT_NO}</code>\n"
        f"👤 Chủ TK: <b>{ACCOUNT_NAME}</b>\n"
        f"📝 Nội dung CK: <code>{memo}</code>"
        f"</blockquote>\n"
        f"👉 <i>Quét mã qua app ngân hàng, số tiền và nội dung đã tự động điền sẵn!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy Nội Dung CK", copy_text=CopyTextButton(text=memo))],
        [InlineKeyboardButton("🔗 Mở Ảnh QR Trực Tiếp", url=photo_url)],
        [InlineKeyboardButton("🔄 Kiểm Tra Số Dư", callback_data='menu_account'), InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]
    ])
    try:
        await query.message.delete()
        await context.bot.send_photo(chat_id=uid, photo=photo_url, caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(chat_id=uid, text=text + f"\n\n🔗 <a href='{photo_url}'>Bấm vào đây để mở mã QR</a>", reply_markup=kb, parse_mode="HTML")

async def process_purchase(query, context, uid, kt, qty):
    with buy_lock:
        u = get_u(uid)
        is_s = is_seller(uid)
        p = db["seller_prices"] if is_s else db["prices"]

        if qty <= 0 or qty > 100:
            await query.answer("❌ Số lượng không hợp lệ (1 - 100)!", show_alert=True)
            return

        price, kho = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}[kt]
        total = price * qty

        if len(kho) < qty:
            await query.answer(f"❌ Kho không đủ! Hiện chỉ còn {len(kho)} key.", show_alert=True)
            return
        if u['balance'] < total:
            await query.answer(f"❌ Số dư không đủ! Cần {total:,}đ (Bạn có {u['balance']:,}đ).", show_alert=True)
            return

        bal_before = u['balance']
        u['balance'] -= total
        bal_after = u['balance']
        db["total_rev"] += total

        if is_s and not is_admin(uid):
            db["sellers"][str(uid)]["daily_rev"] = db["sellers"][str(uid)].get("daily_rev", 0) + total

        keys_bought = [kho.pop(0) for _ in range(qty)]
        for k in keys_bought:
            u['my_keys'].append(f"[{kt.upper()}] {k}")

        time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        # Lưu chi tiết lịch sử mua + số dư trước/sau theo thời gian thực
        hist_entry = (
            f"• <b>[{time_str}]</b> Mua <code>{qty}x {kt.upper()}</code> (-{total:,}đ)\n"
            f"  └ Số dư: <code>{bal_before:,}đ</code> ➔ <code>{bal_after:,}đ</code>"
        )
        u['buy_history'].append(hist_entry)
        save_data()

    # Gửi thông báo Admin theo thời gian thực
    try:
        log_msg = (
            f"🛍️ <b>GIAO DỊCH MUA KEY MỚI (REAL-TIME)</b>\n"
            f"<blockquote>"
            f"• Khách hàng ID: <code>{uid}</code>\n"
            f"• Phân khúc: <b>{'SELLER' if is_s else 'MEMBER'}</b>\n"
            f"• Sản phẩm: <b>{qty}x Gói {kt.upper()}</b>\n"
            f"• Thanh toán: <code>-{total:,}đ</code>\n"
            f"• Biến động ví: <code>{bal_before:,}đ</code> ➔ <code>{bal_after:,}đ</code>\n"
            f"• Thời gian: <code>{time_str}</code>"
            f"</blockquote>"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_msg, parse_mode="HTML")
    except Exception:
        pass

    # Tạo danh sách nút Copy 1 chạm cho từng Key vừa mua
    kb_buy_res = []
    for k in keys_bought:
        short_k = k[:16] + "..." if len(k) > 16 else k
        kb_buy_res.append([InlineKeyboardButton(f"📋 Copy Key: {short_k}", copy_text=CopyTextButton(text=k))])

    if len(keys_bought) > 1:
        all_keys_joined = "\n".join(keys_bought)
        kb_buy_res.append([InlineKeyboardButton("📑 Copy Toàn Bộ Key", copy_text=CopyTextButton(text=all_keys_joined))])

    kb_buy_res.append([InlineKeyboardButton("📥 Tải File / Nhóm", url=CLIENT_GROUP_LINK)])
    kb_buy_res.append([InlineKeyboardButton("🔑 Kho Key", callback_data='my_keys'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')])

    keys_display = "\n".join([f"• <code>{k}</code>" for k in keys_bought])
    res_text = (
        f"✅ <b>THANH TOÁN THÀNH CÔNG {qty}x GÓI {kt.upper()}!</b>\n\n"
        f"<blockquote>"
        f"👇 <b>Danh sách Key của bạn:</b>\n"
        f"{keys_display}\n"
        f"➖ ➖ ➖ ➖ ➖ ➖ ➖ ➖\n"
        f"💰 Đã trừ: <code>-{total:,}đ</code>\n"
        f"💎 Số dư còn lại: <code>{bal_after:,}đ</code>"
        f"</blockquote>\n"
        f"👉 <i>Bấm trực tiếp vào nút <b>Copy Key</b> bên dưới để sao chép ngay:</i>"
    )
    await edit_or_send(query, res_text, InlineKeyboardMarkup(kb_buy_res))

# ================= XỬ LÝ TIN NHẮN VĂN BẢN & FILE BACKUP =================
async def handle_document_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return
    doc = update.message.document
    if doc and doc.file_name.endswith(".json"):
        try:
            file = await context.bot.get_file(doc.file_id)
            file_bytes = await file.download_as_bytearray()
            new_db = json.loads(file_bytes.decode("utf-8"))
            if "user_data" in new_db and "prices" in new_db:
                global db
                db = new_db
                save_data()
                tot_k = len(db.get('s_1h', [])) + len(db.get('s_1d', [])) + len(db.get('s_7d', [])) + len(db.get('s_30d', []))
                await update.message.reply_text(
                    f"✅ <b>KHÔI PHỤC DATABASE THÀNH CÔNG!</b>\n"
                    f"<blockquote>"
                    f"• Tổng thành viên: <code>{len(db.get('users', {}))}</code>\n"
                    f"• Tổng Seller: <code>{len(db.get('sellers', {}))}</code>\n"
                    f"• Tổng tồn kho: <code>{tot_k} key</code>"
                    f"</blockquote>",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("❌ File JSON không đúng cấu trúc database của Bot!")
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi đọc file backup: {e}")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid not in admin_state:
        return
    state = admin_state[uid]
    text = update.message.text

    if state.startswith('buy_custom_'):
        kt = state.replace('buy_custom_', '')
        del admin_state[uid]
        try:
            qty = int(text.strip())
            class DummyQuery:
                def __init__(self, msg, user): self.message, self.from_user = msg, user
                async def answer(self, *a, **kw): pass
            await process_purchase(DummyQuery(update.message, update.message.from_user), context, uid, kt, qty)
        except Exception:
            await update.message.reply_text("❌ Số lượng không hợp lệ!")
        return

    if state == 'waiting_deposit':
        del admin_state[uid]
        try:
            amt = int(text.replace(".", "").replace(",", "").strip())
            if amt < 2000:
                await update.message.reply_text("❌ Số tiền nạp tối thiểu là 2,000đ!")
                return
            memo = f"NAP {uid}"
            photo_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amt}&addInfo={quote(memo)}&accountName={quote(ACCOUNT_NAME)}"
            text_qr = (
                f"💳 <b>MÃ QR NẠP {amt:,}Đ</b>\n"
                f"<blockquote>"
                f"🏦 Ngân hàng: <b>{BANK_ID}</b>\n"
                f"🔢 STK: <code>{ACCOUNT_NO}</code>\n"
                f"📝 Nội dung CK: <code>{memo}</code>"
                f"</blockquote>"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Copy Nội Dung CK", copy_text=CopyTextButton(text=memo))],
                [InlineKeyboardButton("🔗 Mở Ảnh QR Trực Tiếp", url=photo_url)],
                [InlineKeyboardButton("🔄 Kiểm Tra Số Dư", callback_data='menu_account')]
            ])
            try:
                await update.message.reply_photo(photo=photo_url, caption=text_qr, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(text_qr + f"\n\n🔗 <a href='{photo_url}'>Bấm mở mã QR</a>", reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Số tiền không hợp lệ!")
        return

    if not is_admin(uid):
        return

    # Gửi thông báo toàn hệ thống
    if state == 'broadcast_msg':
        del admin_state[uid]
        users_list = list(db["users"].keys())
        status_msg = await update.message.reply_text(f"⏳ Đang gửi thông báo tới <code>{len(users_list)}</code> người dùng...", parse_mode="HTML")
        success_cnt = 0
        broadcast_text = (
            f"📢 <b>THÔNG BÁO TỪ QUẢN TRỊ VIÊN</b>\n"
            f"<blockquote>{text}</blockquote>"
        )
        for target_uid in users_list:
            try:
                await context.bot.send_message(chat_id=int(target_uid), text=broadcast_text, parse_mode="HTML")
                success_cnt += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await status_msg.edit_text(f"✅ <b>HOÀN TẤT GỬI THÔNG BÁO!</b>\nĐã gửi thành công tới <code>{success_cnt}/{len(users_list)}</code> thành viên.", parse_mode="HTML")
        return

    if state.startswith('setprice_mem_'):
        pk = state.replace('setprice_mem_', '')
        del admin_state[uid]
        try:
            new_p = int(text.replace(".", "").strip())
            db["prices"][pk] = new_p
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá Member gói <b>{pk.upper()}</b> thành <code>{new_p:,}đ</code>!", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Giá không hợp lệ!")
        return

    if state.startswith('setprice_sel_'):
        pk = state.replace('setprice_sel_', '')
        del admin_state[uid]
        try:
            new_p = int(text.replace(".", "").strip())
            db["seller_prices"][pk] = new_p
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá Seller gói <b>{pk.upper()}</b> thành <code>{new_p:,}đ</code>!", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Giá không hợp lệ!")
        return

    if state.startswith('addk_'):
        k_type = state.replace('addk_', '')
        del admin_state[uid]
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        target = m_map.get(k_type)
        if target is not None:
            added = 0
            dup = 0
            for line in text.split('\n'):
                ckey = line.strip()
                if ckey:
                    if ckey not in target:
                        target.append(ckey)
                        added += 1
                    else:
                        dup += 1
            save_data()
            await update.message.reply_text(
                f"✅ <b>NHẬP KHO THÀNH CÔNG GÓI {k_type.upper()}!</b>\n"
                f"• Đã thêm mới: <code>+{added} key</code> (Trùng bỏ qua: {dup})\n"
                f"• Tổng tồn kho hiện tại: <code>{len(target)} key</code>",
                parse_mode="HTML"
            )
            # Thông báo ngay lập tức về nhóm Admin Log
            try:
                time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                log_add_key = (
                    f"📦 <b>CẬP NHẬT KHO HÀNG (ADMIN NHẬP KEY)</b>\n"
                    f"<blockquote>"
                    f"• Loại gói: <b>Gói {k_type.upper()}</b>\n"
                    f"• Số lượng thêm: <code>+{added} key</code>\n"
                    f"• Tổng tồn kho mới: <code>{len(target)} key</code>\n"
                    f"• Admin thực hiện: <code>{uid}</code>\n"
                    f"• Thời gian: <code>{time_str}</code>"
                    f"</blockquote>"
                )
                await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_add_key, parse_mode="HTML")
            except Exception:
                pass
        return

    if state in ('add_bal', 'sub_bal'):
        try:
            tid, amt = text.split()
            tid, amt = int(tid), int(amt)
            u = get_u(tid)
            bal_before = u['balance']
            if state == 'add_bal':
                u['balance'] += amt
                u['total_deposit'] += amt
                u['month_deposit'] += amt
                action_str = f"+{amt:,}đ"
            else:
                u['balance'] = max(0, u['balance'] - amt)
                action_str = f"-{amt:,}đ"
            bal_after = u['balance']
            time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            u['deposit_history'].append(f"• <b>[{time_str}]</b> Admin điều chỉnh <code>{action_str}</code> (Ví: <code>{bal_after:,}đ</code>)")
            save_data()

            await update.message.reply_text(f"✅ Đã điều chỉnh <code>{action_str}</code> cho ID <code>{tid}</code>!\nSố dư mới: <code>{bal_after:,}đ</code>", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=tid,
                    text=f"🔔 <b>BIẾN ĐỘNG SỐ DƯ TÀI KHOẢN</b>\n<blockquote>• Thay đổi: <code>{action_str}</code>\n• Số dư trước: <code>{bal_before:,}đ</code>\n• Số dư hiện tại: <code>{bal_after:,}đ</code></blockquote>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        except Exception:
            await update.message.reply_text("❌ Sai cú pháp! Nhập: <code>[ID] [Số_tiền]</code>", parse_mode="HTML")
        del admin_state[uid]

    elif state == 'add_seller_id':
        try:
            parts = text.split()
            sid = str(parts[0])
            target = int(parts[1]) if len(parts) > 1 else 500000
            db["sellers"][sid] = {"daily_rev": 0, "target": target}
            save_data()
            await update.message.reply_text(f"✅ Đã cấp quyền Seller cho ID <code>{sid}</code> (Chỉ tiêu: <code>{target:,}đ/ngày</code>)!", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Sai cú pháp! Nhập: <code>[ID] [Chỉ_tiêu]</code>", parse_mode="HTML")
        del admin_state[uid]

    elif state == 'del_seller_id':
        sid = text.strip()
        if sid in db["sellers"]:
            del db["sellers"][sid]
            save_data()
            await update.message.reply_text(f"✅ Đã xóa quyền Seller của ID <code>{sid}</code>!", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Không tìm thấy ID Seller này!")
        del admin_state[uid]

# ================= WEBHOOK SEPAY TỰ ĐỘNG REAL-TIME =================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "MIZZE STORE BOT RUNNING", 200

@flask_app.route('/sepay_webhook', methods=['POST'])
def sepay():
    data = request.json
    if data:
        content = str(data.get("content", data.get("description", "")))
        m = re.search(r"NAP[\s\-]*(\d+)", content, re.IGNORECASE)
        if m:
            tid, amt = int(m.group(1)), int(data.get("transferAmount", data.get("amount", 0)))
            if amt > 0:
                with buy_lock:
                    u = get_u(tid)
                    bal_before = u['balance']
                    u['balance'] += amt
                    u['total_deposit'] += amt
                    u['month_deposit'] += amt
                    bal_after = u['balance']
                    db["total_rev"] += amt
                    if str(tid) in db["sellers"]:
                        db["sellers"][str(tid)]["daily_rev"] = db["sellers"][str(tid)].get("daily_rev", 0) + amt

                    time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    u['deposit_history'].append(
                        f"• <b>[{time_str}]</b> Nạp Auto <code>+{amt:,}đ</code>\n"
                        f"  └ Ví: <code>{bal_before:,}đ</code> ➔ <code>{bal_after:,}đ</code>"
                    )
                    save_data()

                try:
                    user_msg = (
                        f"🎉 <b>NẠP TIỀN THÀNH CÔNG (TỰ ĐỘNG)!</b>\n"
                        f"<blockquote>"
                        f"• Số tiền nạp: <code>+{amt:,}đ</code>\n"
                        f"• Số dư trước: <code>{bal_before:,}đ</code>\n"
                        f"• Số dư hiện tại: <code>{bal_after:,}đ</code>\n"
                        f"• Thời gian: <code>{time_str}</code>"
                        f"</blockquote>"
                    )
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": tid, "text": user_msg, "parse_mode": "HTML"})

                    admin_notify = (
                        f"💳 <b>NẠP TIỀN THÀNH CÔNG (SEPAY REAL-TIME)</b>\n"
                        f"<blockquote>"
                        f"• Khách hàng ID: <code>{tid}</code>\n"
                        f"• Số tiền cộng: <code>+{amt:,}đ</code>\n"
                        f"• Biến động ví: <code>{bal_before:,}đ</code> ➔ <code>{bal_after:,}đ</code>\n"
                        f"• Thời gian: <code>{time_str}</code>"
                        f"</blockquote>"
                    )
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": LOG_GROUP_ID, "text": admin_notify, "parse_mode": "HTML"})
                except Exception:
                    pass
    return jsonify({"success": True}), 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# Đăng ký tự động danh sách lệnh Menu góc trái (giống ảnh 2)
async def post_init(application: Application):
    commands = [
        BotCommand("start", "Mở shop"),
        BotCommand("shop", "Mở Cửa hàng Key"),
        BotCommand("help", "Hướng dẫn sử dụng"),
        BotCommand("id", "Xem Telegram ID"),
        BotCommand("me", "Thông tin tài khoản"),
        BotCommand("admin", "Bảng lệnh admin"),
        BotCommand("stats", "Thống kê shop"),
        BotCommand("users", "Đếm người dùng"),
        BotCommand("thongbao", "Admin gửi thông báo"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("thongbao", cmd_thongbao))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("json"), handle_document_restore))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()