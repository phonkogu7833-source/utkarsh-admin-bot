import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB = "utkarsh.db"

def db():
    return sqlite3.connect(DB)

def setup():
    con = db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            credits REAL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    con.commit()
    con.close()

def add_user(user):
    con = db()
    con.execute(
        "INSERT OR IGNORE INTO users(user_id, username) VALUES(?,?)",
        (user.id, user.username or "")
    )
    con.commit()
    con.close()

def balance(user_id):
    con = db()
    row = con.execute(
        "SELECT credits FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()
    con.close()
    return row[0] if row else 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user)

    text = (
        "❄️ <b>𝐔𝐓𝐊𝐀𝐑𝐒𝐇 𝐕𝐈𝐒𝐔𝐀𝐋𝐒</b> ❄️\n\n"
        "🚀 <b>𝐒𝐌𝐌 𝐏𝐀𝐍𝐄𝐋</b>\n"
        "💎 𝐃𝐢𝐠𝐢𝐭𝐚𝐥 𝐒𝐞𝐫𝐯𝐢𝐜𝐞𝐬\n\n"
        f"💰 <b>𝐁𝐀𝐋𝐀𝐍𝐂𝐄:</b> ${balance(user.id):.2f}\n\n"
        "👇 <b>𝐂𝐇𝐎𝐎𝐒𝐄 𝐀𝐍 𝐎𝐏𝐓𝐈𝐎𝐍</b>"
    )

    buttons = [
        [
            InlineKeyboardButton("💳 𝐁𝐔𝐘 𝐂𝐑𝐄𝐃𝐈𝐓", callback_data="buy"),
            InlineKeyboardButton("💰 𝐁𝐀𝐋𝐀𝐍𝐂𝐄", callback_data="bal")
        ],
        [
            InlineKeyboardButton("📦 𝐎𝐑𝐃𝐄𝐑", callback_data="order"),
            InlineKeyboardButton("👤 𝐏𝐑𝐎𝐅𝐈𝐋𝐄", callback_data="profile")
        ],
        [
            InlineKeyboardButton("🛟 𝐒𝐔𝐏𝐏𝐎𝐑𝐓", url="https://t.me/utkarshvisuals")
        ]
    ]

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    add_user(user)

    if q.data == "bal":
        await q.message.reply_text(
            f"💰 <b>𝐘𝐎𝐔𝐑 𝐁𝐀𝐋𝐀𝐍𝐂𝐄</b>\n\n"
            f"❄️ Credits: <b>${balance(user.id):.2f}</b>",
            parse_mode="HTML"
        )

    elif q.data == "profile":
        await q.message.reply_text(
            f"👤 <b>𝐏𝐑𝐎𝐅𝐈𝐋𝐄</b>\n\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📛 Username: @{user.username or 'N/A'}\n"
            f"💰 Balance: ${balance(user.id):.2f}",
            parse_mode="HTML"
        )

    elif q.data == "buy":
        context.user_data["state"] = "payment"
        await q.message.reply_text(
            "💳 <b>𝐁𝐔𝐘 𝐂𝐑𝐄𝐃𝐈𝐓</b>\n\n"
            "1️⃣ Payment complete karo.\n"
            "2️⃣ Payment screenshot bhejo.\n"
            "3️⃣ Saath mein amount bhi likho.\n\n"
            "📩 Proof admin verification ke liye jayega.\n"
            "🛡️ Approval ke baad credits add honge.",
            parse_mode="HTML"
        )

    elif q.data == "order":
        context.user_data["state"] = "order"
        await q.message.reply_text(
            "📦 <b>𝐍𝐄𝐖 𝐎𝐑𝐃𝐄𝐑</b>\n\n"
            "Service, quantity aur username/details ek message mein bhejo.\n\n"
            "Example:\n"
            "Instagram — 1000\n"
            "@username",
            parse_mode="HTML"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user)
    state = context.user_data.get("state")

    if state == "payment":
        if update.message.photo:
            context.user_data["payment_photo"] = update.message.photo[-1].file_id
            context.user_data["state"] = "payment_amount"

            await update.message.reply_text(
                "💵 Ab <b>payment amount</b> likho.\n"
                "Example: <code>10</code>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("📸 Payment screenshot bhejo.")

    elif state == "payment_amount":
        try:
            amount = float(update.message.text.strip())
        except:
            await update.message.reply_text("❌ Valid amount likho. Example: 10")
            return

        photo = context.user_data.get("payment_photo")

        con = db()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO payments(user_id, amount) VALUES(?,?)",
            (user.id, amount)
        )
        payment_id = cur.lastrowid
        con.commit()
        con.close()

        caption = (
            "💳 <b>𝐍𝐄𝐖 𝐏𝐀𝐘𝐌𝐄𝐍𝐓</b>\n\n"
            f"👤 User: @{user.username or 'N/A'}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"💵 Amount: <b>${amount:.2f}</b>\n"
            f"🔢 Payment ID: <code>{payment_id}</code>"
        )

        buttons = [[
            InlineKeyboardButton(
                "✅ APPROVE",
                callback_data=f"approve:{payment_id}"
            ),
            InlineKeyboardButton(
                "❌ REJECT",
                callback_data=f"reject:{payment_id}"
            )
        ]]

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ <b>Payment proof submitted!</b>\n\n"
            "⏳ Admin verification ke baad aapka balance update hoga.",
            parse_mode="HTML"
        )

    elif state == "order":
        order = update.message.text

        await context.bot.send_message(
            ADMIN_ID,
            "📦 <b>𝐍𝐄𝐖 𝐎𝐑𝐃𝐄𝐑</b>\n\n"
            f"👤 @{user.username or 'N/A'}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"💰 Balance: ${balance(user.id):.2f}\n\n"
            f"📝 <b>Order:</b>\n{order}",
            parse_mode="HTML"
        )

        context.user_data.clear()

        await update.message.reply_text(
            "🚀 <b>Order received!</b>\n\n"
            "📩 Admin ko order details bhej di gayi hain.",
            parse_mode="HTML"
        )

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        await q.message.reply_text("❌ Unauthorized")
        return

    action, payment_id = q.data.split(":")
    payment_id = int(payment_id)

    con = db()
    cur = con.cursor()

    payment = cur.execute(
        "SELECT user_id, amount, status FROM payments WHERE id=?",
        (payment_id,)
    ).fetchone()

    if not payment:
        con.close()
        return

    user_id, amount, status = payment

    if status != "pending":
        con.close()
        await q.message.reply_text("⚠️ Already processed.")
        return

    if action == "approve":
        cur.execute(
            "UPDATE payments SET status='approved' WHERE id=?",
            (payment_id,)
        )
        cur.execute(
            "UPDATE users SET credits = credits + ? WHERE user_id=?",
            (amount, user_id)
        )
        con.commit()

        await context.bot.send_message(
            user_id,
            f"✅ <b>PAYMENT APPROVED</b>\n\n"
            f"💵 Added: ${amount:.2f}\n"
            f"💰 New Balance: ${balance(user_id) + amount:.2f}",
            parse_mode="HTML"
        )

        await q.edit_message_caption(
            caption=q.message.caption + "\n\n✅ <b>APPROVED</b>",
            parse_mode="HTML"
        )

    else:
        cur.execute(
            "UPDATE payments SET status='rejected' WHERE id=?",
            (payment_id,)
        )
        con.commit()

        await context.bot.send_message(
            user_id,
            "❌ <b>PAYMENT REJECTED</b>\n\n"
            "Please contact support if you think this is incorrect.",
            parse_mode="HTML"
        )

        await q.edit_message_caption(
            caption=q.message.caption + "\n\n❌ <b>REJECTED</b>",
            parse_mode="HTML"
        )

    con.close()

def main():
    setup()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(
        admin_action,
        pattern=r"^(approve|reject):"
    ))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.TEXT & ~filters.COMMAND,
        message_handler
    ))

    print("Utkarsh Visuals Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
