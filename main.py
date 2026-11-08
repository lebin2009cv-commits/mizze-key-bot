import os, logging, threading, httpx, re, time, html, datetime, json
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

LOG_GROUP_ID = -1003912025872
CLIENT_GROUP_LINK = "https://t.me/mizze_lebin" 
SIGNATURE = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚡ 🔮 **MIZZE STORE - NEXUS CORE** 🔮 ⚡"
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
        "users": {}, "user_data": {}, "sellers": {},
        "s_1h": [], "s_1d": [], "s_7d": [], "s_30d": [], 
        "prices": {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000},
        "seller_prices": {"1h": 5000, "1d": 15000, "7d": 60000, "30d": 120000},
        "total_rev": 0, "bot_active": True, "last_reset_date": datetime.datetime.now().strftime("%Y-%m-%d")
    }

db = load_data()
if "prices" not in db: db["prices"] = {"1h": 7000, "1d": 20000, "7d": 75000, "30d": 150000}
if "seller_prices" not in db: db["seller_prices"] = {"1h": 5000, "1d": 15000, "7d": 60000, "30d": 120000}
if "sellers" not in db: db["sellers"] = {}

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
    except: pass

async def auto_backup_to_admin(context):
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                for adm in admin_list:
                    await context.bot.send_document(chat_id=adm, document=f, filename="database_backup.json", caption="🛡️ **[SYSTEM BACKUP]**\nDữ liệu database đã được sao lưu tự động!")
    except: pass

admin_state = {}
cooldown_cache = {}

def get_u(uid):
    uid_str = str(uid)
    if uid_str not in db["user_data"]:
        db["user_data"][uid_str] = {'balance': 0, 'total_deposit': 0, 'deposit_history': [], 'buy_history': [], 'my_keys': []}
        save_data()
    return db["user_data"][uid_str]

def is_admin(uid): return uid in admin_list
def is_seller(uid): return str(uid) in db["sellers"] or uid in admin_list

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 1.2: return True
    if len(cooldown_cache) > 1000: cooldown_cache.clear()
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

async def check_seller_quotas_on_startup(context):
    expired = db.pop("_expired_sellers_yesterday", [])
    if expired:
        for s_id in expired:
            if s_id in db["sellers"]:
                del db["sellers"][s_id]
                save_data()
                try:
                    msg = (
                        f"🚨 ⚡ **THÔNG BÁO THU HỒI QUYỀN SELLER** ⚡ 🚨\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"❌ Doanh thu ngày hôm qua của bạn không đạt chỉ tiêu hệ thống.\n"
                        f"👉 Quyền Seller đã tự động hủy. Tài khoản chuyển về cấp độ Member chuẩn."
                        f"{SIGNATURE}"
                    )
                    await context.bot.send_message(chat_id=int(s_id), text=msg, parse_mode="HTML")
                    await context.bot.send_message(chat_id=LOG_GROUP_ID, text=f"⚠️ **HỆ THỐNG ĐÃ TỰ ĐỘNG HỦY QUYỀN SELLER ID:** <code>{s_id}</code> do trượt chỉ tiêu ngày!", parse_mode="HTML")
                except: pass

async def show_main_menu(update, context):
    uid = update.effective_user.id
    user_obj = update.effective_user
    save_data()
    await check_seller_quotas_on_startup(context)

    if not db["bot_active"] and not is_admin(uid):
        maint_text = f"🚧 🛑 **MIZZE STORE - HỆ THỐNG BẢO TRÌ** 🛑 🚧\n\n<i>Trạm dịch vụ đang tạm khóa để tối ưu hóa lõi mạng. Vui lòng quay lại sau ít phút!</i>{SIGNATURE}"
        if update.message: await update.message.reply_text(maint_text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.reply_text(maint_text, parse_mode="HTML")
        return

    u = get_u(uid)
    role_badge = "👑 ⟦ ADMIN / MASTER VIP ⟧" if is_admin(uid) else ("💎 ⟦ SELLER PARTNER ⟧" if is_seller(uid) else "🛡️ ⟦ MEMBER STANDARD ⟧")
    
    text = (
        f"👋 Chào mừng <b>{user_obj.full_name}</b> đã đến với <b>Mizze Store</b>! 🌟\n\n"
        f"┏━━━━━━✦ <b>M I Z Z E  S T O R E</b> ✦━━━━━━┓\n"
        f"┃ 👤 <b>Cấp độ:</b> {role_badge}\n"
        f"┃ 💎 <b>Số dư ví:</b> <code>{u['balance']:,} VNĐ</code>\n"
        f"┃ 💳 <b>Tổng nạp:</b> <code>{u['total_deposit']:,} VNĐ</code>\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📡 **KÊNH & TRỢ GIÚP:**\n"
        f"  • 🌐 Kênh thông báo: <a href='{CHANNEL_URL}'>[ Bấm vào đây ]</a>\n"
        f"  • 💬 Hỗ trợ trực tuyến: <a href='{ADMIN_CONTACT}'>[ Liên hệ Admin ]</a>\n\n"
        f"📦 **KHO LƯU TRỮ KEY HỆ THỐNG:**\n"
        f"  ⚡ <b>Gói 1H:</b> <code>[{len(db['s_1h'])} key]</code> | 💎 <b>Gói 1D:</b> <code>[{len(db['s_1d'])} key]</code>\n"
        f"  👑 <b>Gói 7D:</b> <code>[{len(db['s_7d'])} key]</code> | 🚀 <b>Gói 30D:</b> <code>[{len(db['s_30d'])} key]</code>"
        f"{SIGNATURE}"
    )
    
    kb_buttons = [
        [InlineKeyboardButton("🔮 [ TRUNG TÂM MUA KEY ]", callback_data='menu_shop'), InlineKeyboardButton("💳 [ NẠP TIỀN TỰ ĐỘNG ]", callback_data='menu_deposit')],
        [InlineKeyboardButton("🔑 [ KHO KEY CỦA TÔI ]", callback_data='my_keys'), InlineKeyboardButton("👤 [ TÀI KHOẢN CÁ NHÂN ]", callback_data='menu_account')],
        [InlineKeyboardButton("🧾 [ LỊCH SỬ NẠP ]", callback_data='hist_deposit'), InlineKeyboardButton("🛍️ [ LỊCH SỬ MUA HÀNG ]", callback_data='hist_buy')],
    ]
    if is_seller(uid) and not is_admin(uid): kb_buttons.append([InlineKeyboardButton("📊 [ DOANH THU & CHỈ TIÊU SELLER ]", callback_data='seller_stats')])
    if is_admin(uid): kb_buttons.append([InlineKeyboardButton("⚙️ [ TRẠM QUẢN TRỊ ADMIN ]", callback_data='admin_panel')])
    else: kb_buttons.append([InlineKeyboardButton("🎧 [ HỖ TRỢ KHÁCH HÀNG ]", url=SUPPORT_CONTACT), InlineKeyboardButton("🚀 [ ĐĂNG KÝ SELLER ]", callback_data='register_seller')])

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
    db["users"][str(uid)] = True
    get_u(uid)
    save_data()
    await show_main_menu(update, context)

async def button_handler(update, context):
    query = update.callback_query
    uid = query.from_user.id
    if check_spam(uid):
        await query.answer("⚠️ Thao tác quá nhanh! Bình tĩnh lại nhé.", show_alert=True)
        return
    await query.answer()
    u = get_u(uid)
    data = query.data
    is_s = is_seller(uid)
    p = db["seller_prices"] if is_s else db["prices"]

    if data == 'back_menu': await show_main_menu(update, context)
    elif data.startswith('copy_memo_'):
        memo_text = data.replace('copy_memo_', '')
        await query.answer(f"📋 Đã copy nội dung: [{memo_text}]", show_alert=True)
    elif data.startswith('copy_val_'):
        await query.answer(f"📋 Đã sao chép key thành công!", show_alert=True)
    elif data == 'register_seller':
        await edit_or_send(query, f"🚀 **ĐĂNG KÝ SELLER PARTNER - MIZZE STORE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nLiên hệ ngay Admin để nhận chính sách giá sỉ ưu đãi:\n👉 <a href='{ADMIN_CONTACT}'>Bấm vào đây liên hệ Admin</a>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='back_menu')]]))
    elif data == 'my_keys':
        keys_list = "\n".join([f"• <code>{k}</code>" for k in u['my_keys']]) if u['my_keys'] else "<i>Kho key cá nhân đang trống. Hãy mua hàng tại cửa hàng!</i>"
        await edit_or_send(query, f"🔑 **KHO KEY ĐÃ SỞ HỮU - MIZZE STORE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{keys_list}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 <i>Dữ liệu được lưu trữ vĩnh viễn trên trạm hệ thống!</i>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("🔮 ⟦ MUA THÊM KEY ⟧", callback_data='menu_shop')], [InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='back_menu')]]))
    elif data == 'seller_stats':
        s_info = db["sellers"].get(str(uid), {"daily_rev": 0, "target": 500000})
        rev, target = s_info["daily_rev"], s_info.get("target", 500000)
        percent = min(100, int((rev / target) * 100)) if target > 0 else 100
        status = "🟢 HOÀN THÀNH XUẤT SẮC" if rev >= target else "🔴 CHƯA ĐẠT CHỈ TIÊU (CẢNH BÁO)"
        await edit_or_send(query, f"📊 **BẢNG CHỈ TIÊU & DOANH THU SELLER**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Doanh thu hôm nay: <code>{rev:,} VNĐ</code>\n- Mục tiêu yêu cầu: <code>{target:,} VNĐ</code>\n- Tiến độ: <b>{percent}%</b>\n- Trạng thái: <b>{status}</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='back_menu')]]))
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ 1H ➔ {p['1h']:,}đ [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 1D ➔ {p['1d']:,}đ [{len(db['s_1d'])}]", callback_data='shop_1d')],
            [InlineKeyboardButton(f"👑 7D ➔ {p['7d']:,}đ [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 30D ➔ {p['30d']:,}đ [{len(db['s_30d'])}]", callback_data='shop_30d')],
            [InlineKeyboardButton("💳 [ NẠP THÊM TIỀN VÀO VÍ ]", callback_data='menu_deposit')],
            [InlineKeyboardButton("◀️ [ QUAY LẠI MENU CHÍNH ]", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🔮 **TRUNG TÂM MUA GÓI TỰ ĐỘNG - MIZZE STORE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Ví hiện tại: <b>{u['balance']:,} VNĐ</b>\n- Bảng giá áp dụng: <b>{'SELLER (GIÁ ƯU ĐÃI)' if is_s else 'MEMBER'}</b>{SIGNATURE}", kb)
    elif data.startswith('shop_'):
        kt = data.split('_')[1]
        price, kho = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}[kt]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ Mua 1 Key", callback_data=f"buyq_{kt}_1"), InlineKeyboardButton("2️⃣ Mua 2 Key", callback_data=f"buyq_{kt}_2")],
            [InlineKeyboardButton("5️⃣ Mua 5 Key", callback_data=f"buyq_{kt}_5"), InlineKeyboardButton("🔟 Mua 10 Key", callback_data=f"buyq_{kt}_10")],
            [InlineKeyboardButton("✏️ [ NHẬP SỐ LƯỢNG TÙY CHỈNH ]", callback_data=f"buyq_custom_{kt}")],
            [InlineKeyboardButton("◀️ [ QUAY LẠI CỬA HÀNG ]", callback_data='menu_shop')]
        ])
        await edit_or_send(query, f"📦 **GÓI DỊCH VỤ: {kt.upper()}**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Đơn giá: <b>{price:,} VNĐ / key</b>\n- Tồn kho khả dụng: <b>{len(kho)} key</b>", kb)
    elif data.startswith('buyq_custom_'):
        kt = data.split('_')[2]
        admin_state[uid] = f"buy_custom_{kt}"
        await edit_or_send(query, f"💬 **Nhập số lượng key bạn muốn mua vào khung chat:**", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data=f"shop_{kt}")]]))
    elif data.startswith('buyq_'):
        _, kt, qty = data.split('_')
        await process_purchase(query, context, uid, kt, int(qty))
    elif data == 'menu_deposit':
        kb_dep = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 10.000đ", callback_data='pre_qr_10000'), InlineKeyboardButton("💵 50.000đ", callback_data='pre_qr_50000')],
            [InlineKeyboardButton("💵 100.000đ", callback_data='pre_qr_100000'), InlineKeyboardButton("💵 200.000đ", callback_data='pre_qr_200000')],
            [InlineKeyboardButton("✏️ [ NHẬP SỐ TIỀN TÙY Ý ]", callback_data='pre_qr_custom')],
            [InlineKeyboardButton("◀️ [ QUAY LẠI MENU CHÍNH ]", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"💳 **CỔNG NẠP TIỀN TỰ ĐỘNG 24/7 - MIZZE STORE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Chọn nhanh hạn mức hoặc nhập tự do:</i>", kb_dep)
    elif data.startswith('pre_qr_'):
        sub = data.replace('pre_qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, f"💬 **Nhập số tiền bạn muốn nạp vào khung chat:**", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='menu_deposit')]]))
            return
        await show_copy_warning(query, uid, int(sub))
    elif data.startswith('show_qr_'):
        await send_qr(query, context, uid, int(data.replace('show_qr_', '')))
    elif data == 'menu_account':
        await edit_or_send(query, f"👤 **HỒ SƠ TÀI KHOẢN - MIZZE STORE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- ID Telegram: <code>{uid}</code>\n- Số dư ví: <b>{u['balance']:,} VNĐ</b>\n- Tổng nạp tích lũy: <b>{u['total_deposit']:,} VNĐ</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI MENU ]", callback_data='back_menu')]]))
    elif data == 'hist_deposit':
        h = "\n".join(u['deposit_history'][-10:]) if u['deposit_history'] else "Chưa ghi nhận lịch sử nạp."
        await edit_or_send(query, f"🧾 **LỊCH SỬ NẠP TIỀN**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{h}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='back_menu')]]))
    elif data == 'hist_buy':
        b = "\n".join(u['buy_history'][-10:]) if u['buy_history'] else "Chưa ghi nhận lịch sử mua hàng."
        await edit_or_send(query, f"🛍️ **LỊCH SỬ MUA HÀNG**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{b}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='back_menu')]]))
    elif data == 'admin_panel' and is_admin(uid):
        st = "🟢 Hoạt Động" if db["bot_active"] else "🔴 Đang Bảo Trì"
        await edit_or_send(query, f"🛡️ **TRẠM QUẢN TRỊ ADMIN - MIZZE STORE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Trạng thái: <b>{st}</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 Tắt Bot (Bảo Trì)" if db["bot_active"] else "🟢 Bật Lại Bot", callback_data='toggle_bot_status')],
            [InlineKeyboardButton("💰 [ CHỈNH SỬA BẢNG GIÁ KEY ]", callback_data='ad_price_menu')],
            [InlineKeyboardButton("📊 Thống Kê", callback_data='ad_stats'), InlineKeyboardButton("💾 Lấy Backup", callback_data='ad_get_backup')],
            [InlineKeyboardButton("💸 Cộng Tiền", callback_data='ad_bal'), InlineKeyboardButton("📉 Trừ Tiền", callback_data='ad_subbal')],
            [InlineKeyboardButton("👥 Quản Lý Seller & Chỉ Tiêu", callback_data='ad_manageseller'), InlineKeyboardButton("📦 Quản Lý Kho Key", callback_data='ad_checkkey')],
            [InlineKeyboardButton("🏠 [ VỀ MENU CHÍNH ]", callback_data='back_menu')]
        ]))
    elif data == 'toggle_bot_status' and is_admin(uid):
        db["bot_active"] = not db["bot_active"]
        save_data()
        await query.answer("Đã chuyển đổi trạng thái bot!", show_alert=True)
        await button_handler(update, context)
    elif data == 'ad_price_menu' and is_admin(uid):
        await edit_or_send(query, f"💰 **TRUNG TÂM CHỈNH SỬA BẢNG GIÁ KEY**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nChọn bảng giá cấp độ cần thay đổi:", InlineKeyboardMarkup([
            [InlineKeyboardButton("🏷️ Sửa Giá Member (Khách)", callback_data='set_type_mem'), InlineKeyboardButton("👑 Sửa Giá Seller (Sỉ)", callback_data='set_type_sel')],
            [InlineKeyboardButton("◀️ ⟦ QUAY LẠI ADMIN PANEL ⟧", callback_data='admin_panel')]
        ]))
    elif data == 'set_type_mem' and is_admin(uid):
        p_m = db["prices"]
        await edit_or_send(query, f"🏷️ **SỬA GIÁ MEMBER HIỆN TẠI:**\n- 1H: {p_m['1h']}đ | 1D: {p_m['1d']}đ\n- 7D: {p_m['7d']}đ | 30D: {p_m['30d']}đ\n\nChọn gói Member cần chỉnh sửa:", InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Gói 1H", callback_data='pm_1h'), InlineKeyboardButton("💎 Gói 1D", callback_data='pm_1d')],
            [InlineKeyboardButton("👑 Gói 7D", callback_data='pm_7d'), InlineKeyboardButton("🚀 Gói 30D", callback_data='pm_30d')],
            [InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='ad_price_menu')]
        ]))
    elif data == 'set_type_sel' and is_admin(uid):
        p_s = db["seller_prices"]
        await edit_or_send(query, f"👑 **SỬA GIÁ SELLER HIỆN TẠI:**\n- 1H: {p_s['1h']}đ | 1D: {p_s['1d']}đ\n- 7D: {p_s['7d']}đ | 30D: {p_s['30d']}đ\n\nChọn gói Seller cần chỉnh sửa:", InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Gói 1H", callback_data='ps_1h'), InlineKeyboardButton("💎 Gói 1D", callback_data='ps_1d')],
            [InlineKeyboardButton("👑 Gói 7D", callback_data='ps_7d'), InlineKeyboardButton("🚀 Gói 30D", callback_data='ps_30d')],
            [InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='ad_price_menu')]
        ]))
    elif data.startswith('pm_') and is_admin(uid):
        pk = data.replace('pm_', '')
        admin_state[uid] = f"setprice_mem_{pk}"
        await edit_or_send(query, f"💬 **Nhập giá MEMBER mới cho gói {pk.upper()}** (Ví dụ: <code>8000</code>):{SIGNATURE}")
    elif data.startswith('ps_') and is_admin(uid):
        pk = data.replace('ps_', '')
        admin_state[uid] = f"setprice_sel_{pk}"
        await edit_or_send(query, f"💬 **Nhập giá SELLER mới cho gói {pk.upper()}** (Ví dụ: <code>5000</code>):{SIGNATURE}")
    elif data == 'ad_stats' and is_admin(uid):
        tot_k = len(db['s_1h']) + len(db['s_1d']) + len(db['s_7d']) + len(db['s_30d'])
        await edit_or_send(query, f"📊 **THỐNG KÊ HỆ THỐNG - MIZZE STORE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Tổng User: {len(db['users'])}\n- Tổng Seller: {len(db['sellers'])}\n- Doanh thu: {db['total_rev']:,} VNĐ\n- Key tồn kho: {tot_k}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='admin_panel')]]))
    elif data == 'ad_get_backup' and is_admin(uid):
        await auto_backup_to_admin(context)
        await query.answer("Đã gửi file backup về tin nhắn riêng!", show_alert=True)
    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, f"💬 Nhập theo cú pháp: `[ID] [Số_tiền]`")
    elif data == 'ad_subbal' and is_admin(uid):
        admin_state[uid] = 'sub_bal'
        await edit_or_send(query, f"💬 Nhập theo cú pháp: `[ID] [Số_tiền]`")
    elif data == 'ad_manageseller' and is_admin(uid):
        await edit_or_send(query, f"👥 **QUẢN LÝ SELLER & CHỈ TIÊU**", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Thêm / Sửa Chỉ Tiêu Seller", callback_data='add_seller_prompt')],
            [InlineKeyboardButton("🗑️ Xóa Quyền Seller", callback_data='del_seller_prompt')],
            [InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='admin_panel')]
        ]))
    elif data == 'add_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'add_seller_id'
        await edit_or_send(query, f"💬 Nhập theo cú pháp:\n`[ID] [Mục_tiêu_doanh_thu_ngày]`\n(Ví dụ: `7976468365 500000`)")
    elif data == 'del_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'del_seller_id'
        await edit_or_send(query, f"💬 Nhập ID Telegram của Seller cần xóa quyền:")
    elif data == 'ad_checkkey' and is_admin(uid):
        await edit_or_send(query, f"📦 **QUẢN LÝ KHO KEY**\nChọn kho cần thêm key mới:", InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Kho 1H", callback_data='k_s1h'), InlineKeyboardButton("💎 Kho 1D", callback_data='k_s1d')],
            [InlineKeyboardButton("👑 Kho 7D", callback_data='k_s7d'), InlineKeyboardButton("🚀 Kho 30D", callback_data='k_s30d')],
            [InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='admin_panel')]
        ]))
    elif data.startswith('k_') and is_admin(uid):
        k_type = data.replace('k_', '')
        admin_state[uid] = f"addk_{k_type}"
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        cur_len = len(m_map.get(k_type, []))
        await edit_or_send(query, f"📦 **THÊM KEY VÀO KHO {k_type.upper()}**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Tồn kho hiện tại: <b>{cur_len} key</b>\n\n📝 <i>Dán danh sách key vào khung chat (Mỗi key nằm trên một dòng riêng biệt). Hệ thống sẽ tự động nhận diện từng key một!</i>", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ⟦ QUAY LẠI ⟧", callback_data='ad_checkkey')]]))

async def show_copy_warning(query, uid, amount):
    memo = f"NAP {uid}"
    text = (
        f"🚨 🛑 **CẢNH BÁO CHUYỂN KHOẢN - MIZZE STORE** 🛑 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❗ **BẠN BẮT BUỘC PHẢI COPY NỘI DUNG SAU:**\n\n"
        f"<code>{memo}</code>\n\n"
        f"❌ <i>Tuyệt đối không sửa đổi hoặc xóa nội dung này!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 [ COPY NỘI DUNG CK ]", callback_data=f"copy_memo_{memo}")],
        [InlineKeyboardButton("✅ [ TÔI ĐÃ COPY - XEM MÃ QR ]", callback_data=f"show_qr_{amount}")],
        [InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='menu_deposit')]
    ])
    await edit_or_send(query, text, kb)

async def send_qr(query, context, uid, amount):
    memo = f"NAP {uid}"
    url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amount}&memo={quote(memo)}"
    text = (
        f"💳 **MÃ QR NẠP TIỀN {amount:,}Đ - MIZZE STORE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Nội dung CK: <code>{memo}</code>\n"
        f"👉 <i>Quét mã qua app ngân hàng để cộng ví tự động!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 [ COPY NỘI DUNG CK ]", callback_data=f"copy_memo_{memo}")],
        [InlineKeyboardButton("🔄 [ KIỂM TRA SỐ DƯ ]", callback_data='menu_account')],
        [InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='menu_deposit')]
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
    price, kho = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}[kt]
    total = price * qty

    if len(kho) < qty:
        await query.answer(f"❌ Kho không đủ số lượng! Hiện chỉ còn {len(kho)} key.", show_alert=True)
        return
    if u['balance'] < total:
        await query.answer("❌ Số dư ví không đủ để thanh toán!", show_alert=True)
        return

    u['balance'] -= total
    db["total_rev"] += total
    if is_s and not is_admin(uid):
        db["sellers"][str(uid)]["daily_rev"] = db["sellers"][str(uid)].get("daily_rev", 0) + total

    keys_bought = [kho.pop(0) for _ in range(qty)]
    for k in keys_bought: u['my_keys'].append(f"[{kt.upper()}] {k}")
    save_data()
    await auto_backup_to_admin(context)

    keys_str = "\n".join([f"<code>{k}</code>" for k in keys_bought])
    time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    try:
        log_msg = (
            f"🛍️ **GIAO DỊCH MUA KEY MỚI - MIZZE STORE**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Khách ID: <code>{uid}</code>\n"
            f"📦 Gói: <b>{qty}x {kt.upper()}</b>\n"
            f"💵 Tổng tiền: <b>{total:,} VNĐ</b>\n"
            f"⏱️ Thời gian: {time_str}"
            f"{SIGNATURE}"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_msg, parse_mode="HTML")
    except: pass

    first_key = keys_bought[0] if keys_bought else "Mizzebin"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 [ COPY KEY ]", callback_data=f"copy_val_{first_key}")],
        [InlineKeyboardButton("📂 [ NHÓM NHẬN FILE ]", url=CLIENT_GROUP_LINK)],
        [InlineKeyboardButton("🔑 [ KHO KEY CỦA TÔI ]", callback_data='my_keys'), InlineKeyboardButton("🏠 [ MENU CHÍNH ]", callback_data='back_menu')]
    ])
    await edit_or_send(query, f"✅ **MUA THÀNH CÔNG {qty} GÓI {kt.upper()}!**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n👇 **Danh sách Key của bạn:**\n{keys_str}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Số dư ví còn lại: <b>{u['balance']:,} VNĐ</b>{SIGNATURE}", kb)

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
            class DummyQuery:
                def __init__(self, msg, user): self.message, self.from_user = msg, user
                async def answer(self, *a, **kw): pass
            await process_purchase(DummyQuery(update.message, update.message.from_user), context, uid, kt, qty)
        except: await update.message.reply_text("❌ Số lượng nhập không hợp lệ!")
        return

    if state == 'waiting_deposit':
        del admin_state[uid]
        try:
            amt = int(text.replace(".", "").strip())
            memo = f"NAP {uid}"
            url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amt}&memo={quote(memo)}"
            await update.message.reply_photo(photo=url, caption=f"💳 **QR NẠP {amt:,}Đ**\n- Nội dung: <code>{memo}</code>")
        except: await update.message.reply_text("❌ Số tiền không hợp lệ!")
        return

    # Sửa giá Member
    if state.startswith('setprice_mem_'):
        pk = state.replace('setprice_mem_', '')
        del admin_state[uid]
        try:
            new_p = int(text.replace(".", "").strip())
            db["prices"][pk] = new_p
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá MEMBER cho gói <b>{pk.upper()}</b> thành <b>{new_p:,} VNĐ</b>!", parse_mode="HTML")
        except: await update.message.reply_text("❌ Giá tiền không hợp lệ!")
        return

    # Sửa giá Seller
    if state.startswith('setprice_sel_'):
        pk = state.replace('setprice_sel_', '')
        del admin_state[uid]
        try:
            new_p = int(text.replace(".", "").strip())
            db["seller_prices"][pk] = new_p
            save_data()
            await update.message.reply_text(f"✅ Đã cập nhật giá SELLER cho gói <b>{pk.upper()}</b> thành <b>{new_p:,} VNĐ</b>!", parse_mode="HTML")
        except: await update.message.reply_text("❌ Giá tiền không hợp lệ!")
        return

    if state.startswith('addk_'):
        k_type = state.replace('addk_', '')
        del admin_state[uid]
        m_map = {'s1h': db['s_1h'], 's1d': db['s_1d'], 's7d': db['s_7d'], 's30d': db['s_30d']}
        target = m_map.get(k_type)
        if target is not None:
            added = 0
            lines = text.split('\n')
            for line in lines:
                clean_key = line.strip()
                if clean_key:
                    target.append(html.escape(clean_key))
                    added += 1
            save_data()
            await update.message.reply_text(f"✅ Đã thêm thành công <code>{added}</code> key mới vào kho <b>{k_type.upper()}</b>!\n📦 Tổng tồn kho hiện tại: <b>{len(target)} key</b>")
        return

    if not is_admin(uid): return
    if state == 'add_bal' or state == 'sub_bal':
        try:
            tid, amt = text.split()
            tid, amt = int(tid), int(amt)
            u = get_u(tid)
            if state == 'add_bal': u['balance'] += amt; u['total_deposit'] += amt
            else: u['balance'] = max(0, u['balance'] - amt)
            save_data()
            await update.message.reply_text(f"✅ Thao tác thành công cho ID {tid}!")
        except: await update.message.reply_text("❌ Sai cú pháp!")
        del admin_state[uid]
    elif state == 'add_seller_id':
        try:
            parts = text.split()
            sid = str(parts[0])
            target = int(parts[1]) if len(parts) > 1 else 500000
            db["sellers"][sid] = {"daily_rev": 0, "target": target}
            save_data()
            await update.message.reply_text(f"✅ Thêm/Cập nhật Seller ID `{sid}` với chỉ tiêu ngày `{target:,} VNĐ` thành công!")
        except: await update.message.reply_text("❌ Sai cú pháp! Nhập: `[ID] [Mục_tiêu]`")
        del admin_state[uid]
    elif state == 'del_seller_id':
        sid = text.strip()
        if sid in db["sellers"]: del db["sellers"][sid]; save_data(); await update.message.reply_text("✅ Xóa quyền Seller thành công!")
        else: await update.message.reply_text("❌ Không tìm thấy ID Seller này!")
        del admin_state[uid]

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
                u = get_u(tid)
                u['balance'] += amt
                u['total_deposit'] += amt
                db["total_rev"] += amt
                if str(tid) in db["sellers"]: 
                    db["sellers"][str(tid)]["daily_rev"] = db["sellers"][str(tid)].get("daily_rev", 0) + amt
                save_data()
                time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                try:
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": tid, "text": f"🎉 **NẠP TIỀN THÀNH CÔNG +{amt:,} VNĐ!**\n- Số dư ví mới: <b>{u['balance']:,} VNĐ</b>{SIGNATURE}", "parse_mode": "HTML"})
                    admin_notify = f"💳 **NẠP TIỀN THÀNH CÔNG - MIZZE STORE:**\n- Khách ID: <code>{tid}</code>\n- Số tiền: <b>+{amt:,} VNĐ</b>\n- Thời gian: {time_str}{SIGNATURE}"
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": LOG_GROUP_ID, "text": admin_notify, "parse_mode": "HTML"})
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