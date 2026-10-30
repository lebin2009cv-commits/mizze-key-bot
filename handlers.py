# handlers.py
import html
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    ADMIN_ID, BANNER_URL, CHANNEL_URL, ADMIN_CONTACT, SUPPORT_CONTACT,
    BANK_ID, ACCOUNT_NO, ACCOUNT_NAME,
    PRICE_SHOP_1H, PRICE_SHOP_12H, PRICE_SHOP_1D, PRICE_SHOP_1M,
    BOT_USERNAME, DAILY_FREE_LIMIT
)
from database import (
    get_or_create_user, update_balance, get_user_history,
    get_available_key, sell_key, add_keys,
    check_daily_limit, add_daily_usage, check_cooldown, set_cooldown,
    is_bot_active, set_bot_active, get_admin_stats
)
from utils import generate_token, generate_random_key, create_short_link

# State tạm
user_states = {}
admin_adding_state = {}
all_users = set()


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_or_create_user(user_id)
    can_get, remaining = await check_daily_limit(user_id, DAILY_FREE_LIMIT)

    text = (
        "🏪 <b>Chào Mừng Bạn Đến Với Bot Bán Hàng Tự Động</b>\n\n"
        f"📢 <b>Kênh Thông Báo:</b> {CHANNEL_URL}\n"
        f"👮‍♂️ <b>Admin:</b> {ADMIN_CONTACT}\n"
        "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"💸 <b>Tổng nạp:</b> {u['total_deposit']:,}đ\n"
        f"💰 <b>Số dư:</b> {u['balance']:,}đ\n"
        f"🎁 <b>Lượt lấy Key Free hôm nay:</b> {remaining}/{DAILY_FREE_LIMIT}\n"
    )

    keyboard = [
        [InlineKeyboardButton("🔑 LẤY KEY (MIỄN PHÍ)", callback_data='menu_getkey')],
        [InlineKeyboardButton("🛒 Cửa hàng mua Key", callback_data='menu_shop'),
         InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_deposit')],
        [InlineKeyboardButton("📖 Hướng dẫn sử dụng", callback_data='menu_guide')],
        [InlineKeyboardButton("👤 Tài khoản", callback_data='menu_account'),
         InlineKeyboardButton("🧾 Lịch sử", callback_data='menu_history')],
        [InlineKeyboardButton("🐸 Hỗ trợ / Liên hệ Admin", url=SUPPORT_CONTACT)],
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛡️ ADMIN PANEL", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.message:
            await update.message.reply_photo(photo=BANNER_URL, caption=text, reply_markup=reply_markup, parse_mode="HTML")
        elif update.callback_query:
            await update.callback_query.message.delete()
            await context.bot.send_photo(chat_id=user_id, photo=BANNER_URL, caption=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        elif update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)
    await get_or_create_user(user_id)

    if not await is_bot_active() and user_id != ADMIN_ID:
        await update.message.reply_text("🔴 Bot đang bảo trì. Vui lòng quay lại sau.")
        return

    if user_id not in user_states:
        user_states[user_id] = {'type': None, 'step': 0, 'token': None}

    if context.args:
        arg = context.args[0]
        try:
            parts = arg.split("_")
            key_type = parts[0]
            step_num = int(parts[1].replace("step", ""))
            received_token = parts[2] if len(parts) > 2 else None
            current_state = user_states.get(user_id, {})

            if current_state.get('type') == key_type and current_state.get('step') == step_num - 1:
                if received_token != current_state.get('token'):
                    await update.message.reply_text("⚠️ <b>PHÁT HIỆN GIAN LẬN!</b>", parse_mode="HTML")
                    user_states[user_id] = {'type': None, 'step': 0, 'token': None}
                    return

                user_states[user_id]['step'] = step_num

                if key_type == "1h":
                    if step_num == 1:
                        await process_step(update, key_type, 2, 2, 'yeumoney')
                    elif step_num == 2:
                        await deliver_free_key(update, context, '1h')
                elif key_type == "3h":
                    if step_num == 1:
                        await process_step(update, key_type, 2, 4, 'shrinkme')
                    elif step_num == 2:
                        await process_step(update, key_type, 3, 4, 'link4m')
                    elif step_num == 3:
                        await process_step(update, key_type, 4, 4, 'shrinkme')
                    elif step_num == 4:
                        await deliver_free_key(update, context, '3h')
                return
        except Exception:
            pass

    await show_main_menu(update, context)


async def process_step(update, key_type, current_step, total_steps, provider):
    new_token = generate_token()
    user_states[update.effective_user.id]['token'] = new_token
    target_url = f"https://t.me/{BOT_USERNAME}?start={key_type}_step{current_step}_{new_token}"

    short_url, p_name = await create_short_link(target_url, provider)

    if short_url:
        keyboard = [[InlineKeyboardButton(f"🚀 VƯỢT LINK {current_step}/{total_steps} ({p_name})", url=short_url)]]
        text = f"🔄 <b>TIẾN TRÌNH: {current_step}/{total_steps}</b>\nNhà tài trợ: <b>{p_name}</b>\n\n👉 Bấm nút bên dưới để tiếp tục."
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Lỗi tạo link {p_name}. Vui lòng thử lại!")


async def deliver_free_key(update: Update, context: ContextTypes.DEFAULT_TYPE, key_type: str):
    user_id = update.effective_user.id
    db_type = f"free_{key_type}"
    duration = 1 if key_type == "1h" else 3

    key = await get_available_key(db_type)
    if not key:
        await update.message.reply_text(
            f"❌ <b>KHO KEY FREE {key_type.upper()} ĐÃ CẠN!</b>\nVui lòng mua Key tại cửa hàng.",
            parse_mode="HTML"
        )
    else:
        await sell_key(key["id"], user_id, duration)
        await set_cooldown(user_id, key_type, 3600 if key_type == "1h" else 10800)
        await add_daily_usage(user_id)

        text = (
            f"🎉 <b>VƯỢT LINK THÀNH CÔNG!</b> 🎉\n"
            f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
            f"🔑 <b>Key:</b> <code>{key['key_code']}</code>\n"
            f"🔒 <b>Pass:</b> <tg-spoiler>{key['password'] or 'Không có'}</tg-spoiler>\n"
            f"⏳ Hết hạn sau: <b>{duration} giờ</b>\n"
            f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
            f"⏳ <i>Chờ {key_type.upper()} để lấy tiếp.</i>"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    user_states[user_id] = {'type': None, 'step': 0, 'token': None}


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if not await is_bot_active() and user_id != ADMIN_ID:
        await query.message.edit_text("🔴 Bot đang bảo trì.")
        return

    u = await get_or_create_user(user_id)

    if query.data == 'back_menu':
        await show_main_menu(update, context)
        return

    # --- HƯỚNG DẪN ---
    if query.data == 'menu_guide':
        text = (
            "📖 <b>HƯỚNG DẪN SỬ DỤNG BOT</b>\n"
            "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n\n"
            "1️⃣ <b>LẤY KEY MIỄN PHÍ:</b>\n"
            "👉 Bấm <b>'🔑 LẤY KEY'</b> → Chọn 1H hoặc 3H → Vượt link để nhận Key.\n"
            f"⚠️ Mỗi ngày tối đa {DAILY_FREE_LIMIT} lần.\n\n"
            "2️⃣ <b>MUA KEY:</b>\n"
            "👉 Nạp tiền → Vào Cửa hàng → Chọn loại Key.\n\n"
            "3️⃣ <b>LIÊN HỆ:</b> Bấm nút Hỗ trợ nếu cần Admin."
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Quay lại Menu", callback_data='back_menu')]
        ]), parse_mode="HTML")
        return

    # --- LẤY KEY FREE ---
    if query.data == 'menu_getkey':
        can_get, remaining = await check_daily_limit(user_id, DAILY_FREE_LIMIT)
        if not can_get:
            await query.message.edit_text(
                f"🚫 <b>BẠN ĐÃ HẾT {DAILY_FREE_LIMIT} LƯỢT LẤY KEY MIỄN PHÍ HÔM NAY!</b>\nVui lòng mua Key tại Cửa hàng.",
                parse_mode="HTML"
            )
            return

        keyboard = [
            [InlineKeyboardButton("🔑 KEY 1H (2 LINK YEU MONEY)", callback_data='get_1h')],
            [InlineKeyboardButton("💎 KEY 3H (4 LINK XEN KẼ)", callback_data='get_3h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]
        await query.message.edit_text(
            f"👇 Bạn còn <b>{remaining}/{DAILY_FREE_LIMIT}</b> lượt lấy Key miễn phí hôm nay.\nChọn loại Key muốn lấy:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    if query.data.startswith('get_'):
        can_get, _ = await check_daily_limit(user_id, DAILY_FREE_LIMIT)
        if not can_get:
            await query.message.edit_text("🚫 <b>BẠN ĐÃ HẾT LƯỢT HÔM NAY!</b>", parse_mode="HTML")
            return

        key_type = query.data.split('_')[1]
        can_cd, time_left = await check_cooldown(user_id, key_type)
        if not can_cd:
            await query.message.edit_text(
                f"🚫 <b>ĐANG TRONG THỜI GIAN CHỜ!</b>\nVui lòng quay lại sau: <b>{time_left}</b>",
                parse_mode="HTML"
            )
            return

        token = generate_token()
        user_states[user_id] = {'type': key_type, 'step': 0, 'token': token}

        if key_type == '1h':
            url, _ = await create_short_link(f"https://t.me/{BOT_USERNAME}?start=1h_step1_{token}", "yeumoney")
            if url:
                await query.message.edit_text(
                    "🔄 <b>TIẾN TRÌNH 1/2 (YeuMoney)</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK", url=url)]]),
                    parse_mode="HTML"
                )
        elif key_type == '3h':
            url, _ = await create_short_link(f"https://t.me/{BOT_USERNAME}?start=3h_step1_{token}", "link4m")
            if url:
                await query.message.edit_text(
                    "🔄 <b>TIẾN TRÌNH 1/4 (Link4m)</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 VƯỢT LINK", url=url)]]),
                    parse_mode="HTML"
                )
        return

    # --- CỬA HÀNG ---
    if query.data == 'menu_shop':
        text = (
            "🛒 <b>CỬA HÀNG BÁN KEY</b>\n"
            f"💰 Số dư của bạn: <b>{u['balance']:,}đ</b>\n"
            "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"
            f"🔑 Key 1H: <b>{PRICE_SHOP_1H:,}đ</b>\n"
            f"⏳ Key 12H: <b>{PRICE_SHOP_12H:,}đ</b>\n"
            f"📅 Key 1 Ngày: <b>{PRICE_SHOP_1D:,}đ</b>\n"
            f"📆 Key 1 Tháng: <b>{PRICE_SHOP_1M:,}đ</b>"
        )
        keyboard = [
            [InlineKeyboardButton("Mua 1H", callback_data='buy_1h'),
             InlineKeyboardButton("Mua 12H", callback_data='buy_12h')],
            [InlineKeyboardButton("Mua 1 Ngày", callback_data='buy_1d'),
             InlineKeyboardButton("Mua 1 Tháng", callback_data='buy_1m')],
            [InlineKeyboardButton("💳 Nạp thêm tiền", callback_data='menu_deposit')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    if query.data.startswith('buy_'):
        mapping = {
            '1h': ('shop_1h', PRICE_SHOP_1H, 1),
            '12h': ('shop_12h', PRICE_SHOP_12H, 12),
            '1d': ('shop_1d', PRICE_SHOP_1D, 24),
            '1m': ('shop_1m', PRICE_SHOP_1M, 720),
        }
        short = query.data.split('_')[1]
        db_type, price, hours = mapping[short]

        if u['balance'] < price:
            await query.message.edit_text("❌ <b>SỐ DƯ KHÔNG ĐỦ!</b>\nVui lòng nạp thêm tiền.", parse_mode="HTML")
            return

        key = await get_available_key(db_type)
        if not key:
            await query.message.edit_text(f"❌ <b>KHO KEY {short.upper()} ĐÃ HẾT HÀNG!</b>", parse_mode="HTML")
            return

        await update_balance(user_id, -price, "buy", f"Mua Key {short.upper()}", key["id"])
        await sell_key(key["id"], user_id, hours)

        text = (
            f"✅ <b>MUA THÀNH CÔNG!</b>\n"
            f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
            f"🔑 <b>Key:</b> <code>{key['key_code']}</code>\n"
            f"🔒 <b>Pass:</b> <tg-spoiler>{key['password'] or 'Không có'}</tg-spoiler>\n"
            f"⏳ Hết hạn sau: <b>{hours} giờ</b>\n"
            f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
            f"💰 Số dư còn: <b>{u['balance'] - price:,}đ</b>"
        )
        await query.message.edit_text(text, parse_mode="HTML")
        return

    # --- NẠP TIỀN ---
    if query.data == 'menu_deposit':
        add_info = f"NAP {user_id}"
        qr_url = (
            f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png"
            f"?addInfo={add_info.replace(' ', '%20')}&accountName={ACCOUNT_NAME.replace(' ', '%20')}"
        )
        text = (
            "💳 <b>NẠP TIỀN TỰ ĐỘNG</b>\n"
            "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰\n"
            f"🏦 <b>Ngân hàng:</b> {BANK_ID}\n"
            f"🔢 <b>STK:</b> <code>{ACCOUNT_NO}</code>\n"
            f"👤 <b>Chủ TK:</b> {ACCOUNT_NAME}\n"
            f"📝 <b>Nội dung CK:</b> <code>{add_info}</code>\n\n"
            "👉 Quét mã QR bên dưới để nạp tiền.\n"
            "⚠️ Tiền sẽ được cộng tự động sau 1-2 phút."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]]
        try:
            await query.message.delete()
            await context.bot.send_photo(chat_id=user_id, photo=qr_url, caption=text,
                                         reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except Exception:
            await context.bot.send_message(chat_id=user_id, text=text,
                                           reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # --- TÀI KHOẢN & LỊCH SỬ ---
    if query.data == 'menu_account':
        can_get, remaining = await check_daily_limit(user_id, DAILY_FREE_LIMIT)
        text = (
            f"👤 <b>TÀI KHOẢN</b>\n"
            f"ID: <code>{user_id}</code>\n"
            f"Số dư: <b>{u['balance']:,}đ</b>\n"
            f"Tổng nạp: <b>{u['total_deposit']:,}đ</b>\n"
            f"Lượt Free còn lại: <b>{remaining}/{DAILY_FREE_LIMIT}</b>"
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]), parse_mode="HTML")
        return

    if query.data == 'menu_history':
        hist = await get_user_history(user_id)
        hist_text = "\n".join(hist) if hist else "Chưa có giao dịch nào."
        text = f"🧾 <b>LỊCH SỬ GIAO DỊCH</b>\n\n{hist_text}"
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='back_menu')]
        ]), parse_mode="HTML")
        return

    # ==========================================
    # ADMIN PANEL
    # ==========================================
    if query.data == 'admin_panel':
        if user_id != ADMIN_ID:
            return
        active = await is_bot_active()
        status = "🟢 ONLINE" if active else "🔴 MAINTENANCE"
        keyboard = [
            [InlineKeyboardButton(f"⚙️ BOT: {status}", callback_data='admin_toggle')],
            [InlineKeyboardButton("📊 Thống kê", callback_data='admin_stats')],
            [InlineKeyboardButton("➕ Thêm Key FREE", callback_data='admin_add_free_menu'),
             InlineKeyboardButton("🛒 Thêm Key SHOP", callback_data='admin_add_shop_menu')],
            [InlineKeyboardButton("🎲 Tạo Key Random (Free)", callback_data='admin_rand_menu')],
            [InlineKeyboardButton("💸 Cộng tiền cho User", callback_data='admin_add_balance')],
            [InlineKeyboardButton("📢 Gửi thông báo", callback_data='admin_broadcast')],
            [InlineKeyboardButton("⬅️ Về Menu", callback_data='back_menu')]
        ]
        await query.message.edit_text("🛡️ <b>BẢNG ĐIỀU KHIỂN ADMIN</b>",
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    if query.data == 'admin_toggle':
        if user_id != ADMIN_ID:
            return
        current = await is_bot_active()
        await set_bot_active(not current)
        await button_handler(update, context)
        return

    if query.data == 'admin_stats':
        if user_id != ADMIN_ID:
            return
        stats = await get_admin_stats()
        keys_text = "\n".join([f"• {k}: <b>{v}</b>" for k, v in stats["keys"].items()]) or "Không còn key"
        text = (
            "📊 <b>THỐNG KÊ HỆ THỐNG</b>\n\n"
            f"👥 Tổng user: <b>{stats['total_users']}</b>\n"
            f"💰 Nạp hôm nay: <b>{stats['deposit_today']:,}đ</b>\n"
            f"📅 Nạp tháng này: <b>{stats['deposit_month']:,}đ</b>\n\n"
            f"🔑 <b>Key còn lại:</b>\n{keys_text}"
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]), parse_mode="HTML")
        return

    if query.data == 'admin_add_balance':
        if user_id != ADMIN_ID:
            return
        admin_adding_state[user_id] = 'add_balance'
        await query.message.edit_text("Nhập ID và Số tiền (VD: `7976468365 50000`):")
        return

    if query.data == 'admin_broadcast':
        if user_id != ADMIN_ID:
            return
        admin_adding_state[user_id] = 'broadcast'
        await query.message.edit_text("Nhập nội dung thông báo gửi đến toàn bộ người dùng:")
        return

    if query.data == 'admin_add_free_menu':
        if user_id != ADMIN_ID:
            return
        keyboard = [
            [InlineKeyboardButton("Thêm Kho Free 1H", callback_data='add_free_1h')],
            [InlineKeyboardButton("Thêm Kho Free 3H", callback_data='add_free_3h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho Free để thêm Key:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if query.data == 'admin_add_shop_menu':
        if user_id != ADMIN_ID:
            return
        keyboard = [
            [InlineKeyboardButton("Thêm Kho Shop 1H", callback_data='add_shop_1h')],
            [InlineKeyboardButton("Thêm Kho Shop 12H", callback_data='add_shop_12h')],
            [InlineKeyboardButton("Thêm Kho Shop 1 Ngày", callback_data='add_shop_1d')],
            [InlineKeyboardButton("Thêm Kho Shop 1 Tháng", callback_data='add_shop_1m')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho Shop để thêm Key:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if query.data.startswith('add_free_') or query.data.startswith('add_shop_'):
        if user_id != ADMIN_ID:
            return
        parts = query.data.split('_')
        k_type = f"{parts[1]}_{parts[2]}"
        admin_adding_state[user_id] = f'add_{k_type}'
        await query.message.edit_text(
            "📝 Hãy dán danh sách Key vào chat.\n"
            "Hỗ trợ format:\n"
            "Key: XXXXX\nMật khẩu: YYYYY\n\n"
            "Hoặc mỗi key một dòng."
        )
        return

    if query.data == 'admin_rand_menu':
        if user_id != ADMIN_ID:
            return
        keyboard = [
            [InlineKeyboardButton("Tạo Random Free 1H", callback_data='rand_free_1h')],
            [InlineKeyboardButton("Tạo Random Free 3H", callback_data='rand_free_3h')],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data='admin_panel')]
        ]
        await query.message.edit_text("Chọn kho để tạo Key tự động:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if query.data.startswith('rand_'):
        if user_id != ADMIN_ID:
            return
        parts = query.data.split('_')
        k_type = f"{parts[1]}_{parts[2]}"
        admin_adding_state[user_id] = f'rand_{k_type}'
        await query.message.edit_text("🎲 Nhập số lượng Key muốn tạo:")
        return


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID or user_id not in admin_adding_state:
        return

    state = admin_adding_state[user_id]
    text = update.message.text

    if state == 'add_balance':
        try:
            target_id, amount = text.split()
            amount = int(amount)
            target_id = int(target_id)
            await update_balance(target_id, amount, "admin_add", "Admin cộng tiền")
            await update.message.reply_text(f"✅ Đã cộng {amount:,}đ cho ID {target_id}.")
            try:
                await context.bot.send_message(target_id, f"💰 Bạn vừa được Admin cộng {amount:,}đ vào số dư!")
            except:
                pass
        except:
            await update.message.reply_text("❌ Sai cú pháp.")
        del admin_adding_state[user_id]
        return

    if state == 'broadcast':
        await update.message.reply_text("⏳ Đang gửi thông báo...")
        success = 0
        for uid in list(all_users):
            try:
                await context.bot.send_message(uid, f"📢 <b>THÔNG BÁO TỪ ADMIN</b>\n\n{html.escape(text)}", parse_mode="HTML")
                success += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await update.message.reply_text(f"✅ Đã gửi đến {success} người dùng.")
        del admin_adding_state[user_id]
        return

    if state.startswith('add_'):
        duration_map = {
            'add_free_1h': (1, 'free_1h'),
            'add_free_3h': (3, 'free_3h'),
            'add_shop_1h': (1, 'shop_1h'),
            'add_shop_12h': (12, 'shop_12h'),
            'add_shop_1d': (24, 'shop_1d'),
            'add_shop_1m': (720, 'shop_1m'),
        }
        hours, db_type = duration_map.get(state, (1, 'free_1h'))

        keys = []
        matches = re.findall(r"Key:\s*([^\n]+)\s*\n.*?Mật khẩu:\s*([^\n]+)", text, re.IGNORECASE)
        if matches:
            for k, p in matches:
                keys.append({"key_code": k.strip(), "password": p.strip()})
        else:
            for line in text.strip().splitlines():
                line = line.strip()
                if line:
                    keys.append({"key_code": line, "password": None})

        if keys:
            added = await add_keys(keys, db_type, hours)
            await update.message.reply_text(f"✅ Đã thêm {added} Key vào kho <b>{db_type}</b>!", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Không tìm thấy Key hợp lệ.")
        del admin_adding_state[user_id]
        return

    if state.startswith('rand_'):
        duration_map = {
            'rand_free_1h': (1, 'free_1h'),
            'rand_free_3h': (3, 'free_3h'),
        }
        hours, db_type = duration_map.get(state, (1, 'free_1h'))
        try:
            sl = int(text.strip())
            keys = [generate_random_key() for _ in range(sl)]
            added = await add_keys(keys, db_type, hours)
            await update.message.reply_text(f"✅ Đã tạo {added} Key Random thành công!")
        except:
            await update.message.reply_text("❌ Vui lòng nhập số.")
        del admin_adding_state[user_id]
        return