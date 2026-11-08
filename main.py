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
SIGNATURE = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚡ 🔮 **MIZZE CYBERPUNK STORE** 🔮 ⚡"
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
            for s_info in db["sellers"].values(): s_info["daily_rev"] = 0
            db["last_reset_date"] = today_str
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
    except: pass

async def auto_backup_to_admin(context):
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                for adm in admin_list:
                    await context.bot.send_document(chat_id=adm, document=f, filename="database_backup.json", caption="🛡️ **[AUTO BACKUP SYSTEM]**\nFile dữ liệu database mới nhất đã được sao lưu tự động an toàn tuyệt đối!")
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

async def show_main_menu(update, context):
    uid = update.effective_user.id
    save_data()
    if not db["bot_active"] and not is_admin(uid):
        maint_text = f"🚧 **HỆ THỐNG ĐANG BẢO TRÌ NÂNG CẤP** 🚧\n\n<i>Bot đang tạm dừng để bảo trì hệ thống. Vui lòng quay lại sau ít phút nhé!</i>{SIGNATURE}"
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
    
    # Giao diện Button mới hoàn toàn: Sang trọng, màu sắc hiện đại, bố cục cân đối
    kb_buttons = [
        [InlineKeyboardButton("💎 [ CỬA HÀNG MUA KEY ]", callback_data='menu_shop'), InlineKeyboardButton("💳 [ NẠP TIỀN VÍ ]", callback_data='menu_deposit')],
        [InlineKeyboardButton("🔑 [ KHO KEY CỦA TÔI ]", callback_data='my_keys'), InlineKeyboardButton("👤 [ TÀI KHOẢN ]", callback_data='menu_account')],
        [InlineKeyboardButton("🧾 [ LỊCH SỬ NẠP ]", callback_data='hist_deposit'), InlineKeyboardButton("🛍️ [ LỊCH SỬ MUA ]", callback_data='hist_buy')],
    ]
    if is_seller(uid) and not is_admin(uid): kb_buttons.append([InlineKeyboardButton("📊 [ THỐNG KÊ DOANH THU SELLER ]", callback_data='seller_stats')])
    if is_admin(uid): kb_buttons.append([InlineKeyboardButton("⚙️ [ BẢNG QUẢN TRỊ ADMIN ]", callback_data='admin_panel')])
    else: kb_buttons.append([InlineKeyboardButton("💬 [ HỖ TRỢ ]", url=SUPPORT_CONTACT), InlineKeyboardButton("🚀 [ ĐĂNG KÝ SELLER ]", callback_data='register_seller')])

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
        await query.answer("⚠️ Thao tác quá nhanh, hãy từ từ thôi nhé!", show_alert=True)
        return
    await query.answer()
    u = get_u(uid)
    data = query.data
    is_s = is_seller(uid)
    p = db["seller_prices"] if is_s else db["prices"]

    if data == 'back_menu': await show_main_menu(update, context)
    elif data.startswith('copy_memo_'):
        memo_text = data.replace('copy_memo_', '')
        await query.answer(f"📋 Đã sao chép nội dung: [{memo_text}]", show_alert=True)
    elif data.startswith('copy_val_'):
        val_text = data.replace('copy_val_', '')
        await query.answer(f"📋 Đã sao chép thành công!", show_alert=True)
    elif data == 'register_seller':
        await edit_or_send(query, f"🚀 **ĐĂNG KÝ SELLER PARTNER**\nLiên hệ ngay Admin để được nhận ưu đãi: <a href='{ADMIN_CONTACT}'>Bấm vào đây</a>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='back_menu')]]))
    elif data == 'my_keys':
        keys_list = "\n".join([f"• <code>{k}</code>" for k in u['my_keys']]) if u['my_keys'] else "<i>Bạn chưa sở hữu key nào. Hãy mua ngay tại cửa hàng!</i>"
        await edit_or_send(query, f"🔑 **KHO KEY CỦA TÔI**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{keys_list}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 <i>Key của bạn được lưu vĩnh viễn tại đây!</i>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("🛒 [ MUA THÊM KEY ]", callback_data='menu_shop')], [InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='back_menu')]]))
    elif data == 'seller_stats':
        s_info = db["sellers"].get(str(uid), {"daily_rev": 0, "target": 500000})
        rev, target = s_info["daily_rev"], s_info.get("target", 500000)
        status = "✅ ĐÃ ĐẠT CHỈ TIÊU" if rev >= target else "⚠️ CHƯA ĐẠT CHỈ TIÊU"
        await edit_or_send(query, f"📊 **THỐNG KÊ DOANH THU SELLER**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- Hôm nay: <code>{rev:,}đ</code>\n- Mục tiêu: <code>{target:,}đ</code>\n- Trạng thái: <b>{status}</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='back_menu')]]))
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ 1H ({p['1h']:,}đ) [{len(db['s_1h'])}]", callback_data='shop_1h'), InlineKeyboardButton(f"💎 1D ({p['1d']:,}đ) [{len(db['s_1d'])}]", callback_data='shop_1d')],
            [InlineKeyboardButton(f"👑 7D ({p['7d']:,}đ) [{len(db['s_7d'])}]", callback_data='shop_7d'), InlineKeyboardButton(f"🚀 30D ({p['30d']:,}đ) [{len(db['s_30d'])}]", callback_data='shop_30d')],
            [InlineKeyboardButton("💳 [ NẠP THÊM TIỀN ]", callback_data='menu_deposit')],
            [InlineKeyboardButton("◀️ [ QUAY LẠI MENU ]", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛒 **CỬA HÀNG MUA KEY TỰ ĐỘNG**\n- Số dư: <b>{u['balance']:,}đ</b>\n- Cấp bậc: {'SELLER VIP' if is_s else 'MEMBER'}{SIGNATURE}", kb)
    elif data.startswith('shop_'):
        kt = data.split('_')[1]
        price, kho = {'1h': (p['1h'], db['s_1h']), '1d': (p['1d'], db['s_1d']), '7d': (p['7d'], db['s_7d']), '30d': (p['30d'], db['s_30d'])}[kt]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ Mua 1 Key", callback_data=f"buyq_{kt}_1"), InlineKeyboardButton("2️⃣ Mua 2 Key", callback_data=f"buyq_{kt}_2")],
            [InlineKeyboardButton("5️⃣ Mua 5 Key", callback_data=f"buyq_{kt}_5"), InlineKeyboardButton("🔟 Mua 10 Key", callback_data=f"buyq_{kt}_10")],
            [InlineKeyboardButton("✏️ [ NHẬP SỐ LƯỢNG TÙY Ý ]", callback_data=f"buyq_custom_{kt}")],
            [InlineKeyboardButton("◀️ [ QUAY LẠI CỬA HÀNG ]", callback_data='menu_shop')]
        ])
        await edit_or_send(query, f"📦 **GÓI DỊCH VỤ: {kt.upper()}**\n- Giá niêm yết: <b>{price:,}đ / key</b>\n- Tồn kho sẵn sàng: <b>{len(kho)} key</b>", kb)
    elif data.startswith('buyq_custom_'):
        kt = data.split('_')[2]
        admin_state[uid] = f"buy_custom_{kt}"
        await edit_or_send(query, f"💬 **Vui lòng nhập số lượng cần mua vào khung chat:**", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data=f"shop_{kt}")]]))
    elif data.startswith('buyq_'):
        _, kt, qty = data.split('_')
        await process_purchase(query, context, uid, kt, int(qty))
    elif data == 'menu_deposit':
        kb_dep = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 10.000đ", callback_data='pre_qr_10000'), InlineKeyboardButton("💵 50.000đ", callback_data='pre_qr_50000')],
            [InlineKeyboardButton("💵 100.000đ", callback_data='pre_qr_100000'), InlineKeyboardButton("💵 200.000đ", callback_data='pre_qr_200000')],
            [InlineKeyboardButton("✏️ [ NHẬP SỐ TIỀN TÙY CHỈNH ]", callback_data='pre_qr_custom')],
            [InlineKeyboardButton("◀️ [ QUAY LẠI MENU ]", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"💳 **HỆ THỐNG NẠP TIỀN TỰ ĐỘNG 24/7**\nChọn nhanh hạn mức nạp bên dưới:", kb_dep)
    elif data.startswith('pre_qr_'):
        sub = data.replace('pre_qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, f"💬 **Vui lòng nhập số tiền cần nạp vào khung chat:**", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='menu_deposit')]]))
            return
        await show_copy_warning(query, uid, int(sub))
    elif data.startswith('show_qr_'):
        await send_qr(query, context, uid, int(data.replace('show_qr_', '')))
    elif data == 'menu_account':
        await edit_or_send(query, f"👤 **THÔNG TIN TÀI KHOẢN**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n- ID: <code>{uid}</code>\n- Số dư: <b>{u['balance']:,}đ</b>\n- Tổng nạp: <b>{u['total_deposit']:,}đ</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI MENU ]", callback_data='back_menu')]]))
    elif data == 'hist_deposit':
        h = "\n".join(u['deposit_history'][-10:]) if u['deposit_history'] else "Chưa có lịch sử nạp."
        await edit_or_send(query, f"🧾 **LỊCH SỬ NẠP TIỀN**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{h}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='back_menu')]]))
    elif data == 'hist_buy':
        b = "\n".join(u['buy_history'][-10:]) if u['buy_history'] else "Chưa có lịch sử mua."
        await edit_or_send(query, f"🛍️ **LỊCH SỬ MUA HÀNG**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{b}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='back_menu')]]))
    elif data == 'admin_panel' and is_admin(uid):
        st = "🟢 Hoạt Động" if db["bot_active"] else "🔴 Đang Bảo Trì"
        await edit_or_send(query, f"🛡️ **BẢNG QUẢN TRỊ ADMIN**\nTrạng thái bot: <b>{st}</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 Tắt Bot (Bảo Trì)" if db["bot_active"] else "🟢 Bật Lại Bot", callback_data='toggle_bot_status')],
            [InlineKeyboardButton("📊 Thống Kê", callback_data='ad_stats'), InlineKeyboardButton("💾 Lấy Backup", callback_data='ad_get_backup')],
            [InlineKeyboardButton("💸 Cộng Tiền", callback_data='ad_bal'), InlineKeyboardButton("📉 Trừ Tiền", callback_data='ad_subbal')],
            [InlineKeyboardButton("👥 Quản Lý Seller", callback_data='ad_manageseller'), InlineKeyboardButton("📦 Kho Key", callback_data='ad_checkkey')],
            [InlineKeyboardButton("🏠 [ VỀ MENU CHÍNH ]", callback_data='back_menu')]
        ]))
    elif data == 'toggle_bot_status' and is_admin(uid):
        db["bot_active"] = not db["bot_active"]
        save_data()
        await query.answer("Đã đổi trạng thái bot thành công!", show_alert=True)
        await button_handler(update, context)
    elif data == 'ad_stats' and is_admin(uid):
        tot_k = len(db['s_1h']) + len(db['s_1d']) + len(db['s_7d']) + len(db['s_30d'])
        await edit_or_send(query, f"📊 **THỐNG KÊ HỆ THỐNG**\n- Tổng User: {len(db['users'])}\n- Doanh thu: {db['total_rev']:,}đ\n- Tồn kho: {tot_k} key", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='admin_panel')]]))
    elif data == 'ad_get_backup' and is_admin(uid):
        await auto_backup_to_admin(context)
        await query.answer("Đã gửi file backup về chat riêng!", show_alert=True)
    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, f"💬 Nhập theo định dạng: `[ID] [Số_tiền]`")
    elif data == 'ad_subbal' and is_admin(uid):
        admin_state[uid] = 'sub_bal'
        await edit_or_send(query, f"💬 Nhập theo định dạng: `[ID] [Số_tiền]`")
    elif data == 'ad_manageseller' and is_admin(uid):
        await edit_or_send(query, f"👥 **QUẢN LÝ SELLER**", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Thêm Seller", callback_data='add_seller_prompt'), InlineKeyboardButton("🗑️ Xóa Seller", callback_data='del_seller_prompt')],
            [InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='admin_panel')]
        ]))
    elif data == 'add_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'add_seller_id'
        await edit_or_send(query, f"💬 Nhập: `[ID] [Mục_tiêu_ngày]`")
    elif data == 'del_seller_prompt' and is_admin(uid):
        admin_state[uid] = 'del_seller_id'
        await edit_or_send(query, f"💬 Nhập ID Seller cần xóa:")
    elif data == 'ad_checkkey' and is_admin(uid):
        await edit_or_send(query, f"📦 **TỒN KHO HIỆN TẠI:**\n- 1H: {len(db['s_1h'])}\n- 1D: {len(db['s_1d'])}\n- 7D: {len(db['s_7d'])}\n- 30D: {len(db['s_30d'])}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='admin_panel')]]))

async def show_copy_warning(query, uid, amount):
    memo = f"NAP {uid}"
    text = (
        f"🚨 🛑 **CẢNH BÁO CHUYỂN KHOẢN** 🛑 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❗ **BẠN BẮT BUỘC PHẢI COPY NỘI DUNG SAU:**\n\n"
        f"<code>{memo}</code>\n\n"
        f"❌ <i>Tuyệt đối không sửa đổi hoặc xóa nội dung này!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 [ COPY NỘI DUNG CK ]", callback_data=f"copy_memo_{memo}")],
        [InlineKeyboardButton("✅ [ TÔI ĐÃ COPY - XEM QR ]", callback_data=f"show_qr_{amount}")],
        [InlineKeyboardButton("◀️ [ QUAY LẠI ]", callback_data='menu_deposit')]
    ])
    await edit_or_send(query, text, kb)

async def send_qr(query, context, uid, amount):
    memo = f"NAP {uid}"
    url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amount}&memo={quote(memo)}"
    text = (
        f"💳 **MÃ QR NẠP TIỀN {amount:,}Đ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Nội dung CK: <code>{memo}</code>\n"
        f"👉 <i>Quét mã bằng app ngân hàng để cộng tiền tự động!</i>"
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
        await query.answer(f"❌ Kho không đủ số lượng! Chỉ còn {len(kho)} key.", show_alert=True)
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

    # Chỉ thông báo các phần quan trọng cho Admin / Nhóm log: Mua gói nào, mấy giờ, ID nào
    try:
        log_msg = (
            f"🛍️ **CÓ GIAO DỊCH MUA KEY MỚI!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Khách ID: <code>{uid}</code>\n"
            f"📦 Gói: <b>{qty}x {kt.upper()}</b>\n"
            f"💵 Tổng tiền: <b>{total:,}đ</b>\n"
            f"⏱️ Thời gian: {time_str}"
            f"{SIGNATURE}"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_msg, parse_mode="HTML")
    except: pass

    first_key = keys_bought[0] if keys_bought else "Mizzebin"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 [ COPY KEY ]", callback_data=f"copy_val_{first_key}"), InlineKeyboardButton("📋 [ COPY MẬT KHẨU ]", callback_data=f"copy_val_{first_key}")],
        [InlineKeyboardButton("📂 [ NHÓM NHẬN FILE ]", url=CLIENT_GROUP_LINK)],
        [InlineKeyboardButton("🔑 [ KHO KEY CỦA TÔI ]", callback_data='my_keys'), InlineKeyboardButton("🏠 [ MENU CHÍNH ]", callback_data='back_menu')]
    ])
    await edit_or_send(query, f"✅ **MUA THÀNH CÔNG {qty} GÓI {kt.upper()}!**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n👇 **Key của bạn:**\n{keys_str}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n💎 Số dư ví còn lại: <b>{u['balance']:,}đ</b>{SIGNATURE}", kb)

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
            db["sellers"][str(parts[0])] = {"daily_rev": 0, "target": int(parts[1]) if len(parts) > 1 else 500000}
            save_data()
            await update.message.reply_text("✅ Thêm Seller thành công!")
        except: await update.message.reply_text("❌ Sai cú pháp!")
        del admin_state[uid]
    elif state == 'del_seller_id':
        sid = text.strip()
        if sid in db["sellers"]: del db["sellers"][sid]; save_data(); await update.message.reply_text("✅ Xóa Seller thành công!")
        else: await update.message.reply_text("❌ Không tìm thấy ID Seller!")
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
                if str(tid) in db["sellers"]: db["sellers"][str(tid)]["daily_rev"] = db["sellers"][str(tid)].get("daily_rev", 0) + amt
                save_data()
                time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                try:
                    # Gửi tin nhắn cộng tiền cho khách
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": tid, "text": f"🎉 **NẠP TIỀN THÀNH CÔNG +{amt:,}đ!**\n- Số dư ví mới: <b>{u['balance']:,}đ</b>{SIGNATURE}", "parse_mode": "HTML"})
                    
                    # Thông báo quan trọng cho Admin: Nạp tiền thành công, mấy giờ, ID nào
                    admin_notify = (
                        f"💳 **CÓ GIAO DỊCH NẠP TIỀN THÀNH CÔNG!**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 Khách ID: <code>{tid}</code>\n"
                        f"💵 Số tiền: <b>+{amt:,}đ</b>\n"
                        f"⏱️ Thời gian: {time_str}"
                        f"{SIGNATURE}"
                    )
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