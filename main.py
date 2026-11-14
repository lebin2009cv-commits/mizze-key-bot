import os, logging, threading, httpx, re, time, datetime, json, asyncio, gc
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

LOG_GROUP_ID = -1003912025872
CLIENT_GROUP_LINK = "https://t.me/mizze_lebin"
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
admin_view_mode = {}

def make_copy_btn(label: str, text_to_copy: str):
    """Tạo nút copy an toàn tương thích mọi thiết bị"""
    btn = InlineKeyboardButton(label, callback_data="none")
    btn._api_kwargs = {"copy_text": {"text": str(text_to_copy)}}
    return btn

def load_data():
    default_data = {
        "users": {}, "user_data": {}, "sellers": {},
        "s_1h": [], "s_1d": [], "s_7d": [], "s_30d": [],
        "prices": {"1h": 5000, "1d": 20000, "7d": 70000, "30d": 150000},
        "seller_prices": {"1h": 5000, "1d": 10000, "7d": 45000, "30d": 70000},
        "total_rev": 2905000, "bot_active": True,
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
        except Exception: pass
    return default_data

db = load_data()

def save_data():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if db.get("last_reset_date") != today_str:
            for s_info in db["sellers"].values():
                s_info["daily_rev"] = 0
            db["last_reset_date"] = today_str
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
        gc.collect()
    except Exception: pass

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {'balance': 0, 'total_deposit': 0, 'month_deposit': 0, 'deposit_history': [], 'buy_history': [], 'my_keys': []}
        save_data()
    u = db["user_data"][uid_str]
    for key in ['month_deposit', 'deposit_history', 'buy_history', 'my_keys']:
        if key not in u: u[key] = 0 if key == 'month_deposit' else []
    return u

def is_admin(uid): return uid in admin_list
def is_seller(uid):
    if is_admin(uid): return admin_view_mode.get(uid, 'seller') == 'seller'
    return str(uid) in db["sellers"]

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 0.4: return True
    if len(cooldown_cache) > 500: cooldown_cache.clear()
    cooldown_cache[uid] = now
    return False

async def edit_or_send(query, text, reply_markup=None):
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        try: await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
        except Exception: pass

def build_main_menu_content(uid):
    u = get_u(uid)
    mode_tag = f"\n⚡ <b>Kho xem:</b> <code>{admin_view_mode.get(uid, 'seller').upper()}</code>" if is_admin(uid) else ""
    text = (
        f"✨ <b>CHÀO MỪNG BẠN ĐẾN VỚI BOT BÁN HÀNG</b> 💫\n\n"
        f"<blockquote>"
        f"🔔 <b>Kênh thông báo:</b> <a href='{CHANNEL_URL}'>Mizze Store</a>\n"
        f"☑️ <b>Admin:</b> <a href='{ADMIN_CONTACT}'>Le Bin</a>\n"
        f"➖ ➖ ➖ ➖ ➖ ➖ ➖ ➖\n"
        f"⏱️ <b>Tổng nạp:</b> <code>{u['total_deposit']:,}đ</code>\n"
        f"📊 <b>Tổng nạp tháng:</b> <code>{u['month_deposit']:,}đ</code>\n"
        f"💳 <b>Số dư:</b> <code>{u['balance']:,}đ</code>"
        f"{mode_tag}"
        f"</blockquote>"
    )
    kb = [
        [InlineKeyboardButton("👤 TÀI KHOẢN", callback_data='menu_account'), InlineKeyboardButton("🛒 CỬA HÀNG", callback_data='menu_shop')],
        [InlineKeyboardButton("💰 NẠP TIỀN", callback_data='menu_deposit'), InlineKeyboardButton("📊 LỊCH SỬ", callback_data='menu_history_hub')],
        [InlineKeyboardButton("🔑 GET KEY", callback_data='my_keys'), InlineKeyboardButton("📥 TẢI FILE", url=CLIENT_GROUP_LINK)],
        [InlineKeyboardButton("💬 HỖ TRỢ / LIÊN HỆ", url=SUPPORT_CONTACT)]
    ]
    if is_seller(uid) and not is_admin(uid):
        kb.insert(3, [InlineKeyboardButton("📈 DOANH THU SELLER", callback_data='seller_stats')])
    if is_admin(uid):
        kb.append([InlineKeyboardButton("⚙️ QUẢN TRỊ ADMIN", callback_data='admin_panel')])
    return text, InlineKeyboardMarkup(kb)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_start=False):
    uid = update.effective_user.id
    save_data()
    if not db["bot_active"] and not is_admin(uid):
        msg = "🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ</b>\n<blockquote>Vui lòng quay lại sau!</blockquote>"
        if update.message: await update.message.reply_text(msg, parse_mode="HTML")
        elif update.callback_query: await edit_or_send(update.callback_query, msg)
        return

    text, kb = build_main_menu_content(uid)
    if is_start and update.message:
        l_msg = await update.message.reply_text("✨ <i>Đang tải giao diện...</i>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        try: await l_msg.delete()
        except Exception: pass
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif update.message: await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif update.callback_query: await edit_or_send(update.callback_query, text, kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["users"][str(update.effective_user.id)] = True
    get_u(update.effective_user.id)
    save_data()
    await show_main_menu(update, context, is_start=True)

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u, is_s = get_u(update.effective_user.id), is_seller(update.effective_user.id)
    p = db["seller_prices"] if is_s else db["prices"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ 1H: {p['1h']:,}đ [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 1D: {p['1d']:,}đ [{len(db['s_1d'])}]", callback_data='shop_1d')],
        [InlineKeyboardButton(f"👑 7D: {p['7d']:,}đ [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 30D: {p['30d']:,}đ [{len(db['s_30d'])}]", callback_data='shop_30d')],
        [InlineKeyboardButton("💸 Nạp Tiền", callback_data='menu_deposit'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ])
    await update.message.reply_text(f"🛒 <b>CỬA HÀNG HACK VIP</b>\n<blockquote>💎 Số dư: <code>{u['balance']:,}đ</code></blockquote>", reply_markup=kb, parse_mode="HTML")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 <b>HƯỚNG DẪN:</b>\n<blockquote>1. Chọn Nạp tiền (Mã QR tích hợp ID của bạn).\n2. Vào Cửa hàng mua key.\n3. Nhấn nút Copy để lấy key.</blockquote>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]]), parse_mode="HTML")

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(f"🆔 <b>ID của bạn:</b> <code>{uid}</code>", reply_markup=InlineKeyboardMarkup([[make_copy_btn("📋 Copy ID", str(uid))]]), parse_mode="HTML")

async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_u(uid)
    await update.message.reply_text(f"👤 <b>TÀI KHOẢN</b>\n<blockquote>ID: <code>{uid}</code>\nSố dư: <code>{u['balance']:,}đ</code>\nTổng nạp: <code>{u['total_deposit']:,}đ</code></blockquote>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]]), parse_mode="HTML")

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id): await show_admin_panel(update.message, update.effective_user.id, is_edit=False)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        tot_k = len(db['s_1h']) + len(db['s_1d']) + len(db['s_7d']) + len(db['s_30d'])
        await update.message.reply_text(f"📊 <b>THỐNG KÊ HỆ THỐNG</b>\n<blockquote>User: {len(db['users'])}\nDoanh thu: {db['total_rev']:,}đ\nTồn kho: {tot_k} key</blockquote>", parse_mode="HTML")

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id): await update.message.reply_text(f"👥 Tổng User: <code>{len(db['users'])}</code>", parse_mode="HTML")

async def cmd_thongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        admin_state[update.effective_user.id] = 'broadcast_msg'
        await update.message.reply_text("📢 Nhập nội dung thông báo:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data='cancel_state')]]), parse_mode="HTML")

async def show_admin_panel(target_msg, uid, is_edit=True):
    st, cur = ("🟢 Hoạt động" if db["bot_active"] else "🔴 Bảo trì"), admin_view_mode.get(uid, 'seller')
    text = f"⚙️ <b>QUẢN TRỊ ADMIN</b>\n<blockquote>Trạng thái: <b>{st}</b>\nKho xem hiện tại: <b>{cur.upper()}</b></blockquote>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔄 Đổi kho xem ({cur.upper()})", callback_data='ad_switch_view')],
        [InlineKeyboardButton("📢 Gửi Thông Báo", callback_data='ad_broadcast'), InlineKeyboardButton("🔴 Bật/Tắt Bảo Trì", callback_data='toggle_bot_status')],
        [InlineKeyboardButton("📦 Thêm Key", callback_data='ad_checkkey'), InlineKeyboardButton("💰 Sửa Giá", callback_data='ad_price_menu')],
        [InlineKeyboardButton("💸 Cộng/Trừ Tiền", callback_data='ad_bal'), InlineKeyboardButton("👥 Doanh Thu Seller", callback_data='ad_manageseller')],
        [InlineKeyboardButton("💾 Tải File Backup", callback_data='ad_get_backup'), InlineKeyboardButton("📥 Khôi Phục", callback_data='ad_restore_prompt')],
        [InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ])
    if is_edit: await edit_or_send(target_msg, text, kb)
    else: await target_msg.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if check_spam(uid):
        await query.answer("⚠️ Thao tác quá nhanh!", show_alert=True)
        return
    await query.answer()
    u, data, is_s = get_u(uid), query.data, is_seller(uid)
    p = db["seller_prices"] if is_s else db["prices"]

    if data == 'cancel_state':
        admin_state.pop(uid, None)
        await show_main_menu(update, context)
    elif data == 'back_menu': await show_main_menu(update, context)
    elif data == 'menu_account':
        text = f"👤 <b>TÀI KHOẢN</b>\n<blockquote>ID: <code>{uid}</code>\nSố dư: <code>{u['balance']:,}đ</code>\nTổng nạp: <code>{u['total_deposit']:,}đ</code></blockquote>"
        await edit_or_send(query, text, InlineKeyboardMarkup([[make_copy_btn("📋 Copy ID", str(uid))], [InlineKeyboardButton("🔑 Kho Key Đã Mua", callback_data='my_keys'), InlineKeyboardButton("📊 Lịch Sử", callback_data='menu_history_hub')], [InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]]))
    
    elif data == 'my_keys':
        kb_keys = []
        if u['my_keys']:
            for idx, item in enumerate(reversed(u['my_keys'][-12:]), 1):
                clean_k = item.split('] ')[-1] if '] ' in item else item
                label = item.split('] ')[0] + ']' if '] ' in item else '[KEY]'
                kb_keys.append([make_copy_btn(f"📋 Copy {label} {clean_k[:14]}...", clean_k)])
            keys_block = "<i>Nhấn nút Copy bên dưới để lấy key:</i>"
        else: keys_block = "<i>Bạn chưa mua key nào.</i>"
        kb_keys.append([InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')])
        await edit_or_send(query, f"🔑 <b>KHO KEY ĐÃ MUA</b>\n<blockquote>{keys_block}</blockquote>", InlineKeyboardMarkup(kb_keys))

    elif data == 'menu_history_hub':
        await edit_or_send(query, f"📊 <b>LỊCH SỬ GIAO DỊCH</b>\n<blockquote>Số dư: <code>{u['balance']:,}đ</code></blockquote>", InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ Lịch Sử Mua", callback_data='hist_buy')], [InlineKeyboardButton("💳 Lịch Sử Nạp", callback_data='hist_deposit')], [InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]]))
    elif data == 'hist_buy':
        b_list = "\n".join(reversed(u['buy_history'][-10:])) if u['buy_history'] else "<i>Trống.</i>"
        await edit_or_send(query, f"🛍️ <b>LỊCH SỬ MUA KEY</b>\n<blockquote>{b_list}</blockquote>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_history_hub')]]))
    elif data == 'hist_deposit':
        h_list = "\n".join(reversed(u['deposit_history'][-10:])) if u['deposit_history'] else "<i>Trống.</i>"
        await edit_or_send(query, f"💳 <b>LỊCH SỬ NẠP TIỀN</b>\n<blockquote>{h_list}</blockquote>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_history_hub')]]))
    elif data == 'seller_stats':
        s_info = db["sellers"].get(str(uid), {"daily_rev": 0, "target": 500000})
        await edit_or_send(query, f"📈 <b>DOANH THU SELLER</b>\n<blockquote>• Doanh thu: <code>{s_info['daily_rev']:,}đ</code>\n• Chỉ tiêu: <code>{s_info['target']:,}đ</code></blockquote>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]]))
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ 1H: {p['1h']:,}đ [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 1D: {p['1d']:,}đ [{len(db['s_1d'])}]", callback_data='shop_1d')],
            [InlineKeyboardButton(f"👑 7D: {p['7d']:,}đ [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 30D: {p['30d']:,}đ [{len(db['s_30d'])}]", callback_data='shop_30d')],
            [InlineKeyboardButton("💸 Nạp Tiền", callback_data='menu_deposit'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛒 <b>CỬA HÀNG HACK VIP</b>\n<blockquote>Số dư: <code>{u['balance']:,}đ</code></blockquote>", kb)
    elif data.startswith('shop_'):
        kt = data.split('_')[1]
        price, kho = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}[kt]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Mua 1 Key", callback_data=f"buyq_{kt}_1"), InlineKeyboardButton("Mua 5 Key", callback_data=f"buyq_{kt}_5")],
            [InlineKeyboardButton("✏️ Nhập Số Lượng", callback_data=f"buyq_custom_{kt}")],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_shop')]
        ])
        await edit_or_send(query, f"📦 <b>GÓI {kt.upper()}</b>\n<blockquote>Giá: <code>{price:,}đ</code> | Kho: <code>{len(kho)}</code></blockquote>", kb)
    elif data.startswith('buyq_custom_'):
        admin_state[uid] = f"buy_custom_{data.split('_')[2]}"
        await edit_or_send(query, "💬 Nhập số lượng cần mua:", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_shop')]]))
    elif data.startswith('buyq_'):
        _, kt, qty = data.split('_')
        await process_purchase(query, context, uid, kt, int(qty))
    elif data == 'menu_deposit':
        kb_dep = InlineKeyboardMarkup([
            [InlineKeyboardButton("10.000đ", callback_data='pre_qr_10000'), InlineKeyboardButton("50.000đ", callback_data='pre_qr_50000')],
            [InlineKeyboardButton("100.000đ", callback_data='pre_qr_100000'), InlineKeyboardButton("200.000đ", callback_data='pre_qr_200000')],
            [InlineKeyboardButton("✏️ Nhập Số Tiền", callback_data='pre_qr_custom')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]
        ])
        await edit_or_send(query, "💸 <b>NẠP TIỀN TỰ ĐỘNG</b>\n<blockquote>Mã QR tích hợp sẵn ID của bạn:</blockquote>", kb_dep)
    elif data.startswith('pre_qr_'):
        sub = data.replace('pre_qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, "💬 Nhập số tiền cần nạp:", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]]))
            return
        await send_qr_direct(query, context, uid, int(sub))
    elif data == 'admin_panel' and is_admin(uid): await show_admin_panel(query, uid, is_edit=True)
    elif data == 'ad_switch_view' and is_admin(uid):
        admin_view_mode[uid] = 'member' if admin_view_mode.get(uid, 'seller') == 'seller' else 'seller'
        await show_admin_panel(query, uid, is_edit=True)
    elif data == 'ad_broadcast' and is_admin(uid):
        admin_state[uid] = 'broadcast_msg'
        await edit_or_send(query, "📢 Nhập nội dung thông báo:", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data='admin_panel')]]))
    elif data == 'toggle_bot_status' and is_admin(uid):
        db["bot_active"] = not db["bot_active"]
        save_data()
        await show_admin_panel(query, uid, is_edit=True)
    elif data == 'ad_price_menu' and is_admin(uid):
        await edit_or_send(query, "💰 Chọn bảng giá:", InlineKeyboardMarkup([[InlineKeyboardButton("Member", callback_data='set_type_mem'), InlineKeyboardButton("Seller", callback_data='set_type_sel')], [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]]))
    elif data == 'set_type_mem' and is_admin(uid):
        await edit_or_send(query, "🏷️ Gói Member:", InlineKeyboardMarkup([[InlineKeyboardButton("1H", callback_data='pm_1h'), InlineKeyboardButton("1D", callback_data='pm_1d')], [InlineKeyboardButton("7D", callback_data='pm_7d'), InlineKeyboardButton("30D", callback_data='pm_30d')], [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_price_menu')]]))
    elif data == 'set_type_sel' and is_admin(uid):
        await edit_or_send(query, "👑 Gói Seller:", InlineKeyboardMarkup([[InlineKeyboardButton("1H", callback_data='ps_1h'), InlineKeyboardButton("1D", callback_data='ps_1d')], [InlineKeyboardButton("7D", callback_data='ps_7d'), InlineKeyboardButton("30D", callback_data='ps_30d')], [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_price_menu')]]))
    elif data.startswith('pm_') and is_admin(uid):
        admin_state[uid] = f"setprice_mem_{data.replace('pm_', '')}"
        await edit_or_send(query, "💬 Nhập giá Member mới:")
    elif data.startswith('ps_') and is_admin(uid):
        admin_state[uid] = f"setprice_sel_{data.replace('ps_', '')}"
        await edit_or_send(query, "💬 Nhập giá Seller mới:")
    elif data == 'ad_get_backup' and is_admin(uid):
        save_data()
        try:
            with open(DB_FILE, "rb") as f:
                await context.bot.send_document(chat_id=uid, document=f, filename="database_backup.json", caption="🛡️ <b>[BACKUP FILE]</b>")
            await query.answer("Đã gửi file backup!", show_alert=True)
        except Exception: pass
    elif data == 'ad_restore_prompt' and is_admin(uid):
        await edit_or_send(query, "📥 Gửi file `database.json` vào đây để khôi phục!", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]]))
    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, "💬 Nhập: <code>[ID] [Số_tiền]</code>")
    elif data == 'ad_manageseller' and is_admin(uid):
        s_text = "👥 <b>QUẢN LÝ SELLER</b>\n<blockquote>"
        for s_id, s_info in db["sellers"].items():
            s_text += f"• ID: <code>{s_id}</code> — <b>{s_info.get('daily_rev',0):,}đ</b> / {s_info.get('target',500000):,}đ\n"
        if not db["sellers"]: s_text += "<i>Trống.</i>"
        s_text += "</blockquote>"
        await edit_or_send(query, s_text, InlineKeyboardMarkup([[InlineKeyboardButton("➕ Thêm Seller", callback_data='add_seller_prompt')], [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]]))
    elif data == 'add_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'add_seller_id'
        await edit_or_send(query, "💬 Nhập: <code>[ID] [Chỉ_tiêu]</code>")
    elif data == 'ad_checkkey' and is_admin(uid):
        await edit_or_send(query, "📦 Chọn kho thêm key:", InlineKeyboardMarkup([[InlineKeyboardButton("1H", callback_data='k_s1h'), InlineKeyboardButton("1D", callback_data='k_s1d')], [InlineKeyboardButton("7D", callback_data='k_s7d'), InlineKeyboardButton("30D", callback_data='k_s30d')], [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]]))
    elif data.startswith('k_') and is_admin(uid):
        k_type = data.replace('k_', '')
        admin_state[uid] = f"addk_{k_type}"
        await edit_or_send(query, f"📦 Gửi key kho <b>{k_type.upper()}</b>:", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_checkkey')]]))

async def send_qr_direct(query, context, uid, amount):
    memo = f"NAP {uid}"
    photo_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo={quote(memo)}&accountName={quote(ACCOUNT_NAME)}"
    text = f"💳 <b>QR NẠP {amount:,}Đ</b>\n<blockquote>STK: <code>{ACCOUNT_NO}</code>\nNội dung (Đã gắn ID): <code>{memo}</code></blockquote>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Mở Ảnh QR", url=photo_url)], [InlineKeyboardButton("🔄 Kiểm Tra Số Dư", callback_data='menu_account'), InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]])
    try:
        await query.message.delete()
        await context.bot.send_photo(chat_id=uid, photo=photo_url, caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(chat_id=uid, text=text + f"\n\n🔗 <a href='{photo_url}'>Mở ảnh QR</a>", reply_markup=kb, parse_mode="HTML")

async def process_purchase(query, context, uid, kt, qty):
    with buy_lock:
        u, is_s = get_u(uid), is_seller(uid)
        p = db["seller_prices"] if is_s else db["prices"]
        if qty <= 0 or qty > 100:
            await query.answer("❌ Số lượng không hợp lệ!", show_alert=True)
            return
        price, kho = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}[kt]
        total = price * qty
        if len(kho) < qty:
            await query.answer(f"❌ Kho không đủ ({len(kho)} key)!", show_alert=True)
            return
        if u['balance'] < total:
            await query.answer("❌ Số dư không đủ!", show_alert=True)
            return

        b_before = u['balance']
        u['balance'] -= total
        b_after = u['balance']
        db["total_rev"] += total
        if is_s and not is_admin(uid): db["sellers"][str(uid)]["daily_rev"] = db["sellers"][str(uid)].get("daily_rev", 0) + total

        keys_bought = [kho.pop(0) for _ in range(qty)]
        for k in keys_bought: u['my_keys'].append(f"[{kt.upper()}] {k}")
        t_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        u['buy_history'].append(f"• <b>[{t_str}]</b> Mua <code>{qty}x {kt.upper()}</code> (-{total:,}đ)")
        save_data()

    try:
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=f"🛍️ <b>MUA HÀNG:</b> ID <code>{uid}</code> mua {qty}x {kt.upper()} (-{total:,}đ)\n💰 Số dư còn: <code>{b_after:,}đ</code>", parse_mode="HTML")
    except Exception: pass

    kb_buy = []
    for k in keys_bought:
        kb_buy.append([make_copy_btn(f"📋 Copy Key: {k[:14]}...", k)])
    if len(keys_bought) > 1:
        kb_buy.append([make_copy_btn("📑 Copy Tất Cả Key", "\n".join(keys_bought))])
    kb_buy.append([InlineKeyboardButton("🔑 Kho Key", callback_data='my_keys'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')])

    keys_display = "\n".join([f"<code>{k}</code>" for k in keys_bought])
    res_text = f"✅ <b>MUA THÀNH CÔNG {qty}x {kt.upper()}!</b>\n<blockquote><b>Key của bạn:</b>\n{keys_display}\n\nĐã trừ: <code>-{total:,}đ</code>\nSố dư: <code>{b_after:,}đ</code></blockquote>"
    await edit_or_send(query, res_text, InlineKeyboardMarkup(kb_buy))

async def handle_document_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    doc = update.message.document
    if doc and doc.file_name.endswith(".json"):
        try:
            file = await context.bot.get_file(doc.file_id)
            new_db = json.loads((await file.download_as_bytearray()).decode("utf-8"))
            if "user_data" in new_db and "prices" in new_db:
                global db
                db = new_db
                save_data()
                await update.message.reply_text("✅ <b>Khôi phục database thành công!</b>", parse_mode="HTML")
        except Exception as e: await update.message.reply_text(f"❌ Lỗi: {e}")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, text = update.message.from_user.id, update.message.text
    if uid not in admin_state: return
    state = admin_state[uid]

    if state.startswith('buy_custom_'):
        admin_state.pop(uid, None)
        try:
            class DummyQuery:
                def __init__(self, msg, user): self.message, self.from_user = msg, user
                async def answer(self, *a, **kw): pass
            await process_purchase(DummyQuery(update.message, update.message.from_user), context, uid, state.replace('buy_custom_', ''), int(text.strip()))
        except Exception: await update.message.reply_text("❌ Lỗi số lượng!")
        return

    if state == 'waiting_deposit':
        admin_state.pop(uid, None)
        try:
            amt = int(text.replace(".", "").replace(",", "").strip())
            memo = f"NAP {uid}"
            photo_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amt}&addInfo={quote(memo)}&accountName={quote(ACCOUNT_NAME)}"
            await update.message.reply_photo(photo=photo_url, caption=f"💳 <b>QR NẠP {amt:,}Đ</b>\nNội dung: <code>{memo}</code>", parse_mode="HTML")
        except Exception: await update.message.reply_text("❌ Số tiền không hợp lệ!")
        return

    if not is_admin(uid): return
    if state == 'broadcast_msg':
        admin_state.pop(uid, None)
        cnt = 0
        for t_uid in list(db["users"].keys()):
            try:
                await context.bot.send_message(chat_id=int(t_uid), text=f"📢 <b>THÔNG BÁO</b>\n<blockquote>{text}</blockquote>", parse_mode="HTML")
                cnt += 1
                await asyncio.sleep(0.03)
            except Exception: pass
        await update.message.reply_text(f"✅ Đã gửi tới <code>{cnt}</code> user.", parse_mode="HTML")
        return

    if state.startswith('setprice_mem_') or state.startswith('setprice_sel_'):
        is_m = state.startswith('setprice_mem_')
        pk = state.replace('setprice_mem_' if is_m else 'setprice_sel_', '')
        admin_state.pop(uid, None)
        try:
            db["prices" if is_m else "seller_prices"][pk] = int(text.replace(".", "").strip())
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá gói {pk.upper()}!", parse_mode="HTML")
        except Exception: await update.message.reply_text("❌ Giá lỗi!")
        return

    if state.startswith('addk_'):
        k_type = state.replace('addk_', '')
        admin_state.pop(uid, None)
        target = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}.get(k_type)
        if target is not None:
            added = 0
            for line in text.split('\n'):
                ckey = line.strip()
                if ckey and ckey not in target:
                    target.append(ckey)
                    added += 1
            save_data()
            await update.message.reply_text(f"✅ Đã thêm <code>+{added} key</code> vào kho {k_type.upper()}!", parse_mode="HTML")
        return

    if state == 'add_bal':
        admin_state.pop(uid, None)
        try:
            tid, amt = text.split()
            tid, amt = int(tid), int(amt)
            u = get_u(tid)
            u['balance'] += amt
            if amt > 0: u['total_deposit'] += amt
            save_data()
            await update.message.reply_text(f"✅ Đã điều chỉnh số dư cho ID <code>{tid}</code>!", parse_mode="HTML")
        except Exception: await update.message.reply_text("❌ Sai cú pháp!")
        return

    if state == 'add_seller_id':
        admin_state.pop(uid, None)
        try:
            parts = text.split()
            db["sellers"][str(parts[0])] = {"daily_rev": 0, "target": int(parts[1]) if len(parts) > 1 else 500000}
            save_data()
            await update.message.reply_text("✅ Thêm Seller thành công!", parse_mode="HTML")
        except Exception: await update.message.reply_text("❌ Sai cú pháp!")
        return

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "OK", 200

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
                    b_before = u['balance']
                    u['balance'] += amt
                    u['total_deposit'] += amt
                    u['month_deposit'] += amt
                    b_after = u['balance']
                    db["total_rev"] += amt
                    t_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    u['deposit_history'].append(f"• <b>[{t_str}]</b> Nạp Auto <code>+{amt:,}đ</code> (Số dư: <code>{b_after:,}đ</code>)")
                    save_data()
                try:
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": tid, "text": f"🎉 <b>NẠP THÀNH CÔNG +{amt:,}đ!</b>\nSố dư mới: <code>{b_after:,}đ</code>", "parse_mode": "HTML"})
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": LOG_GROUP_ID, "text": f"💳 <b>NẠP TIỀN THÀNH CÔNG:</b> ID <code>{tid}</code> vừa nạp <code>+{amt:,}đ</code>\n💎 Số dư hiện tại: <code>{b_after:,}đ</code>", "parse_mode": "HTML"})
                except Exception: pass
    return jsonify({"success": True}), 200

def run_flask(): flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Mở shop"),
        BotCommand("shop", "Cửa hàng"),
        BotCommand("help", "Hướng dẫn"),
        BotCommand("id", "Xem ID"),
        BotCommand("me", "Tài khoản"),
        BotCommand("admin", "Quản trị"),
        BotCommand("stats", "Thống kê"),
        BotCommand("users", "Số user"),
        BotCommand("thongbao", "Thông báo"),
    ])

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