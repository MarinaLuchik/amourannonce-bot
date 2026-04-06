import logging
import sqlite3
import os
import re
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
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "8549540559:AAEd3EllVX0oQnaRUooL54krXwSwg5Iz_wA")
CHANNEL_ID  = "@amourannonce"
ADMIN_ID    = 2021397237
SUPPORT_URL = "https://t.me/loveparis777"
VMODLS_URL  = "https://t.me/VModls"
MINIAPP_URL = "https://amourannonce.com"
MAX_PHOTOS  = 8

# ─── STATES ───────────────────────────────────────────────────────────────────
(
    CHOOSE_LANG, MAIN_MENU,
    # Модель
    M_REGION, M_CITY, M_NAME, M_AGE, M_NATIONALITY,
    M_HEIGHT, M_WEIGHT, M_MEASUREMENTS,
    M_HAIR, M_INCALL, M_LANGUAGES, M_AVAILABILITY,
    M_PRICES, M_DESCRIPTION, M_CONTACT, M_PHOTOS,
    # Тур
    T_WHO, T_FROM_CITY, T_TO_REGION, T_TO_CITY,
    T_DATE_FROM, T_DATE_TO, T_NAME, T_NOTES, T_CONTACT, T_PHOTOS,
    # Объявление
    A_REGION, A_CITY, A_TITLE, A_DESC, A_CONTACT, A_PHOTOS,
    # Просмотр
    BR_REGION, BR_CITY, BR_TYPE,
    # Админ
    ADMIN_MENU,
    # Быстрое добавление от админа
    ADM_ADD_CITY, ADM_ADD_NAME, ADM_ADD_AGE, ADM_ADD_PRICES,
    ADM_ADD_CONTACT, ADM_ADD_PHOTOS,
) = range(44)

# ─── REGIONS ──────────────────────────────────────────────────────────────────
REGIONS = {
    "🗼 Paris — Centre (1-4)": ["Paris 1er","Paris 2e","Paris 3e","Paris 4e"],
    "🗼 Paris — Rive Gauche (5-7)": ["Paris 5e","Paris 6e","Paris 7e"],
    "🗼 Paris — Grands Boulevards (8-10)": ["Paris 8e","Paris 9e","Paris 10e"],
    "🗼 Paris — Est (11-12)": ["Paris 11e","Paris 12e"],
    "🗼 Paris — Sud (13-15)": ["Paris 13e","Paris 14e","Paris 15e"],
    "🗼 Paris — Ouest & Nord (16-18)": ["Paris 16e","Paris 17e","Paris 18e"],
    "🗼 Paris — Nord-Est (19-20)": ["Paris 19e","Paris 20e"],
    "🏙 Île-de-France — Proche banlieue": [
        "Boulogne-Billancourt","Neuilly-sur-Seine","Levallois-Perret",
        "Issy-les-Moulineaux","Courbevoie","La Défense","Puteaux",
        "Saint-Cloud","Vincennes","Saint-Mandé","Montreuil",
        "Bagnolet","Saint-Denis","Aubervilliers","Pantin",
    ],
    "🏙 Île-de-France — Grande banlieue": [
        "Versailles","Saint-Germain-en-Laye","Massy","Créteil",
        "Évry","Pontoise","Cergy","Melun","Fontainebleau",
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
        "Toulouse","Montpellier","Perpignan","Nîmes","Sète","Béziers","Montauban",
    ],
    "🍷 Nouvelle-Aquitaine": [
        "Bordeaux","Biarritz","Arcachon","Bayonne","La Rochelle",
        "Pau","Périgueux","Limoges","Poitiers",
    ],
    "⚓️ Pays de la Loire": ["Nantes","Angers","Le Mans","Saint-Nazaire"],
    "🥨 Grand Est": ["Strasbourg","Reims","Metz","Nancy","Mulhouse","Colmar"],
    "🍇 Bourgogne-Franche-Comté": ["Dijon","Besançon","Belfort"],
    "🌿 Normandie": ["Rouen","Caen","Le Havre","Deauville","Cherbourg"],
    "🏛 Hauts-de-France": ["Lille","Amiens","Dunkerque","Valenciennes"],
    "🌊 Bretagne": ["Rennes","Brest","Quimper","Saint-Malo","Lorient","Vannes"],
    "🌺 Centre-Val de Loire": ["Tours","Orléans","Blois"],
}

# ─── ТЕКСТЫ ───────────────────────────────────────────────────────────────────
T = {
    "fr": {
        "welcome": (
            "💋 *Amour Annonce*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "La plateforme №1 pour les modèles\n"
            "et professionnels en France 🇫🇷\n\n"
            "Que souhaitez-vous faire ?"
        ),
        "btn_browse":    "🔍  Voir les annonces",
        "btn_model":     "👗  Déposer mon profil",
        "btn_tour":      "✈️  En Tour",
        "btn_ad":        "📢  Publier une annonce",
        "btn_site":      "🌐  Ouvrir le site",
        "btn_support":   "💬  Support — @loveparis777",
        "btn_agency":    "🌟  Agence — @VModls",
        "btn_admin":     "🔐  Admin Panel",
        "btn_back":      "◀️ Retour",
        "btn_cancel":    "✖️ Annuler",
        "btn_done":      "✅ Terminer",
        "btn_skip":      "⏭ Passer",
        "choose_region": "📍 Choisissez une région :",
        "choose_city":   "🏙 Choisissez une ville :",
        "sent_moderation": "✅ *Envoyé en modération !*\nNous vous répondrons sous 24h.",
        "no_ads":        "😔 Aucune annonce pour l'instant.",
        "end_ads":       "— Fin des annonces —",
        "btn_contact":   "💬 Contacter",
        "btn_fav":       "❤️ Favoris",
        "vip_badge":     "⭐️ VIP",
        "btn_tour_model": "👗 Modèle — je pars en tour",
        "btn_tour_host":  "🏨 J'accueille des modèles",
    },
    "en": {
        "welcome": (
            "💋 *Amour Annonce*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "The №1 platform for models\n"
            "and professionals in France 🇫🇷\n\n"
            "What would you like to do?"
        ),
        "btn_browse":    "🔍  Browse listings",
        "btn_model":     "👗  Post my profile",
        "btn_tour":      "✈️  On Tour",
        "btn_ad":        "📢  Post an ad",
        "btn_site":      "🌐  Open website",
        "btn_support":   "💬  Support — @loveparis777",
        "btn_agency":    "🌟  Agency — @VModls",
        "btn_admin":     "🔐  Admin Panel",
        "btn_back":      "◀️ Back",
        "btn_cancel":    "✖️ Cancel",
        "btn_done":      "✅ Done",
        "btn_skip":      "⏭ Skip",
        "choose_region": "📍 Choose a region:",
        "choose_city":   "🏙 Choose a city:",
        "sent_moderation": "✅ *Sent for moderation!*\nWe'll reply within 24h.",
        "no_ads":        "😔 No listings yet.",
        "end_ads":       "— End of listings —",
        "btn_contact":   "💬 Contact",
        "btn_fav":       "❤️ Favourite",
        "vip_badge":     "⭐️ VIP",
        "btn_tour_model": "👗 Model — going on tour",
        "btn_tour_host":  "🏨 I host models",
    }
}

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

def validate_phone(phone):
    """Проверяет что номер телефона правильный."""
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if cleaned.startswith('+') and len(cleaned) >= 10:
        return True
    if cleaned.startswith('0') and len(cleaned) >= 9:
        return True
    return False

def validate_age(age_str):
    try:
        age = int(age_str)
        return 18 <= age <= 65
    except:
        return False

def validate_height(h_str):
    try:
        h = int(h_str)
        return 140 <= h <= 200
    except:
        return False

def validate_weight(w_str):
    try:
        w = int(w_str)
        return 40 <= w <= 120
    except:
        return False

def parse_prices(text):
    """Парсит цены из текста. Ожидает числа в определённом порядке."""
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    slots = ['15min','20min','30min','45min','1h','1h30','2h','3h','soiree','nuit']
    prices = {}
    for i, line in enumerate(lines):
        if i >= len(slots):
            break
        # Извлекаем только число из строки
        nums = re.findall(r'\d+', line)
        if nums:
            prices[slots[i]] = nums[0] + '€'
    return prices

# ─── DATABASE ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS annonces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT, region TEXT, city TEXT,
        name TEXT, age TEXT,
        height TEXT, weight TEXT, measurements TEXT,
        nationality TEXT, languages TEXT, incall TEXT,
        price_15min TEXT, price_20min TEXT, price_30min TEXT,
        price_45min TEXT, price_1h TEXT, price_1h30 TEXT,
        price_2h TEXT, price_3h TEXT, price_soiree TEXT, price_nuit TEXT,
        hair TEXT, availability TEXT, description TEXT,
        contact TEXT, photos TEXT,
        ad_title TEXT, ad_desc TEXT,
        tour_who TEXT, tour_from TEXT,
        tour_date_from TEXT, tour_date_to TEXT, tour_notes TEXT,
        is_vip INTEGER DEFAULT 0,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        source TEXT DEFAULT 'bot'
    )""")
    # Миграции для старых БД
    migrations = [
        "ALTER TABLE annonces ADD COLUMN price_15min TEXT",
        "ALTER TABLE annonces ADD COLUMN price_20min TEXT",
        "ALTER TABLE annonces ADD COLUMN price_30min TEXT",
        "ALTER TABLE annonces ADD COLUMN price_45min TEXT",
        "ALTER TABLE annonces ADD COLUMN price_1h TEXT",
        "ALTER TABLE annonces ADD COLUMN price_1h30 TEXT",
        "ALTER TABLE annonces ADD COLUMN price_2h TEXT",
        "ALTER TABLE annonces ADD COLUMN price_3h TEXT",
        "ALTER TABLE annonces ADD COLUMN price_soiree TEXT",
        "ALTER TABLE annonces ADD COLUMN price_nuit TEXT",
        "ALTER TABLE annonces ADD COLUMN hair TEXT",
        "ALTER TABLE annonces ADD COLUMN availability TEXT",
        "ALTER TABLE annonces ADD COLUMN description TEXT",
        "ALTER TABLE annonces ADD COLUMN expires_at TIMESTAMP",
        "ALTER TABLE annonces ADD COLUMN source TEXT DEFAULT 'bot'",
    ]
    for m in migrations:
        try:
            c.execute(m)
        except Exception:
            pass
    conn.commit()
    conn.close()

def save_ad(ad, is_vip=False):
    conn = sqlite3.connect("annonces.db")
    c = conn.cursor()
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    prices = ad.get('prices', {})
    c.execute("""INSERT INTO annonces
        (type,region,city,name,age,height,weight,measurements,
        nationality,languages,incall,
        price_15min,price_20min,price_30min,price_45min,
        price_1h,price_1h30,price_2h,price_3h,price_soiree,price_nuit,
        hair,availability,description,
        contact,photos,ad_title,ad_desc,
        tour_who,tour_from,tour_date_from,tour_date_to,tour_notes,
        is_vip,user_id,expires_at,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ad.get("type","model"), ad.get("region","-"), ad.get("city","-"),
            ad.get("name","-"), ad.get("age","-"),
            ad.get("height","-"), ad.get("weight","-"), ad.get("measurements","-"),
            ad.get("nationality","-"), ad.get("languages","-"), ad.get("incall","-"),
            prices.get("15min","-"), prices.get("20min","-"),
            prices.get("30min","-"), prices.get("45min","-"),
            prices.get("1h","-"), prices.get("1h30","-"),
            prices.get("2h","-"), prices.get("3h","-"),
            prices.get("soiree","-"), prices.get("nuit","-"),
            ad.get("hair","-"), ad.get("availability","-"),
            ad.get("description","-"),
            ad.get("contact","-"),
            ",".join(ad.get("photos", [])),
            ad.get("ad_title","-"), ad.get("ad_desc","-"),
            ad.get("tour_who","-"), ad.get("tour_from","-"),
            ad.get("tour_date_from","-"), ad.get("tour_date_to","-"),
            ad.get("tour_notes","-"),
            1 if is_vip else 0,
            ad.get("user_id"),
            expires,
            ad.get("source","bot"),
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
        c.execute("SELECT COUNT(*) FROM annonces")
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
        [InlineKeyboardButton(tx("btn_support", ctx), url=SUPPORT_URL)],
        [InlineKeyboardButton(tx("btn_agency", ctx), url=VMODLS_URL)],
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
                row.append(InlineKeyboardButton(keys[i+j], callback_data=f"{prefix}_r_{i+j}"))
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

def hair_kb(ctx):
    l = lang(ctx)
    fr = l == "fr"
    options = [
        ("👱 Blonde", "hair_blonde"),
        ("🟤 Brune", "hair_brune"),
        ("🔴 Rousse", "hair_rousse"),
        ("⬛ Noire", "hair_noire"),
        ("🌰 Châtain", "hair_chatain"),
        ("🎨 Colorée", "hair_coloree"),
        ("✂️ Courte", "hair_courte"),
    ]
    kb = []
    row = []
    for label, data in options:
        row.append(InlineKeyboardButton(label, callback_data=data))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(tx("btn_cancel", ctx), callback_data="go_menu")])
    return InlineKeyboardMarkup(kb)

def incall_kb(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Incall uniquement", callback_data="incall_in")],
        [InlineKeyboardButton("🚗 Outcall uniquement", callback_data="incall_out")],
        [InlineKeyboardButton("🏠🚗 Incall + Outcall", callback_data="incall_both")],
        [InlineKeyboardButton(tx("btn_cancel", ctx), callback_data="go_menu")],
    ])

def languages_kb(ctx):
    options = [
        ("🇫🇷 Français", "lang_fr"), ("🇬🇧 Anglais", "lang_en"),
        ("🇷🇺 Russe", "lang_ru"), ("🇪🇸 Espagnol", "lang_es"),
        ("🇮🇹 Italien", "lang_it"), ("🇩🇪 Allemand", "lang_de"),
        ("🇵🇹 Portugais", "lang_pt"), ("🇸🇦 Arabe", "lang_ar"),
        ("🇺🇦 Ukrainien", "lang_uk"), ("🇯🇵 Japonais", "lang_jp"),
    ]
    kb = []
    row = []
    for label, data in options:
        row.append(InlineKeyboardButton(label, callback_data=data))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([
        InlineKeyboardButton("✅ Confirmer", callback_data="langs_done"),
        InlineKeyboardButton(tx("btn_cancel", ctx), callback_data="go_menu"),
    ])
    return InlineKeyboardMarkup(kb)

def availability_kb(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕐 24h/24", callback_data="avail_24h")],
        [InlineKeyboardButton("☀️ En journée", callback_data="avail_day"),
         InlineKeyboardButton("🌙 En soirée", callback_data="avail_evening")],
        [InlineKeyboardButton("🌃 Nuits uniquement", callback_data="avail_night")],
        [InlineKeyboardButton("📅 Weekends", callback_data="avail_weekend"),
         InlineKeyboardButton("📞 Sur rendez-vous", callback_data="avail_rdv")],
        [InlineKeyboardButton(tx("btn_cancel", ctx), callback_data="go_menu")],
    ])

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

def moderation_kb(ad_key):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{ad_key}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{ad_key}"),
        ],
        [InlineKeyboardButton("⭐️ Одобрить как VIP", callback_data=f"mod_vip_{ad_key}")],
    ])

def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ожидают модерации", callback_data="adm_pending")],
        [InlineKeyboardButton("➕ Добавить анкету", callback_data="adm_add")],
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


# ─── УВЕДОМЛЕНИЕ АДМИНУ ───────────────────────────────────────────────────────
def build_admin_notification(ad, source="бот"):
    flow = ad.get("type", ad.get("flow", "model"))
    type_labels = {"model": "👗 Профиль модели", "tour": "✈️ Тур", "ad": "📢 Объявление"}
    type_label = type_labels.get(flow, "📋 Анкета")
    prices = ad.get("prices", {})

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
            f"🌍 Нац.: {ad.get('nationality', '—')}",
            f"📏 Рост: {ad.get('height', '—')} см  ⚖️ Вес: {ad.get('weight', '—')} кг",
            f"📐 Параметры: {ad.get('measurements', '—')}",
            f"💇 Волосы: {ad.get('hair', '—')}",
            f"🗣 Языки: {ad.get('languages', '—')}",
            f"🏠 {ad.get('incall', '—')}",
            f"🕐 Доступность: {ad.get('availability', '—')}",
        ]
        if prices:
            price_lines = []
            for slot, val in prices.items():
                if val and val != '-':
                    price_lines.append(f"{slot}: {val}")
            if price_lines:
                lines.append(f"💶 Тарифы: {' | '.join(price_lines)}")
        if ad.get('description'):
            lines.append(f"📝 О себе: {ad.get('description', '—')}")
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


# ─── FORMAT AD ────────────────────────────────────────────────────────────────
def format_ad(row, ctx):
    try:
        type_   = row[1]
        city    = row[3]
        name    = row[4]
        age     = row[5]
        height  = row[6]
        weight  = row[7]
        measurements = row[8]
        nationality  = row[9]
        languages    = row[10]
        incall       = row[11]
        # Новая схема: цены начиная с колонки 12
        contact  = row[25] if len(row) > 25 else row[15]
        tour_who = row[29] if len(row) > 29 else "-"
        tour_from = row[30] if len(row) > 30 else "-"
        tour_date_from = row[31] if len(row) > 31 else "-"
        tour_date_to = row[32] if len(row) > 32 else "-"
        tour_notes = row[33] if len(row) > 33 else "-"
        is_vip = row[34] if len(row) > 34 else 0
        ad_title = row[27] if len(row) > 27 else "-"
        ad_desc = row[28] if len(row) > 28 else "-"
        description = row[24] if len(row) > 24 else "-"
        hair = row[21] if len(row) > 21 else "-"
        availability = row[22] if len(row) > 22 else "-"
        # Цены
        price_1h = row[16] if len(row) > 16 else "-"
        price_nuit = row[21] if len(row) > 21 else "-"
    except Exception:
        return "Ошибка отображения анкеты"

    vip = "⭐️ VIP | " if is_vip else ""

    if type_ == "model":
        lines = [
            f"{vip}👗 *{name}*, {age} ans — {city}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"📏 {height} cm  ⚖️ {weight} kg  📐 {measurements}",
            f"🌍 {nationality}  🗣 {languages}",
            f"🏠 {incall}",
        ]
        if price_1h and price_1h != "-":
            lines.append(f"💶 1h: *{price_1h}*")
        if description and description != "-":
            lines.append(f"📝 {description}")
        lines.append(f"📞 {contact}")
    elif type_ == "tour":
        who_label = "👗 Modèle" if tour_who == "model" else "🏨 Hôte"
        lines = [
            f"{vip}✈️ *En Tour* — {who_label}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"📍 {city}",
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
        photos_str = row[26] if len(row) > 26 else ""
        photos = [p for p in photos_str.split(",") if p] if photos_str else []
        ad_id = row[0]
        contact = row[25] if len(row) > 25 else "-"
        try:
            if photos:
                await q.message.reply_photo(photo=photos[0], caption=caption, parse_mode="Markdown")
            else:
                await q.message.reply_text(caption, parse_mode="Markdown")
            await q.message.reply_text("⬆️", reply_markup=ad_action_kb(ad_id, contact, context))
        except Exception as e:
            logger.error(f"Ошибка: {e}")
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
    context.user_data["selected_langs"] = []
    await q.edit_message_text(
        "👗 *Déposer mon profil*\n\n"
        "📍 Étape 1/15 — Choisissez votre région :",
        parse_mode="Markdown",
        reply_markup=region_kb(context, "m")
    )
    return M_REGION

async def model_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("m_r_", ""))
    region = list(REGIONS.keys())[idx]
    context.user_data["region"] = region
    await q.edit_message_text(
        f"📍 Étape 1/15 — {region}\n\nChoisissez votre ville :",
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
        f"✅ Ville: *{city}*\n\n"
        f"👤 Étape 2/15 — Votre prénom :\n\n"
        f"_Exemple: Sofia, Marie, Anna..._",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_NAME

async def model_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 30:
        await update.message.reply_text(
            "⚠️ Le prénom doit contenir entre 2 et 30 caractères.\n_Exemple: Sofia_",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_NAME
    context.user_data["name"] = name
    await update.message.reply_text(
        f"✅ Prénom: *{name}*\n\n"
        f"🎂 Étape 3/15 — Votre âge :\n\n"
        f"_Entrez un nombre entre 18 et 65 (ex: 25)_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_AGE

async def model_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    age_str = update.message.text.strip()
    if not validate_age(age_str):
        await update.message.reply_text(
            "⚠️ Âge invalide. Entrez un nombre entre 18 et 65.\n_Exemple: 25_",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_AGE
    context.user_data["age"] = age_str
    await update.message.reply_text(
        f"✅ Âge: *{age_str} ans*\n\n"
        f"🌍 Étape 4/15 — Votre nationalité :\n\n"
        f"_Exemple: Ukrainienne, Russe, Française, Brésilienne..._",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_NATIONALITY

async def model_nationality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nat = update.message.text.strip()
    if len(nat) < 2:
        await update.message.reply_text(
            "⚠️ Veuillez entrer votre nationalité.\n_Exemple: Ukrainienne_",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_NATIONALITY
    context.user_data["nationality"] = nat
    await update.message.reply_text(
        f"✅ Nationalité: *{nat}*\n\n"
        f"📏 Étape 5/15 — Votre taille en cm :\n\n"
        f"_Entrez un nombre entre 140 et 200 (ex: 168)_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_HEIGHT

async def model_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    h = update.message.text.strip()
    if not validate_height(h):
        await update.message.reply_text(
            "⚠️ Taille invalide. Entrez un nombre entre 140 et 200.\n_Exemple: 168_",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_HEIGHT
    context.user_data["height"] = h
    await update.message.reply_text(
        f"✅ Taille: *{h} cm*\n\n"
        f"⚖️ Étape 6/15 — Votre poids en kg :\n\n"
        f"_Entrez un nombre entre 40 et 120 (ex: 55)_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_WEIGHT

async def model_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    w = update.message.text.strip()
    if not validate_weight(w):
        await update.message.reply_text(
            "⚠️ Poids invalide. Entrez un nombre entre 40 et 120.\n_Exemple: 55_",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_WEIGHT
    context.user_data["weight"] = w
    await update.message.reply_text(
        f"✅ Poids: *{w} kg*\n\n"
        f"📐 Étape 7/15 — Vos mensurations :\n\n"
        f"_Format: Bonnet — Taille — Hanches_\n"
        f"_Exemple: 90C — 60 — 90_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_MEASUREMENTS

async def model_measurements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message.text.strip()
    if len(m) < 3:
        await update.message.reply_text(
            "⚠️ Format invalide.\n_Exemple: 90C — 60 — 90_",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_MEASUREMENTS
    context.user_data["measurements"] = m
    await update.message.reply_text(
        f"✅ Mensurations: *{m}*\n\n"
        f"💇 Étape 8/15 — Couleur de cheveux :",
        parse_mode="Markdown",
        reply_markup=hair_kb(context)
    )
    return M_HAIR

async def model_hair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    hair_map = {
        "hair_blonde": "Blonde", "hair_brune": "Brune",
        "hair_rousse": "Rousse", "hair_noire": "Noire",
        "hair_chatain": "Châtain", "hair_coloree": "Colorée",
        "hair_courte": "Courte",
    }
    hair = hair_map.get(q.data, "Autre")
    context.user_data["hair"] = hair
    await q.edit_message_text(
        f"✅ Cheveux: *{hair}*\n\n"
        f"🏠 Étape 9/15 — Type de service :",
        parse_mode="Markdown",
        reply_markup=incall_kb(context)
    )
    return M_INCALL

async def model_incall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mapping = {
        "incall_in": "Incall uniquement",
        "incall_out": "Outcall uniquement",
        "incall_both": "Incall + Outcall"
    }
    incall = mapping.get(q.data, "-")
    context.user_data["incall"] = incall
    # Инициализируем список языков
    context.user_data["selected_langs"] = []
    await q.edit_message_text(
        f"✅ Service: *{incall}*\n\n"
        f"🗣 Étape 10/15 — Langues parlées :\n\n"
        f"_Sélectionnez une ou plusieurs langues, puis appuyez sur ✅ Confirmer_",
        parse_mode="Markdown",
        reply_markup=languages_kb(context)
    )
    return M_LANGUAGES

async def model_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    lang_map = {
        "lang_fr": "Français", "lang_en": "Anglais",
        "lang_ru": "Russe", "lang_es": "Espagnol",
        "lang_it": "Italien", "lang_de": "Allemand",
        "lang_pt": "Portugais", "lang_ar": "Arabe",
        "lang_uk": "Ukrainien", "lang_jp": "Japonais",
    }

    if q.data == "langs_done":
        selected = context.user_data.get("selected_langs", [])
        if not selected:
            await q.answer("⚠️ Sélectionnez au moins une langue!", show_alert=True)
            return M_LANGUAGES
        langs_str = ", ".join(selected)
        context.user_data["languages"] = langs_str
        await q.edit_message_text(
            f"✅ Langues: *{langs_str}*\n\n"
            f"🕐 Étape 11/15 — Vos disponibilités :",
            parse_mode="Markdown",
            reply_markup=availability_kb(context)
        )
        return M_AVAILABILITY

    if q.data in lang_map:
        selected = context.user_data.get("selected_langs", [])
        lang_name = lang_map[q.data]
        if lang_name in selected:
            selected.remove(lang_name)
        else:
            selected.append(lang_name)
        context.user_data["selected_langs"] = selected
        selected_str = ", ".join(selected) if selected else "Aucune"
        await q.answer(f"✅ Sélection: {selected_str}")
    return M_LANGUAGES

async def model_availability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    avail_map = {
        "avail_24h": "24h/24",
        "avail_day": "En journée",
        "avail_evening": "En soirée",
        "avail_night": "Nuits uniquement",
        "avail_weekend": "Weekends",
        "avail_rdv": "Sur rendez-vous",
    }
    avail = avail_map.get(q.data, "-")
    context.user_data["availability"] = avail
    await q.edit_message_text(
        f"✅ Disponibilités: *{avail}*\n\n"
        f"💶 Étape 12/15 — Vos tarifs :\n\n"
        f"Entrez vos prix *ligne par ligne* (uniquement les chiffres) :\n\n"
        f"```\n"
        f"15min: 80\n"
        f"20min: 100\n"
        f"30min: 150\n"
        f"45min: 200\n"
        f"1h: 300\n"
        f"1h30: 420\n"
        f"2h: 550\n"
        f"3h: 750\n"
        f"Soirée: 1200\n"
        f"Nuit: 1800\n"
        f"```\n"
        f"_Laissez 0 si vous n'offrez pas ce créneau._",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_PRICES

async def model_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prices = parse_prices(text)

    if not prices or not any(v != '0' for v in prices.values()):
        await update.message.reply_text(
            "⚠️ Format invalide. Entrez les prix ligne par ligne:\n\n"
            "```\n15min: 80\n20min: 100\n30min: 150\n45min: 200\n"
            "1h: 300\n1h30: 420\n2h: 550\n3h: 750\nSoirée: 1200\nNuit: 1800\n```\n"
            "_Entrez 0 si vous n'offrez pas ce créneau._",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_PRICES

    context.user_data["prices"] = prices
    price_summary = "\n".join([f"• {k}: {v}" for k, v in prices.items() if v and v != '0'])
    await update.message.reply_text(
        f"✅ Tarifs enregistrés:\n{price_summary}\n\n"
        f"📝 Étape 13/15 — Description (à propos de vous) :\n\n"
        f"_Exemple: Douce et élégante, je reçois dans un appartement discret..._\n"
        f"_Minimum 20 caractères._",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_DESCRIPTION

async def model_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if len(desc) < 20:
        await update.message.reply_text(
            "⚠️ Description trop courte. Minimum 20 caractères.\n"
            "_Exemple: Douce et élégante, je reçois dans un appartement discret et propre..._",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_DESCRIPTION
    context.user_data["description"] = desc
    await update.message.reply_text(
        f"✅ Description enregistrée.\n\n"
        f"📞 Étape 14/15 — Votre contact :\n\n"
        f"_Entrez votre Telegram @username OU votre numéro de téléphone_\n\n"
        f"Exemples:\n"
        f"• @votre_pseudo\n"
        f"• +33 6 12 34 56 78\n"
        f"• +33612345678",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_CONTACT

async def model_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()

    # Валидация — должен быть @username или номер телефона
    is_tg = contact.startswith("@") and len(contact) > 2
    is_phone = validate_phone(contact)

    if not is_tg and not is_phone:
        await update.message.reply_text(
            "⚠️ Format invalide.\n\n"
            "Entrez soit:\n"
            "• Un Telegram: *@votre_pseudo*\n"
            "• Un téléphone: *+33 6 12 34 56 78*",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return M_CONTACT

    context.user_data["contact"] = contact
    context.user_data["photos"] = []
    await update.message.reply_text(
        f"✅ Contact: *{contact}*\n\n"
        f"📸 Étape 15/15 — Photos :\n\n"
        f"Envoyez vos photos (max {MAX_PHOTOS})\n"
        f"_Minimum 1 photo requise._\n\n"
        f"Quand vous avez terminé → /done",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return M_PHOTOS


# ─── TOUR FLOW ────────────────────────────────────────────────────────────────
async def go_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["flow"] = "tour"
    l = lang(context)
    await q.edit_message_text(
        "✈️ *En Tour*\n\nVous êtes :" if l=="fr" else "✈️ *On Tour*\n\nYou are:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tx("btn_tour_model", context), callback_data="tour_who_model")],
            [InlineKeyboardButton(tx("btn_tour_host", context), callback_data="tour_who_host")],
            [InlineKeyboardButton(
                "🔍 Je cherche un tour → @loveparis777" if l=="fr" else "🔍 Looking for a tour → @loveparis777",
                url=SUPPORT_URL
            )],
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
        await q.edit_message_text(
            "🛫 Votre ville de départ :\n\n_Exemple: Moscou, Kiev, Varsovie..._",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return T_FROM_CITY
    else:
        await q.edit_message_text(
            tx("choose_region", context),
            reply_markup=region_kb(context, "t")
        )
        return T_TO_REGION

async def tour_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_from"] = update.message.text.strip()
    await update.message.reply_text(
        tx("choose_region", context),
        reply_markup=region_kb(context, "t")
    )
    return T_TO_REGION

async def tour_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("t_r_", ""))
    region = list(REGIONS.keys())[idx]
    context.user_data["region"] = region
    await q.edit_message_text(
        f"{region}\n\nChoisissez la ville de destination :",
        reply_markup=city_kb(context, region, "t")
    )
    return T_TO_CITY

async def tour_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "t_back_region":
        await q.edit_message_text(tx("choose_region", context), reply_markup=region_kb(context, "t"))
        return T_TO_REGION
    city = q.data.replace("t_c_", "")
    context.user_data["city"] = city
    await q.edit_message_text(
        f"✅ Destination: *{city}*\n\n"
        f"📅 Date d'arrivée :\n\n_Exemple: 15.04 ou 15/04/2026_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return T_DATE_FROM

async def tour_date_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_date_from"] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Date de départ :\n\n_Exemple: 20.04 ou 20/04/2026_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return T_DATE_TO

async def tour_date_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_date_to"] = update.message.text.strip()
    await update.message.reply_text(
        "👤 Votre prénom :\n\n_Exemple: Sofia_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return T_NAME

async def tour_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Notes (tarifs, conditions, hébergement) :\n\n"
        "_Exemple: Cherche appartement, tarif 200€/h..._\n\n"
        "Ou appuyez sur Passer →",
        parse_mode="Markdown",
        reply_markup=skip_cancel_kb(context)
    )
    return T_NOTES

async def tour_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_notes"] = update.message.text.strip()
    await update.message.reply_text(
        "📞 Votre contact :\n\n"
        "_@votre_telegram ou +33 6 12 34 56 78_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return T_CONTACT

async def tour_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()
    is_tg = contact.startswith("@") and len(contact) > 2
    is_phone = validate_phone(contact)
    if not is_tg and not is_phone:
        await update.message.reply_text(
            "⚠️ Format invalide.\n• @pseudo\n• +33 6 12 34 56 78",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return T_CONTACT
    context.user_data["contact"] = contact
    context.user_data["photos"] = []
    await update.message.reply_text(
        f"📸 Photos (max {MAX_PHOTOS}) → /done quand terminé",
        reply_markup=cancel_kb(context)
    )
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
        f"📝 Titre de l'annonce :\n\n_Exemple: Massage relaxant Paris 8e_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return A_TITLE

async def ad_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_title"] = update.message.text.strip()
    await update.message.reply_text(
        "📋 Description :\n\n_Décrivez votre service en détail..._",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return A_DESC

async def ad_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_desc"] = update.message.text.strip()
    await update.message.reply_text(
        "📞 Contact :\n\n_@pseudo ou +33 6 12 34 56 78_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
    return A_CONTACT

async def ad_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()
    is_tg = contact.startswith("@") and len(contact) > 2
    is_phone = validate_phone(contact)
    if not is_tg and not is_phone:
        await update.message.reply_text(
            "⚠️ Format invalide.\n• @pseudo\n• +33 6 12 34 56 78",
            parse_mode="Markdown",
            reply_markup=cancel_kb(context)
        )
        return A_CONTACT
    context.user_data["contact"] = contact
    context.user_data["photos"] = []
    await update.message.reply_text(
        f"📸 Photos (max {MAX_PHOTOS}) → /done quand terminé",
        reply_markup=cancel_kb(context)
    )
    return A_PHOTOS


# ─── ФОТО ─────────────────────────────────────────────────────────────────────
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"⚠️ Maximum {MAX_PHOTOS} photos. Envoyez /done")
        return None
    file_id = update.message.photo[-1].file_id
    photos.append(file_id)
    context.user_data["photos"] = photos
    count = len(photos)
    if count >= MAX_PHOTOS:
        await update.message.reply_text(f"✅ Photo {count}/{MAX_PHOTOS} — Maximum! → /done")
    else:
        await update.message.reply_text(f"✅ Photo {count}/{MAX_PHOTOS} — Continuez ou → /done")
    return None

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])
    if not photos:
        await update.message.reply_text("⚠️ Envoyez au moins une photo avant de terminer.")
        return None

    user_id = update.effective_user.id
    flow = context.user_data.get("flow", "model")
    ad_key = str(user_id)
    context.user_data["type"] = flow
    context.user_data["user_id"] = user_id
    context.user_data["source"] = "bot"

    pending_ads[ad_key] = dict(context.user_data)

    await update.message.reply_text(
        tx("sent_moderation", context),
        reply_markup=main_menu_kb(context, user_id),
        parse_mode="Markdown"
    )

    # Уведомление админу на русском
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
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="👇 *Выбери действие:*",
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
    await q.edit_message_text(
        "📞 Contact :\n\n_@pseudo ou +33 6 12 34 56 78_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(context)
    )
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
    status = "⭐️ VIP" if is_vip else "standard"
    await q.edit_message_text(
        f"✅ *Анкета одобрена и опубликована!*\n🆔 ID: {ad_id} | {status}",
        parse_mode="Markdown"
    )


# ─── ПУБЛИКАЦИЯ В КАНАЛ ───────────────────────────────────────────────────────
async def publish_to_channel(context, ad, is_vip=False):
    flow = ad.get("type", "model")
    city = ad.get("city", "-")
    vip = "⭐️ VIP | " if is_vip else ""
    vip_tag = "#vip " if is_vip else ""
    city_tag = city.lower().replace(" ","_").replace("-","_").replace("'","").replace(".","")
    prices = ad.get("prices", {})

    if flow == "model":
        price_line = ""
        if prices.get("1h") and prices["1h"] != "0":
            price_line = f"1h: *{prices['1h']}€*"
        if prices.get("nuit") and prices["nuit"] != "0":
            price_line += f"  |  Nuit: *{prices['nuit']}€*"
        caption = (
            f"{vip}👗 *{ad.get('name')}, {ad.get('age')} ans* — {city}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📏 {ad.get('height')} cm  ⚖️ {ad.get('weight')} kg\n"
            f"🌍 {ad.get('nationality')}  🗣 {ad.get('languages')}\n"
            f"🏠 {ad.get('incall')}\n"
        )
        if price_line:
            caption += f"💶 {price_line}\n"
        if ad.get('description') and ad['description'] != '-':
            desc = ad['description'][:200]
            caption += f"📝 {desc}\n"
        caption += f"📞 {ad.get('contact')}\n\n{vip_tag}#{city_tag} #modele #amourannonce"
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
                chat_id=CHANNEL_ID, photo=photos[0],
                caption=caption, parse_mode="Markdown"
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

    if data == "adm_add":
        # Быстрое добавление анкеты от админа
        context.user_data["flow"] = "model"
        context.user_data["source"] = "admin"
        context.user_data["selected_langs"] = []
        await q.edit_message_text(
            "➕ *Добавить анкету напрямую*\n\n"
            "📍 Выберите регион:",
            parse_mode="Markdown",
            reply_markup=region_kb(context, "m")
        )
        return M_REGION

    if data == "adm_stats":
        total, vip, today, from_site = get_db_stats()
        pending = len(pending_ads)
        await q.edit_message_text(
            f"📊 *Статистика*\n"
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

    if data == "adm_pending":
        if not pending_ads:
            await q.edit_message_text("✅ Нет заявок на модерации.", reply_markup=admin_menu_kb())
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
        try:
            c.execute("""SELECT id,type,city,name,is_vip,source,created_at
                FROM annonces WHERE expires_at > ?
                ORDER BY created_at DESC LIMIT 20""",
                (datetime.now().isoformat(),))
        except Exception:
            c.execute("SELECT id,type,city,name,is_vip,created_at FROM annonces ORDER BY created_at DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await q.edit_message_text("Нет анкет.", reply_markup=admin_menu_kb())
            return ADMIN_MENU
        kb = []
        for row in rows:
            ad_id = row[0]; type_ = row[1]; city = row[2]; name = row[3]; is_vip = row[4]
            vip_icon = "⭐️ " if is_vip else ""
            label = f"{vip_icon}{type_[:1].upper()} | {city} | {name}"
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
            new_vip = 0 if row[34] else 1
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


# ─── БЫСТРОЕ ДОБАВЛЕНИЕ ОТ АДМИНА ────────────────────────────────────────────
async def admin_approve_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Когда админ заполняет анкету — она публикуется сразу без модерации."""
    if update.effective_user.id != ADMIN_ID:
        return

    photos = context.user_data.get("photos", [])
    if not photos:
        await update.message.reply_text("⚠️ Добавьте хотя бы одно фото.")
        return None

    context.user_data["type"] = "model"
    context.user_data["user_id"] = ADMIN_ID
    context.user_data["source"] = "admin"

    ad = dict(context.user_data)
    ad_id = save_ad(ad, is_vip=False)
    await publish_to_channel(context, ad, is_vip=False)

    await update.message.reply_text(
        f"✅ *Анкета добавлена и опубликована!*\n🆔 ID: {ad_id}",
        parse_mode="Markdown",
        reply_markup=admin_menu_kb()
    )
    context.user_data.clear()
    return ADMIN_MENU


# ─── CANCEL ───────────────────────────────────────────────────────────────────
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        return await show_menu(update, context)
    await update.message.reply_text("Annulé.", reply_markup=lang_keyboard())
    return CHOOSE_LANG


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    photo_handler = MessageHandler(filters.PHOTO, receive_photo)
    done_handler  = CommandHandler("done", done_photos)
    admin_done    = CommandHandler("done", admin_approve_direct)
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

            # Model flow
            M_REGION: [
                CallbackQueryHandler(model_region, pattern="^m_r_"),
                CallbackQueryHandler(admin_menu, pattern="^(go_admin|adm_)"),
            ],
            M_CITY:         [CallbackQueryHandler(model_city, pattern="^(m_c_|m_back_region)")],
            M_NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, model_name)],
            M_AGE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, model_age)],
            M_NATIONALITY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, model_nationality)],
            M_HEIGHT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, model_height)],
            M_WEIGHT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, model_weight)],
            M_MEASUREMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_measurements)],
            M_HAIR:         [CallbackQueryHandler(model_hair, pattern="^hair_")],
            M_INCALL:       [CallbackQueryHandler(model_incall, pattern="^incall_")],
            M_LANGUAGES:    [CallbackQueryHandler(model_languages, pattern="^(lang_|langs_done)")],
            M_AVAILABILITY: [CallbackQueryHandler(model_availability, pattern="^avail_")],
            M_PRICES:       [MessageHandler(filters.TEXT & ~filters.COMMAND, model_prices)],
            M_DESCRIPTION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, model_description)],
            M_CONTACT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, model_contact)],
            M_PHOTOS: [
                photo_handler,
                CommandHandler("done", done_photos),
                cancel_cmd,
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],

            # Tour flow
            T_WHO:       [CallbackQueryHandler(tour_who, pattern="^tour_who_")],
            T_FROM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_from_city)],
            T_TO_REGION: [CallbackQueryHandler(tour_region, pattern="^t_r_")],
            T_TO_CITY:   [CallbackQueryHandler(tour_city, pattern="^(t_c_|t_back_region)")],
            T_DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_from)],
            T_DATE_TO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_to)],
            T_NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_name)],
            T_NOTES:     [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tour_notes),
                CallbackQueryHandler(skip_handler, pattern="^skip$"),
            ],
            T_CONTACT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_contact)],
            T_PHOTOS:    [
                photo_handler,
                CommandHandler("done", done_photos),
                cancel_cmd,
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],

            # Ad flow
            A_REGION:  [CallbackQueryHandler(ad_region, pattern="^a_r_")],
            A_CITY:    [CallbackQueryHandler(ad_city, pattern="^(a_c_|a_back_region)")],
            A_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_title)],
            A_DESC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_desc)],
            A_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_contact)],
            A_PHOTOS:  [
                photo_handler,
                CommandHandler("done", done_photos),
                cancel_cmd,
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],

            # Admin
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu, pattern="^(go_admin|adm_)"),
                CallbackQueryHandler(show_menu, pattern="^go_menu$"),
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

    print("🚀 Бот Amour Annonce v6 запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
