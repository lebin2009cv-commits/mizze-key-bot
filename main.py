import os, logging, threading, httpx, re, secrets, string, time, asyncio, html, datetime
from urllib.parse import quote
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9112215461:AAFDBZr4BEt5e5iSFW33AfpXd6iMrdPBaaM")
BOT_USERNAME = "GetkeyMizzebot"
ADMIN_ID = 7976468365

USER_SIGNATURE = "\n\n────────────────────\n🤖 <i>Powered by Mizze Key Bot</i>"
BANNER_URL = "https://files.catbox.moe/f01erm.jpeg"
CHANNEL_URL = "https://t.me/mizze_store"
ADMIN_CONTACT = "https://t.me/lebindz"
SUPPORT_CONTACT = "https://t.me/NTH_VIP"

LINK4M_API_KEY = os.environ.get("LINK4M_API_KEY", "6a38ad422de39b3f34159f96")
YEUMONEY_API_KEY = os.environ.get("YEUMONEY_API_KEY", "316b5434e78e4ffe8475d87e407754f0ab92a4b85055a7ecd19c86a196cd702a")
SHRINKME_API_KEY = os.environ.get("SHRINKME_API_KEY", "cbf0c1f1343fbb4755913212000f0ad1178e3a46")

BANK_ID = "VPBANK"
ACCOUNT_NO = "0382570538"
ACCOUNT_NAME = "LE GIA BAO"
SEPAY_API_KEY = os.environ.get("SEPAY_API_KEY", "botgetkey_sepay")

PRICE_1H, PRICE_12H, PRICE_1D, PRICE_1M = 10000, 20000, 70000, 150000

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

kho_free_1h, kho_free_3h = [], []
kho_shop_1h, kho_shop_12h, kho_shop_1d, kho_shop_1m = [], [], [], []
user_states, cooldowns, admin_adding_state = {}, {}, {}
all_users, user_data, daily_limits = set(), {}, {}
bot_status = {"active": True}
total_revenue = 0

def get_user(uid):
    if uid not in user_data: user_data[uid] = {'balance': 0, 'total_deposit': 0, 'history': []}
    return user_data[uid]

def check_daily_limit(uid):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if uid not in daily_limits or daily_limits[uid]['date'] != today:
        daily_limits[uid] = {'date': today, 'count': 0}
    return (False, 0) if daily_limits[uid]['count'] >= 3 else (True, 3 - daily_limits[uid]['count'])

def add_daily_usage(uid):
    if uid in daily_limits: daily_limits[uid]['count'] += 1

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

async def shorten_link4m(url):
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"https://link4m.co/api-shorten/v2?api={LINK4M_API_KEY}&url={quote(url, safe='')}", timeout=10)
            if r.json().get("status") == "success": return r.json().get("shortenedUrl").strip()
    except: pass
    return None

async def shorten_yeumoney(url):
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"https://yeumoney.com/QL_api.php?token={YEUMONEY_API_KEY}&url={quote(url, safe='')}&format=json", timeout=10)
            if r.json().get("status") == "success": return r.json().get("shortenedUrl").strip()
    except: pass
    return None

async def shorten_shrinkme(url):
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"https://shrinkme.io/api?api={SHRINKME_API_KEY}&url={quote(url, safe='')}", timeout=10)
            if r.json().get("status") == "success": return r.json().get("shortenedUrl").strip()
    except: pass
    return None

async def notify_admin(context, msg):
    try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 <b>ADMIN</b>\n\n{msg}" + USER_SIGNATURE, parse_mode="HTML")
    except: pass

async def show_main_menu(update, context):
    uid = update.effective_user.id
    if not bot_status["active"] and uid != ADMIN_ID:
        text = "🚧 <b>BẢO TRÌ</b> 🚧" + USER_SIGNATURE
        if update.message: await update.message.reply_text(text, parse_mode="HTML")
        elif update.callback_query: await update.callback_query.message.edit_text(text, parse_mode="HTML")
        return

    u = get_user(uid)
    _, rem = check_daily_limit(uid)
    text = f"🏪 <b>MIZZE KEY VIP</b>\n\n📢 <b>Kênh:</b> {CHANNEL_URL}\n👮‍♂️ <b>Admin:</b> {ADMIN_CONTACT}\n〰️〰️〰️〰️〰️〰️〰️〰️\n💸 <b>Tổng nạp:</b> {u['total_deposit']:,}đ\n💰 <b>Số dư:</b> {u['balance']:,}đ\n🎁 <b>Free hôm nay:</b> {rem}/3\n" + USER_SIGNATURE
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 LẤY KEY (MIỄN PHÍ)", callback_data='menu_getkey')],
        [InlineKeyboardButton("🛒 Cửa hàng", callback_data='menu_shop'), InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit')],
        [InlineKeyboardButton("📖 Hướng dẫn", callback_data='menu_guide'), InlineKeyboardButton("👤 Tài khoản", callback_data='menu_account')],
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
    all_users.add(uid)
    get_user(uid)
    if uid not in user_states: user_states[uid] = {'type': None, 'step': 0, 'token': None}

    if context.args:
        try:
            parts = context.args[0].split("_")
            kt, step = parts[0], int(parts[1].replace("step", ""))
            token = parts[2] if len(parts) > 2 else None
            st = user_states[uid]
            if st['type'] == kt and st['step'] == step - 1 and token == st['token']:
                st['step'] = step
                if kt == "1h":
                    if step == 1:
                        t = secrets.token_hex(4)
                        st['token'] = t
                        u = await shorten_yeumoney(f"https://t.me/{BOT_USERNAME}?start=1h_step2_{t}")
                        await update.message.reply_text("🔄 <b>Tiến trình 2/2 (YeuMoney)</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK", url=u)]]), parse_mode="HTML")
                    elif step == 2:
                        if kho_free_1h:
                            k = kho_free_1h.pop(0)
                            cooldowns[uid] = cooldowns.get(uid, {})
                            cooldowns[uid]['1h'] = time.time() + 3600
                            add_daily_usage(uid)
                            await update.message.reply_text(f"🎉 <b>Thành công!</b>\n{k}" + USER_SIGNATURE, parse_mode="HTML")
                        else: await update.message.reply_text("❌ Kho Key 1H đã cạn!", parse_mode="HTML")
                        st.update({'type': None, 'step': 0, 'token': None})
                elif kt == "3h":
                    if step in [1, 2, 3]:
                        t = secrets.token_hex(4)
                        st['token'] = t
                        prov = shorten_shrinkme if step in [1, 3] else shorten_link4m
                        u = await prov(f"https://t.me/{BOT_USERNAME}?start=3h_step{step+1}_{t}")
                        await update.message.reply_text(f"🔄 <b>Tiến trình {step+1}/4</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK", url=u)]]), parse_mode="HTML")
                    elif step == 4:
                        if kho_free_3h:
                            k = kho_free_3h.pop(0)
                            cooldowns[uid] = cooldowns.get(uid, {})
                            cooldowns[uid]['3h'] = time.time() + 10800
                            add_daily_usage(uid)
                            await update.message.reply_text(f"🎉 <b>Thành công!</b>\n{k}" + USER_SIGNATURE, parse_mode="HTML")
                        else: await update.message.reply_text("❌ Kho Key 3H đã cạn!", parse_mode="HTML")
                        st.update({'type': None, 'step': 0, 'token': None})
            return
        except: pass
    await show_main_menu(update, context)

async def button_handler(update, context):
    global total_revenue
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    u = get_user(uid)
    data = query.data

    if data == 'back_menu': await show_main_menu(update, context)
    elif data == 'menu_guide':
        await edit_or_send(query, "📖 <b>Hướng dẫn:</b>\n1️⃣ Lấy Key miễn phí qua các bước.\n2️⃣ Mua Key bằng số dư ví." + USER_SIGNATURE, InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
    elif data == 'menu_getkey':
        ok, rem = check_daily_limit(uid)
        if not ok:
            await edit_or_send(query, "🚫 <b>Đã hết 3 lượt miễn phí hôm nay!</b>")
            return
        await edit_or_send(query, f"👇 Còn <b>{rem}/3</b> lượt. Chọn loại:", InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 KEY 1H", callback_data='get_1h')],
            [InlineKeyboardButton("💎 KEY 3H", callback_data='get_3h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]))
    elif data.startswith('get_'):
        kt = data.split('_')[1]
        t = secrets.token_hex(4)
        user_states[uid] = {'type': kt, 'step': 0, 'token': t}
        url = await (shorten_yeumoney if kt == '1h' else shorten_link4m)(f"https://t.me/{BOT_USERNAME}?start={kt}_step1_{t}")
        await edit_or_send(query, "🔄 <b>Tiến trình 1</b>", InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK", url=url)]]))
    elif data == 'menu_shop':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Mua 1H", callback_data='buy_1h'), InlineKeyboardButton("Mua 12H", callback_data='buy_12h')],
            [InlineKeyboardButton("Mua 1 Ngày", callback_data='buy_1d'), InlineKeyboardButton("Mua 1 Tháng", callback_data='buy_1m')],
            [InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit'), InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ])
        await edit_or_send(query, f"🛒 <b>CỬA HÀNG</b>\n💰 Số dư: <b>{u['balance']:,}đ</b>", kb)
    elif data.startswith('buy_'):
        kt = data.split('_')[1]
        p_map = {'1h': (PRICE_1H, kho_shop_1h), '12h': (PRICE_12H, kho_shop_12h), '1d': (PRICE_1D, kho_shop_1d), '1m': (PRICE_1M, kho_shop_1m)}
        price, kho = p_map[kt]
        if u['balance'] < price:
            await edit_or_send(query, "❌ <b>Số dư không đủ!</b>")
            return
        if not kho:
            await edit_or_send(query, f"❌ <b>Kho Key {kt.upper()} đã hết!</b>")
            return
        u['balance'] -= price
        total_revenue += price
        key_nhan = kho.pop(0)
        u['history'].append(f"Mua {kt.upper()} (-{price:,}đ)")
        await notify_admin(context, f"User <code>{uid}</code> mua Key {kt.upper()} (+{price:,}đ)")
        await edit_or_send(query, f"✅ <b>Thành công!</b>\n{key_nhan}\n💰 Còn: <b>{u['balance']:,}đ</b>", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data='back_menu')]]))
    elif data == 'menu_deposit':
        await edit_or_send(query, "💳 <b>Chọn mức nạp:</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("50.000đ", callback_data='qr_50000'), InlineKeyboardButton("100.000đ", callback_data='qr_100000')],
            [InlineKeyboardButton("200.000đ", callback_data='qr_200000'), InlineKeyboardButton("✏️ Nhập khác", callback_data='qr_custom')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]))
    elif data.startswith('qr_'):
        sub = data.replace('qr_', '')
        if sub == 'custom':
            admin_adding_state[uid] = 'waiting_deposit'
            await edit_or_send(query, "💬 Nhập số tiền muốn nạp (VD: `50000`):", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='menu_deposit')]]))
            return
        await send_qr(query, context, uid, int(sub))
    elif data.startswith('check_pay_'):
        await query.answer("⏳ Đang kiểm tra giao dịch với SePay...", show_alert=True)
    elif data == 'menu_account':
        _, rem = check_daily_limit(uid)
        await edit_or_send(query, f"👤 ID: <code>{uid}</code>\nVí: <b>{u['balance']:,}đ</b>\nTổng nạp: <b>{u['total_deposit']:,}đ</b>\nFree: {rem}/3", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
    elif data == 'menu_history':
        hist = "\n".join(u['history'][-10:]) if u['history'] else "Trống."
        await edit_or_send(query, f"🧾 <b>Lịch sử:</b>\n{hist}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]))
    elif data == 'admin_panel' and uid == ADMIN_ID:
        await edit_or_send(query, "🛡️ <b>ADMIN PANEL</b>", InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Thống kê", callback_data='ad_stats'), InlineKeyboardButton("💸 Cộng tiền", callback_data='ad_bal')],
            [InlineKeyboardButton("➕ Thêm Key", callback_data='ad_addk'), InlineKeyboardButton("📢 Broadcast", callback_data='ad_bc')],
            [InlineKeyboardButton("⬅️ Menu", callback_data='back_menu')]
        ]))
    elif data == 'ad_stats' and uid == ADMIN_ID:
        await edit_or_send(query, f"📊 Users: {len(all_users)} | Doanh thu: {total_revenue:,}đ\nFree 1H: {len(kho_free_1h)} | 3H: {len(kho_free_3h)}", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin", callback_data='admin_panel')]]))
    elif data == 'ad_bal' and uid == ADMIN_ID:
        admin_adding_state[uid] = 'add_bal'
        await edit_or_send(query, "Nhập ID và số tiền (VD: `7976468365 50000`):")
    elif data == 'ad_bc' and uid == ADMIN_ID:
        admin_adding_state[uid] = 'bc'
        await edit_or_send(query, "Nhập nội dung thông báo:")
    elif data == 'ad_addk' and uid == ADMIN_ID:
        await edit_or_send(query, "Chọn kho thêm Key:", InlineKeyboardMarkup([
            [InlineKeyboardButton("Free 1H", callback_data='k_f1h'), InlineKeyboardButton("Free 3H", callback_data='k_f3h')],
            [InlineKeyboardButton("Shop 1H", callback_data='k_s1h'), InlineKeyboardButton("Shop 12H", callback_data='k_s12h')],
            [InlineKeyboardButton("⬅️ Admin", callback_data='admin_panel')]
        ]))
    elif data.startswith('k_') and uid == ADMIN_ID:
        admin_adding_state[uid] = f"addk_{data.replace('k_', '')}"
        await edit_or_send(query, "📝 Dán danh sách Key vào đây:")

async def send_qr(query, context, uid, amount):
    add_info = f"NAP {uid}"
    url = f"