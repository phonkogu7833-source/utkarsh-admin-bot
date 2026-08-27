"""
❄️ UTKARSH VISUALS BOT ❄️
Telegram bot: balance top-up (crypto), admin approval, and Instagram
followers ordering through an SMM provider API.

Run:  python bot.py
Requires: python-telegram-bot>=20, requests
"""

import logging
import math

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import database as db
import smm_api

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("utkarsh_visuals_bot")

# ---------------------------------------------------------------- #
# Conversation states
# ---------------------------------------------------------------- #
ADD_AMOUNT, ADD_SCREENSHOT = range(2)
ORDER_LINK, ORDER_QTY = range(2, 4)

# ================================================================ #
# 𝐒𝐦𝐚𝐥𝐥-𝐜𝐚𝐩𝐬 / 𝐛𝐨𝐥𝐝 𝐮𝐧𝐢𝐜𝐨𝐝𝐞 𝐭𝐞𝐱𝐭 𝐡𝐞𝐥𝐩𝐞𝐫
# Converts plain ASCII text (typed dynamically, e.g. names, error text
# coming back from the SMM provider) into the same Mathematical Bold
# unicode style used across every static string in this bot, so the
# whole UI — including runtime values — always looks consistent.
# ================================================================ #

_BOLD_UPPER = "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"
_BOLD_LOWER = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
_BOLD_DIGIT = "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"


def bold(text: str) -> str:
    """Map plain ASCII → Mathematical Bold unicode (matches this bot's style)."""
    out = []
    for ch in str(text):
        if "A" <= ch <= "Z":
            out.append(_BOLD_UPPER[ord(ch) - ord("A")])
        elif "a" <= ch <= "z":
            out.append(_BOLD_LOWER[ord(ch) - ord("a")])
        elif "0" <= ch <= "9":
            out.append(_BOLD_DIGIT[ord(ch) - ord("0")])
        else:
            out.append(ch)
    return "".join(out)


# ================================================================ #
# UI helpers
# ================================================================ #

def main_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👤 𝐏𝐑𝐎𝐅𝐈𝐋𝐄", callback_data="profile"),
         InlineKeyboardButton("💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄", callback_data="balance")],
        [InlineKeyboardButton("💳 𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄", callback_data="addbalance"),
         InlineKeyboardButton("🚀 𝐎𝐑𝐃𝐄𝐑 𝐅𝐎𝐋𝐋𝐎𝐖𝐄𝐑𝐒", callback_data="order")],
        [InlineKeyboardButton("📦 𝐌𝐘 𝐎𝐑𝐃𝐄𝐑𝐒", callback_data="orders"),
         InlineKeyboardButton("⚙️ 𝐒𝐄𝐓𝐓𝐈𝐍𝐆𝐒", callback_data="settings")],
        [InlineKeyboardButton("👨‍💻 𝐃𝐌 𝐀𝐃𝐌𝐈𝐍", callback_data="dmadmin")],
    ]
    # 🎨 Icons above map every menu action to a distinct colourful emoji
    # (👤💰💳🚀📦⚙️👨‍💻) so each button stays instantly recognisable.
    return InlineKeyboardMarkup(rows)


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ 𝐁𝐀𝐂𝐊", callback_data="back")]])


def welcome_text(custom_id: str, balance: float) -> str:
    return (
        f"❄️ *{config.BRAND_NAME}* ❄️\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        f"👋 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐘𝐎𝐔𝐑 🚀 𝐃𝐈𝐆𝐈𝐓𝐀𝐋 𝐒𝐄𝐑𝐕𝐈𝐂𝐄 𝐏𝐀𝐍𝐄𝐋\n\n"
        f"👤 𝐀𝐂𝐂𝐎𝐔𝐍𝐓: 🟢 𝐀𝐂𝐓𝐈𝐕𝐄\n"
        f"🆔 𝐔𝐒𝐄𝐑 𝐈𝐃: `{custom_id}`\n"
        f"💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄: {config.CURRENCY_SYMBOL}{balance:,.2f}\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        "✨ 𝐂𝐇𝐎𝐎𝐒𝐄 𝐀𝐍 𝐎𝐏𝐓𝐈𝐎𝐍 𝐁𝐄𝐋𝐎𝐖 👇"
    )


async def show_main_menu(update_or_query, custom_id: str, balance: float, edit: bool = False):
    text = welcome_text(custom_id, balance)
    if edit:
        await update_or_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb()
        )
    else:
        await update_or_query.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb()
        )


# ================================================================ #
# /start and menu navigation
# ================================================================ #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = db.get_or_create_user(user.id, user.full_name, user.username or "")
    await show_main_menu(update.message, row["custom_id"], row["balance"])


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    row = db.get_user(query.from_user.id)
    await show_main_menu(query.message, row["custom_id"], row["balance"], edit=True)


async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    row = db.get_user(query.from_user.id)
    orders = db.get_user_orders(query.from_user.id, limit=1000)
    text = (
        "👤 *𝐌𝐘 𝐏𝐑𝐎𝐅𝐈𝐋𝐄*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        f"📛 𝐍𝐀𝐌𝐄: {bold(row['name'])}\n"
        f"🆔 𝐔𝐒𝐄𝐑 𝐈𝐃: `{row['custom_id']}`\n"
        f"💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄: {config.CURRENCY_SYMBOL}{row['balance']:,.2f}\n"
        f"📦 𝐓𝐎𝐓𝐀𝐋 𝐎𝐑𝐃𝐄𝐑𝐒: {len(orders)}\n"
        f"🟢 𝐒𝐓𝐀𝐓𝐔𝐒: 𝐀𝐂𝐓𝐈𝐕𝐄\n"
        f"📅 𝐉𝐎𝐈𝐍𝐄𝐃: {row['created_at'][:10]}"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())


async def balance_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    row = db.get_user(query.from_user.id)
    text = (
        "💰 *𝐌𝐘 𝐁𝐀𝐋𝐀𝐍𝐂𝐄*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        f"💵 𝐂𝐔𝐑𝐑𝐄𝐍𝐓 𝐁𝐀𝐋𝐀𝐍𝐂𝐄: {config.CURRENCY_SYMBOL}{row['balance']:,.2f}\n"
        "✨ 𝐖𝐀𝐋𝐋𝐄𝐓 𝐒𝐓𝐀𝐓𝐔𝐒: 🟢 𝐎𝐊\n\n"
        "🔔 𝐓𝐚𝐩 💳 *𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄* 𝐟𝐫𝐨𝐦 𝐭𝐡𝐞 𝐦𝐞𝐧𝐮 𝐭𝐨 𝐭𝐨𝐩 𝐮𝐩 ⚡"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())


async def orders_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rows = db.get_user_orders(query.from_user.id, limit=10)
    if not rows:
        text = "📦 *𝐌𝐘 𝐎𝐑𝐃𝐄𝐑𝐒*\n━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n📭 𝐍𝐨 𝐨𝐫𝐝𝐞𝐫𝐬 𝐲𝐞𝐭."
    else:
        lines = ["📦 *𝐌𝐘 𝐎𝐑𝐃𝐄𝐑𝐒*", "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━"]
        status_emoji = {"pending": "🟡", "processing": "🔵", "completed": "🟢", "failed": "🔴"}
        for o in rows:
            emo = status_emoji.get(o["status"], "⚪")
            lines.append(
                f"{emo} 🆔 #{o['order_id']} 🔗 {o['quantity']} 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐫𝐬 💰 "
                f"{config.CURRENCY_SYMBOL}{o['amount']:,.2f} 📊 {bold(o['status'].upper())}"
            )
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())


async def settings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "⚙️ *𝐒𝐄𝐓𝐓𝐈𝐍𝐆𝐒*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        "🔔 𝐍𝐨𝐭𝐢𝐟𝐢𝐜𝐚𝐭𝐢𝐨𝐧𝐬: 🟢 𝐎𝐍\n"
        "🌐 𝐋𝐚𝐧𝐠𝐮𝐚𝐠𝐞: 🇬🇧 𝐄𝐍𝐆𝐋𝐈𝐒𝐇 / 🇮🇳 𝐇𝐈𝐍𝐃𝐈\n"
        "🔒 𝐒𝐞𝐜𝐮𝐫𝐢𝐭𝐲: 🟢 𝐏𝐑𝐎𝐓𝐄𝐂𝐓𝐄𝐃\n\n"
        "✉️ 𝐅𝐨𝐫 𝐚𝐧𝐲 𝐜𝐡𝐚𝐧𝐠𝐞𝐬, 𝐩𝐥𝐞𝐚𝐬𝐞 👨‍💻 𝐃𝐌 𝐭𝐡𝐞 𝐚𝐝𝐦𝐢𝐧."
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())


async def dmadmin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "👨‍💻 *𝐂𝐎𝐍𝐓𝐀𝐂𝐓 𝐒𝐔𝐏𝐏𝐎𝐑𝐓*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        "💬 𝐉𝐮𝐬𝐭 𝐬𝐞𝐧𝐝 𝐲𝐨𝐮𝐫 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐡𝐞𝐫𝐞 𝐚𝐧𝐝 𝐨𝐮𝐫 𝐭𝐞𝐚𝐦 𝐰𝐢𝐥𝐥 𝐫𝐞𝐩𝐥𝐲 𝐬𝐨𝐨𝐧 ⏳\n"
        "📩 𝐎𝐫 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 @𝐘𝐨𝐮𝐫𝐀𝐝𝐦𝐢𝐧𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞 𝐝𝐢𝐫𝐞𝐜𝐭𝐥𝐲 🚀"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())


# ================================================================ #
# ADD BALANCE conversation
# ================================================================ #

async def addbalance_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "💳 *𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        f"✏️ 𝐄𝐧𝐭𝐞𝐫 𝐭𝐡𝐞 𝐚𝐦𝐨𝐮𝐧𝐭 ({config.CURRENCY_SYMBOL}) 𝐲𝐨𝐮 𝐰𝐚𝐧𝐭 𝐭𝐨 𝐚𝐝𝐝 👇\n"
        "🚫 𝐒𝐞𝐧𝐝 /cancel 𝐭𝐨 𝐬𝐭𝐨𝐩."
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return ADD_AMOUNT


async def addbalance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        amount = float(raw)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐞𝐧𝐭𝐞𝐫 𝐚 𝐯𝐚𝐥𝐢𝐝 𝐧𝐮𝐦𝐛𝐞𝐫, 𝐞.𝐠. 500")
        return ADD_AMOUNT

    context.user_data["pending_amount"] = amount
    w = config.WALLETS
    text = (
        "🧾 *𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐈𝐍𝐒𝐓𝐑𝐔𝐂𝐓𝐈𝐎𝐍𝐒*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        f"💰 𝐀𝐌𝐎𝐔𝐍𝐓: {config.CURRENCY_SYMBOL}{amount:,.2f}\n\n"
        "💠 𝐒𝐞𝐧𝐝 𝐔𝐒𝐃𝐓 𝐭𝐨 𝐚𝐧𝐲 𝐨𝐧𝐞 𝐨𝐟 𝐭𝐡𝐞 𝐧𝐞𝐭𝐰𝐨𝐫𝐤𝐬 𝐛𝐞𝐥𝐨𝐰 👇\n\n"
        f"🟡 *𝐁𝐄𝐏𝟐𝟎 (𝐁𝐒𝐂):*\n`{w['BEP20']}`\n\n"
        f"🔴 *𝐓𝐑𝐂𝟐𝟎 (𝐓𝐑𝐎𝐍):*\n`{w['TRC20']}`\n\n"
        f"🔵 *𝐄𝐑𝐂𝟐𝟎 (𝐄𝐭𝐡𝐞𝐫𝐞𝐮𝐦):*\n`{w['ERC20']}`\n\n"
        "📸 𝐀𝐟𝐭𝐞𝐫 𝐩𝐚𝐲𝐦𝐞𝐧𝐭, 𝐬𝐞𝐧𝐝 𝐚 𝐬𝐜𝐫𝐞𝐞𝐧𝐬𝐡𝐨𝐭 ✅ 𝐩𝐫𝐨𝐨𝐟 𝐡𝐞𝐫𝐞.\n"
        "🚫 𝐒𝐞𝐧𝐝 /cancel 𝐭𝐨 𝐬𝐭𝐨𝐩."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return ADD_SCREENSHOT


async def addbalance_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo and not update.message.document:
        await update.message.reply_text("📸 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐚 𝐩𝐡𝐨𝐭𝐨/𝐟𝐢𝐥𝐞 𝐨𝐟 𝐲𝐨𝐮𝐫 𝐩𝐚𝐲𝐦𝐞𝐧𝐭 𝐩𝐫𝐨𝐨𝐟 🧾")
        return ADD_SCREENSHOT

    file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
    amount = context.user_data.pop("pending_amount")
    user = update.effective_user
    row = db.get_user(user.id)

    payment_id = db.create_payment(user.id, amount, file_id)

    await update.message.reply_text(
        "✅ 𝐏𝐫𝐨𝐨𝐟 𝐫𝐞𝐜𝐞𝐢𝐯𝐞𝐝! 🙌 𝐘𝐨𝐮𝐫 𝐩𝐚𝐲𝐦𝐞𝐧𝐭 𝐢𝐬 𝐮𝐧𝐝𝐞𝐫 𝐫𝐞𝐯𝐢𝐞𝐰 🔍\n"
        "💰 𝐁𝐚𝐥𝐚𝐧𝐜𝐞 𝐰𝐢𝐥𝐥 𝐛𝐞 𝐚𝐝𝐝𝐞𝐝 𝐨𝐧𝐜𝐞 𝐚𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ⏳",
        reply_markup=main_menu_kb(),
    )

    admin_text = (
        "🔔 *𝐍𝐄𝐖 𝐏𝐀𝐘𝐌𝐄𝐍𝐓*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        f"👤 𝐍𝐀𝐌𝐄: {bold(row['name'])}\n"
        f"🆔 𝐔𝐒𝐄𝐑 𝐈𝐃: `{row['custom_id']}`\n"
        f"💰 𝐀𝐌𝐎𝐔𝐍𝐓: {config.CURRENCY_SYMBOL}{amount:,.2f}\n"
        "📸 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐏𝐑𝐎𝐎𝐅: ✅ 𝐀𝐓𝐓𝐀𝐂𝐇𝐄𝐃"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 𝐀𝐂𝐂𝐄𝐏𝐓", callback_data=f"acc_{payment_id}"),
        InlineKeyboardButton("❌ 𝐑𝐄𝐉𝐄𝐂𝐓", callback_data=f"rej_{payment_id}"),
    ]])

    for admin_id in config.ADMIN_IDS:
        try:
            sent = await context.bot.send_photo(
                chat_id=admin_id, photo=file_id, caption=admin_text,
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
            )
            db.set_payment_admin_msg(payment_id, sent.message_id)
        except Exception as e:
            log.warning("Could not notify admin %s: %s", admin_id, e)

    return ConversationHandler.END


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ 𝐂𝐚𝐧𝐜𝐞𝐥𝐥𝐞𝐝 🚫", reply_markup=main_menu_kb())
    return ConversationHandler.END


# ---- admin accept / reject ----

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in config.ADMIN_IDS:
        await query.answer("🚫 𝐍𝐨𝐭 𝐚𝐮𝐭𝐡𝐨𝐫𝐢𝐳𝐞𝐝.", show_alert=True)
        return

    action, payment_id_str = query.data.split("_", 1)
    payment_id = int(payment_id_str)
    payment = db.get_payment(payment_id)

    if payment is None:
        await query.edit_message_caption("⚠️ 𝐏𝐚𝐲𝐦𝐞𝐧𝐭 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝.")
        return

    if payment["status"] != "pending":
        await query.answer("𝐀𝐥𝐫𝐞𝐚𝐝𝐲 𝐩𝐫𝐨𝐜𝐞𝐬𝐬𝐞𝐝.", show_alert=True)
        return

    user_row = db.get_user(payment["telegram_id"])

    if action == "acc":
        db.set_payment_status(payment_id, "accepted")
        db.adjust_balance(payment["telegram_id"], payment["amount"])
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ *𝐀𝐂𝐂𝐄𝐏𝐓𝐄𝐃* 🎉",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            await context.bot.send_message(
                chat_id=payment["telegram_id"],
                text=(
                    "✅ *𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐀𝐂𝐂𝐄𝐏𝐓𝐄𝐃* 🎉\n"
                    "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
                    f"💰 {config.CURRENCY_SYMBOL}{payment['amount']:,.2f} 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐚𝐝𝐝𝐞𝐝 𝐭𝐨 𝐲𝐨𝐮𝐫 𝐛𝐚𝐥𝐚𝐧𝐜𝐞 💎\n"
                    "🚀 𝐘𝐨𝐮'𝐫𝐞 𝐫𝐞𝐚𝐝𝐲 𝐭𝐨 𝐨𝐫𝐝𝐞𝐫!"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            log.warning("Could not notify user %s: %s", payment["telegram_id"], e)
    else:
        db.set_payment_status(payment_id, "rejected")
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ *𝐑𝐄𝐉𝐄𝐂𝐓𝐄𝐃* 🚫",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            await context.bot.send_message(
                chat_id=payment["telegram_id"],
                text=(
                    "❌ *𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐑𝐄𝐉𝐄𝐂𝐓𝐄𝐃*\n"
                    "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
                    "👨‍💻 𝐏𝐥𝐞𝐚𝐬𝐞 𝐜𝐨𝐧𝐭𝐚𝐜𝐭 𝐬𝐮𝐩𝐩𝐨𝐫𝐭 𝐢𝐟 𝐭𝐡𝐢𝐬 𝐢𝐬 𝐚 𝐦𝐢𝐬𝐭𝐚𝐤𝐞 ⚠️"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            log.warning("Could not notify user %s: %s", payment["telegram_id"], e)


# ================================================================ #
# ORDER FOLLOWERS conversation
# ================================================================ #

async def order_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🚀 *𝐎𝐑𝐃𝐄𝐑 𝐅𝐎𝐋𝐋𝐎𝐖𝐄𝐑𝐒*\n"
        "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
        "🔗 𝐒𝐞𝐧𝐝 𝐲𝐨𝐮𝐫 📸 𝐈𝐧𝐬𝐭𝐚𝐠𝐫𝐚𝐦 𝐩𝐫𝐨𝐟𝐢𝐥𝐞 𝐥𝐢𝐧𝐤 👇\n"
        "🚫 𝐒𝐞𝐧𝐝 /cancel 𝐭𝐨 𝐬𝐭𝐨𝐩."
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return ORDER_LINK


async def order_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not link.startswith("http"):
        await update.message.reply_text("⚠️ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐚 𝐯𝐚𝐥𝐢𝐝 𝐥𝐢𝐧𝐤 🔗 (https://instagram.com/username)")
        return ORDER_LINK

    context.user_data["order_link"] = link
    text = (
        f"🔢 𝐇𝐨𝐰 𝐦𝐚𝐧𝐲 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐫𝐬? ✨ (𝐌𝐢𝐧 {bold(config.MIN_QUANTITY)}, 𝐌𝐚𝐱 {bold(config.MAX_QUANTITY)})\n"
        f"💵 𝐏𝐫𝐢𝐜𝐞: {config.CURRENCY_SYMBOL}{config.PRICE_PER_1000_INR} 𝐩𝐞𝐫 𝟏𝟎𝟎𝟎 📦"
    )
    await update.message.reply_text(text)
    return ORDER_QTY


async def order_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        quantity = int(raw)
    except ValueError:
        await update.message.reply_text("⚠️ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐞𝐧𝐭𝐞𝐫 𝐚 𝐰𝐡𝐨𝐥𝐞 𝐧𝐮𝐦𝐛𝐞𝐫, 𝐞.𝐠. 𝟏𝟎𝟎𝟎")
        return ORDER_QTY

    if not (config.MIN_QUANTITY <= quantity <= config.MAX_QUANTITY):
        await update.message.reply_text(
            f"⚠️ 𝐐𝐮𝐚𝐧𝐭𝐢𝐭𝐲 𝐦𝐮𝐬𝐭 𝐛𝐞 𝐛𝐞𝐭𝐰𝐞𝐞𝐧 {bold(config.MIN_QUANTITY)} 𝐚𝐧𝐝 {bold(config.MAX_QUANTITY)}."
        )
        return ORDER_QTY

    link = context.user_data.pop("order_link")
    amount = math.ceil((quantity / 1000) * config.PRICE_PER_1000_INR)
    user = update.effective_user
    row = db.get_user(user.id)

    if row["balance"] < amount:
        await update.message.reply_text(
            "🚫 *𝐈𝐍𝐒𝐔𝐅𝐅𝐈𝐂𝐈𝐄𝐍𝐓 𝐁𝐀𝐋𝐀𝐍𝐂𝐄*\n"
            "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
            f"💰 𝐑𝐞𝐪𝐮𝐢𝐫𝐞𝐝: {config.CURRENCY_SYMBOL}{amount:,.2f}\n"
            f"💵 𝐘𝐨𝐮𝐫 𝐛𝐚𝐥𝐚𝐧𝐜𝐞: {config.CURRENCY_SYMBOL}{row['balance']:,.2f}\n\n"
            "💳 𝐏𝐥𝐞𝐚𝐬𝐞 𝐚𝐝𝐝 𝐛𝐚𝐥𝐚𝐧𝐜𝐞 𝐟𝐢𝐫𝐬𝐭 ⚡",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb(),
        )
        return ConversationHandler.END

    # Deduct balance and record order first
    db.adjust_balance(user.id, -amount)
    order_id = db.create_order(user.id, link, quantity, amount)

    # Call the SMM provider
    result = smm_api.place_followers_order(link, quantity)

    if "order" in result:
        db.set_order_provider_id(order_id, str(result["order"]), status="processing")
        await update.message.reply_text(
            "✅ *𝐎𝐑𝐃𝐄𝐑 𝐏𝐋𝐀𝐂𝐄𝐃!* 🎉\n"
            "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
            f"🆔 𝐎𝐫𝐝𝐞𝐫 #{order_id}\n"
            f"🔗 {link}\n"
            f"🔢 {bold(quantity)} 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐫𝐬\n"
            f"💰 {config.CURRENCY_SYMBOL}{amount:,.2f} 𝐝𝐞𝐝𝐮𝐜𝐭𝐞𝐝\n"
            "📊 𝐒𝐭𝐚𝐭𝐮𝐬: 🔵 𝐏𝐑𝐎𝐂𝐄𝐒𝐒𝐈𝐍𝐆 ⚡",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb(),
        )
    else:
        # Provider failed — refund the user
        db.adjust_balance(user.id, amount)
        db.set_order_status(order_id, "failed")
        err = bold(result.get("error", "Unknown error"))
        await update.message.reply_text(
            "🔴 *𝐎𝐑𝐃𝐄𝐑 𝐅𝐀𝐈𝐋𝐄𝐃*\n"
            "━❰💎❱━━━━━❰💎❱━━━━━❰💎❱━\n"
            f"⚠️ {err}\n"
            "💰 𝐘𝐨𝐮𝐫 𝐛𝐚𝐥𝐚𝐧𝐜𝐞 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐫𝐞𝐟𝐮𝐧𝐝𝐞𝐝 ↩️\n"
            "👨‍💻 𝐏𝐥𝐞𝐚𝐬𝐞 𝐭𝐫𝐲 𝐚𝐠𝐚𝐢𝐧 𝐨𝐫 𝐜𝐨𝐧𝐭𝐚𝐜𝐭 𝐬𝐮𝐩𝐩𝐨𝐫𝐭.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb(),
        )

    return ConversationHandler.END


# ================================================================ #
# App wiring
# ================================================================ #

def build_app() -> Application:
    db.init_db()
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back$"))
    app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(balance_cb, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(orders_cb, pattern="^orders$"))
    app.add_handler(CallbackQueryHandler(settings_cb, pattern="^settings$"))
    app.add_handler(CallbackQueryHandler(dmadmin_cb, pattern="^dmadmin$"))
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(acc|rej)_\\d+$"))

    addbalance_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(addbalance_entry, pattern="^addbalance$")],
        states={
            ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbalance_amount)],
            ADD_SCREENSHOT: [MessageHandler((filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND, addbalance_screenshot)],
        },
        fallbacks=[CommandHandler("cancel", cance
