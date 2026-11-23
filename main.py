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

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
DB_FILE = "database.json"

buy_lock = threading.Lock()
admin_state = {}
cooldown_cache = {}
admin_view_mode = {}

PROXY_KEYS = ["1h", "1d", "3d", "7d", "30d", "90d"]
TIPA_KEYS = ["7d", "30d"]

def load_data():
    default_data = {
        "users": {},
        "user_data": {},
        "sellers": {},
        "proxy_stocks": {"1h": [], "1d": [], "3d": [], "7d": [], "30d": [], "90d": []},
        "tipa_stocks": {"7d": [], "30d": []},
        "proxy_prices": {"1h": 5000, "1d": 20000, "3d": 12000, "7d": 70000, "30d": 150000, "90d": 350000},
        "proxy_seller_prices": {"1h": 5000, "1d": 10000, "3d": 10000, "7d": 45000, "30d": 70000, "90d": 200000},
        "tipa_prices": {"7d": 80000, "30d": 180000},
        "tipa_seller_prices": {"7d": 55000, "30d": 120000},
        "total_rev": 2905000,
        "today_rev": 0,
        "bot_active": True,
        "last_reset_date": datetime.datetime.now().strftime("%Y-%m-%d")
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v

                # Di chuyển dữ liệu kho cũ s_1h..s_90d sang proxy_stocks nếu có
                legacy_map = {"1h": "s_1h", "1d": "s_1d", "3d": "s_3d", "7d": "s_7d", "30d": "s_30d", "90d": "s_90d"}
                for pkg, old_k in legacy_map.items():
                    if old_k in data and isinstance(data[old_k], list) and data[old_k]:
                        for item in data[old_k]:
                            if item not in data["proxy_stocks"][pkg]:
                                data["proxy_stocks"][pkg].append(item)

                # Đồng bộ giá cũ sang proxy_prices nếu có
                if "prices" in data and isinstance(data["prices"], dict):
                    for pkg, val in data["prices"].items():
                        if pkg in data["proxy_prices"]:
                            data["proxy_prices"][pkg] = val
                if "seller_prices" in data and isinstance(data["seller_prices"], dict):
                    for pkg, val in data["seller_prices"].items():
                        if pkg in data["proxy_seller_prices"]:
                            data["proxy_seller_prices"][pkg] = val

                for sub_k in ["proxy_stocks", "tipa_stocks", "proxy_prices", "proxy_seller_prices", "tipa_prices", "tipa_seller_prices"]:
                    for item_k, item_v in default_data[sub_k].items():
                        if item_k not in data[sub_k]:
                            data[sub_k][item_k] = item_v

                return data
        except Exception:
            pass
    return default_data

db = load_data()

def check_daily_reset():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if db.get("last_reset_date") != today_str:
        db["today_rev"] = 0
        for s_info in db["sellers"].values():
            s_info["daily_rev"] = 0
        db["last_reset_date"] = today_str

def save_data():
    try:
        check_daily_reset()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
        gc.collect()
    except Exception:
        pass

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {
            'balance': 0, 'total_deposit': 0, 'month_deposit': 0,
            'deposit_history': [], 'buy_history': [], 'my_keys': []
        }
        save_data()
    u = db["user_data"][uid_str]
    for key in ['month_deposit', 'deposit_history', 'buy_history', 'my_keys']:
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
    if uid in cooldown_cache and now - cooldown_cache[uid] < 0.2:
        return True
    if len(cooldown_cache) > 500:
        cooldown_cache.clear()
    cooldown_cache[uid] = now
    return False

def get_category_stock_and_price(category, pkg, uid):
    s_mode = is_seller(uid)
    if category == "proxy":
        kho = db["proxy_stocks"].get(pkg, [])
        price_dict = db["proxy_seller_prices"] if s_mode else db["proxy_prices"]
        price = price_dict.get(pkg, 5000)
        label = f"PROXY {pkg.upper()}"
    else:
        kho = db["tipa_stocks"].get(pkg, [])
        price_dict = db["tipa_seller_prices"] if s_mode else db["tipa_prices"]
        price = price_dict.get(pkg, 80000)
        label = f"TIPA {pkg.upper()}"
    return kho, price, label

async def safe_send_or_edit(query_or_update, text, reply_markup=None):
    try:
        if hasattr(query_or_update, 'message') and query_or_update.message:
            await query_or_update.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
            return
    except Exception:
        try:
            if hasattr(query_or_update, 'message') and query_or_update.message:
                await query_or_update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
                return
            elif hasattr(query_or_update, 'reply_text'):
                await query_or_update.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
                return
        except Exception:
            pass

def get_main_menu_markup(uid):
    u = get_u(uid)
    mode_tag = f"\n⚡ <b>Kho xem:</b> <code>{admin_view_mode.get(uid, 'seller').upper()}</code>" if is_admin(uid) else ""
    text = (
        f"🛍️ <b>BOT BÁN KEY TỰ ĐỘNG 24/7</b> 🌐\n\n"
        f"<blockquote>"
        f"👑 <b>Admin:</b> <a href='{ADMIN_CONTACT}'>@lebindz</a>\n"
        f"📢 <b>Kênh:</b> <a href='{CHANNEL_URL}'>Tham Gia Kênh Mizze Store</a>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>Tổng Nạp:</b> <code>{u['total_deposit']:,}đ</code>\n"
        f"💰 <b>Số Dư:</b> <code>{u['balance']:,}đ</code>"
        f"{mode_tag}"
        f"</blockquote>"
    )
    kb = [
        [InlineKeyboardButton("👤 Tài khoản", callback_data='menu_account'), InlineKeyboardButton("🛒 Cửa hàng", callback_data='menu_shop')],
        [InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit'), InlineKeyboardButton("📊 Lịch sử", callback_data='menu_history_hub')],
        [InlineKeyboardButton("🔑 Kho Key Cũ", callback_data='my_keys'), InlineKeyboardButton("📥 Tải File Hack", url=CLIENT_GROUP_LINK)],
        [InlineKeyboardButton("💬 Hỗ trợ / Liên hệ", url=SUPPORT_CONTACT)]
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
        if update.message:
            await update.message.reply_text(msg, parse_mode="HTML")
        elif update.callback_query:
            await safe_send_or_edit(update.callback_query, msg)
        return

    text, kb = get_main_menu_markup(uid)
    if is_start and update.message:
        l_msg = await update.message.reply_text("✨ <i>Đang tải hệ thống...</i>", parse_mode="HTML")
        await asyncio.sleep(0.15)
        try:
            await l_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif update.callback_query:
        await safe_send_or_edit(update.callback_query, text, kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["users"][str(update.effective_user.id)] = True
    get_u(update.effective_user.id)
    save_data()
    await show_main_menu(update, context, is_start=True)

async def show_shop_menu(query_or_update):
    uid = query_or_update.from_user.id if hasattr(query_or_update, 'from_user') else query_or_update.effective_user.id
    u = get_u(uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 KHO PROXY", callback_data='shop_cat_proxy'), InlineKeyboardButton("⚡ GÓI TIPA (7D / 30D)", callback_data='shop_cat_tipa')],
        [InlineKeyboardButton("💳 Nạp Tiền", callback_data='menu_deposit'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ])
    text = f"🛒 <b>CỬA HÀNG HACK VIP</b>\n<blockquote>💎 Số dư ví: <code>{u['balance']:,}đ</code>\nVui lòng chọn danh mục sản phẩm bên dưới:</blockquote>"
    if hasattr(query_or_update, 'callback_query') and query_or_update.callback_query:
        await safe_send_or_edit(query_or_update.callback_query, text, kb)
    elif hasattr(query_or_update, 'message') and query_or_update.message:
        await query_or_update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await safe_send_or_edit(query_or_update, text, kb)

async def show_proxy_shop(query, uid):
    u = get_u(uid)
    p = db["proxy_seller_prices"] if is_seller(uid) else db["proxy_prices"]
    s = db["proxy_stocks"]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⚡ 1H: {p['1h']:,}đ [{len(s['1h'])}]", callback_data='buy_proxy_1h'),
            InlineKeyboardButton(f"💎 1D: {p['1d']:,}đ [{len(s['1d'])}]", callback_data='buy_proxy_1d')
        ],
        [
            InlineKeyboardButton(f"⏱️ 3D: {p['3d']:,}đ [{len(s['3d'])}]", callback_data='buy_proxy_3d'),
            InlineKeyboardButton(f"👑 7D: {p['7d']:,}đ [{len(s['7d'])}]", callback_data='buy_proxy_7d')
        ],
        [
            InlineKeyboardButton(f"🚀 30D: {p['30d']:,}đ [{len(s['30d'])}]", callback_data='buy_proxy_30d'),
            InlineKeyboardButton(f"🌟 90D: {p['90d']:,}đ [{len(s['90d'])}]", callback_data='buy_proxy_90d')
        ],
        [InlineKeyboardButton("◀️ Danh Mục", callback_data='menu_shop'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ])
    text = f"🌐 <b>CỬA HÀNG PROXY</b>\n<blockquote>💎 Số dư ví: <code>{u['balance']:,}đ</code>\nChọn gói thời gian Proxy cần mua:</blockquote>"
    await safe_send_or_edit(query, text, kb)

async def show_tipa_shop(query, uid):
    u = get_u(uid)
    p = db["tipa_seller_prices"] if is_seller(uid) else db["tipa_prices"]
    s = db["tipa_stocks"]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"👑 7D: {p['7d']:,}đ [{len(s['7d'])}]", callback_data='buy_tipa_7d'),
            InlineKeyboardButton(f"🚀 30D: {p['30d']:,}đ [{len(s['30d'])}]", callback_data='buy_tipa_30d')
        ],
        [InlineKeyboardButton("◀️ Danh Mục", callback_data='menu_shop'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ])
    text = f"⚡ <b>CỬA HÀNG TIPA</b>\n<blockquote>💎 Số dư ví: <code>{u['balance']:,}đ</code>\nChọn gói Tipa (7 ngày / 30 ngày):</blockquote>"
    await safe_send_or_edit(query, text, kb)

async def render_deposit(query):
    uid = query.from_user.id
    u = get_u(uid)
    kb_dep = InlineKeyboardMarkup([
        [InlineKeyboardButton("10.000đ", callback_data='pre_qr_10000'), InlineKeyboardButton("20.000đ", callback_data='pre_qr_20000')],
        [InlineKeyboardButton("45.000đ", callback_data='pre_qr_45000'), InlineKeyboardButton("70.000đ", callback_data='pre_qr_70000')],
        [InlineKeyboardButton("100.000đ", callback_data='pre_qr_100000'), InlineKeyboardButton("150.000đ", callback_data='pre_qr_150000')],
        [InlineKeyboardButton("300.000đ", callback_data='pre_qr_300000')],
        [InlineKeyboardButton("✏️ Nhập Số Tiền Tự Chọn", callback_data='pre_qr_custom')],
        [InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ])
    text = f"💳 <b>NẠP TIỀN TỰ ĐỘNG QUA QR</b>\n<blockquote>Số dư hiện tại: <code>{u['balance']:,}đ</code>\nChọn nhanh mệnh giá nạp bên dưới:</blockquote>"
    await safe_send_or_edit(query, text, kb_dep)

async def render_admin_panel(query_or_update):
    uid = query_or_update.from_user.id if hasattr(query_or_update, 'from_user') else query_or_update.effective_user.id
    if not is_admin(uid):
        return
    check_daily_reset()
    mode = admin_view_mode.get(uid, 'seller').upper()
    text = (
        f"⚙️ <b>QUẢN TRỊ HỆ THỐNG ADMIN</b>\n\n"
        f"<blockquote>"
        f"📅 <b>Doanh thu hôm nay:</b> <code>{db['today_rev']:,}đ</code>\n"
        f"📊 <b>Tổng doanh thu:</b> <code>{db['total_rev']:,}đ</code>\n"
        f"👥 <b>Tổng thành viên:</b> <code>{len(db['users'])}</code>\n"
        f"🟢 <b>Trạng thái bot:</b> <code>{'HOẠT ĐỘNG' if db['bot_active'] else 'BẢO TRÌ'}</code>\n"
        f"⚡ <b>Chế độ xem:</b> <code>{mode}</code>"
        f"</blockquote>"
    )
    kb = [
        [InlineKeyboardButton("🔄 Chuyển Chế Độ Xem", callback_data='ad_switch_view'), InlineKeyboardButton("📢 Gửi Thông Báo", callback_data='ad_broadcast')],
        [InlineKeyboardButton("💰 Sửa Bảng Giá", callback_data='ad_price_menu'), InlineKeyboardButton("📦 Thêm Kho Key", callback_data='ad_checkkey')],
        [InlineKeyboardButton("👥 Quản Lý Seller", callback_data='ad_manageseller'), InlineKeyboardButton("💳 Cộng / Trừ Tiền", callback_data='ad_bal')],
        [InlineKeyboardButton("🛡️ Sao Lưu (Backup)", callback_data='ad_get_backup'), InlineKeyboardButton("📥 Khôi Phục (Restore)", callback_data='ad_restore_prompt')],
        [InlineKeyboardButton(f"🔄 Bật/Tắt Bot: {'Đang Bật' if db['bot_active'] else 'Đang Tắt'}", callback_data='toggle_bot_status')],
        [InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
    ]
    await safe_send_or_edit(query_or_update, text, InlineKeyboardMarkup(kb))

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_shop_menu(update)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if check_spam(uid):
        try:
            await query.answer("⚠️ Thao tác quá nhanh!", show_alert=True)
        except Exception:
            pass
        return
    try:
        await query.answer()
    except Exception:
        pass

    u, data = get_u(uid), query.data

    if data == 'cancel_state':
        admin_state.pop(uid, None)
        await show_main_menu(update, context)
    elif data == 'back_menu':
        await show_main_menu(update, context)
    elif data == 'menu_shop':
        await show_shop_menu(query)
    elif data == 'shop_cat_proxy':
        await show_proxy_shop(query, uid)
    elif data == 'shop_cat_tipa':
        await show_tipa_shop(query, uid)
    elif data == 'menu_deposit':
        await render_deposit(query)
    elif data == 'admin_panel' and is_admin(uid):
        await render_admin_panel(query)
    elif data == 'menu_account':
        text = (
            f"👤 <b>TÀI KHOẢN CÁ NHÂN</b>\n"
            f"<blockquote>🆔 ID: <code>{uid}</code>\n"
            f"💳 Số dư: <code>{u['balance']:,}đ</code>\n"
            f"⏱️ Tổng nạp: <code>{u['total_deposit']:,}đ</code>\n"
            f"📦 Tổng key đã mua: <code>{len(u['my_keys'])} key</code></blockquote>"
        )
        kb_acc = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 Kho Key Của Bạn", callback_data='my_keys'), InlineKeyboardButton("📊 Lịch Sử", callback_data='menu_history_hub')],
            [InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
        ])
        await safe_send_or_edit(query, text, kb_acc)
    elif data == 'my_keys':
        kb_keys = []
        if u['my_keys']:
            for idx, item in enumerate(reversed(u['my_keys'][-15:]), 1):
                kb_keys.append([InlineKeyboardButton(f"🔑 Lấy Key Cũ [{idx}] {item[:22]}...", callback_data=f"getkey_{idx}")])
            keys_block = f"<i>Bạn đã sở hữu tổng cộng <b>{len(u['my_keys'])}</b> key. Bấm vào nút bên dưới để trích xuất:</i>"
        else:
            keys_block = "<i>Bạn chưa có lịch sử mua key nào.</i>"
        kb_keys.append([InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')])
        await safe_send_or_edit(query, f"🔑 <b>KHO KEY CỦA BẠN</b>\n<blockquote>{keys_block}</blockquote>", InlineKeyboardMarkup(kb_keys))
    elif data.startswith('getkey_'):
        idx = int(data.split('_')[1]) - 1
        rev_keys = list(reversed(u['my_keys'][-15:]))
        if 0 <= idx < len(rev_keys):
            await context.bot.send_message(
                chat_id=uid,
                text=f"🔑 <b>TRÍCH XUẤT KEY CŨ:</b>\n<blockquote><code>{rev_keys[idx]}</code></blockquote>\n<i>(Chạm vào đoạn mã trên để sao chép)</i>",
                parse_mode="HTML"
            )
        else:
            await query.answer("❌ Key không tồn tại!", show_alert=True)
    elif data == 'menu_history_hub':
        await safe_send_or_edit(
            query,
            f"📊 <b>LỊCH SỬ GIAO DỊCH</b>\n<blockquote>Số dư hiện tại: <code>{u['balance']:,}đ</code></blockquote>",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Lịch Sử Mua Key", callback_data='hist_buy'), InlineKeyboardButton("💳 Lịch Sử Nạp Tiền", callback_data='hist_deposit')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]
            ])
        )
    elif data == 'hist_buy':
        b_list = "\n".join(reversed(u['buy_history'][-10:])) if u['buy_history'] else "<i>Trống.</i>"
        await safe_send_or_edit(query, f"🛍️ <b>LỊCH SỬ MUA KEY</b>\n<blockquote>{b_list}</blockquote>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_history_hub')]]))
    elif data == 'hist_deposit':
        h_list = "\n".join(reversed(u['deposit_history'][-10:])) if u['deposit_history'] else "<i>Trống.</i>"
        await safe_send_or_edit(query, f"💳 <b>LỊCH SỬ NẠP TIỀN</b>\n<blockquote>{h_list}</blockquote>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_history_hub')]]))
    elif data == 'seller_stats':
        check_daily_reset()
        s_info = db["sellers"].get(str(uid), {"daily_rev": 0, "target": 500000})
        await safe_send_or_edit(
            query,
            f"📈 <b>DOANH THU SELLER HÔM NAY</b>\n<blockquote>• Doanh thu hôm nay: <code>{s_info['daily_rev']:,}đ</code>\n• Chỉ tiêu: <code>{s_info['target']:,}đ</code></blockquote>",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='back_menu')]])
        )
    elif data.startswith('buy_proxy_') or data.startswith('buy_tipa_'):
        parts = data.split('_')
        category, pkg = parts[1], parts[2]
        kho, price, label = get_category_stock_and_price(category, pkg, uid)
        back_cb = 'shop_cat_proxy' if category == 'proxy' else 'shop_cat_tipa'
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Mua 1 Key", callback_data=f"buyq_{category}_{pkg}_1"), InlineKeyboardButton("Mua 5 Key", callback_data=f"buyq_{category}_{pkg}_5")],
            [InlineKeyboardButton("✏️ Nhập Số Lượng", callback_data=f"buyq_custom_{category}_{pkg}")],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data=back_cb)]
        ])
        await safe_send_or_edit(query, f"📦 <b>GÓI {label}</b>\n<blockquote>Giá: <code>{price:,}đ</code> | Kho sẵn: <code>{len(kho)}</code></blockquote>", kb)
    elif data.startswith('buyq_custom_'):
        parts = data.split('_')
        category, pkg = parts[2], parts[3]
        admin_state[uid] = f"buy_custom_{category}_{pkg}"
        back_cb = 'shop_cat_proxy' if category == 'proxy' else 'shop_cat_tipa'
        await safe_send_or_edit(query, "💬 <b>Nhập số lượng cần mua:</b>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data=back_cb)]]))
    elif data.startswith('buyq_'):
        _, category, pkg, qty = data.split('_')
        await process_purchase(query, context, uid, category, pkg, int(qty))
    elif data.startswith('pre_qr_'):
        sub = data.replace('pre_qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await safe_send_or_edit(query, "💬 <b>Vui lòng nhập số tiền bạn muốn nạp (ví dụ: 50000):</b>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]]))
            return
        await send_qr_direct(query, context, uid, int(sub))
    elif data == 'ad_switch_view' and is_admin(uid):
        admin_view_mode[uid] = 'member' if admin_view_mode.get(uid, 'seller') == 'seller' else 'seller'
        await render_admin_panel(query)
    elif data == 'ad_broadcast' and is_admin(uid):
        admin_state[uid] = 'broadcast_msg'
        await safe_send_or_edit(query, "📢 Nhập nội dung thông báo:", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data='admin_panel')]]))
    elif data == 'toggle_bot_status' and is_admin(uid):
        db["bot_active"] = not db["bot_active"]
        save_data()
        await render_admin_panel(query)

    # CHỈNH GIÁ CHO CẢ PROXY VÀ TIPA (MEMBER & SELLER)
    elif data == 'ad_price_menu' and is_admin(uid):
        await safe_send_or_edit(
            query,
            "💰 <b>CHỌN DANH MỤC SỬA GIÁ</b>",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Giá Proxy", callback_data='price_cat_proxy'), InlineKeyboardButton("⚡ Giá Tipa", callback_data='price_cat_tipa')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
            ])
        )
    elif data in ['price_cat_proxy', 'price_cat_tipa'] and is_admin(uid):
        cat = data.replace('price_cat_', '')
        await safe_send_or_edit(
            query,
            f"💰 <b>BẢNG GIÁ {cat.upper()}</b> — Chọn đối tượng:",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Member", callback_data=f'ptype_{cat}_mem'), InlineKeyboardButton("👑 Seller", callback_data=f'ptype_{cat}_sel')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_price_menu')]
            ])
        )
    elif data.startswith('ptype_') and is_admin(uid):
        _, cat, role = data.split('_')
        role_label = "Member" if role == "mem" else "Seller"
        if cat == "proxy":
            rows = [
                [InlineKeyboardButton("1H", callback_data=f'setp_proxy_{role}_1h'), InlineKeyboardButton("1D", callback_data=f'setp_proxy_{role}_1d'), InlineKeyboardButton("3D", callback_data=f'setp_proxy_{role}_3d')],
                [InlineKeyboardButton("7D", callback_data=f'setp_proxy_{role}_7d'), InlineKeyboardButton("30D", callback_data=f'setp_proxy_{role}_30d'), InlineKeyboardButton("90D", callback_data=f'setp_proxy_{role}_90d')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='price_cat_proxy')]
            ]
        else:
            rows = [
                [InlineKeyboardButton("7D", callback_data=f'setp_tipa_{role}_7d'), InlineKeyboardButton("30D", callback_data=f'setp_tipa_{role}_30d')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='price_cat_tipa')]
            ]
        await safe_send_or_edit(query, f"🏷️ Chọn gói <b>{cat.upper()} ({role_label})</b> cần đổi giá:", InlineKeyboardMarkup(rows))
    elif data.startswith('setp_') and is_admin(uid):
        _, cat, role, pkg = data.split('_')
        admin_state[uid] = f"setprice_{cat}_{role}_{pkg}"
        role_label = "Member" if role == "mem" else "Seller"
        await safe_send_or_edit(query, f"💬 Nhập giá mới cho <b>{cat.upper()} - {pkg.upper()} ({role_label})</b>:")

    elif data == 'ad_get_backup' and is_admin(uid):
        save_data()
        try:
            with open(DB_FILE, "rb") as f:
                await context.bot.send_document(chat_id=uid, document=f, filename="database_backup.json", caption="🛡️ <b>[BACKUP FILE]</b>")
            await query.answer("Đã gửi file backup!", show_alert=True)
        except Exception:
            pass
    elif data == 'ad_restore_prompt' and is_admin(uid):
        await safe_send_or_edit(query, "📥 Gửi file `database.json` vào đây để khôi phục!", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]]))
    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await safe_send_or_edit(query, "💬 Nhập cú pháp cộng/trừ tiền:\n<code>[ID_Khách] [+Số_tiền]</code> hoặc <code>[ID_Khách] [-Số_tiền]</code>")
    elif data == 'ad_manageseller' and is_admin(uid):
        check_daily_reset()
        s_text = "👥 <b>QUẢN LÝ SELLER</b>\n<blockquote>"
        kb_seller = [[InlineKeyboardButton("➕ Thêm Seller", callback_data='add_seller_prompt')]]
        for s_id, s_info in db["sellers"].items():
            s_text += f"• ID: <code>{s_id}</code> — Hôm nay: <b>{s_info.get('daily_rev',0):,}đ</b>\n"
            kb_seller.append([InlineKeyboardButton(f"❌ Xóa Seller {s_id}", callback_data=f"delsel_{s_id}")])
        if not db["sellers"]:
            s_text += "<i>Trống.</i>"
        s_text += "</blockquote>"
        kb_seller.append([InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')])
        await safe_send_or_edit(query, s_text, InlineKeyboardMarkup(kb_seller))
    elif data.startswith('delsel_') and is_admin(uid):
        s_id = data.replace('delsel_', '')
        if s_id in db["sellers"]:
            db["sellers"].pop(s_id)
            save_data()
            await query.answer(f"✅ Đã xóa Seller {s_id}!", show_alert=True)
        await render_admin_panel(query)
    elif data == 'add_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'add_seller_id'
        await safe_send_or_edit(query, "💬 Nhập: <code>[ID] [Chỉ_tiêu]</code>")

    # THÊM KEY VÀO KHO PROXY HOẶC TIPA
    elif data == 'ad_checkkey' and is_admin(uid):
        await safe_send_or_edit(
            query,
            "📦 <b>CHỌN KHO CẦN THÊM KEY</b>",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Kho Proxy", callback_data='stock_cat_proxy'), InlineKeyboardButton("⚡ Kho Tipa", callback_data='stock_cat_tipa')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
            ])
        )
    elif data == 'stock_cat_proxy' and is_admin(uid):
        await safe_send_or_edit(
            query,
            "📦 Chọn gói kho <b>PROXY</b>:",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("1H", callback_data='addkey_proxy_1h'), InlineKeyboardButton("1D", callback_data='addkey_proxy_1d'), InlineKeyboardButton("3D", callback_data='addkey_proxy_3d')],
                [InlineKeyboardButton("7D", callback_data='addkey_proxy_7d'), InlineKeyboardButton("30D", callback_data='addkey_proxy_30d'), InlineKeyboardButton("90D", callback_data='addkey_proxy_90d')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_checkkey')]
            ])
        )
    elif data == 'stock_cat_tipa' and is_admin(uid):
        await safe_send_or_edit(
            query,
            "📦 Chọn gói kho <b>TIPA</b>:",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("7D", callback_data='addkey_tipa_7d'), InlineKeyboardButton("30D", callback_data='addkey_tipa_30d')],
                [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_checkkey')]
            ])
        )
    elif data.startswith('addkey_') and is_admin(uid):
        _, cat, pkg = data.split('_')
        admin_state[uid] = f"addk_{cat}_{pkg}"
        back_cb = 'stock_cat_proxy' if cat == 'proxy' else 'stock_cat_tipa'
        await safe_send_or_edit(query, f"📦 Gửi danh sách key cho kho <b>{cat.upper()} {pkg.upper()}</b> (mỗi key 1 dòng):", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data=back_cb)]]))

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

async def process_purchase(query, context, uid, category, pkg, qty):
    with buy_lock:
        check_daily_reset()
        u, s_mode = get_u(uid), is_seller(uid)
        if qty <= 0 or qty > 100:
            await query.answer("❌ Số lượng không hợp lệ!", show_alert=True)
            return

        kho, price, label = get_category_stock_and_price(category, pkg, uid)
        total = price * qty
        if len(kho) < qty:
            await query.answer(f"❌ Kho không đủ ({len(kho)} key)!", show_alert=True)
            return
        if u['balance'] < total:
            await query.answer("❌ Số dư không đủ!", show_alert=True)
            return

        u['balance'] -= total
        b_after = u['balance']
        db["total_rev"] += total
        db["today_rev"] += total
        if s_mode and not is_admin(uid):
            db["sellers"][str(uid)]["daily_rev"] = db["sellers"][str(uid)].get("daily_rev", 0) + total

        keys_bought = [kho.pop(0) for _ in range(qty)]
        for k in keys_bought:
            u['my_keys'].append(f"[{label}] {k}")
        t_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        u['buy_history'].append(f"• <b>[{t_str}]</b> Mua <code>{qty}x {label}</code> (-{total:,}đ)")
        save_data()

    try:
        log_msg = (
            f"🛒 <b>[REALTIME] KHÁCH MUA HÀNG THÀNH CÔNG</b>\n"
            f"👤 <b>Khách hàng:</b> ID <code>{uid}</code>\n"
            f"📦 <b>Sản phẩm:</b> <code>{qty}x {label}</code>\n"
            f"💵 <b>Tổng tiền:</b> <code>-{total:,}đ</code>\n"
            f"💳 <b>Số dư ví còn lại:</b> <code>{b_after:,}đ</code>\n"
            f"📅 <b>Doanh thu hôm nay:</b> <code>{db['today_rev']:,}đ</code>\n"
            f"⏰ <b>Thời gian:</b> <code>{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</code>"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_msg, parse_mode="HTML")
    except Exception:
        pass

    kb_buy = [[InlineKeyboardButton("🔑 Kho Key Của Bạn", callback_data='my_keys'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]]
    keys_display = "\n".join([f"<code>{k}</code>" for k in keys_bought])
    res_text = f"✅ <b>MUA THÀNH CÔNG {qty}x {label}!</b>\n<blockquote><b>Key của bạn:</b>\n{keys_display}\n\nĐã trừ: <code>-{total:,}đ</code>\nSố dư: <code>{b_after:,}đ</code></blockquote>"
    await safe_send_or_edit(query, res_text, InlineKeyboardMarkup(kb_buy))

async def handle_document_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    doc = update.message.document
    if doc and doc.file_name.endswith(".json"):
        try:
            file = await context.bot.get_file(doc.file_id)
            new_db = json.loads((await file.download_as_bytearray()).decode("utf-8"))
            if "user_data" in new_db:
                global db
                db = new_db
                save_data()
                await update.message.reply_text("✅ <b>Khôi phục database thành công!</b>", parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, text = update.message.from_user.id, update.message.text
    if uid not in admin_state:
        return
    state = admin_state[uid]

    if state == 'waiting_deposit':
        admin_state.pop(uid, None)
        cleaned_text = re.sub(r'[^\d]', '', text)
        if not cleaned_text:
            await update.message.reply_text("❌ Số tiền không hợp lệ! Vui lòng chỉ nhập số (ví dụ: 50000).")
            return
        amt = int(cleaned_text)
        if amt <= 0:
            await update.message.reply_text("❌ Số tiền phải lớn hơn 0!")
            return
        memo = f"NAP {uid}"
        photo_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amt}&addInfo={quote(memo)}&accountName={quote(ACCOUNT_NAME)}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Mở Ảnh QR", url=photo_url)],
            [InlineKeyboardButton("🔄 Kiểm Tra Số Dư", callback_data='menu_account'), InlineKeyboardButton("🏠 Trang Chủ", callback_data='back_menu')]
        ])
        await update.message.reply_photo(photo=photo_url, caption=f"💳 <b>QR NẠP {amt:,}Đ</b>\n<blockquote>STK: <code>{ACCOUNT_NO}</code>\nNội dung: <code>{memo}</code></blockquote>", reply_markup=kb, parse_mode="HTML")
        return

    if state.startswith('buy_custom_'):
        admin_state.pop(uid, None)
        try:
            parts = state.split('_')
            category, pkg = parts[2], parts[3]
            class DummyQuery:
                def __init__(self, msg, user):
                    self.message, self.from_user = msg, user
                async def answer(self, *a, **kw):
                    pass
            cleaned_qty = re.sub(r'[^\d]', '', text)
            await process_purchase(DummyQuery(update.message, update.message.from_user), context, uid, category, pkg, int(cleaned_qty))
        except Exception:
            await update.message.reply_text("❌ Số lượng không hợp lệ!")
        return

    if not is_admin(uid):
        return
    if state == 'broadcast_msg':
        admin_state.pop(uid, None)
        cnt = 0
        for t_uid in list(db["users"].keys()):
            try:
                await context.bot.send_message(chat_id=int(t_uid), text=f"📢 <b>THÔNG BÁO</b>\n<blockquote>{text}</blockquote>", parse_mode="HTML")
                cnt += 1
                await asyncio.sleep(0.03)
            except Exception:
                pass
        await update.message.reply_text(f"✅ Đã gửi tới <code>{cnt}</code> user.", parse_mode="HTML")
        return

    if state.startswith('setprice_'):
        _, cat, role, pkg = state.split('_')
        admin_state.pop(uid, None)
        try:
            new_val = int(re.sub(r'[^\d]', '', text))
            if cat == "proxy":
                target_dict = db["proxy_prices"] if role == "mem" else db["proxy_seller_prices"]
            else:
                target_dict = db["tipa_prices"] if role == "mem" else db["tipa_seller_prices"]
            target_dict[pkg] = new_val
            save_data()
            role_label = "Member" if role == "mem" else "Seller"
            await update.message.reply_text(f"✅ Đã cập nhật giá <b>{cat.upper()} {pkg.upper()} ({role_label})</b> thành <code>{new_val:,}đ</code>!", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Giá lỗi!")
        return

    if state.startswith('addk_'):
        _, cat, pkg = state.split('_')
        admin_state.pop(uid, None)
        target = db["proxy_stocks"].get(pkg) if cat == "proxy" else db["tipa_stocks"].get(pkg)
        if target is not None:
            added = 0
            for line in text.split('\n'):
                ckey = line.strip()
                if ckey and ckey not in target:
                    target.append(ckey)
                    added += 1
            save_data()
            label = f"{cat.upper()} {pkg.upper()}"
            await update.message.reply_text(f"✅ Đã thêm <code>+{added} key</code> vào kho <b>{label}</b>!", parse_mode="HTML")
            if added > 0:
                asyncio.create_task(broadcast_new_keys(context, label, added))
        return

    if state == 'add_bal':
        admin_state.pop(uid, None)
        try:
            parts = text.split()
            tid = int(parts[0])
            raw_amt = parts[1]
            amt = int(re.sub(r'[^\d\-]', '', raw_amt))
            amt = -abs(amt) if '-' in raw_amt else abs(amt)

            u = get_u(tid)
            u['balance'] += amt
            if amt > 0:
                u['total_deposit'] += amt
            save_data()

            action_name = "cộng" if amt > 0 else "trừ"
            await update.message.reply_text(f"✅ Đã {action_name} <code>{amt:,}đ</code> cho ID <code>{tid}</code>!\nSố dư mới: <code>{u['balance']:,}đ</code>", parse_mode="HTML")
            try:
                notif_action = f"đã cộng +{amt:,}đ vào tài khoản" if amt > 0 else f"đã trừ {amt:,}đ từ tài khoản"
                await context.bot.send_message(chat_id=tid, text=f"ℹ️ <b>THÔNG BÁO SỐ DƯ:</b> Admin {notif_action}.\nSố dư hiện tại của bạn: <code>{u['balance']:,}đ</code>", parse_mode="HTML")
            except Exception:
                pass
        except Exception:
            await update.message.reply_text("❌ Sai cú pháp! Định dạng đúng: <code>[ID] [+số_tiền]</code> hoặc <code>[ID] [-số_tiền]</code>")
        return

    if state == 'add_seller_id':
        admin_state.pop(uid, None)
        try:
            parts = text.split()
            db["sellers"][str(parts[0])] = {"daily_rev": 0, "target": int(re.sub(r'[^\d]', '', parts[1])) if len(parts) > 1 else 500000}
            save_data()
            await update.message.reply_text("✅ Thêm Seller thành công!", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Sai cú pháp!")
        return

async def broadcast_new_keys(context, package_name, quantity):
    notif_text = (
        f"🚨 <b>THÔNG BÁO: KHO HÀNG ĐÃ ĐƯỢC LÀM MỚI!</b> 🚀\n\n"
        f"<blockquote>"
        f"📦 <b>Gói vừa cập nhật:</b> <code>{package_name}</code>\n"
        f"🔢 <b>Số lượng key mới về:</b> <code>+{quantity} key</code>\n"
        f"🛒 Hệ thống kho đã sẵn sàng, anh em nhanh tay vào shop mua ngay kẻo hết nhé!"
        f"</blockquote>"
    )
    for t_uid in list(db["users"].keys()):
        try:
            await context.bot.send_message(chat_id=int(t_uid), text=notif_text, parse_mode="HTML")
            await asyncio.sleep(0.03)
        except Exception:
            pass

flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "OK", 200

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
                    check_daily_reset()
                    u = get_u(tid)
                    u['balance'] += amt
                    u['total_deposit'] += amt
                    u['month_deposit'] += amt
                    b_after = u['balance']
                    db["total_rev"] += amt
                    db["today_rev"] += amt
                    t_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    u['deposit_history'].append(f"• <b>[{t_str}]</b> Nạp Auto <code>+{amt:,}đ</code> (Số dư: <code>{b_after:,}đ</code>)")
                    save_data()
                try:
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": tid, "text": f"🎉 <b>NẠP THÀNH CÔNG +{amt:,}đ!</b>\nSố dư mới: <code>{b_after:,}đ</code>", "parse_mode": "HTML"})
                    realtime_log = (
                        f"💳 <b>[REALTIME] NẠP TIỀN THÀNH CÔNG (SEPAY)</b>\n"
                        f"👤 <b>Khách hàng:</b> ID <code>{tid}</code>\n"
                        f"💵 <b>Số tiền nạp:</b> <code>+{amt:,}đ</code>\n"
                        f"💎 <b>Số dư ví hiện tại:</b> <code>{b_after:,}đ</code>\n"
                        f"📅 <b>Doanh thu hôm nay:</b> <code>{db['today_rev']:,}đ</code>\n"
                        f"⏰ <b>Thời gian:</b> <code>{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</code>"
                    )
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": LOG_GROUP_ID, "text": realtime_log, "parse_mode": "HTML"})
                except Exception:
                    pass
    return jsonify({"success": True}), 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

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
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("📖 Hướng dẫn sử dụng hệ thống.")))
    app.add_handler(CommandHandler("id", lambda u, c: u.message.reply_text(f"🆔 ID: <code>{u.effective_user.id}</code>", parse_mode="HTML")))
    app.add_handler(CommandHandler("me", lambda u, c: u.message.reply_text(f"👤 Số dư: <code>{get_u(u.effective_user.id)['balance']:,}đ</code>", parse_mode="HTML")))
    app.add_handler(CommandHandler("admin", lambda u, c: render_admin_panel(u.message) if is_admin(u.effective_user.id) else None))
    app.add_handler(CommandHandler("stats", lambda u, c: (check_daily_reset(), u.message.reply_text(f"📅 Hôm nay: {db['today_rev']:,}đ | 📊 Tổng: {db['total_rev']:,}đ")) if is_admin(u.effective_user.id) else None))
    app.add_handler(CommandHandler("users", lambda u, c: u.message.reply_text(f"👥 Users: {len(db['users'])}") if is_admin(u.effective_user.id) else None))
    app.add_handler(CommandHandler("thongbao", lambda u, c: admin_bits(u, c)))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("json"), handle_document_restore))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    app.run_polling(drop_pending_updates=True)

def admin_bits(update, context):
    if is_admin(update.effective_user.id):
        admin_state[update.effective_user.id] = 'broadcast_msg'
        update.message.reply_text("📢 Nhập nội dung thông báo:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data='cancel_state')]]))

if __name__ == '__main__':
    main()