import os, logging, threading, httpx, re, secrets, time, html, datetime, json
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
BOT_USERNAME = "GetkeyMizzebot"

ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

# Cấu hình ID nhóm và Link nhóm nhận file của bạn
LOG_GROUP_ID = -1003912025872
CLIENT_GROUP_LINK = "https://t.me/mizze_lebin" 

SIGNATURE = "\n\n━━━━━━━━━━━━━━━━━━━\n💎 <b>✨ MIZZE STORE - PREMIUM VIP SHOP ✨</b> 💎"
BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
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

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {
        "users": {}, "user_data": {}, 
        "s_1h": [], "s_1d": [], "s_7d": [], "s_30d": [], 
        "prices": {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000},
        "total_rev": 0, "bot_active": True
    }

db = load_data()
if "prices" not in db:
    db["prices"] = {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000}
# Đảm bảo dọn sạch kho 6h nếu còn sót dữ liệu cũ
if "s_6h" in db:
    del db["s_6h"]

def save_data():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
    except: pass

admin_state = {}
cooldown_cache = {}

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {'balance': 0, 'total_deposit': 0, 'deposit_history': [], 'buy_history': []}
        save_data()
    return db["user_data"][uid_str]

def is_admin(uid):
    return uid in admin_list

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 2:
        return True
    if len(cooldown_cache) > 1000:
        cooldown_cache.clear()
    cooldown_cache[uid] = now
    return False

async def edit_or_send(query, text, reply_markup=None):
    try:
        if query.message.photo:
            await query.message.delete()
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except:
        try: await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except: pass

async def notify_all_admins(context, msg):
    for adm in list(admin_list):
        try:
            await context.bot.send_message(chat_id=adm, text="⚡ <b>[THÔNG BÁO QUẢN TRỊ]</b>\n\n" + msg + SIGNATURE, parse_mode="HTML")
        except:
            pass

async def broadcast_all(context, msg):
    for u_str in list(db["users"]):
        try: await context.bot.send_message(int(u_str), msg, parse_mode="HTML")
        except: pass

async def show_main_menu(update, context):
    uid = update.effective_user.id
    
    if not db["bot_active"] and not is_admin(uid):
        text = (
            f"🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ NÂNG CẤP</b> 🚧\n\n"
            f"<i>Bot hiện đang tạm dừng hoạt động để bảo trì hệ thống. Vui lòng quay lại sau ít phút nhé!</i>"
            f"{SIGNATURE}"
        )
        if update.message: await update.message.reply_text(text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML")
        return

    u = get_u(uid)
    p = db["prices"]
    text = (
        f"🌌 <b>✨ 🔮 MIZZE STORE - CỬA HÀNG KEY VIP 🔮 ✨</b> 🌌\n\n"
        f"📢 <b>Kênh Thông Báo:</b> <a href='{CHANNEL_URL}'>🔗 Bấm Vào Đây</a>\n"
        f"👑 <b>Admin Hỗ Trợ:</b> <a href='{ADMIN_CONTACT}'>💬 Liên Hệ Ngay</a>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>Tổng Nạp:</b> <code>{u['total_deposit']:,}đ</code> | 💎 <b>Số Dư Ví:</b> <b>{u['balance']:,}đ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>📊 KHO HÀNG VIP REAL-TIME:</b>\n"
        f"  • ⚡ <b>1H:</b> <code>[{len(db['s_1h'])}]</code> | 💎 <b>1D:</b> <code>[{len(db['s_1d'])}]</code>\n"
        f"  • 👑 <b>7D:</b> <code>[{len(db['s_7d'])}]</code> | 🚀 <b>30D:</b> <code>[{len(db['s_30d'])}]</code>"
        f"{SIGNATURE}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Mua Key VIP Ngay 🚀", callback_data='menu_shop'), InlineKeyboardButton("💳 Nạp Tiền Tự Động ⚡", callback_data='menu_deposit')],
        [InlineKeyboardButton("👤 Tài Khoản 💼", callback_data='menu_account'), InlineKeyboardButton("🧾 Lịch Sử Nạp 📜", callback_data='hist_deposit')],
        [InlineKeyboardButton("🛍️ Lịch Sử Mua Hàng 📦", callback_data='hist_buy'), InlineKeyboardButton("💬 Hỗ Trợ ☎️", url=SUPPORT_CONTACT)],
        [InlineKeyboardButton("⚙️ BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN 🛡️", callback_data='admin_panel')] if is_admin(uid) else [InlineKeyboardButton("💬 Liên Hệ Hỗ Trợ Khách Hàng", url=SUPPORT_CONTACT)]
    ])
    try:
        if update.message: await update.message.reply_photo(photo=BANNER_URL, caption=text, reply_markup=kb, parse_mode="HTML")
        elif update.callback_query:
            await update.callback_query.message.delete()
            await context.bot.send_photo(chat_id=uid, photo=BANNER_URL, caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        if update.message: await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

async def start(update, context):
    uid = update.effective_user.id
    db["users"][str(uid)] = True
    get_u(uid)
    save_data()
    await show_main_menu(update, context)

async def button_handler(update, context):
    query = update.callback_query
    uid = query.from_user.id

    if check_spam(uid):
        await query.answer("⚠️ Bạn đang thao tác quá nhanh! Vui lòng từ từ.", show_alert=True)
        return

    await query.answer()
    u = get_u(uid)
    data = query.data
    p = db["prices"]

    if data == 'back_menu': await show_main_menu(update, context)
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ Mua 1H ({p['1h']:,}đ) [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 Mua 1D ({p['1d']:,}đ) [{len(db['s_1d'])}]", callback_data='shop_1d')],
            [InlineKeyboardButton(f"👑 Mua 7D ({p['7d']:,}đ) [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 Mua 30D ({p['30d']:,}đ) [{len(db['s_30d'])}]", callback_data='shop_30d')],
            [InlineKeyboardButton("💳 Nạp Tiền Thêm ⚡", callback_data='menu_deposit'), InlineKeyboardButton("◀️ Menu Chính 🏠", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛒 <b>✨ CỬA HÀNG MUA KEY VIP TỰ ĐỘNG ✨</b>\n💎 Số dư ví của bạn: <b>{u['balance']:,}đ</b>\n━━━━━━━━━━━━━━━━━━━\n<i>🔥 Chọn gói dịch vụ bạn muốn sở hữu bên dưới:</i>", kb)
    elif data.startswith('shop_'):
        kt = data.split('_')[1]
        p_map = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}
        price, kho = p_map[kt]
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ Mua 1 Key", callback_data=f"buyq_{kt}_1"), InlineKeyboardButton("2️⃣ Mua 2 Key", callback_data=f"buyq_{kt}_2")],
            [InlineKeyboardButton("3️⃣ Mua 3 Key", callback_data=f"buyq_{kt}_3"), InlineKeyboardButton("5️⃣ Mua 5 Key", callback_data=f"buyq_{kt}_5")],
            [InlineKeyboardButton("🔟 Mua 10 Key", callback_data=f"buyq_{kt}_10"), InlineKeyboardButton("✏️ Nhập Số Lượng", callback_data=f"buyq_custom_{kt}")],
            [InlineKeyboardButton("◀️ Quay Lại Cửa Hàng", callback_data='menu_shop')]
        ])
        await edit_or_send(query, f"📦 <b>BẠN ĐANG CHỌN GÓI: {kt.upper()}</b>\n💰 Giá niêm yết: <b>{price:,}đ / key</b>\n📊 Kho hiện có sẵn: <b>{len(kho)} key</b>\n━━━━━━━━━━━━━━━━━━━\n<i>👉 Chọn số lượng key bạn muốn mua ngay bên dưới:</i>", kb)
    elif data.startswith('buyq_custom_'):
        kt = data.split('_')[2]
        admin_state[uid] = f"buy_custom_{kt}"
        await edit_or_send(query, f"💬 <b>Vui lòng nhập số lượng key gói {kt.upper()} bạn muốn mua vào khung chat</b> (Ví dụ: <code>4</code>):{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data=f"shop_{kt}")]]))
    elif data.startswith('buyq_'):
        parts = data.split('_')
        kt = parts[1]
        qty = int(parts[2])
        await process_purchase(query, context, uid, kt, qty)

    elif data == 'menu_deposit':
        await edit_or_send(query, f"💳 <b>✨ HỆ THỐNG NẠP TIỀN TỰ ĐỘNG 24/7 ✨</b>\n━━━━━━━━━━━━━━━━━━━\n<i>⚡ Chọn nhanh hạn mức nạp hoặc nhập số tiền tùy ý (Tối thiểu <b>10.000đ</b>):</i>", InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 10.000đ", callback_data='pre_qr_10000'), InlineKeyboardButton("💵 50.000đ", callback_data='pre_qr_50000')],
            [InlineKeyboardButton("💵 100.000đ", callback_data='pre_qr_100000'), InlineKeyboardButton("💵 200.000đ", callback_data='pre_qr_200000')],
            [InlineKeyboardButton("✏️ Nhập Số Tiền Tùy Chỉnh", callback_data='pre_qr_custom')],
            [InlineKeyboardButton("◀️ Menu Chính 🏠", callback_data='back_menu')]
        ]))
    elif data.startswith('pre_qr_'):
        sub = data.replace('pre_qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, f"💬 <b>Vui lòng nhập số tiền bạn muốn nạp vào khung chat</b> (Ví dụ: <code>50000</code>):{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]]))
            return
        # Bắt buộc hiện màn hình cảnh báo copy nội dung to rõ trước khi xem QR
        await show_copy_warning(query, uid, int(sub))
    elif data.startswith('show_qr_'):
        amt = int(data.replace('show_qr_', ''))
        await send_qr(query, context, uid, amt)

    elif data == 'menu_account':
        await edit_or_send(query, f"👤 <b>✨ THÔNG TIN TÀI KHOẢN CÁ NHÂN ✨</b>\n━━━━━━━━━━━━━━━━━━━\n🆔 Telegram ID: <code>{uid}</code>\n💎 Số Dư Ví: <b>{u['balance']:,}đ</b>\n💳 Tổng Nạp: <b>{u['total_deposit']:,}đ</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu Chính 🏠", callback_data='back_menu')]]))
    elif data == 'hist_deposit':
        h_list = "\n".join(u['deposit_history'][-10:]) if u['deposit_history'] else "Chưa có lịch sử nạp tiền nào."
        await edit_or_send(query, f"🧾 <b>✨ LỊCH SỬ NẠP TIỀN GẦN NHẤT ✨</b>\n━━━━━━━━━━━━━━━━━━━\n{h_list}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu Chính 🏠", callback_data='back_menu')]]))
    elif data == 'hist_buy':
        b_list = "\n".join(u['buy_history'][-10:]) if u['buy_history'] else "Chưa có lịch sử mua hàng nào."
        await edit_or_send(query, f"🛍️ <b>✨ LỊCH SỬ MUA HÀNG GẦN NHẤT ✨</b>\n━━━━━━━━━━━━━━━━━━━\n{b_list}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu Chính 🏠", callback_data='back_menu')]]))
    elif data == 'admin_panel' and is_admin(uid):
        status_text = "🟢 Đang Hoạt Động" if db["bot_active"] else "🔴 Đang Bảo Trì"
        toggle_text = "🔴 Tắt Bot (Bảo Trì)" if db["bot_active"] else "🟢 Bật Bot (Mở Lại)"
        await edit_or_send(query, f"🛡️ <b>✨ BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN ✨</b> 🛡️\n━━━━━━━━━━━━━━━━━━━\nTrạng thái Bot: <b>{status_text}</b>\n<i>⚡ Lựa chọn tính năng quản lý hệ thống bên dưới:</i>", InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data='toggle_bot_status')],
            [InlineKeyboardButton("📊 Thống Kê Kho & Doanh Thu 📈", callback_data='ad_stats')],
            [InlineKeyboardButton("💸 Cộng Tiền", callback_data='ad_bal'), InlineKeyboardButton("📉 Trừ Tiền", callback_data='ad_subbal')],
            [InlineKeyboardButton("💰 Sửa Giá Gói Key", callback_data='ad_setprice'), InlineKeyboardButton("🔍 Kiểm Tra Kho Key", callback_data='ad_checkkey')],
            [InlineKeyboardButton("➕ Bổ Sung Lô Key Mới", callback_data='ad_addk'), InlineKeyboardButton("🔍 Kiểm Tra Số Dư User", callback_data='ad_checkbal')],
            [InlineKeyboardButton("👥 Thêm Admin Phụ", callback_data='ad_addadmin'), InlineKeyboardButton("📢 Gửi Broadcast", callback_data='ad_bc')],
            [InlineKeyboardButton("🏠 Về Menu Chính 🏠", callback_data='back_menu')]
        ]))
    elif data == 'toggle_bot_status' and is_admin(uid):
        db["bot_active"] = not db["bot_active"]
        save_data()
        await query.answer(f"Đã chuyển trạng thái bot thành công!", show_alert=True)
        
        if not db["bot_active"]:
            await broadcast_all(context, f"🚧 <b>THÔNG BÁO BẢO TRÌ HỆ THỐNG</b>\n━━━━━━━━━━━━━━━━━━━\nBot hiện đang tạm dừng hoạt động để nâng cấp. Xin lỗi quý khách vì sự bất tiện này!")
        else:
            await broadcast_all(context, f"🚀 <b>THÔNG BÁO MỞ LẠI HỆ THỐNG</b>\n━━━━━━━━━━━━━━━━━━━\nBot đã chính thức hoạt động trở lại bình thường. Chúc quý khách mua sắm vui vẻ!")
            
        status_text = "🟢 Đang Hoạt Động" if db["bot_active"] else "🔴 Đang Bảo Trì"
        toggle_text = "🔴 Tắt Bot (Bảo Trì)" if db["bot_active"] else "🟢 Bật Bot (Mở Lại)"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data='toggle_bot_status')],
            [InlineKeyboardButton("📊 Thống Kê Kho & Doanh Thu 📈", callback_data='ad_stats')],
            [InlineKeyboardButton("💸 Cộng Tiền", callback_data='ad_bal'), InlineKeyboardButton("📉 Trừ Tiền", callback_data='ad_subbal')],
            [InlineKeyboardButton("💰 Sửa Giá Gói Key", callback_data='ad_setprice'), InlineKeyboardButton("🔍 Kiểm Tra Kho Key", callback_data='ad_checkkey')],
            [InlineKeyboardButton("➕ Bổ Sung Lô Key Mới", callback_data='ad_addk'), InlineKeyboardButton("🔍 Kiểm Tra Số Dư User", callback_data='ad_checkbal')],
            [InlineKeyboardButton("👥 Thêm Admin Phụ", callback_data='ad_addadmin'), InlineKeyboardButton("📢 Gửi Broadcast", callback_data='ad_bc')],
            [InlineKeyboardButton("🏠 Về Menu Chính 🏠", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛡️ <b>✨ BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN ✨</b> 🛡️\n━━━━━━━━━━━━━━━━━━━\nTrạng thái Bot: <b>{status_text}</b>\n<i>⚡ Lựa chọn tính năng quản lý hệ thống bên dưới:</i>", kb)
    elif data == 'ad_stats' and is_admin(uid):
        p = db["prices"]
        total_keys = len(db['s_1h']) + len(db['s_1d']) + len(db['s_7d']) + len(db['s_30d'])
        await edit_or_send(query, f"📊 <b>✨ THỐNG KÊ KHO & DOANH THU ✨</b>\n━━━━━━━━━━━━━━━━━━━\n👥 Tổng User: <code>{len(db['users'])}</code>\n💰 Tổng Doanh Thu: <code>{db['total_rev']:,}đ</code>\n📦 Tổng Số Key Tồn Kho: <b>{total_keys} key</b>\n\n📦 <b>Chi Tiết Từng Kho & Giá:</b>\n• <b>1H</b> ({p['1h']:,}đ): <code>{len(db['s_1h'])} key</code>\n• <b>1D</b> ({p['1d']:,}đ): <code>{len(db['s_1d'])} key</code>\n• <b>7D</b> ({p['7d']:,}đ): <code>{len(db['s_7d'])} key</code>\n• <b>30D</b> ({p['30d']:,}đ): <code>{len(db['s_30d'])} key</code>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Admin Panel", callback_data='admin_panel')]]))
    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, f"💬 <b>Nhập ID user và số tiền cần cộng</b> theo định dạng:\n<code>[ID] [Số_tiền]</code>\n(Ví dụ: <code>7976468365 50000</code>){SIGNATURE}")
    elif data == 'ad_subbal' and is_admin(uid):
        admin_state[uid] = 'sub_bal'
        await edit_or_send(query, f"💬 <b>Nhập ID user và số tiền cần trừ/xóa</b> theo định dạng:\n<code>[ID] [Số_tiền]</code>\n(Ví dụ: <code>7976468365 20000</code>){SIGNATURE}")
    elif data == 'ad_setprice' and is_admin(uid):
        await edit_or_send(query, f"💰 <b>CHỌN GÓI KEY CẦN SỬA GIÁ:</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Sửa Giá 1H", callback_data='p_1h'), InlineKeyboardButton("💎 Sửa Giá 1D", callback_data='p_1d')],
            [InlineKeyboardButton("👑 Sửa Giá 7D", callback_data='p_7d'), InlineKeyboardButton("🚀 Sửa Giá 30D", callback_data='p_30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data.startswith('p_') and is_admin(uid):
        pk = data.replace('p_', '')
        admin_state[uid] = f"setprice_{pk}"
        await edit_or_send(query, f"💬 <b>Nhập giá mới cho gói {pk.upper()}</b> (Ví dụ: <code>10000</code>):{SIGNATURE}")
    elif data == 'ad_checkkey' and is_admin(uid):
        await edit_or_send(query, f"🔍 <b>CHỌN KHO HÀNG CẦN KIỂM TRA / THAY THẾ:</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Kho 1H", callback_data='ck_s1h'), InlineKeyboardButton("🛒 Kho 1D", callback_data='ck_s1d')],
            [InlineKeyboardButton("🛒 Kho 7D", callback_data='ck_s7d'), InlineKeyboardButton("🛒 Kho 30D", callback_data='ck_s30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data.startswith('ck_') and is_admin(uid):
        k_type = data.replace('ck_', '')
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        target = m_map.get(k_type, [])
        preview = "\n".join([f"• <code>{k}</code>" for k in target[:10]]) if target else "Kho đang trống."
        if len(target) > 10: preview += f"\n... và còn {len(target) - 10} key khác."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Thay Thế Toàn Bộ Lô (Xóa Cũ Thêm Mới)", callback_data=f"replace_{k_type}")],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_checkkey')]
        ])
        await edit_or_send(query, f"📦 <b>KIỂM TRA KHO {k_type.upper()}</b>\n📊 Tổng tồn kho: <b>{len(target)} key</b>\n━━━━━━━━━━━━━━━━━━━\n{preview}{SIGNATURE}", kb)
    elif data.startswith('replace_') and is_admin(uid):
        k_type = data.replace('replace_', '')
        admin_state[uid] = f"replacekeys_{k_type}"
        await edit_or_send(query, f"⚠️ <b>THAY THẾ TOÀN BỘ KHO {k_type.upper()}</b>\n<i>Hệ thống sẽ xóa sạch danh sách cũ và thay thế hoàn toàn bằng danh sách mới bạn gửi.</i>\n\n📝 <b>Dán danh sách lô Key mới vào khung chat:</b>{SIGNATURE}")
    elif data == 'ad_checkbal' and is_admin(uid):
        admin_state[uid] = 'check_user_bal'
        await edit_or_send(query, f"💬 <b>Nhập Telegram ID của người dùng cần kiểm tra số dư:</b>\n(Ví dụ: <code>7976468365</code>){SIGNATURE}")
    elif data == 'ad_addadmin' and uid == ADMIN_ID:
        admin_state[uid] = 'add_admin_id'
        await edit_or_send(query, f"💬 <b>Nhập Telegram ID của tài khoản muốn phân quyền làm Admin phụ:</b>\n(Ví dụ: <code>123456789</code>){SIGNATURE}")
    elif data == 'ad_bc' and is_admin(uid):
        admin_state[uid] = 'bc'
        await edit_or_send(query, f"💬 <b>Nhập nội dung thông báo (Broadcast)</b> muốn gửi tới toàn bộ người chơi:{SIGNATURE}")
    elif data == 'ad_addk' and is_admin(uid):
        await edit_or_send(query, f"📦 <b>CHỌN KHO HÀNG CẦN BỔ SUNG LÔ KEY:</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Shop 1H", callback_data='k_s1h'), InlineKeyboardButton("🛒 Shop 1D", callback_data='k_s1d')],
            [InlineKeyboardButton("🛒 Shop 7D", callback_data='k_s7d'), InlineKeyboardButton("🛒 Shop 30D", callback_data='k_s30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data.startswith('k_') and is_admin(uid):
        admin_state[uid] = f"addk_{data.replace('k_', '')}"
        await edit_or_send(query, f"📝 <b>Dán danh sách lô Key mới vào khung chat.</b>\n(Mỗi key / dữ liệu cách nhau bằng dòng trống):{SIGNATURE}")

async def show_copy_warning(query, uid, amount):
    # Màn hình cảnh báo cực kỳ to rõ bắt buộc copy nội dung trước khi xem QR
    text = (
        f"🚨 🛑 <b>CẢNH BÁO QUAN TRỌNG TRƯỚC KHI NẠP TIỀN</b> 🛑 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>BẠN BẮT BUỘC PHẢI COPY NỘI DUNG CHUYỂN KHOẢN DƯỚI ĐÂY!</b>\n"
        f"📝 Nội dung CK: <code>NAP {uid}</code> <i>(Chạm vào để copy ngay)</i>\n\n"
        f"❌ <b>TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA ĐỔI HOẶC XÓA NỘI DUNG NÀY!</b>\n"
        f"💡 <i>Hãy chạm vào đoạn mã trên để copy, sau đó bấm nút bên dưới để mở mã QR nạp tiền {amount:,}đ nhé!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ĐÃ COPY NỘI DUNG - XEM MÃ QR NGAY 🚀", callback_data=f"show_qr_{amount}")],
        [InlineKeyboardButton("◀️ Chọn Mức Nạp Khác ⚡", callback_data='menu_deposit')]
    ])
    await edit_or_send(query, text, kb)

async def send_qr(query, context, uid, amount):
    if amount < 10000:
        await query.answer("❌ Số tiền nạp tối thiểu là 10.000đ!", show_alert=True)
        return
    
    add_info = f"NAP {uid}"
    url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amount}&memo={quote(add_info)}"
    
    text = (
        f"💳 <b>✨ MÃ QR NẠP TIỀN TỰ ĐỘNG 24/7 ✨</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Ngân hàng: <b>{BANK_ID}</b>\n"
        f"🔢 Số tài khoản: <code>{ACCOUNT_NO}</code>\n"
        f"👤 Chủ tài khoản: <b>{ACCOUNT_NAME}</b>\n"
        f"💵 Số tiền: <b>{amount:,}đ</b>\n"
        f"📝 Nội dung CK: <code>NAP {uid}</code> <i>(Chạm để copy)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 <b>LƯU Ý CỰC KỲ QUAN TRỌNG:</b>\n"
        f"⚠️ <b>TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA ĐỔI HOẶC XÓA NỘI DUNG CHUYỂN KHOẢN!</b>\n"
        f"⚠️ <i>Nếu bạn ghi sai nội dung <code>NAP {uid}</code>, hệ thống SePay sẽ KHÔNG THỂ nhận diện để tự động cộng tiền cho bạn!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👉 <i>Quét mã QR bằng App ngân hàng. Tiền sẽ được tự động cộng vào ví sau vài giây!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Kiểm Tra Lại Số Dư Ví", callback_data='menu_account')],
        [InlineKeyboardButton("◀️ Chọn Mức Nạp Khác", callback_data='menu_deposit')]
    ])
    try:
        await query.message.delete()
        await context.bot.send_photo(chat_id=uid, photo=url, caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await context.bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")

async def process_purchase(query, context, uid, kt, qty):
    u = get_u(uid)
    p = db["prices"]
    p_map = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}
    price_per_item, kho = p_map[kt]
    total_price = price_per_item * qty

    if len(kho) < qty:
        await query.answer(f"❌ Kho Key {kt.upper()} không đủ số lượng! Hiện chỉ còn {len(kho)} key.", show_alert=True)
        return
    if u['balance'] < total_price:
        await edit_or_send(query, f"❌ <b>Số dư ví không đủ!</b>\nBạn cần <code>{total_price:,}đ</code> cho {qty} key nhưng ví chỉ có <code>{u['balance']:,}đ</code>.\nVui lòng nạp thêm tiền để tiếp tục mua hàng nhé!", InlineKeyboardMarkup([[InlineKeyboardButton("💳 Nạp Tiền Ngay", callback_data='menu_deposit'), InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_shop')]]))
        return

    u['balance'] -= total_price
    db["total_rev"] += total_price
    
    keys_bought = []
    for _ in range(qty):
        keys_bought.append(kho.pop(0))

    time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    u['buy_history'].append(f"[{time_str}] Mua {qty}x gói {kt.upper()} (-{total_price:,}đ)")
    if len(u['buy_history']) > 20: u['buy_history'].pop(0)
    save_data()

    keys_str = "\n".join([f"<code>{k}</code>" for k in keys_bought])
    
    await notify_all_admins(context, f"User <code>{uid}</code> vừa mua thành công <b>{qty}x gói {kt.upper()}</b> với giá <b>{total_price:,}đ</b>. Kho còn lại: <code>{len(kho)}</code>")
    
    try:
        log_msg = (
            f"🛍️ <b>CÓ GIAO DỊCH MUA KEY MỚI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Khách: <code>{query.from_user.full_name}</code> (ID: <code>{uid}</code>)\n"
            f"📦 Gói: <b>{qty}x {kt.upper()}</b>\n"
            f"💵 Tổng tiền: <b>{total_price:,}đ</b>\n"
            f"🔑 Dữ liệu / Key:\n{keys_str}\n"
            f"⏱️ Thời gian: {time_str}"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Không thể gửi log vào nhóm: {e}")

    success_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Nhận File / Truy Cập Nhóm Nhận Dữ Liệu", url=CLIENT_GROUP_LINK)],
        [InlineKeyboardButton("🛒 Mua Thêm Gói Khác", callback_data='menu_shop'), InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]
    ])
    
    await edit_or_send(query, f"✅ <b>GIAO DỊCH MUA {qty} KEY THÀNH CÔNG!</b>\n━━━━━━━━━━━━━━━━━━━\n📦 Gói: <b>{qty}x {kt.upper()}</b> | Tổng trừ: <code>-{total_price:,}đ</code>\n\n👇 <b>Danh sách mã Key / Dữ liệu của bạn:</b>\n{keys_str}\n━━━━━━━━━━━━━━━━━━━\n📂 <i>Dữ liệu file đã được gửi vào nhóm riêng. Bấm nút bên dưới để vào nhóm nhận file cài đặt!</i>\n💎 Số dư ví còn lại: <b>{u['balance']:,}đ</b>{SIGNATURE}", success_kb)

async def handle_admin_text(update, context):
    uid = update.message.from_user.id
    if uid not in admin_state: return
    state = admin_state[uid]
    text = update.message.text

    if state.startswith('buy_custom_'):
        kt = state.replace('buy_custom_', '')
        del admin_state[uid]
        try:
            qty = int(text.strip())
            if qty <= 0:
                await update.message.reply_text("❌ Số lượng phải lớn hơn 0!")
                return
            # Tạo query giả lập để xử lý mua hàng qua hàm chung
            class DummyQuery:
                def __init__(self, msg, user):
                    self.message = msg
                    self.from_user = user
                async def answer(self, *args, **kwargs): pass
            
            dummy_q = DummyQuery(update.message, update.message.from_user)
            # Gửi thông báo đang xử lý
            await update.message.reply_text(f"⏳ Đang xử lý đơn mua {qty} gói {kt.upper()}...")
            await process_purchase(dummy_q, context, uid, kt, qty)
        except:
            await update.message.reply_text("❌ Số lượng nhập không hợp lệ!")
        return

    if state == 'waiting_deposit':
        del admin_state[uid]
        try:
            amt = int(text.replace(".", "").strip())
            if amt < 10000:
                await update.message.reply_text("❌ Số tiền nạp tối thiểu là 10.000đ!")
                return
            
            # Hiển thị màn hình cảnh báo copy trước khi hiện QR tùy chỉnh
            text_warn = (
                f"🚨 🛑 <b>CẢNH BÁO QUAN TRỌNG TRƯỚC KHI NẠP TIỀN</b> 🛑 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>BẮT BUỘC PHẢI COPY NỘI DUNG CHUYỂN KHOẢN SAU:</b>\n"
                f"📝 Nội dung CK: <code>NAP {uid}</code> <i>(Chạm để copy)</i>\n\n"
                f"❌ <b>TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA ĐỔI HOẶC XÓA NỘI DUNG NÀY!</b>"
            )
            add_info = f"NAP {uid}"
            url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amt}&memo={quote(add_info)}"
            
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]])
            await update.message.reply_text(text_warn, parse_mode="HTML")
            await update.message.reply_photo(photo=url, caption=f"💳 <b>QR NẠP {amt:,}đ</b>\n📝 Nội dung CK: <code>NAP {uid}</code>", reply_markup=kb, parse_mode="HTML")
        except: await update.message.reply_text("❌ Số tiền nhập không hợp lệ!")
        return

    if not is_admin(uid): return

    if state.startswith('setprice_'):
        pk = state.replace('setprice_', '')
        del admin_state[uid]
        try:
            new_p = int(text.replace(".", "").strip())
            db["prices"][pk] = new_p
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá mới cho gói <b>{pk.upper()}</b> thành <b>{new_p:,}đ</b>!", parse_mode="HTML")
        except:
            await update.message.reply_text("❌ Giá tiền không hợp lệ!")
        return

    if state.startswith('replacekeys_'):
        k_type = state.replace('replacekeys_', '')
        del admin_state[uid]
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        target = m_map.get(k_type)
        if target is not None:
            target.clear() # Xóa sạch kho cũ
            added = 0
            for b in text.split('\n\n'):
                if b.strip(): target.append(html.escape(b.strip())); added += 1
            save_data()
            await update.message.reply_text(f"✅ Đã thay thế hoàn tất! Kho <b>{k_type.upper()}</b> hiện có <code>{added}</code> key mới.")
        return

    if state == 'add_bal':
        try:
            tid, amt = text.split(); tid, amt = int(tid), int(amt)
            u = get_u(tid)
            u['balance'] += amt; u['total_deposit'] += amt
            time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            u['deposit_history'].append(f"[{time_str}] Admin cộng (+{amt:,}đ)")
            save_data()
            await update.message.reply_text(f"✅ Đã cộng thành công <code>{amt:,}đ</code> cho User ID: <code>{tid}</code>")
            try: await context.bot.send_message(tid, f"🎁 <b>[TÀI CHÍNH]</b> Bạn vừa được Admin cộng thêm <b>+{amt:,}đ</b> vào số dư ví!{SIGNATURE}", parse_mode="HTML")
            except: pass
        except: await update.message.reply_text("❌ Sai cú pháp! Vui lòng nhập: `[ID] [Số_tiền]`")
        del admin_state[uid]
    elif state == 'sub_bal':
        try:
            tid, amt = text.split(); tid, amt = int(tid), int(amt)
            u = get_u(tid)
            u['balance'] = max(0, u['balance'] - amt)
            time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            u['deposit_history'].append(f"[{time_str}] Admin trừ (-{amt:,}đ)")
            save_data()
            await update.message.reply_text(f"✅ Đã trừ thành công <code>{amt:,}đ</code> của User ID: <code>{tid}</code>")
            try: await context.bot.send_message(tid, f"⚠️ <b>[TÀI CHÍNH]</b> Số dư ví của bạn vừa bị Admin trừ bớt <b>-{amt:,}đ</b>!{SIGNATURE}", parse_mode="HTML")
            except: pass
        except: await update.message.reply_text("❌ Sai cú pháp! Vui lòng nhập: `[ID] [Số_tiền]`")
        del admin_state[uid]
    elif state == 'check_user_bal':
        try:
            tid = int(text.strip())
            if str(tid) in db["user_data"]:
                target_u = db["user_data"][str(tid)]
                hist_preview = "\n".join(target_u['deposit_history'][-5:]) if target_u['deposit_history'] else "Trống."
                await update.message.reply_text(f"🔍 <b>THÔNG TIN SỐ DƯ USER</b>\n━━━━━━━━━━━━━━━━━━━\n🆔 ID: <code>{tid}</code>\n💎 Số dư ví: <b>{target_u['balance']:,}đ</b>\n💳 Tổng nạp: <b>{target_u['total_deposit']:,}đ</b>\n\n🧾 <b>Lịch sử nạp gần đây:</b>\n{hist_preview}{SIGNATURE}", parse_mode="HTML")
            else:
                await update.message.reply_text(f"❌ Không tìm thấy dữ liệu của User ID: <code>{tid}</code> trong hệ thống.")
        except:
            await update.message.reply_text("❌ ID không hợp lệ!")
        del admin_state[uid]
    elif state == 'add_admin_id' and uid == ADMIN_ID:
        try:
            new_adm = int(text.strip())
            admin_list.add(new_adm)
            await update.message.reply_text(f"✅ Đã thêm thành công Telegram ID: <code>{new_adm}</code> vào danh sách Quản Trị Viên phụ!")
            try:
                await context.bot.send_message(chat_id=new_adm, text=f"👑 <b>[QUYỀN HẠN]</b> Bạn đã được bổ nhiệm làm Quản Trị Viên của bot! Hãy dùng lệnh /start hoặc mở Admin Panel để quản lý hệ thống.{SIGNATURE}", parse_mode="HTML")
            except:
                pass
        except:
            await update.message.reply_text("❌ ID Admin không hợp lệ!")
        del admin_state[uid]
    elif state == 'bc':
        del admin_state[uid]
        succ = 0
        for u_str in list(db["users"]):
            try: await context.bot.send_message(int(u_str), f"📢 <b>THÔNG BÁO TỪ HỆ THỐNG</b>\n━━━━━━━━━━━━━━━━━━━\n{html.escape(text)}{SIGNATURE}", parse_mode="HTML"); succ += 1
            except: pass
        await update.message.reply_text(f"✅ Đã phát sóng thông báo thành công đến <code>{succ}</code> người dùng.")
    elif state.startswith('addk_'):
        k_type = state.replace('addk_', '')
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        target = m_map.get(k_type)
        if target is not None:
            added = 0
            for b in text.split('\n\n'):
                if b.strip(): target.append(html.escape(b.strip())); added += 1
            save_data()
            await update.message.reply_text(f"✅ Đã bổ sung thành công <code>{added}</code> Key vào kho <b>{k_type.upper()}</b> (Tồn kho: <code>{len(target)}</code>)!")
            await broadcast_all(context, f"📢 <b>CẬP NHẬT KHO HÀNG REAL-TIME</b>\n━━━━━━━━━━━━━━━━━━━\n📦 Kho <b>{k_type.upper()}</b> vừa được Admin cấp thêm lô key mới!\n📊 Tồn kho hiện tại: <code>{len(target)} Key</code>.\n\n👉 Nhanh tay truy cập bot để mua ngay nhé!{SIGNATURE}")
        del admin_state[uid]

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "OK", 200

@flask_app.route('/sepay_webhook', methods=['POST'])
def sepay():
    auth_header = request.headers.get('Authorization', '')
    if SEPAY_KEY not in auth_header and auth_header != f"Apikey {SEPAY_KEY}":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.json
    if data and data.get("transferType") == "in":
        content = data.get("content", "")
        m = re.search(r"NAP[\s\-]*(\d+)", content, re.IGNORECASE)
        if m:
            tid = int(m.group(1))
            amt = int(data.get("transferAmount", 0))
            u = get_u(tid)
            u['balance'] += amt
            u['total_deposit'] += amt
            time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            u['deposit_history'].append(f"[{time_str}] Nạp tự động SePay (+{amt:,}đ)")
            if len(u['deposit_history']) > 20: u['deposit_history'].pop(0)
            save_data()
            
            try:
                msg = (
                    f"🎉 <b>NẠP TIỀN TỰ ĐỘNG THÀNH CÔNG!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 Số tiền nhận: <b>+{amt:,}đ</b>\n"
                    f"💎 Số dư ví mới: <b>{u['balance']:,}đ</b>"
                    f"{SIGNATURE}"
                )
                httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": tid, "text": msg, "parse_mode": "HTML"})
            except: pass
    return jsonify({"success": True}), 200

def run_flask(): flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()