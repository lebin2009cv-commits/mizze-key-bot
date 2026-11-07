import os, logging, threading, httpx, re, secrets, time, html, datetime, json
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
BOT_USERNAME = "GetkeyMizzebot"

ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

# Cấu hình nhóm nhận file & link nhóm khách hàng
LOG_GROUP_ID = -1003912025872
CLIENT_GROUP_LINK = "https://t.me/mizze_lebin" 

SIGNATURE = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚡ 🔮 **MIZZE CYBERPUNK STORE** 🔮 ⚡"
BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/mizze_store"
SUPPORT_CONTACT = "https://t.me/NTH_VIP"

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
        "users": {}, "user_data": {}, "sellers": {},
        "s_1h": [], "s_1d": [], "s_7d": [], "s_30d": [], 
        "prices": {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000},
        "seller_prices": {"1h": 5000, "1d": 15000, "7d": 60000, "30d": 120000},
        "seller_targets": {}, 
        "total_rev": 0, "bot_active": True, "last_reset_date": datetime.datetime.now().strftime("%Y-%m-%d")
    }

db = load_data()
if "prices" not in db:
    db["prices"] = {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000}
if "seller_prices" not in db:
    db["seller_prices"] = {"1h": 5000, "1d": 15000, "7d": 60000, "30d": 120000}
if "sellers" not in db:
    db["sellers"] = {}

def save_data():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if db.get("last_reset_date") != today_str:
            for s_id, s_info in db["sellers"].items():
                s_info["daily_rev"] = 0
            db["last_reset_date"] = today_str

        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
    except: pass

async def auto_backup_to_admin(context):
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                for adm in admin_list:
                    await context.bot.send_document(
                        chat_id=adm,
                        document=f,
                        filename="database_backup.json",
                        caption="🛡️ **[AUTO BACKUP SYSTEM]**\nFile dữ liệu database mới nhất của bot được sao lưu tự động an toàn tuyệt đối!"
                    )
    except Exception as e:
        logger.error(f"Lỗi backup tự động: {e}")

admin_state = {}
cooldown_cache = {}

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {
            'balance': 0, 'total_deposit': 0, 
            'deposit_history': [], 'buy_history': [], 'my_keys': []
        }
        save_data()
    return db["user_data"][uid_str]

def is_admin(uid):
    return uid in admin_list

def is_seller(uid):
    return str(uid) in db["sellers"] or uid in admin_list

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 1.5:
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
            await context.bot.send_message(chat_id=adm, text="⚡ **[SYSTEM ALERT]**\n\n" + msg + SIGNATURE, parse_mode="HTML")
        except:
            pass

async def show_main_menu(update, context):
    uid = update.effective_user.id
    save_data() 
    
    # Kiểm tra trạng thái bảo trì: Chặn tuyệt đối khách thường, chỉ cho phép Admin truy cập
    if not db["bot_active"] and not is_admin(uid):
        maint_text = (
            f"🚧 **HỆ THỐNG ĐANG BẢO TRÌ NÂNG CẤP** 🚧\n\n"
            f"<i>Bot hiện đang tạm dừng hoạt động để bảo trì hệ thống. Vui lòng quay lại sau ít phút khi Admin mở lại nhé!</i>"
            f"{SIGNATURE}"
        )
        if update.message: await update.message.reply_text(maint_text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.reply_text(maint_text, parse_mode="HTML")
        return

    u = get_u(uid)
    role_badge = "👑 [ADMIN / VIP SELLER]" if is_admin(uid) else ("💎 [SELLER PARTNER]" if is_seller(uid) else "🛡️ [MEMBER]")
    
    text = (
        f"🌌 🔮 **MIZZE CYBERPUNK - ULTIMATE STORE** 🔮 🌌\n"
        f"✨ Cấp bậc: {role_badge}\n\n"
        f"📢 **Kênh Thông Báo:** <a href='{CHANNEL_URL}'>🔗 Tham Gia Kênh</a>\n"
        f"👑 **Admin Hỗ Trợ:** <a href='{ADMIN_CONTACT}'>💬 Liên Hệ Ngay</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 **Tổng Nạp:** <code>{u['total_deposit']:,}đ</code> | 💎 **Số Dư Ví:** <b>{u['balance']:,}đ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **📊 KHO HÀNG REAL-TIME:**\n"
        f"  • ⚡ **1H:** <code>[{len(db['s_1h'])}]</code> | 💎 **1D:** <code>[{len(db['s_1d'])}]</code>\n"
        f"  • 👑 **7D:** <code>[{len(db['s_7d'])}]</code> | 🚀 **30D:** <code>[{len(db['s_30d'])}]</code>"
        f"{SIGNATURE}"
    )
    
    kb_buttons = [
        [InlineKeyboardButton("🛒 CỬA HÀNG MUA KEY", callback_data='menu_shop'), InlineKeyboardButton("💳 NẠP TIỀN TỰ ĐỘNG", callback_data='menu_deposit')],
        [InlineKeyboardButton("🔑 KHO KEY CỦA TÔI", callback_data='my_keys'), InlineKeyboardButton("👤 TÀI KHOẢN CÁ NHÂN", callback_data='menu_account')],
        [InlineKeyboardButton("🧾 LỊCH SỬ NẠP", callback_data='hist_deposit'), InlineKeyboardButton("🛍️ LỊCH SỬ MUA HÀNG", callback_data='hist_buy')],
    ]
    
    if is_seller(uid) and not is_admin(uid):
        kb_buttons.append([InlineKeyboardButton("📊 THỐNG KÊ DOANH THU SELLER", callback_data='seller_stats')])
    
    if is_admin(uid):
        kb_buttons.append([InlineKeyboardButton("⚙️ BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN", callback_data='admin_panel')])
    else:
        kb_buttons.append([InlineKeyboardButton("💬 HỖ TRỢ KHÁCH HÀNG", url=SUPPORT_CONTACT), InlineKeyboardButton("🚀 ĐĂNG KÝ SELLER", callback_data='register_seller')])

    kb = InlineKeyboardMarkup(kb_buttons)
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
    user_obj = update.effective_user
    is_new = str(uid) not in db["users"]
    db["users"][str(uid)] = True
    get_u(uid)
    save_data()

    # Báo ngay cho Admin khi có người dùng tương tác /start mới hoặc truy cập bot
    if is_new or not is_admin(uid):
        try:
            status_bot = "🟢 Đang hoạt động" if db["bot_active"] else "🔴 Đang bảo trì"
            notif_msg = (
                f"👤 **CÓ NGƯỜI DÙNG TƯƠNG TÁC BOT!**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Tên: <b>{user_obj.full_name}</b>\n"
                f"🔹 Username: @{user_obj.username if user_obj.username else 'Không có'}\n"
                f"🔹 ID: <code>{uid}</code>\n"
                f"🔹 Trạng thái hệ thống: <b>{status_bot}</b>"
                f"{SIGNATURE}"
            ]
            for adm in admin_list:
                await context.bot.send_message(chat_id=adm, text=notif_msg, parse_mode="HTML")
        except: pass

    await show_main_menu(update, context)

async def button_handler(update, context):
    query = update.callback_query
    uid = query.from_user.id

    if check_spam(uid):
        await query.answer("⚠️ Thao tác quá nhanh! Hãy từ từ thôi nhé.", show_alert=True)
        return

    await query.answer()
    u = get_u(uid)
    data = query.data
    is_s = is_seller(uid)
    p = db["seller_prices"] if is_s else db["prices"]

    if data == 'back_menu': await show_main_menu(update, context)
    elif data.startswith('copy_memo_'):
        memo_text = data.replace('copy_memo_', '')
        await query.answer(f"📋 Đã copy nội dung: [{memo_text}] thành công!", show_alert=True)
    elif data.startswith('copy_val_'):
        val_text = data.replace('copy_val_', '')
        await query.answer(f"📋 Đã sao chép: [{val_text}] vào bộ nhớ tạm!", show_alert=True)
    elif data == 'register_seller':
        await edit_or_send(query, f"🚀 **ĐĂNG KÝ TRỞ THÀNH SELLER PARTNER**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Trở thành Seller để nhận mức giá ưu đãi cực sốc, quản lý doanh thu ngày và kinh doanh hệ thống key riêng!</i>\n\n👉 Vui lòng liên hệ Admin: <a href='{ADMIN_CONTACT}'>Bấm vào đây để đăng ký ngay</a>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]]))
    elif data == 'my_keys':
        keys_list = "\n".join([f"• <code>{k}</code>" for k in u['my_keys']]) if u['my_keys'] else "<i>Bạn chưa sở hữu key nào. Hãy mua ngay tại cửa hàng!</i>"
        await edit_or_send(query, f"🔑 **KHO KEY ĐÃ MUA CỦA BẠN**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{keys_list}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 <i>Mỗi key của bạn được lưu vĩnh viễn tại đây, không bao giờ bị mất!</i>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Mua Thêm Key", callback_data='menu_shop'), InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]]))
    elif data == 'seller_stats':
        s_id_str = str(uid)
        s_info = db["sellers"].get(s_id_str, {"daily_rev": 0, "target": 500000})
        rev = s_info["daily_rev"]
        target = s_info.get("target", 500000)
        status = "✅ ĐÃ ĐẠT CHỈ TIÊU HÔM NAY" if rev >= target else "⚠️ CHƯA ĐẠT CHỈ TIÊU (CẢNH BÁO GẠCH TÊN)"
        await edit_or_send(query, f"📊 **THỐNG KÊ DOANH THU SELLER**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 Doanh thu hôm nay: <code>{rev:,}đ</code>\n🎯 Mục tiêu trong ngày: <code>{target:,}đ</code>\n📌 Trạng thái: <b>{status}</b>\n\n<i>Lưu ý: Doanh thu ngày sẽ tự động reset về 0 vào lúc nửa đêm!</i>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]]))
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ Mua 1H ({p['1h']:,}đ) [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 Mua 1D ({p['1d']:,}đ) [{len(db['s_1d'])}]", callback_data='shop_1d')],
            [InlineKeyboardButton(f"👑 Mua 7D ({p['7d']:,}đ) [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 Mua 30D ({p['30d']:,}đ) [{len(db['s_30d'])}]", callback_data='shop_30d')],
            [InlineKeyboardButton("💳 Nạp Thêm Tiền", callback_data='menu_deposit'), InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛒 **✨ CỬA HÀNG MUA KEY VIP TỰ ĐỘNG ✨**\n💎 Số dư ví của bạn: <b>{u['balance']:,}đ</b>\n🏷️ Cấp độ giá: <b>{'SELLER VIP' if is_s else 'MEMBER'}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>🔥 Chọn gói dịch vụ bạn muốn sở hữu bên dưới:</i>", kb)
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
        await edit_or_send(query, f"📦 **BẠN ĐANG CHỌN GÓI: {kt.upper()}**\n💰 Giá niêm yết: <b>{price:,}đ / key</b>\n📊 Kho hiện có sẵn: <b>{len(kho)} key</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>👉 Chọn số lượng key bạn muốn mua ngay bên dưới:</i>", kb)
    elif data.startswith('buyq_custom_'):
        kt = data.split('_')[2]
        admin_state[uid] = f"buy_custom_{kt}"
        await edit_or_send(query, f"💬 **Vui lòng nhập số lượng key gói {kt.upper()} bạn muốn mua vào khung chat** (Ví dụ: <code>4</code>):{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data=f"shop_{kt}")]]))
    elif data.startswith('buyq_'):
        parts = data.split('_')
        kt = parts[1]
        qty = int(parts[2])
        await process_purchase(query, context, uid, kt, qty)

    elif data == 'menu_deposit':
        kb_dep = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 10.000đ", callback_data='pre_qr_10000'), InlineKeyboardButton("💵 50.000đ", callback_data='pre_qr_50000')],
            [InlineKeyboardButton("💵 100.000đ", callback_data='pre_qr_100000'), InlineKeyboardButton("💵 200.000đ", callback_data='pre_qr_200000')],
            [InlineKeyboardButton("✏️ Nhập Số Tiền Tùy Chỉnh", callback_data='pre_qr_custom')],
            [InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"💳 **✨ HỆ THỐNG NẠP TIỀN TỰ ĐỘNG 24/7 ✨**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>⚡ Chọn nhanh hạn mức nạp hoặc nhập số tiền tùy ý (Tối thiểu <b>10.000đ</b>):</i>", kb_dep)
    elif data.startswith('pre_qr_'):
        sub = data.replace('pre_qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, f"💬 **Vui lòng nhập số tiền bạn muốn nạp vào khung chat** (Ví dụ: <code>50000</code>):{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]]))
            return
        await show_copy_warning(query, uid, int(sub))
    elif data.startswith('show_qr_'):
        amt = int(data.replace('show_qr_', ''))
        await send_qr(query, context, uid, amt)

    elif data == 'menu_account':
        await edit_or_send(query, f"👤 **✨ THÔNG TIN TÀI KHOẢN CÁ NHÂN ✨**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n🆔 Telegram ID: <code>{uid}</code>\n💎 Số Dư Ví: <b>{u['balance']:,}đ</b>\n💳 Tổng Nạp: <b>{u['total_deposit']:,}đ</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]]))
    elif data == 'hist_deposit':
        h_list = "\n".join(u['deposit_history'][-10:]) if u['deposit_history'] else "Chưa có lịch sử nạp tiền nào."
        await edit_or_send(query, f"🧾 **✨ LỊCH SỬ NẠP TIỀN GẦN NHẤT ✨**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{h_list}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]]))
    elif data == 'hist_buy':
        b_list = "\n".join(u['buy_history'][-10:]) if u['buy_history'] else "Chưa có lịch sử mua hàng nào."
        await edit_or_send(query, f"🛍️ **✨ LỊCH SỬ MUA HÀNG GẦN NHẤT ✨**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{b_list}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu", callback_data='back_menu')]]))
    elif data == 'admin_panel' and is_admin(uid):
        status_text = "🟢 Đang Hoạt Động" if db["bot_active"] else "🔴 Đang Bảo Trì"
        toggle_text = "🔴 Tắt Bot (Bảo Trì)" if db["bot_active"] else "🟢 Bật Bot (Mở Lại)"
        await edit_or_send(query, f"🛡️ **✨ BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN ✨** 🛡️\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nTrạng thái Bot: <b>{status_text}</b>\n<i>⚡ Lựa chọn tính năng quản lý nâng cao bên dưới:</i>", InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data='toggle_bot_status')],
            [InlineKeyboardButton("📊 Thống Kê Kho & Doanh Thu", callback_data='ad_stats')],
            [InlineKeyboardButton("💾 Lấy File Backup Database", callback_data='ad_get_backup')],
            [InlineKeyboardButton("💸 Cộng Tiền", callback_data='ad_bal'), InlineKeyboardButton("📉 Trừ Tiền", callback_data='ad_subbal')],
            [InlineKeyboardButton("💰 Sửa Giá Member / Seller", callback_data='ad_setprice')],
            [InlineKeyboardButton("👥 Quản Lý Seller (Thêm/Xóa)", callback_data='ad_manageseller')],
            [InlineKeyboardButton("🔍 Kiểm Tra Kho Key & Thay Thế", callback_data='ad_checkkey')],
            [InlineKeyboardButton("➕ Bổ Sung Lô Key Mới", callback_data='ad_addk'), InlineKeyboardButton("🔍 Check User", callback_data='ad_checkbal')],
            [InlineKeyboardButton("♻️ RESET DỮ LIỆU HỆ THỐNG", callback_data='ad_reset_menu')],
            [InlineKeyboardButton("📢 Gửi Broadcast", callback_data='ad_bc'), InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]
        ]))
    elif data == 'ad_get_backup' and is_admin(uid):
        await auto_backup_to_admin(context)
        await query.answer("✅ Đã gửi file database.json mới nhất về tin nhắn riêng cho bạn!", show_alert=True)
    elif data == 'toggle_bot_status' and is_admin(uid):
        db["bot_active"] = not db["bot_active"]
        save_data()
        await query.answer(f"Đã chuyển trạng thái bot thành công!", show_alert=True)
        status_text = "🟢 Đang Hoạt Động" if db["bot_active"] else "🔴 Đang Bảo Trì"
        toggle_text = "🔴 Tắt Bot (Bảo Trì)" if db["bot_active"] else "🟢 Bật Bot (Mở Lại)"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data='toggle_bot_status')],
            [InlineKeyboardButton("📊 Thống Kê Kho & Doanh Thu", callback_data='ad_stats')],
            [InlineKeyboardButton("💾 Lấy File Backup Database", callback_data='ad_get_backup')],
            [InlineKeyboardButton("💸 Cộng Tiền", callback_data='ad_bal'), InlineKeyboardButton("📉 Trừ Tiền", callback_data='ad_subbal')],
            [InlineKeyboardButton("💰 Sửa Giá Member / Seller", callback_data='ad_setprice')],
            [InlineKeyboardButton("👥 Quản Lý Seller (Thêm/Xóa)", callback_data='ad_manageseller')],
            [InlineKeyboardButton("🔍 Kiểm Tra Kho Key & Thay Thế", callback_data='ad_checkkey')],
            [InlineKeyboardButton("➕ Bổ Sung Lô Key Mới", callback_data='ad_addk'), InlineKeyboardButton("🔍 Check User", callback_data='ad_checkbal')],
            [InlineKeyboardButton("♻️ RESET DỮ LIỆU HỆ THỐNG", callback_data='ad_reset_menu')],
            [InlineKeyboardButton("📢 Gửi Broadcast", callback_data='ad_bc'), InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛡️ **✨ BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN ✨** 🛡️\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nTrạng thái Bot: <b>{status_text}</b>", kb)
    elif data == 'ad_stats' and is_admin(uid):
        p = db["prices"]
        sp = db["seller_prices"]
        total_keys = len(db['s_1h']) + len(db['s_1d']) + len(db['s_7d']) + len(db['s_30d'])
        await edit_or_send(query, f"📊 **✨ THỐNG KÊ KHO & DOANH THU ✨**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n👥 Tổng User: <code>{len(db['users'])}</code>\n👑 Tổng Seller: <code>{len(db['sellers'])}</code>\n💰 Tổng Doanh Thu: <code>{db['total_rev']:,}đ</code>\n📦 Tổng Key Tồn Kho: <b>{total_keys} key</b>\n\n📦 **Chi Tiết Kho & Giá:**\n• <b>1H</b> (Mem: {p['1h']:,} | Sel: {sp['1h']:,}): <code>{len(db['s_1h'])} key</code>\n• <b>1D</b> (Mem: {p['1d']:,} | Sel: {sp['1d']:,}): <code>{len(db['s_1d'])} key</code>\n• <b>7D</b> (Mem: {p['7d']:,} | Sel: {sp['7d']:,}): <code>{len(db['s_7d'])} key</code>\n• <b>30D</b> (Mem: {p['30d']:,} | Sel: {sp['30d']:,}): <code>{len(db['s_30d'])} key</code>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Admin Panel", callback_data='admin_panel')]]))
    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, f"💬 **Nhập ID user và số tiền cần cộng** theo định dạng:\n<code>[ID] [Số_tiền]</code>\n(Ví dụ: <code>7976468365 50000</code>){SIGNATURE}")
    elif data == 'ad_subbal' and is_admin(uid):
        admin_state[uid] = 'sub_bal'
        await edit_or_send(query, f"💬 **Nhập ID user và số tiền cần trừ/xóa** theo định dạng:\n<code>[ID] [Số_tiền]</code>\n(Ví dụ: <code>7976468365 20000</code>){SIGNATURE}")
    elif data == 'ad_setprice' and is_admin(uid):
        await edit_or_send(query, f"💰 **CHỌN CẤP ĐỘ GIÁ CẦN SỬA:**", InlineKeyboardMarkup([
            [InlineKeyboardButton("🏷️ Sửa Giá Member", callback_data='set_type_mem'), InlineKeyboardButton("👑 Sửa Giá Seller", callback_data='set_type_sel')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data == 'set_type_mem' and is_admin(uid):
        await edit_or_send(query, f"🏷️ **CHỌN GÓI MEMBER CẦN SỬA GIÁ:**", InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ 1H", callback_data='pm_1h'), InlineKeyboardButton("💎 1D", callback_data='pm_1d')],
            [InlineKeyboardButton("👑 7D", callback_data='pm_7d'), InlineKeyboardButton("🚀 30D", callback_data='pm_30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_setprice')]
        ]))
    elif data == 'set_type_sel' and is_admin(uid):
        await edit_or_send(query, f"👑 **CHỌN GÓI SELLER CẦN SỬA GIÁ:**", InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ 1H", callback_data='ps_1h'), InlineKeyboardButton("💎 1D", callback_data='ps_1d')],
            [InlineKeyboardButton("👑 7D", callback_data='ps_7d'), InlineKeyboardButton("🚀 30D", callback_data='ps_30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_setprice')]
        ]))
    elif data.startswith('pm_') and is_admin(uid):
        pk = data.replace('pm_', '')
        admin_state[uid] = f"setprice_mem_{pk}"
        await edit_or_send(query, f"💬 **Nhập giá MEMBER mới cho gói {pk.upper()}** (Ví dụ: <code>8000</code>):{SIGNATURE}")
    elif data.startswith('ps_') and is_admin(uid):
        pk = data.replace('ps_', '')
        admin_state[uid] = f"setprice_sel_{pk}"
        await edit_or_send(query, f"💬 **Nhập giá SELLER mới cho gói {pk.upper()}** (Ví dụ: <code>5000</code>):{SIGNATURE}")
    elif data == 'ad_manageseller' and is_admin(uid):
        s_count = len(db["sellers"])
        await edit_or_send(query, f"👥 **QUẢN LÝ SELLER PARTNER**\n📊 Tổng số Seller hiện tại: <b>{s_count}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nChọn thao tác bên dưới:", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Thêm Seller Mới (Theo ID)", callback_data='add_seller_prompt')],
            [InlineKeyboardButton("🗑️ Xóa Seller (Theo ID)", callback_data='del_seller_prompt')],
            [InlineKeyboardButton("📋 Danh Sách Seller", callback_data='list_sellers')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data == 'add_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'add_seller_id'
        await edit_or_send(query, f"💬 **Nhập Telegram ID và Mục Tiêu Doanh Thu Ngày** (Mặc định 500k nếu không nhập) theo định dạng:\n<code>[ID] [Mục_tiêu]</code>\n(Ví dụ: <code>7976468365 500000</code>){SIGNATURE}")
    elif data == 'del_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'del_seller_id'
        await edit_or_send(query, f"💬 **Nhập Telegram ID của Seller cần hủy quyền:**\n(Ví dụ: <code>7976468365</code>){SIGNATURE}")
    elif data == 'list_sellers' and is_admin(uid):
        s_txt = "\n".join([f"• ID: <code>{sid}</code> | Doanh thu ngày: <code>{info.get('daily_rev',0):,}đ</code>" for sid, info in db["sellers"].items()]) if db["sellers"] else "Chưa có Seller nào."
        await edit_or_send(query, f"📋 **DANH SÁCH SELLER PARTNER**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{s_txt}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='ad_manageseller')]]))
    elif data == 'ad_checkkey' and is_admin(uid):
        await edit_or_send(query, f"🔍 **CHỌN KHO HÀNG CẦN KIỂM TRA / THAY THẾ:**", InlineKeyboardMarkup([
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
        await edit_or_send(query, f"📦 **KIỂM TRA KHO {k_type.upper()}**\n📊 Tổng tồn kho: <b>{len(target)} key</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{preview}{SIGNATURE}", kb)
    elif data.startswith('replace_') and is_admin(uid):
        k_type = data.replace('replace_', '')
        admin_state[uid] = f"replacekeys_{k_type}"
        await edit_or_send(query, f"⚠️ **THAY THẾ TOÀN BỘ KHO {k_type.upper()}**\n<i>Hệ thống sẽ xóa sạch danh sách cũ và thay thế hoàn toàn bằng danh sách mới bạn gửi.</i>\n\n📝 **Dán danh sách lô Key mới vào khung chat:**{SIGNATURE}")
    elif data == 'ad_reset_menu' and is_admin(uid):
        await edit_or_send(query, f"♻️ **TRUNG TÂM RESET DỮ LIỆU HỆ THỐNG**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Chọn hạng mục bạn muốn reset trắng:</i>", InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Reset Toàn Bộ Doanh Thu Về 0", callback_data='reset_rev_confirm')],
            [InlineKeyboardButton("🔄 Reset Trắng Tất Cả Kho Key", callback_data='reset_kho_confirm')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data == 'reset_rev_confirm' and is_admin(uid):
        db["total_rev"] = 0
        for s_info in db["sellers"].values(): s_info["daily_rev"] = 0
        save_data()
        await query.answer("✅ Đã reset toàn bộ doanh thu hệ thống về 0!", show_alert=True)
    elif data == 'reset_kho_confirm' and is_admin(uid):
        db["s_1h"].clear(); db["s_1d"].clear(); db["s_7d"].clear(); db["s_30d"].clear()
        save_data()
        await query.answer("✅ Đã xóa sạch toàn bộ key trong kho!", show_alert=True)
    elif data == 'ad_checkbal' and is_admin(uid):
        admin_state[uid] = 'check_user_bal'
        await edit_or_send(query, f"💬 **Nhập Telegram ID của người dùng cần kiểm tra số dư:**\n(Ví dụ: <code>7976468365</code>){SIGNATURE}")
    elif data == 'ad_addadmin' and uid == ADMIN_ID:
        admin_state[uid] = 'add_admin_id'
        await edit_or_send(query, f"💬 **Nhập Telegram ID của tài khoản muốn phân quyền làm Admin phụ:**\n(Ví dụ: <code>123456789</code>){SIGNATURE}")
    elif data == 'ad_bc' and is_admin(uid):
        admin_state[uid] = 'bc'
        await edit_or_send(query, f"💬 **Nhập nội dung thông báo (Broadcast)** muốn gửi tới toàn bộ người chơi:{SIGNATURE}")
    elif data == 'ad_addk' and is_admin(uid):
        await edit_or_send(query, f"📦 **CHỌN KHO HÀNG CẦN BỔ SUNG LÔ KEY:**", InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Kho 1H", callback_data='k_s1h'), InlineKeyboardButton("🛒 Kho 1D", callback_data='k_s1d')],
            [InlineKeyboardButton("🛒 Kho 7D", callback_data='k_s7d'), InlineKeyboardButton("🛒 Kho 30D", callback_data='k_s30d')],
            [InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data.startswith('k_') and is_admin(uid):
        admin_state[uid] = f"addk_{data.replace('k_', '')}"
        await edit_or_send(query, f"📝 **Dán danh sách lô Key mới vào khung chat.**\n(Mỗi key / dữ liệu cách nhau bằng dòng trống):{SIGNATURE}")

async def show_copy_warning(query, uid, amount):
    memo_code = f"NAP {uid}"
    text = (
        f"🚨 🛑 **CẢNH BÁO CỰC KỲ QUAN TRỌNG** 🛑 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❗ ⚠️ **BẠN BẮT BUỘC PHẢI COPY NỘI DUNG CHUYỂN KHOẢN SAU ĐÂY!**\n\n"
        f"📝 Nội dung CK: <code>{memo_code}</code>\n"
        f"👉 <i>(Nhấn vào nút bên dưới để sao chép tự động hoặc chạm vào mã để copy)</i>\n\n"
        f"❌ <b>TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA ĐỔI HOẶC XÓA NỘI DUNG NÀY!</b>\n"
        f"💡 <i>Sau khi đã copy nội dung, hãy bấm nút xác nhận để mở mã QR nạp tiền {amount:,}đ!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 BẤM ĐỂ COPY NỘI DUNG NGAY", callback_data=f"copy_memo_{memo_code}")],
        [InlineKeyboardButton("✅ TÔI ĐÃ COPY - XEM MÃ QR 🚀", callback_data=f"show_qr_{amount}")],
        [InlineKeyboardButton("◀️ Chọn Mức Nạp Khác", callback_data='menu_deposit')]
    ])
    await edit_or_send(query, text, kb)

async def send_qr(query, context, uid, amount):
    if amount < 10000:
        await query.answer("❌ Số tiền nạp tối thiểu là 10.000đ!", show_alert=True)
        return
    
    memo_code = f"NAP {uid}"
    url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amount}&memo={quote(memo_code)}"
    
    text = (
        f"💳 **✨ MÃ QR NẠP TIỀN TỰ ĐỘNG 24/7 ✨**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Ngân hàng: <b>{BANK_ID}</b>\n"
        f"🔢 Số tài khoản: <code>{ACCOUNT_NO}</code>\n"
        f"👤 Chủ tài khoản: <b>{ACCOUNT_NAME}</b>\n"
        f"💵 Số tiền: <b>{amount:,}đ</b>\n"
        f"📝 Nội dung CK: <code>{memo_code}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 **LƯU Ý CỰC KỲ QUAN TRỌNG:**\n"
        f"⚠️ <b>TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA ĐỔI HOẶC XÓA NỘI DUNG CHUYỂN KHOẢN!</b>\n"
        f"⚠️ <i>Nếu bạn ghi sai nội dung <code>{memo_code}</code>, hệ thống SePay sẽ KHÔNG THỂ nhận diện để tự động cộng tiền cho bạn!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👉 <i>Quét mã QR bằng App ngân hàng. Tiền sẽ được tự động cộng vào ví sau vài giây!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 COPY NỘI DUNG CK", callback_data=f"copy_memo_{memo_code}")],
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
    is_s = is_seller(uid)
    p = db["seller_prices"] if is_s else db["prices"]
    p_map = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}
    price_per_item, kho = p_map[kt]
    total_price = price_per_item * qty

    if len(kho) < qty:
        await query.answer(f"❌ Kho Key {kt.upper()} không đủ số lượng! Hiện chỉ còn {len(kho)} key.", show_alert=True)
        return
    if u['balance'] < total_price:
        await edit_or_send(query, f"❌ **Số dư ví không đủ!**\nBạn cần <code>{total_price:,}đ</code> cho {qty} key nhưng ví chỉ có <code>{u['balance']:,}đ</code>.\nVui lòng nạp thêm tiền để tiếp tục mua hàng nhé!", InlineKeyboardMarkup([[InlineKeyboardButton("💳 Nạp Tiền Ngay", callback_data='menu_deposit'), InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_shop')]]))
        return

    u['balance'] -= total_price
    db["total_rev"] += total_price
    
    if is_s and not is_admin(uid):
        s_id_str = str(uid)
        if s_id_str in db["sellers"]:
            db["sellers"][s_id_str]["daily_rev"] = db["sellers"][s_id_str].get("daily_rev", 0) + total_price

    keys_bought = []
    for _ in range(qty):
        k = kho.pop(0)
        keys_bought.append(k)
        u['my_keys'].append(f"[{kt.upper()}] {k}")

    time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    u['buy_history'].append(f"[{time_str}] Mua {qty}x gói {kt.upper()} (-{total_price:,}đ)")
    if len(u['buy_history']) > 20: u['buy_history'].pop(0)
    save_data()
    
    await auto_backup_to_admin(context)

    keys_str = "\n".join([f"<code>{k}</code>" for k in keys_bought])
    
    # Gửi thông báo mua hàng thẳng lên nhóm khách hàng trực tiếp, không làm phiền Admin
    try:
        group_buy_msg = (
            f"🛍️ **GIAO DỊCH MUA KEY THÀNH CÔNG!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Khách hàng: <code>{query.from_user.full_name}</code> (ID: <code>{uid}</code>)\n"
            f"📦 Gói dịch vụ: <b>{qty}x {kt.upper()}</b>\n"
            f"💵 Tổng thanh toán: <b>{total_price:,}đ</b>\n"
            f"🔑 Key / Dữ liệu của khách:\n{keys_str}\n"
            f"⏱️ Thời gian: {time_str}"
            f"{SIGNATURE}"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=group_buy_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Không thể gửi thông báo mua hàng lên nhóm: {e}")

    # Xây dựng các nút bấm Copy Key, Copy Mật khẩu và Nhận File riêng biệt trực quan
    first_key = keys_bought[0] if keys_bought else "Mizzebin"
    success_kb_buttons = [
        [InlineKeyboardButton("📋 COPY KEY NÀY", callback_data=f"copy_val_{first_key}"), InlineKeyboardButton("📋 COPY MẬT KHẨU", callback_data=f"copy_val_{first_key}")],
        [InlineKeyboardButton("📂 Truy Cập Nhóm Nhận File", url=CLIENT_GROUP_LINK)],
        [InlineKeyboardButton("🔑 Xem Kho Key Của Tôi", callback_data='my_keys')],
        [InlineKeyboardButton("🛒 Mua Gói Khác", callback_data='menu_shop'), InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]
    ]
    success_kb = InlineKeyboardMarkup(success_kb_buttons)
    
    await edit_or_send(query, f"✅ **MUA {qty} KEY THÀNH CÔNG RỰC RỠ!**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n📦 Gói: <b>{qty}x {kt.upper()}</b> | Trừ: <code>-{total_price:,}đ</code>\n\n👇 **Danh sách mã Key / Dữ liệu của bạn:**\n{keys_str}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n📂 <i>Bạn có thể bấm nút copy bên dưới hoặc vào nhóm nhận file cài đặt!</i>\n💎 Số dư ví còn lại: <b>{u['balance']:,}đ</b>{SIGNATURE}", success_kb)

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
            class DummyQuery:
                def __init__(self, msg, user):
                    self.message = msg
                    self.from_user = user
                async def answer(self, *args, **kwargs): pass
            
            dummy_q = DummyQuery(update.message, update.message.from_user)
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
            
            memo_code = f"NAP {uid}"
            text_warn = (
                f"🚨 🛑 **CẢNH BÁO CỰC KỲ QUAN TRỌNG** 🛑 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"❗ ⚠️ **BẠN BẮT BUỘC PHẢI COPY NỘI DUNG CHUYỂN KHOẢN SAU:**\n"
                f"📝 Nội dung CK: <code>{memo_code}</code>\n\n"
                f"❌ <b>TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA ĐỔI HOẶC XÓA NỘI DUNG NÀY!</b>"
            )
            url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amt}&memo={quote(memo_code)}"
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 BẤM ĐỂ COPY NỘI DUNG NGAY", callback_data=f"copy_memo_{memo_code}")],
                [InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]
            ])
            await update.message.reply_text(text_warn, parse_mode="HTML")
            await update.message.reply_photo(photo=url, caption=f"💳 **QR NẠP {amt:,}đ**\n📝 Nội dung CK: <code>{memo_code}</code>", reply_markup=kb, parse_mode="HTML")
        except: await update.message.reply_text("❌ Số tiền nhập không hợp lệ!")
        return

    if not is_admin(uid): return

    if state.startswith('setprice_mem_'):
        pk = state.replace('setprice_mem_', '')
        del admin_state[uid]
        try:
            new_p = int(text.replace(".", "").strip())
            db["prices"][pk] = new_p
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá MEMBER cho gói <b>{pk.upper()}</b> thành <b>{new_p:,}đ</b>!", parse_mode="HTML")
        except:
            await update.message.reply_text("❌ Giá tiền không hợp lệ!")
        return

    if state.startswith('setprice_sel_'):
        pk = state.replace('setprice_sel_', '')
        del admin_state[uid]
        try:
            new_p = int(text.replace(".", "").strip())
            db["seller_prices"][pk] = new_p
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá SELLER cho gói <b>{pk.upper()}</b> thành <b>{new_p:,}đ</b>!", parse_mode="HTML")
        except:
            await update.message.reply_text("❌ Giá tiền không hợp lệ!")
        return

    if state == 'add_seller_id':
        del admin_state[uid]
        try:
            parts = text.split()
            sid = str(parts[0])
            target = int(parts[1]) if len(parts) > 1 else 500000
            db["sellers"][sid] = {"daily_rev": 0, "target": target}
            save_data()
            await update.message.reply_text(f"✅ Đã thêm Seller ID <code>{sid}</code> thành công với mục tiêu ngày <code>{target:,}đ</code>!")
        except:
            await update.message.reply_text("❌ Sai cú pháp! Nhập: `[ID] [Mục_tiêu]`")
        return

    if state == 'del_seller_id':
        del admin_state[uid]
        sid = text.strip()
        if sid in db["sellers"]:
            del db["sellers"][sid]
            save_data()
            await update.message.reply_text(f"✅ Đã hủy quyền Seller của ID <code>{sid}</code> thành công!")
        else:
            await update.message.reply_text(f"❌ Không tìm thấy Seller ID này trong hệ thống.")
        return

    if state.startswith('replacekeys_'):
        k_type = state.replace('replacekeys_', '')
        del admin_state[uid]
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        target = m_map.get(k_type)
        if target is not None:
            target.clear()
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
            try: await context.bot.send_message(tid, f"🎁 **[TÀI CHÍNH]** Bạn vừa được Admin cộng thêm <b>+{amt:,}đ</b> vào số dư ví!{SIGNATURE}", parse_mode="HTML")
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
            try: await context.bot.send_message(tid, f"⚠️ **[TÀI CHÍNH]** Số dư ví của bạn vừa bị Admin trừ bớt <b>-{amt:,}đ</b>!{SIGNATURE}", parse_mode="HTML")
            except: pass
        except: await update.message.reply_text("❌ Sai cú pháp! Vui lòng nhập: `[ID] [Số_tiền]`")
        del admin_state[uid]
    elif state == 'check_user_bal':
        try:
            tid = int(text.strip())
            if str(tid) in db["user_data"]:
                target_u = db["user_data"][str(tid)]
                hist_preview = "\n".join(target_u['deposit_history'][-5:]) if target_u['deposit_history'] else "Trống."
                await update.message.reply_text(f"🔍 **THÔNG TIN SỐ DƯ USER**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n🆔 ID: <code>{tid}</code>\n💎 Số dư ví: <b>{target_u['balance']:,}đ</b>\n💳 Tổng nạp: <b>{target_u['total_deposit']:,}đ</b>\n\n🧾 **Lịch sử nạp gần đây:**\n{hist_preview}{SIGNATURE}", parse_mode="HTML")
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
                await context.bot.send_message(chat_id=new_adm, text=f"👑 **[QUYỀN HẠN]** Bạn đã được bổ nhiệm làm Quản Trị Viên của bot! Hãy dùng lệnh /start hoặc mở Admin Panel để quản lý hệ thống.{SIGNATURE}", parse_mode="HTML")
            except:
                pass
        except:
            await update.message.reply_text("❌ ID Admin không hợp lệ!")
        del admin_state[uid]
    elif state == 'bc':
        del admin_state[uid]
        succ = 0
        for u_str in list(db["users"]):
            try: await context.bot.send_message(int(u_str), f"📢 **THÔNG BÁO TỪ HỆ THỐNG**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{html.escape(text)}{SIGNATURE}", parse_mode="HTML"); succ += 1
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
        del admin_state[uid]

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "OK", 200

@flask_app.route('/sepay_webhook', methods=['POST'])
def sepay():
    auth_header = request.headers.get('Authorization', '')
    if SEPAY_KEY not in auth_header and auth_header != f"Apikey {SEPAY_KEY}" and SEPAY_KEY != "botgetkey_sepay":
        pass
    
    data = request.json
    if data:
        transfer_type = str(data.get("transferType", "in")).lower()
        if transfer_type in ["in", "receive", "plus"] or data.get("transferAmount"):
            content = str(data.get("content", data.get("description", "")))
            m = re.search(r"NAP[\s\-]*(\d+)", content, re.IGNORECASE)
            if m:
                tid = int(m.group(1))
                amt = int(data.get("transferAmount", data.get("amount", 0)))
                if amt > 0:
                    u = get_u(tid)
                    u['balance'] += amt
                    u['total_deposit'] += amt
                    db["total_rev"] += amt
                    
                    if str(tid) in db["sellers"]:
                        db["sellers"][str(tid]]["daily_rev"] = db["sellers"][str(tid)].get("daily_rev", 0) + amt

                    time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    u['deposit_history'].append(f"[{time_str}] Nạp tự động SePay (+{amt:,}đ)")
                    if len(u['deposit_history']) > 20: u['deposit_history'].pop(0)
                    save_data()
                    
                    try:
                        msg = (
                            f"🎉 **NẠP TIỀN TỰ ĐỘNG THÀNH CÔNG!**\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💵 Số tiền nhận: <b>+{amt:,}đ</b>\n"
                            f"💎 Số dư ví mới: <b>{u['balance']:,}đ</b>"
                            f"{SIGNATURE}"
                        )
                        httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": tid, "text": msg, "parse_mode": "HTML"})
                        
                        # Tự động gửi thông báo nạp tiền thẳng lên nhóm khách hàng và backup cho Admin
                        dep_group_msg = (
                            f"💳 **CÓ GIAO DỊCH NẠP TIỀN THÀNH CÔNG!**\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 Khách hàng ID: <code>{tid}</code>\n"
                            f"💵 Số tiền nạp: <b>+{amt:,}đ</b>\n"
                            f"⏱️ Thời gian: {time_str}"
                            f"{SIGNATURE}"
                        )
                        httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": LOG_GROUP_ID, "text": dep_group_msg, "parse_mode": "HTML"})
                        
                        with open(DB_FILE, "rb") as f_bak:
                            httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument", data={"chat_id": ADMIN_ID, "caption": f"🛡️ [AUTO BACKUP] Cập nhật database sau khi User {tid} nạp {amt:,}đ!"}, files={"document": f_bak})
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