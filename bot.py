import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import sqlite3
import random
import string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB = "utkarsh.db"


# =========================
# DATABASE
# =========================

def db():
    return sqlite3.connect(DB)


def setup():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            user_code TEXT UNIQUE,
            name TEXT,
            balance REAL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            user_code TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            proof_file_id TEXT
        )
    """)

    con.commit()
    con.close()


def generate_user_code():
    con = db()
    cur = con.cursor()

    while True:
        code = str(random.randint(10000, 99999))
        cur.execute(
            "SELECT user_code FROM users WHERE user_code=?",
            (code,)
        )

        if not cur.fetchone():
            con.close()
            return code


def get_user(telegram_id):
    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT telegram_id, user_code, name, balance FROM users WHERE telegram_id=?",
        (telegram_id,)
    )

    user = cur.fetchone()
    con.close()

    return user


def create_user(telegram_id, name):
    existing = get_user(telegram_id)

    if existing:
        return existing

    code = generate_user_code()

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        INSERT INTO users
        (telegram_id, user_code, name, balance)
        VALUES (?, ?, ?, 0)
        """,
        (telegram_id, code, name)
    )

    con.commit()
    con.close()

    return get_user(telegram_id)


# =========================
# USER MENU
# =========================

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("👤 Profile", callback_data="profile"),
            InlineKeyboardButton("💰 Balance", callback_data="balance"),
        ],
        [
            InlineKeyboardButton("💳 Add Balance", callback_data="add_balance"),
        ],
        [
            InlineKeyboardButton("🛒 Order Followers", callback_data="followers"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    create_user(
        user.id,
        user.full_name
    )

    text = f"""
❄️ <b>UTKARSH VISUALS</b> ❄️

Welcome <b>{user.first_name}</b> 👋

🚀 Your digital service panel

👤 Account: Active
🆔 User ID: Automatic
💰 Balance: Check below

Choose an option:
"""

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================
# PROFILE
# =========================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = get_user(query.from_user.id)

    if not user:
        create_user(
            query.from_user.id,
            query.from_user.full_name
        )
        user = get_user(query.from_user.id)

    telegram_id, user_code, name, balance = user

    text = f"""
👤 <b>PROFILE</b>

━━━━━━━━━━━━━━

👤 Name: <b>{name}</b>
🆔 User ID: <code>{user_code}</code>
💰 Balance: <b>${balance:.2f}</b>

━━━━━━━━━━━━━━
❄️ Utkarsh Visuals
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================
# BALANCE
# =========================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = get_user(query.from_user.id)

    if not user:
        user = create_user(
            query.from_user.id,
            query.from_user.full_name
        )

    amount = user[3]

    text = f"""
💰 <b>YOUR BALANCE</b>

━━━━━━━━━━━━━━

💵 Available Balance:
<b>${amount:.2f}</b>

━━━━━━━━━━━━━━

💳 Add balance whenever you need.
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================
# ADD BALANCE
# =========================

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    context.user_data["waiting_amount"] = True

    text = """
💳 <b>ADD BALANCE</b>

━━━━━━━━━━━━━━

Enter the amount you want to add.

Example:

<code>5</code>

or

<code>10</code>

After entering the amount, payment instructions will appear.
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML"
    )


# =========================
# AMOUNT MESSAGE
# =========================

async def amount_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_amount"):
        return

    try:
        amount = float(update.message.text)

        if amount <= 0:
            raise ValueError

    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid amount.\n\nExample: 5"
        )
        return

    context.user_data["waiting_amount"] = False
    context.user_data["payment_amount"] = amount

    text = f"""
💳 <b>PAYMENT REQUEST</b>

━━━━━━━━━━━━━━

💵 Amount:
<b>${amount:.2f}</b>

📲 Make your payment using the payment method provided by the administrator.

⚠️ After payment, send the payment screenshot here.

━━━━━━━━━━━━━━

📎 <b>Send Payment Proof</b>
"""

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================
# PAYMENT PROOF
# =========================

async def payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "payment_amount" not in context.user_data:
        return

    amount = context.user_data["payment_amount"]

    user = get_user(update.effective_user.id)

    if not user:
        user = create_user(
            update.effective_user.id,
            update.effective_user.full_name
        )

    telegram_id, user_code, name, balance = user

    photo = update.message.photo[-1]
    file_id = photo.file_id

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        INSERT INTO payments
        (telegram_id, user_code, amount, status, proof_file_id)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (
            telegram_id,
            user_code,
            amount,
            file_id
        )
    )

    payment_id = cur.lastrowid

    con.commit()
    con.close()

    context.user_data.pop("payment_amount", None)

    await update.message.reply_text(
        f"""
✅ <b>PAYMENT PROOF RECEIVED</b>

━━━━━━━━━━━━━━

🆔 User ID: <code>{user_code}</code>
💵 Amount: <b>${amount:.2f}</b>
📌 Status: <b>Pending</b>

Your payment is waiting for admin verification.

━━━━━━━━━━━━━━
""",
        parse_mode="HTML"
    )

    # Send proof to admin

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ ACCEPT",
                callback_data=f"accept_{payment_id}"
            ),
            InlineKeyboardButton(
                "❌ REJECT",
                callback_data=f"reject_{payment_id}"
            )
        ]
    ]

    admin_text = f"""
💳 <b>NEW PAYMENT REQUEST</b>

━━━━━━━━━━━━━━

👤 Name: <b>{name}</b>
🆔 User ID: <code>{user_code}</code>
💵 Amount: <b>${amount:.2f}</b>

📌 Payment ID: <code>{payment_id}</code>

Status: 🟡 <b>PENDING</b>

━━━━━━━━━━━━━━
"""

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=admin_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ADMIN ACCEPT / REJECT
# =========================

async def payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )
        return

    action, payment_id = query.data.split("_")
    payment_id = int(payment_id)

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT telegram_id, user_code, amount, status
        FROM payments
        WHERE id=?
        """,
        (payment_id,)
    )

    payment = cur.fetchone()

    if not payment:
        con.close()

        await query.answer(
            "Payment not found.",
            show_alert=True
        )
        return

    telegram_id, user_code, amount, status = payment

    if status != "pending":
        con.close()

        await query.answer(
            "This payment was already processed.",
            show_alert=True
        )
        return

    # ACCEPT

    if action == "accept":

        cur.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE telegram_id=?
            """,
            (amount, telegram_id)
        )

        cur.execute(
            """
            UPDATE payments
            SET status='accepted'
            WHERE id=?
            """,
            (payment_id,)
        )

        con.commit()
        con.close()

        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"""
✅ <b>PAYMENT ACCEPTED</b>

━━━━━━━━━━━━━━

🆔 User ID: <code>{user_code}</code>
💵 Added: <b>${amount:.2f}</b>

💰 Your balance has been credited successfully.

You can now use your balance for available services.

━━━━━━━━━━━━━━
❄️ Utkarsh Visuals
""",
            parse_mode="HTML"
        )

        await query.edit_message_caption(
            caption=f"""
✅ <b>PAYMENT ACCEPTED</b>

🆔 User ID: <code>{user_code}</code>
💵 Amount: <b>${amount:.2f}</b>
📌 Payment ID: <code>{payment_id}</code>

Balance credited successfully.
""",
            parse_mode="HTML"
        )

    # REJECT

    else:

        cur.execute(
            """
            UPDATE payments
            SET status='rejected'
            WHERE id=?
            """,
            (payment_id,)
        )

        con.commit()
        con.close()

        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"""
❌ <b>PAYMENT REJECTED</b>

━━━━━━━━━━━━━━

🆔 User ID: <code>{user_code}</code>
💵 Amount: <b>${amount:.2f}</b>

Your payment proof was rejected by the administrator.

Please contact the administrator if you believe this was a mistake.

━━━━━━━━━━━━━━
""",
            parse_mode="HTML"
        )

        await query.edit_message_caption(
            caption=f"""
❌ <b>PAYMENT REJECTED</b>

🆔 User ID: <code>{user_code}</code>
💵 Amount: <b>${amount:.2f}</b>
📌 Payment ID: <code>{payment_id}</code>
""",
            parse_mode="HTML"
        )


# =========================
# FOLLOWERS PLACEHOLDER
# =========================

async def followers(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = get_user(query.from_user.id)

    if not user:
        user = create_user(
            query.from_user.id,
            query.from_user.full_name
        )

    balance = user[3]

    text = f"""
🛒 <b>FOLLOWERS SERVICE</b>

━━━━━━━━━━━━━━

💰 Your Balance:
<b>${balance:.2f}</b>

━━━━━━━━━━━━━━

This section will be connected to the followers service system next.

The order system will check your balance before placing an order.
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")

    if ADMIN_ID == 0:
        raise RuntimeError("ADMIN_ID environment variable is missing.")

    setup()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(
            profile,
            pattern="^profile$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            balance,
            pattern="^balance$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            add_balance,
            pattern="^add_balance$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            followers,
            pattern="^followers$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            payment_action,
            pattern="^(accept|reject)_"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            payment_proof
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            amount_message
        )
    )

    print("Utkarsh Visuals Bot Started...")

    app.run_polling()


if __name__ == "__main__":
    main()
