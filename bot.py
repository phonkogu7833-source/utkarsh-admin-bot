import os
import sqlite3
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB = "utkarsh.db"


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Utkarsh Visuals Bot is running successfully!"
        )

    def log_message(self, format, *args):
        return


def run_health_server():

    port = int(os.environ.get("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"Health server running on port {port}")

    server.serve_forever()


# =========================================================
# DATABASE
# =========================================================

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
        """
        SELECT telegram_id, user_code, name, balance
        FROM users
        WHERE telegram_id=?
        """,
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
        (
            telegram_id,
            code,
            name
        )
    )

    con.commit()
    con.close()

    return get_user(telegram_id)


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "👤 PROFILE",
                callback_data="profile"
            ),
            InlineKeyboardButton(
                "💰 BALANCE",
                callback_data="balance"
            )
        ],

        [
            InlineKeyboardButton(
                "💳 ADD BALANCE",
                callback_data="add_balance"
            )
        ],

        [
            InlineKeyboardButton(
                "🛒 ORDER FOLLOWERS",
                callback_data="followers"
            )
        ],

        [
            InlineKeyboardButton(
                "📞 CONTACT ADMIN",
                url="https://t.me/utkarshvisuals"
            )
        ]

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    create_user(
        user.id,
        user.full_name
    )

    text = f"""
❄️ <b>UTKARSH VISUALS</b> ❄️

━━━━━━━━━━━━━━━━━━

👋 Welcome <b>{user.first_name}</b>

🚀 <b>Your Digital Service Panel</b>

👤 Account: 🟢 Active
🆔 User ID: Automatically Generated
💰 Balance: Check below

━━━━━━━━━━━━━━━━━━

✨ Choose an option below:
"""

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# PROFILE
# =========================================================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user = get_user(query.from_user.id)

    if not user:

        user = create_user(
            query.from_user.id,
            query.from_user.full_name
        )

    telegram_id, user_code, name, balance = user

    text = f"""
👤 <b>YOUR PROFILE</b>

━━━━━━━━━━━━━━━━━━

👤 Name:
<b>{name}</b>

🆔 User ID:
<code>{user_code}</code>

💰 Balance:
<b>${balance:.2f}</b>

━━━━━━━━━━━━━━━━━━

❄️ <b>UTKARSH VISUALS</b>
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# BALANCE
# =========================================================

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

━━━━━━━━━━━━━━━━━━

💵 Available Balance:

<b>${amount:.2f}</b>

━━━━━━━━━━━━━━━━━━

💳 Need more balance?

Use <b>ADD BALANCE</b> below.
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# ADD BALANCE
# =========================================================

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    context.user_data["waiting_amount"] = True

    text = """
💳 <b>ADD BALANCE</b>

━━━━━━━━━━━━━━━━━━

Enter the amount you want to add.

Example:

<code>5</code>

or

<code>10</code>

━━━━━━━━━━━━━━━━━━

After entering the amount,
payment instructions will appear.
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# AMOUNT MESSAGE
# =========================================================

async def amount_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_amount"):
        return

    if not update.message or not update.message.text:
        return

    try:

        amount = float(
            update.message.text.strip()
        )

        if amount <= 0:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            """
❌ <b>Invalid Amount</b>

Please enter a valid amount.

Example:

<code>5</code>
""",
            parse_mode="HTML"
        )

        return

    context.user_data["waiting_amount"] = False
    context.user_data["payment_amount"] = amount

    text = f"""
💳 <b>PAYMENT REQUEST</b>

━━━━━━━━━━━━━━━━━━

💵 Amount:
<b>${amount:.2f}</b>

━━━━━━━━━━━━━━━━━━

📲 Please make your payment using
the payment method provided by admin.

⚠️ After payment, send the
<b>payment screenshot</b> here.

━━━━━━━━━━━━━━━━━━

📸 <b>Send Payment Proof Now</b>
"""

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# PAYMENT PROOF
# =========================================================

async def payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "payment_amount" not in context.user_data:

        await update.message.reply_text(
            """
⚠️ Please select <b>ADD BALANCE</b>
first and enter the amount.
""",
            parse_mode="HTML"
        )

        return

    amount = context.user_data["payment_amount"]

    user = get_user(
        update.effective_user.id
    )

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

    context.user_data.pop(
        "payment_amount",
        None
    )

    await update.message.reply_text(
        f"""
✅ <b>PAYMENT PROOF RECEIVED</b>

━━━━━━━━━━━━━━━━━━

🆔 User ID:
<code>{user_code}</code>

💵 Amount:
<b>${amount:.2f}</b>

🆔 Payment ID:
<code>{payment_id}</code>

📌 Status:
🟡 <b>PENDING</b>

━━━━━━━━━━━━━━━━━━

Your payment is waiting for
admin verification.
""",
        parse_mode="HTML"
    )

    # ADMIN BUTTONS

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

━━━━━━━━━━━━━━━━━━

👤 Name:
<b>{name}</b>

🆔 User ID:
<code>{user_code}</code>

💵 Amount:
<b>${amount:.2f}</b>

🆔 Payment ID:
<code>{payment_id}</code>

📌 Status:
🟡 <b>PENDING</b>

━━━━━━━━━━━━━━━━━━

Choose an action:
"""

    try:

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=admin_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

    except Exception as e:

        print(
            "ADMIN NOTIFICATION ERROR:",
            e
        )


# =========================================================
# ADMIN PAYMENT ACTION
# =========================================================

async def payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    await query.answer()

    try:

        action, payment_id = query.data.split("_")

        payment_id = int(payment_id)

    except Exception:

        return

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
            "Already processed.",
            show_alert=True
        )

        return

    # =====================================================
    # ACCEPT
    # =====================================================

    if action == "accept":

        cur.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE telegram_id=?
            """,
            (
                amount,
                telegram_id
            )
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

        try:

            await context.bot.send_message(
                chat_id=telegram_id,
                text=f"""
✅ <b>PAYMENT ACCEPTED</b>

━━━━━━━━━━━━━━━━━━

🆔 User ID:
<code>{user_code}</code>

💵 Added:
<b>${amount:.2f}</b>

💰 Your balance has been
credited successfully.

━━━━━━━━━━━━━━━━━━

❄️ <b>UTKARSH VISUALS</b>
""",
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "USER NOTIFICATION ERROR:",
                e
            )

        try:

            await query.edit_message_caption(
                caption=f"""
✅ <b>PAYMENT ACCEPTED</b>

━━━━━━━━━━━━━━━━━━

🆔 User ID:
<code>{user_code}</code>

💵 Amount:
<b>${amount:.2f}</b>

🆔 Payment ID:
<code>{payment_id}</code>

📌 Status:
🟢 <b>ACCEPTED</b>

💰 Balance credited successfully.
""",
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "CAPTION UPDATE ERROR:",
                e
            )

    # =====================================================
    # REJECT
    # =====================================================

    elif action == "reject":

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

        try:

            await context.bot.send_message(
                chat_id=telegram_id,
                text=f"""
❌ <b>PAYMENT REJECTED</b>

━━━━━━━━━━━━━━━━━━

🆔 User ID:
<code>{user_code}</code>

💵 Amount:
<b>${amount:.2f}</b>

🆔 Payment ID:
<code>{payment_id}</code>

Your payment proof was rejected
by the administrator.

Please contact admin if you
believe this was a mistake.

━━━━━━━━━━━━━━━━━━
""",
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "USER NOTIFICATION ERROR:",
                e
            )

        try:

            await query.edit_message_caption(
                caption=f"""
❌ <b>PAYMENT REJECTED</b>

━━━━━━━━━━━━━━━━━━

🆔 User ID:
<code>{user_code}</code>

💵 Amount:
<b>${amount:.2f}</b>

🆔 Payment ID:
<code>{payment_id}</code>

📌 Status:
🔴 <b>REJECTED</b>
""",
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "CAPTION UPDATE ERROR:",
                e
            )


# =========================================================
# FOLLOWERS
# =========================================================

async def followers(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user = get_user(query.from_user.id)

    if not user:

        user = create_user(
            query.from_user.id,
            query.from_user.full_name
        )

    balance_amount = user[3]

    text = f"""
🛒 <b>FOLLOWERS SERVICE</b>

━━━━━━━━━━━━━━━━━━

💰 Your Balance:

<b>${balance_amount:.2f}</b>

━━━━━━━━━━━━━━━━━━

📱 <b>Instagram Followers</b>

100 Followers — $1
1K Followers — $10
2K Followers — $20
5K Followers — $50
10K Followers — $100

━━━━━━━━━━━━━━━━━━

⚡ Fast Processing
🔒 Secure Service
💎 Utkarsh Visuals

📞 Contact Admin:
@utkarshvisuals
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# HELP COMMAND
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        """
❄️ <b>UTKARSH VISUALS HELP</b>

━━━━━━━━━━━━━━━━━━

/start - Open main menu
/help - Help

💳 Add balance from the menu.
🛒 Order services from the menu.

📞 Admin:
@utkarshvisuals
""",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update, context):

    print(
        "BOT ERROR:",
        repr(context.error)
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print("Starting Utkarsh Visuals Bot...")

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    if ADMIN_ID == 0:

        raise RuntimeError(
            "ADMIN_ID environment variable is missing."
        )

    # Database
    setup()

    # Render health server
    health_thread = threading.Thread(
        target=run_health_server,
        daemon=True
    )

    health_thread.start()

    # Telegram application
    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    # Profile
    app.add_handler(
        CallbackQueryHandler(
            profile,
            pattern=r"^profile$"
        )
    )

    # Balance
    app.add_handler(
        CallbackQueryHandler(
            balance,
            pattern=r"^balance$"
        )
    )

    # Add balance
    app.add_handler(
        CallbackQueryHandler(
            add_balance,
            pattern=r"^add_balance$"
        )
    )

    # Followers
    app.add_handler(
        CallbackQueryHandler(
            followers,
            pattern=r"^followers$"
        )
    )

    # Accept / Reject
    app.add_handler(
        CallbackQueryHandler(
            payment_action,
            pattern=r"^(accept|reject)_\d+$"
        )
    )

    # Payment screenshot
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            payment_proof
        )
    )

    # Amount text
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            amount_message
        )
    )

    # Error handler
    app.add_error_handler(
        error_handler
    )

    print("================================")
    print("UTKARSH VISUALS BOT STARTED")
    print("================================")

    # Start Telegram polling
    app.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
