import telebot
from telebot import types
import sqlite3
from datetime import datetime

# ------------------ SOZLAMALAR ------------------
BOT_TOKEN = "8463099371:AAG1sZM5W9jlCpcwSxs-tUOIQ4tplcRkrf8"  # bot tokenini bu yerga qo‘ying
ADMIN_ID = 7664675013               # admin Telegram user ID
CARD_NUMBER = "6262470029158248"   # to‘lov kartasi
PRICE_PER_STAR = 230
DB_PATH = "orders.db"
# ------------------------------------------------

bot = telebot.TeleBot(BOT_TOKEN)

# --- DB yaratish ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            amount INTEGER,
            price INTEGER,
            receipt_file_id TEXT,
            for_user TEXT,
            status TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_order(user_id, username, amount, price, receipt_file_id, for_user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO orders (
            user_id, username, amount, price,
            receipt_file_id, for_user, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, username, amount, price,
        receipt_file_id, for_user, 'pending',
        datetime.utcnow().isoformat()
    ))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def get_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    row = c.fetchone()
    conn.close()
    return row

# --- Yordamchi funksiyalar ---
def make_amount_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(types.KeyboardButton("50 ⭐"), types.KeyboardButton("100 ⭐"), types.KeyboardButton("150 ⭐"), types.KeyboardButton("200 ⭐"),types.KeyboardButton("250 ⭐"))
    kb.row(types.KeyboardButton("5000 ⭐"))
    kb.row(types.KeyboardButton("Custom kiritish"), types.KeyboardButton("Bekor qilish"))
    return kb

def parse_amount_text(text):
    try:
        return int(''.join(ch for ch in text if ch.isdigit()))
    except:
        return None

# --- START komandasi ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    txt = (
        f"Salom, {message.from_user.first_name}!\n\n"
        f"Bu bot orqali siz Telegram Stars sotib olishingiz mumkin 💫\n\n"
        f"💰 1 ⭐ = {PRICE_PER_STAR} so'm\n"
        f"🔻 Minimal: 50 ⭐\n\n"
        f"Boshlash uchun /buy buyrug‘ini bosing."
    )
    bot.send_message(message.chat.id, txt)

# --- BUY komandasi ---
@bot.message_handler(commands=['buy'])
def cmd_buy(message):
    bot.send_message(
        message.chat.id,
        "Necha stars sotib olmoqchisiz? Tanlang yoki 'Custom miqdor' ni bosing:",
        reply_markup=make_amount_keyboard()
    )

# --- Miqdor tanlash ---
@bot.message_handler(func=lambda m: m.text and (
    m.text.startswith("50") or m.text.startswith("100") or
    m.text.startswith("150") or m.text == "Custom miqdor"
))
def handle_preset_amount(message):
    if message.text == "Bekor qilish":
        bot.send_message(message.chat.id, "Bekor qilindi.", reply_markup=types.ReplyKeyboardRemove())
        return

    if message.text == "Custom miqdor":
        msg = bot.send_message(message.chat.id, "Iltimos, miqdorni son bilan kiriting (minimal 50 ⭐):", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, handle_custom_amount)
        return

    amount = parse_amount_text(message.text)
    if not amount or amount < 50:
        bot.send_message(message.chat.id, "Minimal 50 ⭐ bo'lishi kerak.")
        return

    price = amount * PRICE_PER_STAR
    send_payment_request(message.chat.id, amount, price)

# --- Custom miqdor kiritish ---
def handle_custom_amount(message):
    try:
        amount = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "Faqat son kiriting (masalan: 75).")
        return

    if amount < 50:
        bot.send_message(message.chat.id, "Minimal 50 ⭐ bo'lishi kerak.")
        return

    price = amount * PRICE_PER_STAR
    send_payment_request(message.chat.id, amount, price)

# --- To‘lov ma’lumoti yuborish ---
def send_payment_request(chat_id, amount, price):
    txt = (
        f"Siz tanladingiz: {amount} ⭐\n"
        f"To‘lov summasi: {price} so‘m\n\n"
        f"💳 To‘lovni quyidagi karta raqamga amalga oshiring:\n<b>{CARD_NUMBER}</b>\n\n"
        "To‘lovni amalga oshirgach, chekning rasmini yuboring.\n\n"
        "⏳ Chek yuborilgach, 1–6 soat ichida stars jo‘natiladi (chek tekshiriladi)."
    )
    bot.send_message(chat_id, txt, parse_mode="HTML")
    msg = bot.send_message(chat_id, "Iltimos, to‘lov chekini rasm yoki skrinshot shaklida yuboring:")
    bot.register_next_step_handler(msg, lambda m: handle_receipt(m, amount, price))

# --- Chekni qabul qilish ---
def handle_receipt(message, amount, price):
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "Iltimos, to‘lov chekini rasm shaklida yuboring.")
        return

    file_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "Yaxshi ✅\nEndi ushbu stars kim uchun ekanini yozing (masalan: @username yoki user ID):")
    bot.register_next_step_handler(msg, lambda m: handle_for_user(m, amount, price, file_id))

# --- Kim uchun ekanligini yozish ---
def handle_for_user(message, amount, price, file_id):
    for_user = message.text.strip()
    username = message.from_user.username or ""
    user_id = message.from_user.id

    order_id = create_order(user_id, username, amount, price, file_id, for_user)

    bot.send_message(
        message.chat.id,
        "Chek va foydalanuvchi ma’lumoti qabul qilindi ✅\n"
        "Admin tekshirmoqda, bu 1–6 soat vaqt olishi mumkin."
    )
    send_order_to_admin(order_id)

# --- Adminga yuborish ---
def send_order_to_admin(order_id):
    order = get_order(order_id)
    if not order:
        return

    oid, user_id, username, amount, price, receipt_file_id, for_user, status, created_at = order

    caption = (
        f"🆕 Yangi order #{oid}\n\n"
        f"👤 User: @{username or 'no_username'} ({user_id})\n"
        f"⭐ Miqdor: {amount}\n"
        f"💰 Narx: {price} so'm\n"
        f"🎯 Kim uchun: {for_user}\n"
        f"🕓 Vaqt (UTC): {created_at}\n\n"
        "Admin, iltimos tekshiring:"
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve:{oid}"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"reject:{oid}")
    )

    bot.send_photo(ADMIN_ID, receipt_file_id, caption=caption, reply_markup=kb)

# --- Admin tasdiqlashi yoki rad etishi ---
@bot.callback_query_handler(func=lambda call: call.data and (
    call.data.startswith("approve:") or call.data.startswith("reject:")
))
def handle_admin_action(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Faqat admin uchun.")
        return

    action, oid = call.data.split(":")
    oid = int(oid)
    order = get_order(oid)
    if not order:
        bot.answer_callback_query(call.id, "Order topilmadi.")
        return

    _, user_id, username, amount, price, receipt_file_id, for_user, status, created_at = order

    if action == "approve":
        update_order_status(oid, "approved")
        bot.send_message(user_id, f"✅ Sizning {amount} ⭐ uchun to‘lovingiz tasdiqlandi.\nStars yuborildi, tekshiring.")
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=call.message.caption + "\n\n✅ Admin tasdiqladi."
        )
        bot.answer_callback_query(call.id, "Tasdiqlandi ✅")

    elif action == "reject":
        update_order_status(oid, "rejected")
        bot.send_message(user_id, "❌ Chek fake bo‘lishi mumkin.\nAgar xatolik bo‘lsa: @lkromjonovv ga yozing.")
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=call.message.caption + "\n\n❌ Admin bekor qildi."
        )
        bot.answer_callback_query(call.id, "Bekor qilindi ❌")

# --- Botni ishga tushirish ---
if __name__ == "__main__":
    init_db()
    print("🤖 Bot ishga tushdi...")
    bot.infinity_polling()
