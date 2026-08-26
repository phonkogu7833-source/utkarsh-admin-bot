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
ADMIN_USERNAME = "utkarshvisuals"

# =========================================================
# PAYMENT DETAILS
# =========================================================

BEP20_ADDRESS = "0x56179b245007e87fff0c8cf3c7b0f46e13f3bfa8"
TRC20_ADDRESS = "TKHf38EBVhEWUrYREzAKVGzcAbsZtSiHjk"
ERC20_ADDRESS = "0x56179b245007e87fff0c8cf3c7b0f46e13f3bfa8"

# Put your INR UPI ID here
UPI_ID = os.getenv("UPI_ID", "YOUR-UPI-ID@upi")

# =========================================================
# HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"UTKARSH VISUALS BOT IS RUNNING!"
        )

    def log_message(self, format, *args):
        return


def run_health_server():

    port = int(os.environ.get("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"Health server running on {port}")

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
            currency TEXT DEFAULT 'USD',
            method TEXT,
            status TEXT DEFAULT 'pending',
            proof_file_id TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            user_code TEXT,
            service TEXT,
            quantity INTEGER,
            target TEXT,
            price REAL,
            status TEXT DEFAULT 'pending'
        )
    """)

    # Migration for old databases
    try:
        cur.execute(
            "ALTER TABLE payments ADD COLUMN currency TEXT DEFAULT 'USD'"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute(
            "ALTER TABLE payments ADD COLUMN method TEXT"
        )
    except sqlite3.OperationalError:
        pass

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
        (telegram_id, code, name)
    )

    con.commit()
    con.close()

    return get_user(telegram_id)


# =========================================================
# STYLE
# =========================================================

def title(text):
    return f"❄️ <b>𝐔𝐓𝐊𝐀𝐑𝐒𝐇 𝐕𝐈𝐒𝐔𝐀𝐋𝐒</b> ❄️\n\n<b>{text}</b>"


def divider():
    return "━━━━━━━━━━━━━━━━━━━━"


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "👤 𝐏𝐑𝐎𝐅𝐈𝐋𝐄",
                callback_data="profile"
            ),
            InlineKeyboardButton(
                "💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄",
                callback_data="balance"
            )
        ],

        [
            InlineKeyboardButton(
                "💳 𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄",
                callback_data="add_balance"
            )
        ],

        [
            InlineKeyboardButton(
                "🛒 𝐎𝐑𝐃𝐄𝐑 𝐅𝐎𝐋𝐋𝐎𝐖𝐄𝐑𝐒",
                callback_data="followers"
            )
        ],

        [
            InlineKeyboardButton(
                "💬 𝐃𝐌 𝐀𝐃𝐌𝐈𝐍",
                url=f"https://t.me/{ADMIN_USERNAME}"
            ),
            InlineKeyboardButton(
                "⚙️ 𝐒𝐄𝐓𝐓𝐈𝐍𝐆𝐒",
                callback_data="settings"
            )
        ]

    ]

    return InlineKeyboardMarkup(keyboard)


def back_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 𝐁𝐀𝐂𝐊",
                callback_data="home"
            )
        ]
    ])


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    account = create_user(
        user.id,
        user.full_name
    )

    balance_amount = account[3]

    text = f"""
{title("𝐃𝐈𝐆𝐈𝐓𝐀𝐋 𝐒𝐄𝐑𝐕𝐈𝐂𝐄 𝐏𝐀𝐍𝐄𝐋")}

👋 𝐇𝐄𝐋𝐋𝐎 <b>{user.first_name}</b>!

{divider()}

🚀 <b>𝐘𝐎𝐔𝐑 𝐀𝐂𝐂𝐎𝐔𝐍𝐓 𝐈𝐒 𝐑𝐄𝐀𝐃𝐘</b>

🟢 𝐀𝐂𝐂𝐎𝐔𝐍𝐓: <b>𝐀𝐂𝐓𝐈𝐕𝐄</b>
🆔 𝐔𝐒𝐄𝐑 𝐈𝐃: <code>{account[1]}</code>
💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄: <b>${balance_amount:.2f}</b>

{divider()}

✨ 𝐂𝐇𝐎𝐎𝐒𝐄 𝐀𝐍 𝐎𝐏𝐓𝐈𝐎𝐍 𝐁𝐄𝐋𝐎𝐖 👇
"""

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# HOME
# =========================================================

async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = get_user(query.from_user.id)

    if not user:
        user = create_user(
            query.from_user.id,
            query.from_user.full_name
        )

    text = f"""
{title("𝐌𝐀𝐈𝐍 𝐌𝐄𝐍𝐔")}

👋 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 <b>{query.from_user.first_name}</b>

🆔 𝐔𝐒𝐄𝐑 𝐈𝐃: <code>{user[1]}</code>
💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄: <b>${user[3]:.2f}</b>

{divider()}

✨ 𝐒𝐄𝐋𝐄𝐂𝐓 𝐅𝐑𝐎𝐌 𝐌𝐄𝐍𝐔 👇
"""

    await query.edit_message_text(
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

    _, code, name, balance = user

    text = f"""
{title("👤 𝐘𝐎𝐔𝐑 𝐏𝐑𝐎𝐅𝐈𝐋𝐄")}

{divider()}

👤 𝐍𝐀𝐌𝐄
<b>{name}</b>

🆔 𝐔𝐒𝐄𝐑 𝐈𝐃
<code>{code}</code>

💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄
<b>${balance:.2f}</b>

🟢 𝐒𝐓𝐀𝐓𝐔𝐒
<b>𝐀𝐂𝐓𝐈𝐕𝐄</b>

{divider()}

❄️ <b>𝐔𝐓𝐊𝐀𝐑𝐒𝐇 𝐕𝐈𝐒𝐔𝐀𝐋𝐒</b>
"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_menu()
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

    text = f"""
{title("💰 𝐘𝐎𝐔𝐑 𝐁𝐀𝐋𝐀𝐍𝐂𝐄")}

{divider()}

💵 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄
<b>${user[3]:.2f}</b>

{divider()}

💳 𝐍𝐄𝐄𝐃 𝐌𝐎𝐑𝐄 𝐁𝐀𝐋𝐀𝐍𝐂𝐄?

👇 𝐔𝐒𝐄 𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄
"""

    keyboard = [
        [
            InlineKeyboardButton(
                "💳 𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄",
                callback_data="add_balance"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 𝐁𝐀𝐂𝐊",
                callback_data="home"
            )
        ]
    ]

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# ADD BALANCE
# =========================================================

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    text = f"""
{title("💳 𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄")}

{divider()}

💵 𝐄𝐍𝐓𝐄𝐑 𝐀𝐌𝐎𝐔𝐍𝐓 𝐈𝐍 𝐔𝐒𝐃

Example:
<code>5</code>

<code>10</code>

<code>20</code>

{divider()}

🇺🇸 𝐌𝐈𝐍𝐈𝐌𝐔𝐌: <b>$1</b>

✍️ 𝐒𝐄𝐍𝐃 𝐓𝐇𝐄 𝐀𝐌𝐎𝐔𝐍𝐓 𝐍𝐎𝐖.
"""

    context.user_data["waiting_amount"] = True

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_menu()
    )


# =========================================================
# PAYMENT METHODS
# =========================================================

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    amount = context.user_data.get("payment_amount")

    if not amount:
        await query.answer(
            "Please enter amount first.",
            show_alert=True
        )
        return

    text = f"""
{title("💳 𝐒𝐄𝐋𝐄𝐂𝐓 𝐏𝐀𝐘𝐌𝐄𝐍𝐓")}

{divider()}

💵 𝐀𝐌𝐎𝐔𝐍𝐓
<b>${amount:.2f}</b>

{divider()}

👇 𝐂𝐇𝐎𝐎𝐒𝐄 𝐘𝐎𝐔𝐑 𝐌𝐄𝐓𝐇𝐎𝐃
"""

    keyboard = [
        [
            InlineKeyboardButton(
                "🟡 𝐁𝐄𝐏𝟐𝟎",
                callback_data="pay_bep20"
            ),
            InlineKeyboardButton(
                "🔵 𝐓𝐑𝐂𝟐𝟎",
                callback_data="pay_trc20"
            )
        ],
        [
            InlineKeyboardButton(
                "🟣 𝐄𝐑𝐂𝟐𝟎",
                callback_data="pay_erc20"
            )
        ],
        [
            InlineKeyboardButton(
                "🇮🇳 𝐈𝐍𝐑 / 𝐔𝐏𝐈",
                callback_data="pay_inr"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 𝐁𝐀𝐂𝐊",
                callback_data="add_balance"
            )
        ]
    ]

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# PAYMENT ADDRESS
# =========================================================

async def payment_address(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    method = query.data

    amount = context.user_data.get("payment_amount", 0)

    addresses = {
        "pay_bep20": (
            "𝐁𝐄𝐏𝟐𝟎",
            BEP20_ADDRESS
        ),
        "pay_trc20": (
            "𝐓𝐑𝐂𝟐𝟎",
            TRC20_ADDRESS
        ),
        "pay_erc20": (
            "𝐄𝐑𝐂𝟐𝟎",
            ERC20_ADDRESS
        ),
    }

    if method == "pay_inr":

        text = f"""
{title("🇮🇳 𝐈𝐍𝐑 / 𝐔𝐏𝐈 𝐏𝐀𝐘𝐌𝐄𝐍𝐓")}

{divider()}

💵 𝐀𝐌𝐎𝐔𝐍𝐓
<b>${amount:.2f}</b>

🇮🇳 𝐔𝐏𝐈 𝐈𝐃
<code>{UPI_ID}</code>

{divider()}

⚠️ 𝐏𝐀𝐘 𝐓𝐇𝐄 𝐂𝐎𝐑𝐑𝐄𝐂𝐓 𝐈𝐍𝐑 𝐀𝐌𝐎𝐔𝐍𝐓 𝐀𝐒 𝐈𝐍𝐒𝐓𝐑𝐔𝐂𝐓𝐄𝐃 𝐁𝐘 𝐀𝐃𝐌𝐈𝐍.

📸 𝐀𝐅𝐓𝐄𝐑 𝐏𝐀𝐘𝐌𝐄𝐍𝐓, 𝐒𝐄𝐍𝐃 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐒𝐂𝐑𝐄𝐄𝐍𝐒𝐇𝐎𝐓 𝐁𝐄𝐋𝐎𝐖.
"""

        context.user_data["payment_method"] = "INR / UPI"

    else:

        network, address = addresses[method]

        text = f"""
{title("₿ 𝐂𝐑𝐘𝐏𝐓𝐎 𝐏𝐀𝐘𝐌𝐄𝐍𝐓")}

{divider()}

🌐 𝐍𝐄𝐓𝐖𝐎𝐑𝐊
<b>{network}</b>

💵 𝐀𝐌𝐎𝐔𝐍𝐓
<b>${amount:.2f}</b>

📋 𝐖𝐀𝐋𝐋𝐄𝐓 𝐀𝐃𝐃𝐑𝐄𝐒𝐒

<code>{address}</code>

{divider()}

⚠️ 𝐒𝐄𝐍𝐃 𝐎𝐍𝐋𝐘 𝐎𝐍 𝐓𝐇𝐄 𝐒𝐄𝐋𝐄𝐂𝐓𝐄𝐃 𝐍𝐄𝐓𝐖𝐎𝐑𝐊.

📸 𝐀𝐅𝐓𝐄𝐑 𝐏𝐀𝐘𝐌𝐄𝐍𝐓, 𝐒𝐄𝐍𝐃 𝐒𝐂𝐑𝐄𝐄𝐍𝐒𝐇𝐎𝐓.
"""

        context.user_data["payment_method"] = network

    keyboard = [
        [
            InlineKeyboardButton(
                "📋 𝐒𝐄𝐍𝐃 𝐀𝐃𝐃𝐑𝐄𝐒𝐒",
                callback_data="show_address"
            )
        ],
        [
            InlineKeyboardButton(
                "📸 𝐒𝐄𝐍𝐃 𝐏𝐑𝐎𝐎𝐅",
                callback_data="proof_info"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 𝐁𝐀𝐂𝐊",
                callback_data="payment_methods"
            )
        ]
    ]

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# SHOW ADDRESS
# =========================================================

async def show_address(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    method = context.user_data.get("payment_method", "")

    addresses = {
        "𝐁𝐄𝐏𝟐𝟎": BEP20_ADDRESS,
        "𝐓𝐑𝐂𝟐𝟎": TRC20_ADDRESS,
        "𝐄𝐑𝐂𝟐𝟎": ERC20_ADDRESS,
    }

    if method in addresses:

        await query.message.reply_text(
            f"📋 <b>{method} ADDRESS</b>\n\n"
            f"<code>{addresses[method]}</code>\n\n"
            f"👆 𝐓𝐀𝐏 𝐀𝐍𝐃 𝐇𝐎𝐋𝐃 𝐓𝐎 𝐂𝐎𝐏𝐘.",
            parse_mode="HTML"
        )

    elif method == "INR / UPI":

        await query.message.reply_text(
            f"🇮🇳 <b>𝐔𝐏𝐈 𝐈𝐃</b>\n\n"
            f"<code>{UPI_ID}</code>\n\n"
            f"👆 𝐓𝐀𝐏 𝐀𝐍𝐃 𝐇𝐎𝐋𝐃 𝐓𝐎 𝐂𝐎𝐏𝐘.",
            parse_mode="HTML"
        )


# =========================================================
# PROOF INFO
# =========================================================

async def proof_info(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    text = f"""
{title("📸 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐏𝐑𝐎𝐎𝐅")}

{divider()}

💵 𝐀𝐌𝐎𝐔𝐍𝐓:
<b>${context.user_data.get("payment_amount", 0):.2f}</b>

💳 𝐌𝐄𝐓𝐇𝐎𝐃:
<b>{context.user_data.get("payment_method", "N/A")}</b>

{divider()}

📸 𝐒𝐄𝐍𝐃 𝐀 𝐂𝐋𝐄𝐀𝐑 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐒𝐂𝐑𝐄𝐄𝐍𝐒𝐇𝐎𝐓 𝐍𝐎𝐖.

🟡 𝐀𝐃𝐌𝐈𝐍 𝐖𝐈𝐋𝐋 𝐕𝐄𝐑𝐈𝐅𝐘 𝐈𝐓.
"""

    context.user_data["waiting_proof"] = True

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_menu()
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
❌ <b>𝐈𝐍𝐕𝐀𝐋𝐈𝐃 𝐀𝐌𝐎𝐔𝐍𝐓</b>

Please enter a valid number.

Example:
<code>5</code>
""",
            parse_mode="HTML"
        )

        return

    context.user_data["waiting_amount"] = False
    context.user_data["payment_amount"] = amount

    keyboard = [
        [
            InlineKeyboardButton(
                "💳 𝐒𝐄𝐋𝐄𝐂𝐓 𝐏𝐀𝐘𝐌𝐄𝐍𝐓",
                callback_data="payment_methods"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 𝐁𝐀𝐂𝐊",
                callback_data="home"
            )
        ]
    ]

    await update.message.reply_text(
        f"""
{title("💳 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐑𝐄𝐐𝐔𝐄𝐒𝐓")}

{divider()}

💵 𝐀𝐌𝐎𝐔𝐍𝐓:
<b>${amount:.2f}</b>

{divider()}

👇 𝐒𝐄𝐋𝐄𝐂𝐓 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐌𝐄𝐓𝐇𝐎𝐃.
""",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# PAYMENT PROOF
# =========================================================

async def payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_proof"):

        await update.message.reply_text(
            "⚠️ 𝐏𝐋𝐄𝐀𝐒𝐄 𝐒𝐄𝐋𝐄𝐂𝐓 𝐀𝐃𝐃 𝐁𝐀𝐋𝐀𝐍𝐂𝐄 𝐅𝐈𝐑𝐒𝐓.",
            parse_mode="HTML"
        )
        return

    amount = context.user_data.get("payment_amount", 0)
    method = context.user_data.get(
        "payment_method",
        "Unknown"
    )

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
        (telegram_id, user_code, amount, currency, method,
         status, proof_file_id)
        VALUES (?, ?, ?, 'USD', ?, 'pending', ?)
        """,
        (
            telegram_id,
            user_code,
            amount,
            method,
            file_id
        )
    )

    payment_id = cur.lastrowid

    con.commit()
    con.close()

    context.user_data.pop("payment_amount", None)
    context.user_data["waiting_proof"] = False
    context.user_data.pop("payment_method", None)

    await update.message.reply_text(
        f"""
{title("✅ 𝐏𝐑𝐎𝐎𝐅 𝐑𝐄𝐂𝐄𝐈𝐕𝐄𝐃")}

{divider()}

🆔 𝐔𝐒𝐄𝐑 𝐈𝐃:
<code>{user_code}</code>

💵 𝐀𝐌𝐎𝐔𝐍𝐓:
<b>${amount:.2f}</b>

💳 𝐌𝐄𝐓𝐇𝐎𝐃:
<b>{method}</b>

🆔 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐈𝐃:
<code>{payment_id}</code>

🟡 𝐒𝐓𝐀𝐓𝐔𝐒:
<b>𝐏𝐄𝐍𝐃𝐈𝐍𝐆</b>

{divider()}

⏳ 𝐖𝐀𝐈𝐓𝐈𝐍𝐆 𝐅𝐎𝐑 𝐀𝐃𝐌𝐈𝐍 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍.
""",
        parse_mode="HTML"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ 𝐀𝐂𝐂𝐄𝐏𝐓",
                callback_data=f"accept_{payment_id}"
            ),
            InlineKeyboardButton(
                "❌ 𝐑𝐄𝐉𝐄𝐂𝐓",
                callback_data=f"reject_{payment_id}"
            )
        ]
    ]

    admin_text = f"""
💳 <b>𝐍𝐄𝐖 𝐏𝐀𝐘𝐌𝐄𝐍𝐓</b>

{divider()}

👤 𝐍𝐀𝐌𝐄:
<b>{name}</b>

🆔 𝐔𝐒𝐄𝐑 𝐈𝐃:
<code>{user_code}</code>

💵 𝐀𝐌𝐎𝐔𝐍𝐓:
<b>${amount:.2f}</b>

💳 𝐌𝐄𝐓𝐇𝐎𝐃:
<b>{method}</b>

🆔 𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐈𝐃:
<code>{payment_id}</code>

🟡 𝐒𝐓𝐀𝐓𝐔𝐒: <b>𝐏𝐄𝐍𝐃𝐈𝐍𝐆</b>
"""

    try:

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=admin_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        print("ADMIN PAYMENT ERROR:", e)


# =========================================================
# ADMIN PAYMENT ACTION
# =========================================================

async def payment_a
