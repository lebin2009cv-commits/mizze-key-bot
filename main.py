import os, logging, threading, httpx, re, secrets, time, html, datetime
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
BOT_USERNAME = "GetkeyMizzebot"

ADMIN_ID = 7976468365
admin_list = {ADMIN_ID}

SIGNATURE = "\n\n━━━━━━━━━━━━━━━━━━━\n💎 <b>MIZZE STORE - PREMIUM SHOP</b>"
BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/lebindz"
SUPPORT_CONTACT = "https://t.me/NTH_VIP"

BANK_ID = "VPBank"
ACCOUNT_NO = "AGBSP4LRK4B099"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_KEY = os.environ.get("SEPAY_API_KEY", "botgetkey_sepay")

# Bảng giá gói mua key VIP
P_1H, P_6H, P_1D, P_7D, P_30D = 7000, 15000, 20000, 75000, 150000

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

s_1h, s_6h, s_1d, s_7d, s_30d = [], [], [], [], []
admin_state = {}
users, user_data = set(), {}
cooldown_cache = {}  # Chống spam click liên tục
bot_active = True    # Trạng thái bật/tắt bảo trì bot
total_rev = 0

def get_u(uid):
    if uid not in user_data: 
        user_data[uid] = {'balance': 0, 'total_deposit': 0, 'history': []}
    return user_data[uid]

def is_admin(uid):
    return uid in admin_list

def check_spam(uid):
    now = time.time()
    if uid in cooldown_cache and now - cooldown_cache[uid] < 3:
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
    for u in list(users):
        try: await context.bot.send_message(u, msg, parse_mode="HTML")
        except: pass

async def show_main_menu(update, context):
    uid = update.effective_user.id
    
    if not bot_active and not is_admin(uid):
        text = (
            f"🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ NÂNG CẤP</b> 🚧\n\n"
            f"<i>Bot hiện đang tạm dừng hoạt động để bảo trì hệ thống. Vui lòng quay lại sau ít phút nhé!</i>"
            f"{SIGNATURE}"
        )
        if update.message: await update.message.reply_text(text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML")
        return

    u = get_u(uid)
    text = (
        f"🌌 <b>✨ MIZZE STORE - CỬA HÀNG KEY VIP ✨</b> 🌌\n\n"
        f"📢 <b>Kênh Thông Báo:</b> <a href='{CHANNEL_URL}'>Bấm Vào Đây</a>\n"
        f"👑 <b>Admin Hỗ Trợ:</b> <a href='{ADMIN_CONTACT}'>Liên Hệ Ngay</a>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>Tổng Nạp:</b> <code>{u['total_deposit']:,}đ</code> | 💎 <b>Số Dư Ví:</b> <b>{u['balance']:,}đ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>📊 KHO HÀNG VIP REAL-TIME:</b>\n"
        f"  • ⚡ <b>1H:</b> <code>[{len(s_1h)}]</code> | 🔥 <b>6H:</b> <code>[{len(s_6h)}]</code> | 💎 <b>1D:</b> <code>[{len(s_1d)}]</code>\n"
        f"  • 👑 <b>7D:</b> <code>[{len(s_7d)}]</code> | 🚀 <b>30D:</b> <code>[{len(s_30d)}]</code>"
        f"{SIGNATURE}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Cửa Hàng Mua Key VIP", callback_data='menu_shop')],
        [InlineKeyboardButton("💳 Nạp Tiền Tự Động 24/7", callback_data='menu_deposit')],
        [InlineKeyboardButton("👤 Tài Khoản", callback_data='menu_account'), InlineKeyboardButton("🧾 Lịch Sử", callback_data='menu_history')],
        [InlineKeyboardButton("💬 Hỗ Trợ", url=SUPPORT_CONTACT), InlineKeyboardButton("⚙️ Quản Trị Viên", callback_data='admin_panel')]
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
    users.add(uid)
    get_u(uid)
    await show_main_menu(update, context)

async def button_handler(update, context):
    global total_rev, bot_active
    query = update.callback_query
    uid = query.from_user.id

    if check_spam(uid):
        await query.answer("⚠️ Bạn đang thao tác quá nhanh! Vui lòng từ từ.", show_alert=True)
        return

    await query.answer()
    u = get_u(uid)
    data = query.data

    if data == 'back_menu': await show_main_menu(update, context)
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ 1H ({P_1H:,}đ) [{len(s_1h)}]", callback_data='buy_1h'), InlineKeyboardButton(f"🔥 6H ({P_6H:,}đ) [{len(s_6h)}]", callback_data='buy_6h')],
            [InlineKeyboardButton(f"💎 1D ({P_1D:,}đ) [{len(s_1d)}]", callback_data='buy_1d'), InlineKeyboardButton(f"👑 7D ({P_7D:,}đ) [{len(s_7d)}]", callback_data='buy_7d')],
            [InlineKeyboardButton(f"🚀 30D ({P_30D:,}đ) [{len(s_30d)}]", callback_data='buy_30d')],
            [InlineKeyboardButton("💳 Nạp Tiền", callback_data='menu_deposit'), InlineKeyboardButton("◀️ Menu Chính", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛒 <b>CỬA HÀNG MUA KEY VIP TỰ ĐỘNG</b>\n💎 Số dư ví của bạn: <b>{u['balance']:,}đ</b>\n━━━━━━━━━━━━━━━━━━━\n<i>Chọn gói dịch vụ phù hợp bên dưới:</i>", kb)
    elif data.startswith('buy_'):
        kt = data.split('_')[1]
        p_map = {'1h': (P_1H, s_1h), '6h': (P_6H, s_6h), '1d': (P_1D, s_1d), '7d': (P_7D, s_7d), '30d': (P_30D, s_30d)}
        price, kho = p_map[kt]
        
        if not kho:
            await query.answer(f"❌ Kho Key {kt.upper()} hiện đã hết hàng!", show_alert=True)
            return
        if u['balance'] < price:
            await edit_or_send(query, f"❌ <b>Số dư ví không đủ!</b>\nBạn cần <code>{price:,}đ</code> nhưng ví chỉ có <code>{u['balance']:,}đ</code>.\nVui lòng nạp thêm tiền để tiếp tục mua hàng nhé!", InlineKeyboardMarkup([[InlineKeyboardButton("💳 Nạp Tiền Ngay", callback_data='menu_deposit'), InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_shop')]]))
            return

        u['balance'] -= price; total_rev += price
        k_nhan = kho.pop(0)
        u['history'].append(f"Mua {kt.upper()} (-{price:,}đ)")
        if len(u['history']) > 20: u['history'].pop(0)
        
        await notify_all_admins(context, f"User <code>{uid}</code> vừa mua thành công gói <b>{kt.upper()}</b> với giá <b>{price:,}đ</b>. Kho còn lại: <code>{len(kho)}</code>")
        
        key_display = f"<code>{k_nhan}</code>" if "KEY" in k_nhan.upper() else f"<pre>{k_nhan}</pre>"
        await edit_or_send(query, f"✅ <b>GIAO DỊCH THÀNH CÔNG!</b>\n━━━━━━━━━━━━━━━━━━━\n📦 Gói: <b>{kt.upper()}</b> | Trừ ví: <code>-{price:,}đ</code>\n\n👇 <b>Sao chép mã Key bên dưới:</b>\n{key_display}\n━━━━━━━━━━━━━━━━━━━\n💎 Số dư ví còn lại: <b>{u['balance']:,}đ</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Mua Thêm Gói Khác", callback_data='menu_shop'), InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]]))
    elif data == 'menu_deposit':
        await edit_or_send(query, f"💳 <b>HỆ THỐNG NẠP TIỀN TỰ ĐỘNG 24/7</b>\n━━━━━━━━━━━━━━━━━━━\nChọn nhanh hạn mức nạp hoặc nhập số tiền tùy ý (Tối thiểu <b>10.000đ</b>):", InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 10.000đ", callback_data='qr_10000'), InlineKeyboardButton("💵 50.000đ", callback_data='qr_50000')],
            [InlineKeyboardButton("💵 100.000đ", callback_data='qr_100000'), InlineKeyboardButton("💵 200.000đ", callback_data='qr_200000')],
            [InlineKeyboardButton("✏️ Nhập Số Tiền Tùy Chỉnh", callback_data='qr_custom')],
            [InlineKeyboardButton("◀️ Menu Chính", callback_data='back_menu')]
        ]))
    elif data.startswith('qr_'):
        sub = data.replace('qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, f"💬 <b>Vui lòng nhập số tiền bạn muốn nạp vào khung chat</b> (Ví dụ: <code>50000</code>):{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại", callback_data='menu_deposit')]]))
            return
        await send_qr(query, context, uid, int(sub))

    elif data == 'menu_account':
        await edit_or_send(query, f"👤 <b>THÔNG TIN TÀI KHOẢN CÁ NHÂN</b>\n━━━━━━━━━━━━━━━━━━━\n🆔 Telegram ID: <code>{uid}</code>\n💎 Số Dư Ví: <b>{u['balance']:,}đ</b>\n💳 Tổng Nạp: <b>{u['total_deposit']:,}đ</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu Chính", callback_data='back_menu')]]))
    elif data == 'menu_history':
        hist = "\n".join(u['history'][-10:]) if u['history'] else "Chưa có lịch sử giao dịch nào."
        await edit_or_send(query, f"🧾 <b>LỊCH SỬ GIAO DỊCH GẦN NHẤT:</b>\n━━━━━━━━━━━━━━━━━━━\n{hist}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Menu Chính", callback_data='back_menu')]]))
    elif data == 'admin_panel' and is_admin(uid):
        status_text = "🟢 Đang Hoạt Động" if bot_active else "🔴 Đang Bảo Trì"
        toggle_text = "🔴 Tắt Bot (Bảo Trì)" if bot_active else "🟢 Bật Bot (Mở Lại)"
        await edit_or_send(query, f"🛡️ <b>BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN</b>\n━━━━━━━━━━━━━━━━━━━\nTrạng thái Bot: <b>{status_text}</b>\nLựa chọn tính năng quản lý hệ thống bên dưới:", InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data='toggle_bot_status')],
            [InlineKeyboardButton("📊 Thống Kê Tổng Quan", callback_data='ad_stats'), InlineKeyboardButton("💸 Cộng Tiền Nhanh", callback_data='ad_bal')],
            [InlineKeyboardButton("📉 Trừ Tiền User", callback_data='ad_subbal'), InlineKeyboardButton("🔍 Kiểm Tra Số Dư", callback_data='ad_checkbal')],
            [InlineKeyboardButton("👥 Thêm Admin Phụ", callback_data='ad_addadmin'), InlineKeyboardButton("➕ Bổ Sung Kho Key", callback_data='ad_addk')],
            [InlineKeyboardButton("📢 Gửi Broadcast", callback_data='ad_bc'), InlineKeyboardButton("🏠 Menu Chính", callback_data='back_menu')]
        ]))
    elif data == 'toggle_bot_status' and is_admin(uid):
        bot_active = not bot_active
        await query.answer(f"Đã chuyển trạng thái bot thành công!", show_alert=True)
        
        if not bot_active:
            await broadcast_all(context, f"🚧 <b>THÔNG BÁO BẢO TRÌ HỆ THỐNG</b>\n━━━━━━━━━━━━━━━━━━━\nBot hiện đang tạm dừng hoạt động để nâng cấp. Xin lỗi quý khách vì sự bất tiện này!")
        else:
            await broadcast_all(context, f"🚀 <b>THÔNG BÁO MỞ LẠI HỆ THỐNG</b>\n━━━━━━━━━━━━━━━━━━━\nBot đã chính thức hoạt động trở lại bình thường. Chúc quý khách mua sắm vui vẻ!")
            
        status_text = "🟢 Đang Hoạt Động" if bot_active else "🔴 Đang Bảo Trì"
        toggle_text = "🔴 Tắt Bot (Bảo Trì)" if bot_active else "🟢 Bật Bot (Mở Lại)"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_text, callback_data='toggle_bot_status')],
            [InlineKeyboardButton("📊 Thống Kê Tổng Quan", callback_data='ad_stats'), InlineKeyboardButton("💸 Cộng Tiền Nhanh", callback_data='ad_bal')],
            [InlineKeyboardButton("📉 Trừ Tiền User", callback_data='ad_subbal'), InlineKeyboardButton("🔍 Kiểm Tra Số Dư", callback_data='ad_checkbal')],
            [InlineKeyboardButton("👥 Thêm Admin Phụ", callback_data='ad_addadmin'), InlineKeyboardButton("➕ Bổ Sung Kho Key", callback_data='ad_addk')],
            [InlineKeyboardButton("📢 Gửi Broadcast", callback_data='ad_bc'), InlineKeyboardButton("🏠 Menu Chính", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛡️ <b>BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN</b>\n━━━━━━━━━━━━━━━━━━━\nTrạng thái Bot: <b>{status_text}</b>\nLựa chọn tính năng quản lý hệ thống bên dưới:", kb)
    elif data == 'ad_stats' and is_admin(uid):
        await edit_or_send(query, f"📊 <b>THỐNG KÊ HỆ THỐNG VIP</b>\n━━━━━━━━━━━━━━━━━━━\n👥 Tổng User: <code>{len(users)}</code>\n💰 Tổng Doanh Thu: <code>{total_rev:,}đ</code>\n\n📦 <b>Tồn Kho Chi Tiết:</b>\n• 1H: <code>{len(s_1h)}</code> | 6H: <code>{len(s_6h)}</code> | 1D: <code>{len(s_1d)}</code>\n• 7D: <code>{len(s_7d)}</code> | 30D: <code>{len(s_30d)}</code>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Quay Lại Admin Panel", callback_data='admin_panel')]]))
    elif data == 'ad_bal' and is_admin(uid):
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, f"💬 <b>Nhập ID user và số tiền cần cộng</b> theo định dạng:\n<code>[ID] [Số_tiền]</code>\n(Ví dụ: <code>7976468365 50000</code>){SIGNATURE}")
    elif data == 'ad_subbal' and is_admin(uid):
        admin_state[uid] = 'sub_bal'
        await edit_or_send(query, f"💬 <b>Nhập ID user và số tiền cần trừ/xóa</b> theo định dạng:\n<code>[ID] [Số_tiền]</code>\n(Ví dụ: <code>7976468365 20000</code>){SIGNATURE}")
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
        await edit_or_send(query, f"📦 <b>CHỌN KHO HÀNG CẦN BỔ SUNG KEY:</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Shop 1H", callback_data='k_s1h'), InlineKeyboardButton("🛒 Shop 6H", callback_data='k_s6h')],
            [InlineKeyboardButton("🛒 Shop 1D", callback_data='k_s1d'), InlineKeyboardButton("🛒 Shop 7D", callback_data='k_s7d')],
            [InlineKeyboardButton("🛒 Shop 30D", callback_data='k_s30d'), InlineKeyboardButton("◀️ Quay Lại", callback_data='admin_panel')]
        ]))
    elif data.startswith('k_') and is_admin(uid):
        admin_state[uid] = f"addk_{data.replace('k_', '')}"
        await edit_or_send(query, f"📝 <b>Dán danh sách Key mới vào khung chat.</b>\n(Mỗi key cách nhau bằng dòng trống):{SIGNATURE}")

async def send_qr(query, context, uid, amount):
    if amount < 10000:
        await query.answer("❌ Số tiền nạp tối thiểu là 10.000đ!", show_alert=True)
        return
    
    add_info = f"NAP {uid}"
    url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amount}&memo={quote(add_info)}"
    
    # 💡 Dùng thẻ <code> để Số tài khoản và Nội dung CK hiển thị dạng hộp mã đơn sắc, ấn vào là tự động copy giống Số tài khoản!
    text = (
        f"💳 <b>MÃ QR NẠP TIỀN TỰ ĐỘNG 24/7</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Ngân hàng: <b>{BANK_ID}</b>\n"
        f"🔢 Số tài khoản: <code>{ACCOUNT_NO}</code> <i>(Chạm để copy)</i>\n"
        f"👤 Chủ tài khoản: <b>{ACCOUNT_NAME}</b>\n"
        f"💵 Số tiền: <b>{amount:,}đ</b>\n"
        f"📝 Nội dung CK: <code>NAP {uid}</code> <i>(Chạm để copy)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 <b>LƯU Ý QUAN TRỌNG CHO NGƯỜI MUA:</b>\n"
        f"⚠️ <b>TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA ĐỔI HOẶC XÓA NỘI DUNG CHUYỂN KHOẢN!</b>\n"
        f"⚠️ <i>Nếu bạn tự ý sửa đổi hoặc ghi sai nội dung, hệ thống SePay sẽ KHÔNG THỂ nhận diện để tự động cộng tiền cho bạn!</i>\n"
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

async def handle_admin_text(update, context):
    uid = update.message.from_user.id
    if uid not in admin_state: return
    state = admin_state[uid]
    text = update.message.text

    if state == 'waiting_deposit':
        del admin_state[uid]
        try:
            amt = int(text.replace(".", "").strip())
            if amt < 10000:
                await update.message.reply_text("❌ Số tiền nạp tối thiểu là 10.000đ!")
                return
            add_info = f"NAP {uid}"
            url = f"https://vietqr.app/img?bank={BANK_ID}&acc={ACCOUNT_NO}&template=compact&showinfo=true&holder={quote(ACCOUNT_NAME)}&amount={amt}&memo={quote(add_info)}"
            
            text_custom = (
                f"💳 <b>QR NẠP {amt:,}đ</b>\n"
                f"📝 Nội dung CK bắt buộc: <code>NAP {uid}</code> <i>(Chạm để copy)</i>\n\n"
                f"🚨 <b>LƯU Ý: KHÔNG ĐƯỢC SỬA NỘI DUNG CHUYỂN KHOẢN ĐỂ TRÁNH MẤT TIỀN!</b>"
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Về Menu Chính", callback_data='back_menu')]])
            await update.message.reply_photo(photo=url, caption=text_custom, reply_markup=kb, parse_mode="HTML")
        except: await update.message.reply_text("❌ Số tiền nhập không hợp lệ!")
        return

    if not is_admin(uid): return

    if state == 'add_bal':
        try:
            tid, amt = text.split(); tid, amt = int(tid), int(amt)
            u = get_u(tid)
            u['balance'] += amt; u['total_deposit'] += amt
            u['history'].append(f"Admin cộng (+{amt:,}đ)")
            if len(u['history']) > 20: u['history'].pop(0)
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
            u['history'].append(f"Admin trừ (-{amt:,}đ)")
            if len(u['history']) > 20: u['history'].pop(0)
            await update.message.reply_text(f"✅ Đã trừ thành công <code>{amt:,}đ</code> của User ID: <code>{tid}</code>")
            try: await context.bot.send_message(tid, f"⚠️ <b>[TÀI CHÍNH]</b> Số dư ví của bạn vừa bị Admin trừ bớt <b>-{amt:,}đ</b>!{SIGNATURE}", parse_mode="HTML")
            except: pass
        except: await update.message.reply_text("❌ Sai cú pháp! Vui lòng nhập: `[ID] [Số_tiền]`")
        del admin_state[uid]
    elif state == 'check_user_bal':
        try:
            tid = int(text.strip())
            if tid in user_data:
                target_u = user_data[tid]
                hist_preview = "\n".join(target_u['history'][-5:]) if target_u['history'] else "Trống."
                await update.message.reply_text(f"🔍 <b>THÔNG TIN SỐ DƯ USER</b>\n━━━━━━━━━━━━━━━━━━━\n🆔 ID: <code>{tid}</code>\n💎 Số dư ví: <b>{target_u['balance']:,}đ</b>\n💳 Tổng nạp: <b>{target_u['total_deposit']:,}đ</b>\n\n🧾 <b>Lịch sử gần đây:</b>\n{hist_preview}{SIGNATURE}", parse_mode="HTML")
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
        for u in list(users):
            try: await context.bot.send_message(u, f"📢 <b>THÔNG BÁO TỪ HỆ THỐNG</b>\n━━━━━━━━━━━━━━━━━━━\n{html.escape(text)}{SIGNATURE}", parse_mode="HTML"); succ += 1
            except: pass
        await update.message.reply_text(f"✅ Đã phát sóng thông báo thành công đến <code>{succ}</code> người dùng.")
    elif state.startswith('addk_'):
        k_type = state.replace('addk_', '')
        m_map = {'s1h': s_1h, 's6h': s_6h, 's1d': s_1d, 's7d': s_7d, 's30d': s_30d}
        target = m_map.get(k_type)
        if target is not None:
            added = 0
            for b in text.split('\n\n'):
                if b.strip(): target.append(html.escape(b.strip())); added += 1
            await update.message.reply_text(f"✅ Đã bổ sung thành công <code>{added}</code> Key vào kho <b>{k_type.upper()}</b> (Tồn kho: <code>{len(target)}</code>)!")
            await broadcast_all(context, f"📢 <b>CẬP NHẬT KHO HÀNG REAL-TIME</b>\n━━━━━━━━━━━━━━━━━━━\n📦 Kho <b>{k_type.upper()}</b> vừa được Admin cấp thêm key mới!\n📊 Tồn kho hiện tại: <code>{len(target)} Key</code>.\n\n👉 Nhanh tay truy cập bot để mua ngay nhé!{SIGNATURE}")
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
            u['history'].append(f"SePay Auto (+{amt:,}đ)")
            if len(u['history']) > 20: u['history'].pop(0)
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