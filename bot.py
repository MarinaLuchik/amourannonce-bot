import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8549540559:AAEd3EllVX0oQnaRUooL54krXwSwg5Iz_wA"

REGIONS = {
    "Paris": ["Paris 1", "Paris 2", "Paris 3"],
    "Île-de-France": ["Boulogne", "Neuilly", "Vincennes"],
    "Lyon": ["Lyon 1", "Lyon 2"],
}

user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ]
    await update.message.reply_text("Choisissez la langue:", reply_markup=InlineKeyboardMarkup(keyboard))

async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📍 Choisir région", callback_data="choose_region")]
    ]
    await query.edit_message_text("Menu principal", reply_markup=InlineKeyboardMarkup(keyboard))

async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for region in REGIONS:
        keyboard.append([InlineKeyboardButton(region, callback_data=f"region_{region}")])

    await query.edit_message_text("Choisissez région:", reply_markup=InlineKeyboardMarkup(keyboard))

async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    region = query.data.replace("region_", "")
    cities = REGIONS.get(region, [])

    keyboard = []
    for city in cities:
        keyboard.append([InlineKeyboardButton(city, callback_data="done")])

    await query.edit_message_text(f"Ville: {region}", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_lang, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(choose_region, pattern="choose_region"))
    app.add_handler(CallbackQueryHandler(choose_city, pattern="^region_"))

    print("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
