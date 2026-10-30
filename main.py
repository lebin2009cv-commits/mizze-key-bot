import os, logging, threading, httpx, re, secrets, string, time, html, datetime
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
BOT_USERNAME = "GetkeyMizzebot"
ADMIN_ID = 7976468365

SIGNATURE = "\n\n────────────────────\n🤖 <i>Powered by Mizze Key Bot</i>"
BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/lebindz"
SUPPORT_CONTACT = "https://t.me/NTH_VIP"

LINK4M = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")
SHRINKME = os.environ.get("SHRINKME_API_KEY", "cbf0c1f1343fbb4755913212000f0ad1178e3a46")

BANK_ID = "VPBANK"
ACCOUNT_NO = "0382570538"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_KEY = os.environ.get("SEPAY_API_KEY", "botgetkey_sepay")

# Giá gói mua mới
P_1H, P_6H, P_1D, P_7D, P_30D = 7000, 15000, 20000, 75000, 150000

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

f_3h, f_6h = [], []
s_1h, s_6h, s_1d, s_7d, s_30d = [], [], [], [], []
states, cooldowns, admin_state = {}, {}, {}
users, user_data, limits = set(), {}, {}
bot_active, total_rev = True, 0

def get_u(uid):
    if uid not in user_data: user_data[uid] = {'balance': 0, 'total_deposit': 0, 'history': [], 'checkin': ''}
    return user_data[uid]

def check_lim(uid):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if uid not in limits or limits[uid]['date'] != today:
        limits[uid] = {'date': today, 'count': 0}
    return (False, 0) if limits[uid]['count'] >= 3 else (True, 3 - limits[uid]['count'])

def add_lim(uid):
    if uid in limits: limits[uid]['count'] += 1

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

async def get_link(api_type, url):
    try:
        key_val = LINK4M if api_type == 'l4m' else SHRINKME
        base_url = f"https://link4m.co/api-shorten/v2?api={key_val}&url=" if api_type == 'l4m' else f"https://shrinkme.io/api?api={key_val}&url="
        async with httpx.AsyncClient() as c:
            r = await c.get(base_url + quote(url, safe=''), timeout=10)
            if r.json().get("status") == "success": return r.json().get("shortenedUrl").strip()
    except: pass
    return None

async def notify_ad(context, msg):
    try: await context.bot.send_message(chat_id=ADMIN_ID, text="🔔 <b>THÔNG BÁO</b>\n\n" + msg + SIGNATURE, parse_mode="HTML")
    except: pass

async def show_main_menu(update, context):
    uid = update.effective_user.id
    if not bot_active and uid != ADMIN_ID:
        text = "🚧 <b>HỆ THỐNG ĐANG BẢO TRÌ</b> 🚧" + SIGNATURE
        if update.message: await update.message.reply_text(text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML")
        return

    u = get_u(uid)
    _, rem = check_lim(uid)
    text = f"🏪 <b>MIZZE KEY VIP</b>\n\n📢 <b>Kênh:</b> {CHANNEL_URL}\n👮‍♂️ <b>Admin:</b> {ADMIN_CONTACT}\n〰️〰️〰️〰️〰️〰️〰️〰️\n💸 <b>Tổng nạp:</b> {u['total_deposit']:,}đ\n💰 <b>Số dư ví:</b> <b>{u['balance']:,}đ</b>\n🎁 <b>Free hôm nay:</b> {rem}/3{SIGNATURE}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 LẤY KEY (MIỄN PHÍ)", callback_data='menu_getkey')],
        [InlineKeyboardButton("🛒 Cửa hàng", callback_data='menu_shop'), InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit')],
        [InlineKeyboardButton("📅 Điểm danh nhận quà", callback_data='menu_checkin'), InlineKeyboardButton("👤 Tài khoản", callback_data='menu_account')],
        [InlineKeyboardButton("🧾 Lịch sử", callback_data='menu_history'), InlineKeyboardButton("🐸 Hỗ trợ", url=SUPPORT_CONTACT)],
        [InlineKeyboardButton("🛡️ ADMIN PANEL", callback_data='admin_panel')]
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
    if uid not in states: states[uid] = {'type': None, 'step': 0, 'token': None}

    if context.args:
        try:
            parts = context.args[0].split("_")
            kt, step = parts[0], int(parts[1].replace("step", ""))
            token = parts[2] if len(parts) > 2 else None
            st = states[uid]
            
            if st['type'] == kt and st['step'] == step - 1 and token == st['token']:
                st['step'] = step
                t = secrets.token_hex(4)
                st['token'] = t
                
                if kt == "3h":
                    if step == 1:
                        u = await get_link('shr', f"https://t.me/{BOT_USERNAME}?start=3h_step2_{t}")
                        await update.message.reply_text("🔄 <b>Tiến trình 2/3 (ShrinkMe)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK 2", url=u)]]), parse_mode="HTML")
                    elif step == 2:
                        u = await get_link('l4m', f"https://t.me/{BOT_USERNAME}?start=3h_step3_{t}")
                        await update.message.reply_text("🔄 <b>Tiến trình 3/3 (Link4m)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK 3", url=u)]]), parse_mode="HTML")
                    elif step == 3:
                        if f_3h:
                            k = f_3h.pop(0)
                            cooldowns[uid] = cooldowns.get(uid, {}); cooldowns[uid]['3h'] = time.time() + 10800
                            add_lim(uid)
                            key_display = f"<code>{k}</code>" if "KEY" in k.upper() else f"<pre>{k}</pre>"
                            await update.message.reply_text(f"🎉 <b>Vượt link thành công! Nhấn vào đoạn dưới để copy:</b>\n\n{key_display}{SIGNATURE}", parse_mode="HTML")
                            await notify_ad(context, f"User <code>{uid}</code> nhận <b>Key 3H</b>. Kho còn: <code>{len(f_3h)}</code>")
                        else: await update.message.reply_text("❌ Kho Key 3H đã cạn!", parse_mode="HTML")
                        st.update({'type': None, 'step': 0, 'token': None})
                
                elif kt == "6h":
                    if step == 1:
                        u = await get_link('l4m', f"https://t.me/{BOT_USERNAME}?start=6h_step2_{t}")
                        await update.message.reply_text("🔄 <b>Tiến trình 2/4 (Link4m)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK 2", url=u)]]), parse_mode="HTML")
                    elif step == 2:
                        u = await get_link('shr', f"https://t.me/{BOT_USERNAME}?start=6h_step3_{t}")
                        await update.message.reply_text("🔄 <b>Tiến trình 3/4 (ShrinkMe)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK 3", url=u)]]), parse_mode="HTML")
                    elif step == 3:
                        u = await get_link('l4m', f"https://t.me/{BOT_USERNAME}?start=6h_step4_{t}")
                        await update.message.reply_text("🔄 <b>Tiến trình 4/4 (Link4m)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK 4", url=u)]]), parse_mode="HTML")
                    elif step == 4:
                        if f_6h:
                            k = f_6h.pop(0)
                            cooldowns[uid] = cooldowns.get(uid, {}); cooldowns[uid]['6h'] = time.time() + 21600
                            add_lim(uid)
                            key_display = f"<code>{k}</code>" if "KEY" in k.upper() else f"<pre>{k}</pre>"
                            await update.message.reply_text(f"🎉 <b>Vượt link thành công! Nhấn vào đoạn dưới để copy:</b>\n\n{key_display}{SIGNATURE}", parse_mode="HTML")
                            await notify_ad(context, f"User <code>{uid}</code> nhận <b>Key 6H</b>. Kho còn: <code>{len(f_6h)}</code>")
                        else: await update.message.reply_text("❌ Kho Key 6H đã cạn!", parse_mode="HTML")
                        st.update({'type': None, 'step': 0, 'token': None})
            else:
                await update.message.reply_text(f"⚠️ <b>Link cũ hoặc sai tiến trình!</b>{SIGNATURE}", parse_mode="HTML")
            return
        except: pass
    await show_main_menu(update, context)

async def button_handler(update, context):
    global total_rev
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    u = get_u(uid)
    data = query.data

    if data == 'back_menu': await show_main_menu(update, context)
    elif data == 'menu_guide':
        await edit_or_send(query, f"📖 <b>Hướng dẫn sử dụng:</b>\n1️⃣ Vượt link xen kẽ để nhận Key Free 3H hoặc 6H.\n2️⃣ Dùng số dư ví để mua các gói Key tự động hoặc nạp tiền qua QR.{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
    elif data == 'menu_checkin':
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if u['checkin'] == today:
            await edit_or_send(query, f"⚠️ <b>Bạn đã điểm danh hôm nay rồi! Hãy quay lại vào ngày mai nhé.</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
        else:
            u['checkin'] = today
            u['balance'] += 2000  # Thưởng nóng 2k vào ví khi điểm danh
            await edit_or_send(query, f"🎁 <b>Điểm danh thành công!</b> Bạn nhận được thưởng <b>+2.000đ</b> vào số dư ví.\n💰 Số dư hiện tại: <b>{u['balance']:,}đ</b>{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
    elif data == 'menu_getkey':
        ok, rem = check_lim(uid)
        if not ok:
            await edit_or_send(query, "🚫 <b>Đã hết 3 lượt lấy key free hôm nay!</b>")
            return
        await edit_or_send(query, f"👇 Bạn còn <b>{rem}/3</b> lượt hôm nay. Chọn loại:", InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 KEY 3H (3 Link xen kẽ)", callback_data='get_3h')],
            [InlineKeyboardButton("💎 KEY 6H (4 Link xen kẽ)", callback_data='get_6h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]))
    elif data.startswith('get_'):
        kt = data.split('_')[1]
        t = secrets.token_hex(4)
        states[uid] = {'type': kt, 'step': 0, 'token': t}
        url = await get_link('l4m' if kt=='3h' else 'shr', f"https://t.me/{BOT_USERNAME}?start={kt}_step1_{t}")
        await edit_or_send(query, f"🔄 <b>Tiến trình 1/{'3' if kt=='3h' else '4'}</b>", InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK 1", url=url)]]))
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Mua 1H ({P_1H:,}đ)", callback_data='buy_1h'), InlineKeyboardButton(f"Mua 6H ({P_6H:,}đ)", callback_data='buy_6h')],
            [InlineKeyboardButton(f"Mua 1D ({P_1D:,}đ)", callback_data='buy_1d'), InlineKeyboardButton(f"Mua 7D ({P_7D:,}đ)", callback_data='buy_7d')],
            [InlineKeyboardButton(f"Mua 30D ({P_30D:,}đ)", callback_data='buy_30d')],
            [InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit'), InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛒 <b>CỬA HÀNG MUA KEY</b>\n💰 Số dư ví: <b>{u['balance']:,}đ</b>", kb)
    elif data.startswith('buy_'):
        kt = data.split('_')[1]
        p_map = {'1h': (P_1H, s_1h), '6h': (P_6H, s_6h), '1d': (P_1D, s_1d), '7d': (P_7D, s_7d), '30d': (P_30D, s_30d)}
        price, kho = p_map[kt]
        if u['balance'] < price:
            await edit_or_send(query, f"❌ <b>Số dư ví không đủ! Bạn cần {price:,}đ nhưng ví chỉ có {u['balance']:,}đ. Vui lòng nạp thêm!</b>")
            return
        if not kho:
            await edit_or_send(query, f"❌ <b>Kho Key {kt.upper()} hiện đã hết hàng!</b>")
            return
        # Trừ tiền ví khách hàng ngay lập tức
        u['balance'] -= price; total_rev += price
        k_nhan = kho.pop(0)
        u['history'].append(f"Mua {kt.upper()} (-{price:,}đ)")
        await notify_ad(context, f"User <code>{uid} -> Mua Key {kt.upper()}</code> giá <b>{price:,}đ</b>. Kho còn: <code>{len(kho)}</code>")
        
        key_display = f"<code>{k_nhan}</code>" if "KEY" in k_nhan.upper() else f"<pre>{k_nhan}</pre>"
        await edit_or_send(query, f"✅ <b>MUA THÀNH CÔNG! Trừ ví: -{price:,}đ</b>\n〰️〰️〰️〰️〰️〰️〰️〰️\n<b>Nhấn để copy:</b>\n{key_display}\n〰️〰️〰️〰️〰️〰️〰️〰️\n💰 Số dư còn lại: <b>{u['balance']:,}đ</b>", InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Mua tiếp", callback_data='menu_shop'), InlineKeyboardButton("⬅️ Menu", callback_data='back_menu')]]))
    elif data == 'menu_deposit':
        await edit_or_send(query, "💳 <b>CHỌN MỨC NẠP TIỀN</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("50.000đ", callback_data='qr_50000'), InlineKeyboardButton("100.000đ", callback_data='qr_100000')],
            [InlineKeyboardButton("200.000đ", callback_data='qr_200000'), InlineKeyboardButton("✏️ Nhập khác", callback_data='qr_custom')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]))
    elif data.startswith('qr_'):
        sub = data.replace('qr_', '')
        if sub == 'custom':
            admin_state[uid] = 'waiting_deposit'
            await edit_or_send(query, "💬 Nhập số tiền muốn nạp (VD: `50000`):", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='menu_deposit')]]))
            return
        await send_qr(query, context, uid, int(sub))
    elif data.startswith('check_pay_'):
        await query.answer("⏳ Đang quét giao dịch SePay...", show_alert=True)
    elif data == 'menu_account':
        _, rem = check_lim(uid)
        await edit_or_send(query, f"👤 ID: <code>{uid}</code>\nVí: <b>{u['balance']:,}đ</b>\nTổng nạp: <b>{u['total_deposit']:,}đ</b>\nFree: {rem}/3{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
    elif data == 'menu_history':
        hist = "\n".join(u['history'][-10:]) if u['history'] else "Trống."
        await edit_or_send(query, f"🧾 <b>Lịch sử giao dịch:</b>\n{hist}{SIGNATURE}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
    elif data == 'admin_panel' and uid == ADMIN_ID:
        await edit_or_send(query, "🛡️ <b>ADMIN PANEL</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Thống kê", callback_data='ad_stats'), InlineKeyboardButton("💸 Cộng tiền", callback_data='ad_bal')],
            [InlineKeyboardButton("➕ Thêm Key", callback_data='ad_addk'), InlineKeyboardButton("📢 Broadcast", callback_data='ad_bc')],
            [InlineKeyboardButton("⬅️ Menu", callback_data='back_menu')]
        ]))
    elif data == 'ad_stats' and uid == ADMIN_ID:
        await edit_or_send(query, f"📊 Users: {len(users)} | Doanh thu: {total_rev:,}đ\nFree 3H: {len(f_3h)} | 6H: {len(f_6h)}\nShop 1H: {len(s_1h)} | 6H: {len(s_6h)} | 1D: {len(s_1d)} | 7D: {len(s_7d)} | 30D: {len(s_30d)}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin", callback_data='admin_panel')]]))
    elif data == 'ad_bal' and uid == ADMIN_ID:
        admin_state[uid] = 'add_bal'
        await edit_or_send(query, "💬 Nhập ID và số tiền (VD: `7976468365 50000`):")
    elif data == 'ad_bc' and uid == ADMIN_ID:
        admin_state[uid] = 'bc'
        await edit_or_send(query, "💬 Nhập nội dung broadcast:")
    elif data == 'ad_addk' and uid == ADMIN_ID:
        await edit_or_send(query, "📦 Chọn kho thêm Key:", InlineKeyboardMarkup([
            [InlineKeyboardButton("Free 3H", callback_data='k_f3h'), InlineKeyboardButton("Free 6H", callback_data='k_f6h')],
            [InlineKeyboardButton("Shop 1H", callback_data='k_s1h'), InlineKeyboardButton("Shop 6H", callback_data='k_s6h')],
            [InlineKeyboardButton("Shop 1D", callback_data='k_s1d'), InlineKeyboardButton("Shop 7D", callback_data='k_s7d')],
            [InlineKeyboardButton("Shop 30D", callback_data='k_s30d'), InlineKeyboardButton("⬅️ Admin", callback_data='admin_panel')]
        ]))
    elif data.startswith('k_') and uid == ADMIN_ID:
        admin_state[uid] = f"addk_{data.replace('k_', '')}"
        await edit_or_send(query, "📝 Dán danh sách Key vào đây:")

async def send_qr(query, context, uid, amount):
    add_info = f"NAP {uid}"
    url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo={quote(add_info)}&accountName={quote(ACCOUNT_NAME)}"
    text = f"💳 <b>QR NẠP TIỀN</b>\n🏦 {BANK_ID} - STK: <code>{ACCOUNT_NO}</code>\n💵 Số tiền: <b>{amount:,}đ</b>\n📝 Nội dung: <code>{add_info}</code>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ĐÃ CHUYỂN KHOẢN", callback_data=f"check_pay_{amount}")],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data='menu_deposit')]
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
            add_info = f"NAP {uid}"
            url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amt}&addInfo={quote(add_info)}&accountName={quote(ACCOUNT_NAME)}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ ĐÃ CK", callback_data=f"check_pay_{amt}")], [InlineKeyboardButton("⬅️ Menu", callback_data='back_menu')]])
            await update.message.reply_photo(photo=url, caption=f"💳 QR nạp {amt:,}đ\nNội dung: <code>{add_info}</code>", reply_markup=kb, parse_mode="HTML")
        except: await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    if uid != ADMIN_ID: return

    if state == 'add_bal':
        try:
            tid, amt = text.split(); tid, amt = int(tid), int(amt)
            u = get_u(tid)
            u['balance'] += amt; u['total_deposit'] += amt
            u['history'].append(f"Admin cộng (+{amt:,}đ)")
            await update.message.reply_text(f"✅ Đã cộng {amt:,}đ cho {tid}")
            try: await context.bot.send_message(tid, f"💰 Bạn được cộng {amt:,}đ từ Admin!")
            except: pass
        except: await update.message.reply_text("❌ Sai cú pháp.")
        del admin_state[uid]
    elif state == 'bc':
        del admin_state[uid]
        succ = 0
        for u in list(users):
            try: await context.bot.send_message(u, f"📢 <b>THÔNG BÁO</b>\n\n{html.escape(text)}", parse_mode="HTML"); succ += 1
            except: pass
        await update.message.reply_text(f"✅ Đã gửi đến {succ} user.")
    elif state.startswith('addk_'):
        k_type = state.replace('addk_', '')
        m_map = {'f3h': f_3h, 'f6h': f_6h, 's1h': s_1h, 's6h': s_6h, 's1d': s_1d, 's7d': s_7d, 's30d': s_30d}
        target = m_map.get(k_type)
        if target is not None:
            added = 0
            for b in text.split('\n\n'):
                if b.strip(): target.append(html.escape(b.strip())); added += 1
            await update.message.reply_text(f"✅ Đã thêm {added} Key vào kho {k_type} (Tồn: {len(target)})!")
        del admin_state[uid]

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "OK", 200

@flask_app.route('/sepay_webhook', methods=['POST'])
def sepay():
    if request.headers.get('Authorization') != f"Apikey {SEPAY_KEY}": return jsonify({"success": False}), 401
    data = request.json
    if data and data.get("transferType") == "in":
        m = re.search(r"NAP\s+(\d+)", data.get("content", ""), re.IGNORECASE)
        if m:
            tid = int(m.group(1)); amt = int(data.get("transferAmount", 0))
            u = get_u(tid)
            u['balance'] += amt; u['total_deposit'] += amt
            u['history'].append(f"SePay (+{amt:,}đ)")
            try:
                msg = f"✅ <b>NẠP THÀNH CÔNG!</b>\n+{amt:,}đ\nSố dư: <b>{u['balance']:,}đ</b>"
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