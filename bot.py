import logging
import sqlite3
import os
import json
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "8549540559:AAEd3EllVX0oQnaRUooL54krXwSwg5Iz_wA")
CHANNEL_ID = "@amourannonce"
ADMIN_ID   = 2021397237        # только ты получаешь уведомления
MINIAPP_URL = "https://amourannonce.com"
MAX_PHOTOS  = 8

# ─── STATES ───────────────────────────────────────────────────────────────────
(
    CHOOSE_LANG, MAIN_MENU,
    M_REGION, M_CITY, M_NAME, M_AGE, M_HEIGHT, M_WEIGHT,
    M_MEASUREMENTS, M_NATIONALITY, M_LANGUAGES, M_INCALL,
    M_PRICE_1H, M_PRICE_2H, M_PRICE_NIGHT,
    M_CONTACT, M_PHOTOS,
    T_WHO, T_FROM_CITY, T_TO_REGION, T_TO_CITY,
    T_DATE_FROM, T_DATE_TO, T_NOTES, T_CONTACT, T_PHOTOS,
    A_REGION, A_CITY, A_TITLE, A_DESC, A_CONTACT, A_PHOTOS,
    BR_REGION, BR_CITY, BR_TYPE,
    ADMIN_MENU,
) = range(36)

# ─── REGIONS ──────────────────────────────────────────────────────────────────
REGIONS = {
    "🗼 Paris — Centre (1-4)": [
        "Paris 1er","Paris 2e","Paris 3e","Paris 4e",
    ],
    "🗼 Paris — Rive Gauche (5-7)": [
        "Paris 5e","Paris 6e","Paris 7e",
    ],
    "🗼 Paris — Grands Boulevards (8-10)": [
        "Paris 8e","Paris 9e","Paris 10e",
    ],
    "🗼 Paris — Est (11-12)": [
        "Paris 11e","Paris 12e",
    ],
    "🗼 Paris — Sud (13-15)": [
        "Paris 13e","Paris 14e","Paris 15e",
    ],
    "🗼 Paris — Ouest & Nord (16-18)": [
        "Paris 16e","Paris 17e","Paris 18e",
    ],
    "🗼 Paris — Nord-Est (19-20)": [
        "Paris 19e","Paris 20e",
    ],
    "🏙 Île-de-France — Proche banlieue": [
        "Boulogne-Billancourt","Neuilly-sur-Seine","Levallois-Perret",
        "Issy-les-Moulineaux","Courbevoie","La Défense","Puteaux",
        "Saint-Cloud","Vincennes","Saint-Mandé","Montreuil",
        "Bagnolet","Saint-Denis","Aubervilliers","Pantin",
    ],
    "🏙 Île-de-France — Grande banlieue": [
        "Versailles","Saint-Germain-en-Laye","Massy","Créteil",
        "Évry","Pontoise","Cergy","Melun","Fontainebleau",
        "Roissy / CDG","Orly",
    ],
    "🏔 Auvergne-Rhône-Alpes": [
        "Lyon","Annecy","Grenoble","Chambéry","Clermont-Ferrand",
        "Courchevel","Méribel","Val d'Isère","Megève","Chamonix",
        "Aix-les-Bains","Albertville","Valence","Saint-Étienne",
    ],
    "🌊 Provence-Alpes-Côte d'Azur": [
        "Nice","Cannes","Antibes","Monaco","Marseille",
        "Aix-en-Provence","Toulon","Saint-Tropez","Juan-les-Pins",
        "Menton","Grasse","Villefranche-sur-Mer","Avignon","Fréjus",
    ],
    "🌸 Occitanie": [
        "Toulouse","Montpellier","Perpignan","Nîmes","Sète",
        "Béziers","Montauban",
    ],
    "🍷 Nouvelle-Aquitaine": [
        "Bordeaux","Biarritz","Arcachon","Bayonne","La Rochelle",
        "Pau","Périgueux","Limoges","Poitiers",
    ],
    "⚓️ Pays de la Loire": [
        "Nantes","Angers","Le Mans","Saint-Nazaire",
    ],
    "🥨 Grand Est": [
        "Strasbourg","Reims","Metz","Nancy","Mulhouse","Colmar",
    ],
    "🍇 Bourgogne-Franche-Comté": [
        "Dijon","Besançon","Belfort",
    ],
    "🌿 Normandie": [
        "Rouen","Caen","Le Havre","Deauville","Cherbourg",
    ],
    "🏛 Hauts-de-France": [
        "Lille","Amiens","Dunkerque","Valenciennes",
    ],
    "🌊 Bretagne": [
        "Rennes","Brest","Quimper","Saint-Malo","Lorient","Vannes",
    ],
    "🌺 Centre-Val de Loire": [
        "Tours","Orléans","Blois",
    ],
}

# ─── ТЕКСТЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ (FR/EN) ────────────────────────────────────────
T = {
    "fr": {
        "welcome": (
            "💋 *Amour Annonce*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "La plateforme №1 pour les modèles\n"
            "et professionnels en France 🇫🇷\n\n"
            "Que souhaitez-vous faire ?"
        ),
        "choose_lang":   "🌍 Choisissez votre langue :",
        "btn_browse":    "🔍  Voir les annonces",
        "btn_model":     "👗  Déposer mon profil",
        "btn_tour":      "✈️  En Tour",
        "btn_ad":        "📢  Publier une annonce",
        "btn_site":      "🌐  Ouvrir le site",
        "btn_support":   "💬  Support",
        "btn_admin":     "🔐  Admin Panel",
        "btn_back":      "◀️ Retour",
        "btn_cancel":    "✖️ Annuler",
        "btn_done":      "✅ Terminer",
        "btn_skip":      "⏭ Passer",
        "choose_region": "📍 Choisissez une région :",
        "choose_city":   "🏙 Choisissez une ville :",
        "ask_name":          "👤 Prénom :",
        "ask_age":           "🎂 Âge :",
        "ask_height":        "📏 Taille (cm) :",
        "ask_weight":        "⚖️ Poids (kg) :",
        "ask_measurements":  "📐 Mensurations (ex: 90-60-90) :",
        "ask_nationality":   "🌍 Nationalité :",
        "ask_languages":     "🗣 Langues parlées :",
        "ask_incall":        "🏠 Incall / Outcall ?",
        "ask_price_1h":      "💶 Prix 1h (€) :",
        "ask_price_2h":      "💶 Prix 2h (€) :",
        "ask_price_night":   "💶 Prix nuit (€) :",
        "ask_contact":       "📞 Contact (Telegram @username ou téléphone) :",
        "ask_photos":        f"📸 Envoyez vos photos (max {MAX_PHOTOS})\nQuand vous avez terminé → /done",
        "ask_title":         "📝 Titre de l'annonce :",
        "ask_desc":          "📋 Description :",
        "tour_who":          "✈️ *En Tour* — vous êtes :",
        "btn_tour_model":    "👗 Modèle — je pars en tour",
        "btn_tour_host":     "🏨 J'accueille des modèles",
        "ask_tour_from":     "🛫 Votre ville de départ :",
        "ask_tour_region":   "📍 Région de destination :",
        "ask_tour_city":     "🏙 Ville de destination :",
        "ask_tour_from_date":"📅 Date d'arrivée (ex: 15.04) :",
        "ask_tour_to_date":  "📅 Date de départ (ex: 20.04) :",
        "ask_tour_notes":    "📝 Notes (tarifs, conditions) — /skip pour passer :",
        "sent_moderation":   "✅ *Envoyé en modération !*\nNous vous répondrons sous 24h.",
        "no_ads":            "😔 Aucune annonce pour l'instant.",
        "end_ads":           "— Fin des annonces —",
        "type_model":        "👗 Modèles",
        "type_tour":         "✈️ En Tour",
        "type_ad":           "📢 Annonces",
        "btn_contact":       "💬 Contacter",
        "btn_fav":           "❤️ Favoris",
        "vip_badge":         "⭐️ VIP",
    },
    "en": {
        "welcome": (
            "💋 *Amour Annonce*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "The №1 platform for models\n"
            "and professionals in France 🇫🇷\n\n"
            "What would you like to do?"
        ),
        "choose_lang":   "🌍 Choose your language:",
        "btn_browse":    "🔍  Browse listings",
        "btn_model":     "👗  Post my profile",
        "btn_tour":      "✈️  On Tour",
        "btn_ad":        "📢  Post an ad",
        "btn_site":      "🌐  Open website",
        "btn_support":   "💬  Support",
        "btn_admin":     "🔐  Admin Panel",
        "btn_back":      "◀️ Back",
        "btn_cancel":    "✖️ Cancel",
        "btn_done":      "✅ Done",
        "btn_skip":      "⏭ Skip",
        "choose_region": "📍 Choose a region:",
        "choose_city":   "🏙 Choose a city:",
        "ask_name":          "👤 First name:",
        "ask_age":           "🎂 Age:",
        "ask_height":        "📏 Height (cm):",
        "ask_weight":        "⚖️ Weight (kg):",
        "ask_measurements":  "📐 Measurements (e.g. 90-60-90):",
        "ask_nationality":   "🌍 Nationality:",
        "ask_languages":     "🗣 Languages spoken:",
        "ask_incall":        "🏠 Incall / Outcall?",
        "ask_price_1h":      "💶 Rate 1h (€):",
        "ask_price_2h":      "💶 Rate 2h (€):",
        "ask_price_night":   "💶 Overnight rate (€):",
        "ask_contact":       "📞 Contact (Telegram @username or phone):",
        "ask_photos":        f"📸 Send your photos (max {MAX_PHOTOS})\nWhen done → /done",
        "ask_title":         "📝 Ad title:",
        "ask_desc":          "📋 Description:",
        "tour_who":          "✈️ *On Tour* — you are:",
        "btn_tour_model":    "👗 Model — going on tour",
        "btn_tour_host":     "🏨 I host models",
        "ask_tour_from":     "🛫 Your departure city:",
        "ask_tour_region":   "📍 Destination region:",
        "ask_tour_city":     "🏙 Destination city:",
        "ask_tour_from_date":"📅 Arrival date (e.g. 15.04):",
        "ask_tour_to_date":  "📅 Departure date (e.g. 20.04):",
        "ask_tour_notes":    "📝 Notes (rates, conditions) — /skip to skip:",
        "sent_moderation":   "✅ *Sent for moderation!*\nWe'll reply within 24h.",
        "no_ads":            "😔 No listings yet.",
        "end_ads":           "— End of listings —",
        "type_model":        "👗 Models",
        "type_tour":         "✈️ On Tour",
        "type_ad":           "📢 Ads",
        "btn_contact":       "💬 Contact",
        "btn_fav":           "❤️ Favourite",
        "vip_badge":         "⭐️ VIP",
    }
}

# pending_ads: анкеты до одобрения
pending_ads = {}


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def lang(ctx):
    return ctx.user_data.get("lang", "fr")

def tx(key, ctx):
    return T.get(lang(ctx), T["fr"]).get(key, key)

def cancel_kb(ctx):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(tx("btn_cancel", ctx), callback_data="go_menu")
    ]])

def skip_cancel_kb(ctx):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(tx("btn_skip", ctx), callback_data="skip"),
        InlineKeyboardButton(tx("btn_cancel", ctx), callback_data="go_menu"),
    ]])

def incall_kb(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Incall", callback_data="incall_in"),
         InlineKeyboardButton("🚗 Outcall", callback_data="incall_out")],
        [InlineKeyboardButton("🏠🚗 Les deux / Both", callback_data="incall_both")],
        [InlineKeyboardButton(tx("btn_cancel", ctx), callback_data="go_menu")],
    ])


# ─── УВЕДОМЛЕНИЕ АДМИНУ (РУССКИЙ) ─────────────────────────────────────────────
def build_admin_notification(ad, source="бот"):
    """Строим красивое уведомление на русском для админа."""
    flow = ad.get("type", ad.get("flow", "model"))

    type_labels = {
        "model": "👗 Профиль модели",
        "tour":  "✈️ Тур",
        "ad":    "📢 Объявление",
    }
    type_label = type_labels.get(flow, "📋 Анкета")

    lines = [
        f"🔔 *НОВАЯ ЗАЯВКА НА МОДЕРАЦИЮ*",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📌 Тип: {type_label}",
        f"📍 Город: {ad.get('city', '—')}",
        f"👤 Имя: {ad.get('name', '—')}",
        f"🎂 Возраст: {ad.get('age', '—')}",
    ]

    if flow == "model":
        lines += [
            f"📏 Рост: {ad.get('height', '—')} см",
            f"⚖️ Вес: {ad.get('weight', '—')} кг",
            f"📐 Параметры: {ad.get('measurements', '—')}",
            f"🌍 Нац.: {ad.get('nationality', '—')}",
            f"🗣 Языки: {ad.get('languages', '—')}",
            f"🏠 {ad.get('incall', '—')}",
            f"💶 1ч: {ad.get('price_1h', '—')}€ | 2ч: {ad.get('price_2h', '—')}€ | Ночь: {ad.get('price_night', '—')}€",
        ]
    elif flow == "tour":
        lines += [
            f"🛫 Откуда: {ad.get('tour_from', '—')}",
            f"📅 Даты: {ad.get('tour_date_from', '—')} → {ad.get('tour_date_to', '—')}",
            f"📝 Заметки: {ad.get('tour_notes', '—')}",
        ]
    else:
        lines += [
            f"📝 Заголовок: {ad.get('ad_title', '—')}",
            f"📋 Описание: {ad.get('ad_desc', '—')}",
        ]

    lines += [
        f"📞 Контакт: {ad.get('contact', '—')}",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📥 Источник: {source}",
    ]

    return "\n".join(lines)

def moderation_kb(ad_key):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{ad_key}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{ad_key}"),
        ],
        [InlineKeyboardButton("⭐️ Одобрить как VIP", callback_data=f"mod_vip_{ad_key}")],
    ])


# ─── DATABASE ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS annonces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        region TEXT, city TEXT,
        name TEXT, age TEXT,
        height TEXT, weight TEXT, measurements TEXT,
        nationality TEXT, languages TEXT, incall TEXT,
        price_1h TEXT, price_2h TEXT, price_night TEXT,
        contact TEXT,
        photos TEXT,
        ad_title TEXT, ad_desc TEXT,
        tour_who TEXT, tour_from TEXT,
        tour_date_from TEXT, tour_date_to TEXT, tour_notes TEXT,
        is_vip INTEGER DEFAULT 0,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        source TEXT DEFAULT 'bot'
    )""")
    # Добавляем колонку source если её нет (для старых БД)
    try:
        c.execute("ALTER TABLE annonces ADD COLUMN source TEXT DEFAULT 'bot'")
    except Exception:
        pass
    c.execute("""CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, ad_id INTEGER,
        UNIQUE(user_id, ad_id)
    )""")
    conn.commit()
    conn.close()

def save_ad(ad, is_vip=False):
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    c.execute("""INSERT INTO annonces
        (type,region,city,name,age,height,weight,measurements,
        nationality,languages,incall,price_1h,price_2h,price_night,
        contact,photos,ad_title,ad_desc,
        tour_who,tour_from,tour_date_from,tour_date_to,tour_notes,
        is_vip,user_id,expires_at,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ad.get("type","model"), ad.get("region","-"), ad.get("city","-"),
            ad.get("name","-"), ad.get("age","-"),
            ad.get("height","-"), ad.get("weight","-"), ad.get("measurements","-"),
            ad.get("nationality","-"), ad.get("languages","-"), ad.get("incall","-"),
            ad.get("price_1h","-"), ad.get("price_2h","-"), ad.get("price_night","-"),
            ad.get("contact","-"),
            ",".join(ad.get("photos", [])),
            ad.get("ad_title","-"), ad.get("ad_desc","-"),
            ad.get("tour_who","-"), ad.get("tour_from","-"),
            ad.get("tour_date_from","-"), ad.get("tour_date_to","-"),
            ad.get("tour_notes","-"),
            1 if is_vip else 0,
            ad.get("user_id"),
            expires,
            ad.get("source", "bot"),
        )
    )
    ad_id = c.lastrowid
    conn.commit()
    conn.close()
    return ad_id

def get_ads(city, ad_type, limit=10):
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        if ad_type == "all":
            c.execute("""SELECT * FROM annonces
                WHERE city=? AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY is_vip DESC, created_at DESC LIMIT ?""",
                (city, now, limit))
        else:
            c.execute("""SELECT * FROM annonces
                WHERE city=? AND type=? AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY is_vip DESC, created_at DESC LIMIT ?""",
                (city, ad_type, now, limit))
    except Exception:
        if ad_type == "all":
            c.execute("SELECT * FROM annonces WHERE city=? ORDER BY is_vip DESC, created_at DESC LIMIT ?", (city, limit))
        else:
            c.execute("SELECT * FROM annonces WHERE city=? AND type=? ORDER BY is_vip DESC, created_at DESC LIMIT ?", (city, ad_type, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_ad(ad_id):
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    c.execute("DELETE FROM annonces WHERE id=?", (ad_id,))
    conn.commit()
    conn.close()

def set_vip(ad_id, is_vip=True):
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    c.execute("UPDATE annonces SET is_vip=? WHERE id=?", (1 if is_vip else 0, ad_id))
    conn.commit()
    conn.close()

def get_ad_by_id(ad_id):
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    c.execute("SELECT * FROM annonces WHERE id=?", (ad_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_db_stats():
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("SELECT COUNT(*) FROM annonces WHERE expires_at > ?", (now,))
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM annonces WHERE is_vip=1 AND expires_at > ?", (now,))
        vip = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM annonces WHERE created_at > ?",
                  ((datetime.now() - timedelta(days=1)).isoformat(),))
        today = c.fetchone()[0]
        try:
            c.execute("SELECT COUNT(*) FROM annonces WHERE source='site' AND expires_at > ?", (now,))
            from_site = c.fetchone()[0]
        except Exception:
            from_site = 0
    except Exception:
        c.execute("SELECT COUNT(*) FROM annonces", )
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM annonces WHERE is_vip=1")
        vip = c.fetchone()[0]
        today = 0
        from_site = 0
    conn.close()
    return total, vip, today, from_site


# ─── KEYBOARDS ────────────────────────────────────────────────────────────────
def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    ]])

def main_menu_kb(ctx, user_id=None):
    rows = [
        [InlineKeyboardButton(tx("btn_browse", ctx), callback_data="go_browse")],
        [
            InlineKeyboardButton(tx("btn_model", ctx), callback_data="go_model"),
            InlineKeyboardButton(tx("btn_tour", ctx), callback_data="go_tour"),
        ],
        [InlineKeyboardButton(tx("btn_ad", ctx), callback_data="go_ad")],
        [InlineKeyboardButton(tx("btn_site", ctx), url=MINIAPP_URL)],
        [InlineKeyboardButton(tx("btn_support", ctx), url="https://t.me/amourannonce_tour")],
    ]
    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton(tx("btn_admin", ctx), callback_data="go_admin")])
    return InlineKeyboardMarkup(rows)

def region_kb(ctx, prefix):
    keys = list(REGIONS.keys())
    kb = []
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i+j < len(keys):
                row.append(InlineKeyboardButton(
                    keys[i+j], callback_data=f"{prefix}_r_{i+j}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(tx("btn_back", ctx), callback_data="go_menu")])
    return InlineKeyboardMarkup(kb)

def city_kb(ctx, region_name, prefix):
    cities = REGIONS.get(region_name, [])
    kb = []
    row = []
    for city in cities:
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_c_{city}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(tx("btn_back", ctx), callback_data=f"{prefix}_back_region")])
    return InlineKeyboardMarkup(kb)

def browse_type_kb(ctx):
    l = lang(ctx)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👗 Modèles" if l=="fr" else "👗 Models", callback_data="brt_model")],
        [InlineKeyboardButton("✈️ En Tour" if l=="fr" else "✈️ On Tour", callback_data="brt_tour")],
        [InlineKeyboardButton("📢 Annonces" if l=="fr" else "📢 Ads", callback_data="brt_ad")],
        [InlineKeyboardButton(tx("btn_back", ctx), callback_data="go_browse")],
    ])

def ad_action_kb(ad_id, contact, ctx):
    contact_clean = contact.replace("@","").replace("https://t.me/","").strip()
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(tx("btn_fav", ctx), callback_data=f"fav_{ad_id}"),
        InlineKeyboardButton(tx("btn_contact", ctx), url=f"https://t.me/{contact_clean}"),
    ]])

def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ожидают модерации", callback_data="adm_pending")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🗂 Все анкеты", callback_data="adm_all")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="go_menu")],
    ])

def admin_ad_kb(ad_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐️ VIP вкл/выкл", callback_data=f"adm_vip_{ad_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{ad_id}"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="adm_all")],
    ])


# ─── FORMAT AD ────────────────────────────────────────────────────────────────
def format_ad(row, ctx):
    type_   = row[1]
    region  = row[2]
    city    = row[3]
    name    = row[4]
    age     = row[5]
    height  = row[6]
    weight  = row[7]
    measurements = row[8]
    nationality  = row[9]
    languages    = row[10]
    incall       = row[11]
    price_1h     = row[12]
    price_2h     = row[13]
    price_night  = row[14]
    contact      = row[15]
    tour_who     = row[19]
    tour_from    = row[20]
    tour_date_from = row[21]
    tour_date_to   = row[22]
    tour_notes     = row[23]
    is_vip         = row[24]
    ad_title       = row[17]
    ad_desc        = row[18]

    vip = f"{tx('vip_badge', ctx)} | " if is_vip else ""

    if type_ == "model":
        lines = [
            f"{vip}👗 *{name}*, {age} ans — {city}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"📏 {height} cm  ⚖️ {weight} kg  📐 {measurements}",
            f"🌍 {nationality}  🗣 {languages}",
            f"🏠 {incall}",
            f"💶 1h: *{price_1h}€*  |  2h: *{price_2h}€*  |  Nuit: *{price_night}€*",
            f"📞 {contact}",
        ]
    elif type_ == "tour":
        who_label = "👗 Modèle" if tour_who == "model" else "🏨 Hôte"
        lines = [
            f"{vip}✈️ *En Tour* — {who_label}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"📍 {city}",
        ]
        if tour_who == "model":
            lines.append(f"🛫 Depuis: {tour_from}")
        lines += [
            f"📅 {tour_date_from} → {tour_date_to}",
            f"👤 {name}",
        ]
        if tour_notes and tour_notes != "-":
            lines.append(f"📝 {tour_notes}")
        lines.append(f"📞 {contact}")
    else:
        lines = [
            f"{vip}📢 *{ad_title}*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"📍 {city}",
            f"📋 {ad_desc}",
            f"📞 {contact}",
        ]

    return "\n".join(lines)


# ─── START / MENU ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "💋 *Amour Annonce*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "La plateforme №1 pour les modèles\n"
        "et professionnels en France 🇫🇷\n\n"
        "👇 Ouvrez le site ou choisissez votre langue :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🌸 Ouvrir Amour Annonce",
                web_app=WebAppInfo(url="https://amourannonce.com")
            )],
            [
                InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            ]
        ])
    )
    return CHOOSE_LANG

async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["lang"] = q.data.replace("lang_", "")
    await q.edit_message_text(
        tx("welcome", context),
        reply_markup=main_menu_kb(context, q.from_user.id),
        parse_mode="Markdown"
    )
    return MAIN_MENU

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = tx("welcome", context)
    kb = main_menu_kb(context, user_id)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    return MAIN_MENU


# ─── BROWSE ───────────────────────────────────────────────────────────────────
async def go_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(tx("choose_region", context), reply_markup=region_kb(context, "br"))
    return BR_REGION

async def browse_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "go_browse":
        return await go_browse(update, context)
    idx = int(q.data.replace("br_r_", ""))
    region = list(REGIONS.keys())[idx]
    context.user_data["br_region"] = region
    await q.edit_message_text(
        f"{region}\n\n{tx('choose_city', context)}",
        reply_markup=city_kb(context, region, "br")
    )
    return BR_CITY

async def browse_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "br_back_region":
        return await go_browse(update, context)
    city = q.data.replace("br_c_", "")
    context.user_data["br_city"] = city
    await q.edit_message_text(
        f"📍 *{city}*\n\nType d'annonce :",
        reply_markup=browse_type_kb(context),
        parse_mode="Markdown"
    )
    return BR_TYPE

async def browse_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "go_browse":
        return await go_browse(update, context)
    type_map = {"brt_model": "model", "brt_tour": "tour", "brt_ad": "ad"}
    ad_type = type_map.get(q.data, "all")
    city = context.user_data.get("br_city", "")
    ads = get_ads(city, ad_type)
    if not ads:
        await q.edit_message_text(
            tx("no_ads", context),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(tx("btn_back", context), callback_data="go_browse")
            ]])
        )
        return MAIN_MENU
    await q.edit_message_text(f"📍 *{city}* — {len(ads)} annonce(s)", parse_mode="Markdown")
    for row in ads:
        caption = format_ad(row, context)
        photos_str = row[16]
        photos = [p for p in photos_str.split(",") if p] if photos_str else []
        ad_id = row[0]
        contact = row[15]
        try:
            if photos:
                await q.message.reply_photo(photo=photos[0], caption=caption, parse_mode="Markdown")
                if len(photos) > 1:
                    media = [InputMediaPhoto(media=p) for p in photos[1:min(len(photos), MAX_PHOTOS)]]
                    await q.message.reply_media_group(media=media)
            else:
                await q.message.reply_text(caption, parse_mode="Markdown")
            await q.message.reply_text("⬆️", reply_markup=ad_action_kb(ad_id, contact, context))
        except Exception as e:
            logger.error(f"Ошибка отправки анкеты {ad_id}: {e}")
            await q.message.reply_text(caption, parse_mode="Markdown")
    await q.message.reply_text(
        tx("end_ads", context),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tx("btn_back", context), callback_data="go_browse")],
            [InlineKeyboardButton("🏠 Menu", callback_data="go_menu")],
        ])
    )
    return MAIN_MENU


# ─── MODEL FLOW ───────────────────────────────────────────────────────────────
async def go_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["flow"] = "model"
    await q.edit_message_text(tx("choose_region", context), reply_markup=region_kb(context, "m"))
    return M_REGION

async def model_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("m_r_", ""))
    region = list(REGIONS.keys())[idx]
    context.user_data["region"] = region
    await q.edit_message_text(
        f"{region}\n\n{tx('choose_city', context)}",
        reply_markup=city_kb(context, region, "m")
    )
    return M_CITY

async def model_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "m_back_region":
        return await go_model(update, context)
    city = q.data.replace("m_c_", "")
    context.user_data["city"] = city
    await q.edit_message_text(
        f"📍 *{city}*\n\n{tx('ask_name', context)}",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_NAME

async def model_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(tx("ask_age", context), reply_markup=cancel_kb(context))
    return M_AGE

async def model_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["age"] = update.message.text
    await update.message.reply_text(tx("ask_height", context), reply_markup=cancel_kb(context))
    return M_HEIGHT

async def model_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["height"] = update.message.text
    await update.message.reply_text(tx("ask_weight", context), reply_markup=cancel_kb(context))
    return M_WEIGHT

async def model_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["weight"] = update.message.text
    await update.message.reply_text(tx("ask_measurements", context), reply_markup=cancel_kb(context))
    return M_MEASUREMENTS

async def model_measurements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["measurements"] = update.message.text
    await update.message.reply_text(tx("ask_nationality", context), reply_markup=cancel_kb(context))
    return M_NATIONALITY

async def model_nationality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nationality"] = update.message.text
    await update.message.reply_text(tx("ask_languages", context), reply_markup=cancel_kb(context))
    return M_LANGUAGES

async def model_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["languages"] = update.message.text
    await update.message.reply_text(tx("ask_incall", context), reply_markup=incall_kb(context))
    return M_INCALL

async def model_incall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mapping = {"incall_in": "Incall", "incall_out": "Outcall", "incall_both": "Incall + Outcall"}
    context.user_data["incall"] = mapping.get(q.data, "-")
    await q.edit_message_text(tx("ask_price_1h", context), reply_markup=cancel_kb(context))
    return M_PRICE_1H

async def model_price_1h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price_1h"] = update.message.text
    await update.message.reply_text(tx("ask_price_2h", context), reply_markup=cancel_kb(context))
    return M_PRICE_2H

async def model_price_2h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price_2h"] = update.message.text
    await update.message.reply_text(tx("ask_price_night", context), reply_markup=cancel_kb(context))
    return M_PRICE_NIGHT

async def model_price_night(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price_night"] = update.message.text
    await update.message.reply_text(tx("ask_contact", context), reply_markup=cancel_kb(context))
    return M_CONTACT

async def model_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text
    context.user_data["photos"] = []
    await update.message.reply_text(tx("ask_photos", context), reply_markup=cancel_kb(context))
    return M_PHOTOS


# ─── TOUR FLOW ────────────────────────────────────────────────────────────────
async def go_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["flow"] = "tour"
    await q.edit_message_text(
        tx("tour_who", context),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tx("btn_tour_model", context), callback_data="tour_who_model")],
            [InlineKeyboardButton(tx("btn_tour_host", context), callback_data="tour_who_host")],
            [InlineKeyboardButton(tx("btn_back", context), callback_data="go_menu")],
        ])
    )
    return T_WHO

async def tour_who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    who = q.data.replace("tour_who_", "")
    context.user_data["tour_who"] = who
    if who == "model":
        await q.edit_message_text(tx("ask_tour_from", context), reply_markup=cancel_kb(context))
        return T_FROM_CITY
    else:
        await q.edit_message_text(tx("ask_tour_region", context), reply_markup=region_kb(context, "t"))
        return T_TO_REGION

async def tour_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_from"] = update.message.text
    await update.message.reply_text(tx("ask_tour_region", context), reply_markup=region_kb(context, "t"))
    return T_TO_REGION

async def tour_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("t_r_", ""))
    region = list(REGIONS.keys())[idx]
    context.user_data["region"] = region
    await q.edit_message_text(
        f"{region}\n\n{tx('ask_tour_city', context)}",
        reply_markup=city_kb(context, region, "t")
    )
    return T_TO_CITY

async def tour_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "t_back_region":
        await q.edit_message_text(tx("ask_tour_region", context), reply_markup=region_kb(context, "t"))
        return T_TO_REGION
    city = q.data.replace("t_c_", "")
    context.user_data["city"] = city
    await q.edit_message_text(tx("ask_tour_from_date", context), reply_markup=cancel_kb(context))
    return T_DATE_FROM

async def tour_date_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_date_from"] = update.message.text
    await update.message.reply_text(tx("ask_tour_to_date", context), reply_markup=cancel_kb(context))
    return T_DATE_TO

async def tour_date_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_date_to"] = update.message.text
    await update.message.reply_text(tx("ask_name", context), reply_markup=cancel_kb(context))
    return T_NOTES

async def tour_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("name"):
        context.user_data["name"] = update.message.text
        await update.message.reply_text(tx("ask_tour_notes", context), reply_markup=skip_cancel_kb(context))
        return T_NOTES
    context.user_data["tour_notes"] = update.message.text
    await update.message.reply_text(tx("ask_contact", context), reply_markup=cancel_kb(context))
    return T_CONTACT

async def tour_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text
    context.user_data["photos"] = []
    await update.message.reply_text(tx("ask_photos", context), reply_markup=cancel_kb(context))
    return T_PHOTOS


# ─── AD FLOW ──────────────────────────────────────────────────────────────────
async def go_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["flow"] = "ad"
    await q.edit_message_text(tx("choose_region", context), reply_markup=region_kb(context, "a"))
    return A_REGION

async def ad_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("a_r_", ""))
    region = list(REGIONS.keys())[idx]
    context.user_data["region"] = region
    await q.edit_message_text(
        f"{region}\n\n{tx('choose_city', context)}",
        reply_markup=city_kb(context, region, "a")
    )
    return A_CITY

async def ad_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "a_back_region":
        return await go_ad(update, context)
    city = q.data.replace("a_c_", "")
    context.user_data["city"] = city
    await q.edit_message_text(
        f"📍 *{city}*\n\n{tx('ask_title', context)}",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return A_TITLE

async def ad_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_title"] = update.message.text
    await update.message.reply_text(tx("ask_desc", context), reply_markup=cancel_kb(context))
    return A_DESC

async def ad_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_desc"] = update.message.text
    await update.message.reply_text(tx("ask_contact", context), reply_markup=cancel_kb(context))
    return A_CONTACT

async def ad_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text
    context.user_data["photos"] = []
    await update.message.reply_text(tx("ask_photos", context), reply_markup=cancel_kb(context))
    return A_PHOTOS


# ─── ФОТО (общие) ─────────────────────────────────────────────────────────────
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"⚠️ Максимум {MAX_PHOTOS} фото. Отправьте /done")
        return None
    file_id = update.message.photo[-1].file_id
    photos.append(file_id)
    context.user_data["photos"] = photos
    count = len(photos)
    if count >= MAX_PHOTOS:
        await update.message.reply_text(f"✅ Фото {count}/{MAX_PHOTOS} — максимум!\nОтправьте /done")
    else:
        await update.message.reply_text(f"✅ Фото {count}/{MAX_PHOTOS} — продолжайте или /done")
    return None

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])
    if not photos:
        await update.message.reply_text("⚠️ Отправьте хотя бы одно фото.")
        return None

    user_id = update.effective_user.id
    flow = context.user_data.get("flow", "model")
    ad_key = str(user_id)
    context.user_data["type"] = flow
    context.user_data["user_id"] = user_id
    context.user_data["source"] = "bot"

    pending_ads[ad_key] = dict(context.user_data)

    # Сообщение пользователю
    await update.message.reply_text(
        tx("sent_moderation", context),
        reply_markup=main_menu_kb(context, user_id),
        parse_mode="Markdown"
    )

    # ── Уведомление ТЕБЕ на русском ──
    ad = pending_ads[ad_key]
    notification_text = build_admin_notification(ad, source="бот Telegram")

    try:
        if photos:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photos[0],
                caption=notification_text,
                parse_mode="Markdown"
            )
            if len(photos) > 1:
                media = [InputMediaPhoto(media=p) for p in photos[1:]]
                await context.bot.send_media_group(chat_id=ADMIN_ID, media=media)
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=notification_text,
                parse_mode="Markdown"
            )
        # Кнопки модерации
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"👇 *Выбери действие:*",
            reply_markup=moderation_kb(ad_key),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")

    context.user_data.clear()
    return ConversationHandler.END


# ─── SKIP ─────────────────────────────────────────────────────────────────────
async def skip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["tour_notes"] = "-"
    await q.edit_message_text(tx("ask_contact", context), reply_markup=cancel_kb(context))
    return T_CONTACT


# ─── МОДЕРАЦИЯ ────────────────────────────────────────────────────────────────
async def moderation_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔️ Доступ запрещён.", show_alert=True)
        return

    parts = q.data.split("_", 2)
    action = parts[1]
    ad_key = parts[2]
    ad = pending_ads.get(ad_key)

    if not ad:
        await q.edit_message_text("⚠️ Анкета не найдена (уже обработана?).")
        return

    if action == "reject":
        # Уведомляем пользователя об отклонении (если из бота)
        if ad.get("source") == "bot" and ad.get("user_id"):
            try:
                l = ad.get("lang", "fr")
                msg = "❌ Votre annonce a été refusée." if l == "fr" else "❌ Your listing was rejected."
                await context.bot.send_message(chat_id=ad["user_id"], text=msg)
            except Exception:
                pass
        del pending_ads[ad_key]
        await q.edit_message_text("❌ Заявка отклонена.")
        return

    is_vip = (action == "vip")
    ad_id = save_ad(ad, is_vip)
    await publish_to_channel(context, ad, is_vip)

    # Уведомляем пользователя об одобрении (если из бота)
    if ad.get("source") == "bot" and ad.get("user_id"):
        try:
            l = ad.get("lang", "fr")
            msg = "✅ Votre annonce a été publiée!" if l == "fr" else "✅ Your listing is published!"
            if is_vip:
                msg += "\n⭐️ *Statut VIP accordé!*"
            await context.bot.send_message(
                chat_id=ad["user_id"], text=msg, parse_mode="Markdown"
            )
        except Exception:
            pass

    del pending_ads[ad_key]
    status = "⭐️ VIP" if is_vip else "обычная"
    await q.edit_message_text(
        f"✅ *Анкета одобрена и опубликована!*\n"
        f"🆔 ID: {ad_id} | {status}",
        parse_mode="Markdown"
    )


# ─── ПУБЛИКАЦИЯ В КАНАЛ ───────────────────────────────────────────────────────
async def publish_to_channel(context, ad, is_vip=False):
    flow = ad.get("type", "model")
    city = ad.get("city", "-")
    vip = "⭐️ VIP | " if is_vip else ""
    vip_tag = "#vip " if is_vip else ""
    city_tag = city.lower().replace(" ","_").replace("-","_").replace("'","").replace(".","")

    if flow == "model":
        caption = (
            f"{vip}👗 *{ad.get('name')}, {ad.get('age')} ans* — {city}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📏 {ad.get('height')} cm  ⚖️ {ad.get('weight')} kg  📐 {ad.get('measurements')}\n"
            f"🌍 {ad.get('nationality')}  🗣 {ad.get('languages')}\n"
            f"🏠 {ad.get('incall')}\n"
            f"💶 1h: *{ad.get('price_1h')}€*  |  2h: *{ad.get('price_2h')}€*  |  Nuit: *{ad.get('price_night')}€*\n"
            f"📞 {ad.get('contact')}\n\n"
            f"{vip_tag}#{city_tag} #modele #amourannonce"
        )
    elif flow == "tour":
        who_label = "Modèle" if ad.get("tour_who") == "model" else "Hôte"
        caption = (
            f"{vip}✈️ *En Tour — {who_label}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 {city}\n"
            f"📅 {ad.get('tour_date_from')} → {ad.get('tour_date_to')}\n"
            f"👤 {ad.get('name')}\n"
            f"📝 {ad.get('tour_notes', '-')}\n"
            f"📞 {ad.get('contact')}\n\n"
            f"{vip_tag}#{city_tag} #tour #amourannonce"
        )
    else:
        caption = (
            f"{vip}📢 *{ad.get('ad_title')}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 {city}\n"
            f"📋 {ad.get('ad_desc')}\n"
            f"📞 {ad.get('contact')}\n\n"
            f"{vip_tag}#{city_tag} #annonce #amourannonce"
        )

    photos = ad.get("photos", [])
    try:
        if photos:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photos[0],
                caption=caption,
                parse_mode="Markdown"
            )
            if len(photos) > 1:
                media = [InputMediaPhoto(media=p) for p in photos[1:]]
                await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка публикации в канал: {e}")


# ─── ADMIN PANEL ──────────────────────────────────────────────────────────────
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Доступ запрещён.")
        return MAIN_MENU
    total, vip, today, from_site = get_db_stats()
    pending = len(pending_ads)
    await update.message.reply_text(
        f"🔐 *Панель администратора*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Активных анкет: *{total}*\n"
        f"⭐️ VIP: *{vip}*\n"
        f"🆕 За сегодня: *{today}*\n"
        f"🌐 С сайта: *{from_site}*\n"
        f"⏳ На модерации: *{pending}*",
        reply_markup=admin_menu_kb(),
        parse_mode="Markdown"
    )
    return ADMIN_MENU

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    data = q.data

    if data == "go_admin":
        total, vip, today, from_site = get_db_stats()
        pending = len(pending_ads)
        await q.edit_message_text(
            f"🔐 *Панель администратора*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Активных анкет: *{total}*\n"
            f"⭐️ VIP: *{vip}*\n"
            f"🆕 За сегодня: *{today}*\n"
            f"🌐 С сайта: *{from_site}*\n"
            f"⏳ На модерации: *{pending}*",
            reply_markup=admin_menu_kb(),
            parse_mode="Markdown"
        )
        return ADMIN_MENU

    if data == "adm_stats":
        total, vip, today, from_site = get_db_stats()
        pending = len(pending_ads)
        await q.edit_message_text(
            f"📊 *Статистика*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Активных анкет: *{total}*\n"
            f"⭐️ VIP: *{vip}*\n"
            f"🆕 За сегодня: *{today}*\n"
            f"🌐 Размещено с сайта: *{from_site}*\n"
            f"⏳ Ожидают модерации: *{pending}*",
            reply_markup=admin_menu_kb(),
            parse_mode="Markdown"
        )
        return ADMIN_MENU

    if data == "adm_pending":
        if not pending_ads:
            await q.edit_message_text(
                "✅ Нет заявок на модерации.",
                reply_markup=admin_menu_kb()
            )
            return ADMIN_MENU
        text = f"⏳ *Заявок на модерации: {len(pending_ads)}*\n\n"
        for key, ad in pending_ads.items():
            source = "🌐 сайт" if ad.get("source") == "site" else "📱 бот"
            text += f"• {ad.get('type','?')} | {ad.get('city','-')} | {ad.get('name','-')} | {source}\n"
        await q.edit_message_text(text, reply_markup=admin_menu_kb(), parse_mode="Markdown")
        return ADMIN_MENU

    if data == "adm_all":
        conn = sqlite3.connect("annonces.db")
        c = conn.cursor()
        c.execute("""SELECT id,type,city,name,is_vip,source,created_at
            FROM annonces WHERE expires_at > ?
            ORDER BY created_at DESC LIMIT 20""",
            (datetime.now().isoformat(),))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await q.edit_message_text("Нет анкет.", reply_markup=admin_menu_kb())
            return ADMIN_MENU
        kb = []
        for row in rows:
            ad_id, type_, city, name, is_vip, source, created = row
            vip_icon = "⭐️ " if is_vip else ""
            src_icon = "🌐" if source == "site" else "📱"
            label = f"{vip_icon}{src_icon} {type_[:1].upper()} | {city} | {name}"
            kb.append([InlineKeyboardButton(label, callback_data=f"adm_view_{ad_id}")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="go_admin")])
        await q.edit_message_text(
            "🗂 *Активные анкеты (последние 20):*",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return ADMIN_MENU

    if data.startswith("adm_view_"):
        ad_id = int(data.replace("adm_view_", ""))
        row = get_ad_by_id(ad_id)
        if not row:
            await q.edit_message_text("Не найдено.", reply_markup=admin_menu_kb())
            return ADMIN_MENU
        caption = format_ad(row, context)
        await q.edit_message_text(caption, reply_markup=admin_ad_kb(ad_id), parse_mode="Markdown")
        return ADMIN_MENU

    if data.startswith("adm_vip_"):
        ad_id = int(data.replace("adm_vip_", ""))
        row = get_ad_by_id(ad_id)
        if row:
            new_vip = 0 if row[24] else 1
            set_vip(ad_id, new_vip)
            status = "⭐️ VIP включён" if new_vip else "VIP выключен"
            await q.answer(status, show_alert=True)
            row = get_ad_by_id(ad_id)
            await q.edit_message_text(
                format_ad(row, context),
                reply_markup=admin_ad_kb(ad_id),
                parse_mode="Markdown"
            )
        return ADMIN_MENU

    if data.startswith("adm_del_"):
        ad_id = int(data.replace("adm_del_", ""))
        delete_ad(ad_id)
        await q.answer("🗑 Удалено!", show_alert=True)
        await q.edit_message_text("🗑 Анкета удалена.", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    return ADMIN_MENU


# ─── CANCEL ───────────────────────────────────────────────────────────────────
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        return await show_menu(update, context)
    await update.message.reply_text("Отменено.", reply_markup=lang_keyboard())
    return CHOOSE_LANG


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    photo_handler = MessageHandler(filters.PHOTO, receive_photo)
    done_handler  = CommandHandler("done", done_photos)
    cancel_cmd    = CommandHandler("cancel", cancel_handler)

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(show_menu, pattern="^go_menu$"),
        ],
        states={
            CHOOSE_LANG: [CallbackQueryHandler(choose_lang, pattern="^lang_")],

            MAIN_MENU: [
                CallbackQueryHandler(go_browse,  pattern="^go_browse$"),
                CallbackQueryHandler(go_model,   pattern="^go_model$"),
                CallbackQueryHandler(go_tour,    pattern="^go_tour$"),
                CallbackQueryHandler(go_ad,      pattern="^go_ad$"),
                CallbackQueryHandler(admin_menu, pattern="^(go_admin|adm_)"),
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],

            BR_REGION: [
                CallbackQueryHandler(browse_region, pattern="^br_r_"),
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],
            BR_CITY: [
                CallbackQueryHandler(browse_city, pattern="^(br_c_|br_back_region)"),
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],
            BR_TYPE: [
                CallbackQueryHandler(browse_type, pattern="^(brt_|go_browse)"),
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],

            M_REGION: [CallbackQueryHandler(model_region, pattern="^m_r_")],
            M_CITY:   [CallbackQueryHandler(model_city,   pattern="^(m_c_|m_back_region)")],
            M_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, model_name)],
            M_AGE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, model_age)],
            M_HEIGHT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, model_height)],
            M_WEIGHT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, model_weight)],
            M_MEASUREMENTS:[MessageHandler(filters.TEXT & ~filters.COMMAND, model_measurements)],
            M_NATIONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_nationality)],
            M_LANGUAGES:   [MessageHandler(filters.TEXT & ~filters.COMMAND, model_languages)],
            M_INCALL:      [CallbackQueryHandler(model_incall, pattern="^incall_")],
            M_PRICE_1H:    [MessageHandler(filters.TEXT & ~filters.COMMAND, model_price_1h)],
            M_PRICE_2H:    [MessageHandler(filters.TEXT & ~filters.COMMAND, model_price_2h)],
            M_PRICE_NIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_price_night)],
            M_CONTACT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, model_contact)],
            M_PHOTOS: [photo_handler, done_handler, cancel_cmd,
                       CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],

            T_WHO:       [CallbackQueryHandler(tour_who, pattern="^tour_who_")],
            T_FROM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_from_city)],
            T_TO_REGION: [CallbackQueryHandler(tour_region, pattern="^t_r_")],
            T_TO_CITY:   [CallbackQueryHandler(tour_city,   pattern="^(t_c_|t_back_region)")],
            T_DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_from)],
            T_DATE_TO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_to)],
            T_NOTES:     [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tour_notes),
                CallbackQueryHandler(skip_handler, pattern="^skip$"),
            ],
            T_CONTACT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_contact)],
            T_PHOTOS:    [photo_handler, done_handler, cancel_cmd,
                          CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],

            A_REGION:  [CallbackQueryHandler(ad_region, pattern="^a_r_")],
            A_CITY:    [CallbackQueryHandler(ad_city,   pattern="^(a_c_|a_back_region)")],
            A_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_title)],
            A_DESC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_desc)],
            A_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_contact)],
            A_PHOTOS:  [photo_handler, done_handler, cancel_cmd,
                        CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],

            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu,     pattern="^(go_admin|adm_)"),
                CallbackQueryHandler(show_menu,      pattern="^go_menu$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(moderation_action, pattern="^mod_"))

    print("🚀 Бот Amour Annonce запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
