import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    CallbackQuery,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("amour_annonce_bot")


# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = "@amourannonce"
ADMIN_ID = 2021397237
SUPPORT_URL = "https://t.me/loveparis777"
VMODLS_URL = "https://t.me/VModls"
MINIAPP_URL = "https://amourannonce.com"
DB_PATH = os.environ.get("DB_PATH", "annonces.db")
MAX_PHOTOS = 8
AD_TTL_DAYS = 30


# =========================================================
# STATES
# =========================================================
(
    CHOOSE_LANG,
    MAIN_MENU,

    M_REGION, M_CITY, M_NAME, M_AGE, M_NATIONALITY,
    M_HEIGHT, M_WEIGHT, M_MEASUREMENTS, M_HAIR,
    M_INCALL, M_LANGUAGES, M_AVAILABILITY,
    M_PRICES, M_DESCRIPTION, M_CONTACT, M_PHOTOS,

    T_WHO, T_FROM_CITY, T_TO_REGION, T_TO_CITY,
    T_DATE_FROM, T_DATE_TO, T_NAME, T_NOTES,
    T_CONTACT, T_PHOTOS,

    A_REGION, A_CITY, A_TITLE, A_DESC, A_CONTACT, A_PHOTOS,

    BR_REGION, BR_CITY, BR_TYPE,

    ADMIN_MENU,
) = range(38)


# =========================================================
# REGIONS / CITIES
# =========================================================
REGIONS: Dict[str, List[str]] = {
    "🗼 Paris — Centre (1-4)": ["Paris 1er", "Paris 2e", "Paris 3e", "Paris 4e"],
    "🗼 Paris — Rive Gauche (5-7)": ["Paris 5e", "Paris 6e", "Paris 7e"],
    "🗼 Paris — Grands Boulevards (8-10)": ["Paris 8e", "Paris 9e", "Paris 10e"],
    "🗼 Paris — Est (11-12)": ["Paris 11e", "Paris 12e"],
    "🗼 Paris — Sud (13-15)": ["Paris 13e", "Paris 14e", "Paris 15e"],
    "🗼 Paris — Ouest & Nord (16-18)": ["Paris 16e", "Paris 17e", "Paris 18e"],
    "🗼 Paris — Nord-Est (19-20)": ["Paris 19e", "Paris 20e"],
    "🏙 Île-de-France — Proche banlieue": [
        "Boulogne-Billancourt", "Neuilly-sur-Seine", "Levallois-Perret",
        "Issy-les-Moulineaux", "Courbevoie", "La Défense", "Puteaux",
        "Saint-Cloud", "Vincennes", "Saint-Mandé", "Montreuil",
        "Bagnolet", "Saint-Denis", "Aubervilliers", "Pantin",
    ],
    "🏙 Île-de-France — Grande banlieue": [
        "Versailles", "Saint-Germain-en-Laye", "Massy", "Créteil",
        "Évry", "Pontoise", "Cergy", "Melun", "Fontainebleau",
    ],
    "🏔 Auvergne-Rhône-Alpes": [
        "Lyon", "Annecy", "Grenoble", "Chambéry", "Clermont-Ferrand",
        "Courchevel", "Méribel", "Val d'Isère", "Megève", "Chamonix",
        "Aix-les-Bains", "Albertville", "Valence", "Saint-Étienne",
    ],
    "🌊 Provence-Alpes-Côte d'Azur": [
        "Nice", "Cannes", "Antibes", "Monaco", "Marseille",
        "Aix-en-Provence", "Toulon", "Saint-Tropez", "Juan-les-Pins",
        "Menton", "Grasse", "Villefranche-sur-Mer", "Avignon", "Fréjus",
    ],
    "🌸 Occitanie": ["Toulouse", "Montpellier", "Perpignan", "Nîmes", "Sète", "Béziers", "Montauban"],
    "🍷 Nouvelle-Aquitaine": [
        "Bordeaux", "Biarritz", "Arcachon", "Bayonne", "La Rochelle",
        "Pau", "Périgueux", "Limoges", "Poitiers",
    ],
    "⚓️ Pays de la Loire": ["Nantes", "Angers", "Le Mans", "Saint-Nazaire"],
    "🥨 Grand Est": ["Strasbourg", "Reims", "Metz", "Nancy", "Mulhouse", "Colmar"],
    "🍇 Bourgogne-Franche-Comté": ["Dijon", "Besançon", "Belfort"],
    "🌿 Normandie": ["Rouen", "Caen", "Le Havre", "Deauville", "Cherbourg"],
    "🏛 Hauts-de-France": ["Lille", "Amiens", "Dunkerque", "Valenciennes"],
    "🌊 Bretagne": ["Rennes", "Brest", "Quimper", "Saint-Malo", "Lorient", "Vannes"],
    "🌺 Centre-Val de Loire": ["Tours", "Orléans", "Blois"],
}

REGION_KEYS = list(REGIONS.keys())


# =========================================================
# TEXTS
# =========================================================
T = {
    "fr": {
        "welcome": (
            "💋 *Amour Annonce*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "La plateforme №1 pour les modèles\n"
            "et professionnels en France 🇫🇷\n\n"
            "Que souhaitez-vous faire ?"
        ),
        "btn_browse": "🔍 Voir les annonces",
        "btn_model": "👗 Déposer mon profil",
        "btn_tour": "✈️ En Tour",
        "btn_ad": "📢 Publier une annonce",
        "btn_site": "🌐 Ouvrir le site",
        "btn_support": "💬 Support — @loveparis777",
        "btn_agency": "🌟 Agence — @VModls",
        "btn_admin": "🔐 Admin Panel",
        "btn_back": "◀️ Retour",
        "btn_cancel": "✖️ Annuler",
        "btn_skip": "⏭ Passer",
        "btn_done": "✅ Terminer",
        "choose_region": "📍 Choisissez une région :",
        "choose_city": "🏙 Choisissez une ville :",
        "no_ads": "😔 Aucune annonce pour l'instant.",
        "end_ads": "— Fin des annonces —",
        "sent_moderation": "✅ *Envoyé en modération !*\nNous vous répondrons sous 24h.",
        "btn_contact": "💬 Contacter",
        "btn_fav": "❤️ Favoris",
        "btn_tour_model": "👗 Modèle — je pars en tour",
        "btn_tour_host": "🏨 J'accueille des modèles",
        "type_prompt": "Type d'annonce :",
        "contact_prompt": "📞 Contact :\n\n_@pseudo ou +33 6 12 34 56 78_",
        "need_one_photo": "⚠️ Envoyez au moins une photo avant de terminer.",
        "cancelled": "Annulé.",
    },
    "en": {
        "welcome": (
            "💋 *Amour Annonce*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "The №1 platform for models\n"
            "and professionals in France 🇫🇷\n\n"
            "What would you like to do?"
        ),
        "btn_browse": "🔍 Browse listings",
        "btn_model": "👗 Post my profile",
        "btn_tour": "✈️ On Tour",
        "btn_ad": "📢 Post an ad",
        "btn_site": "🌐 Open website",
        "btn_support": "💬 Support — @loveparis777",
        "btn_agency": "🌟 Agency — @VModls",
        "btn_admin": "🔐 Admin Panel",
        "btn_back": "◀️ Back",
        "btn_cancel": "✖️ Cancel",
        "btn_skip": "⏭ Skip",
        "btn_done": "✅ Done",
        "choose_region": "📍 Choose a region:",
        "choose_city": "🏙 Choose a city:",
        "no_ads": "😔 No listings yet.",
        "end_ads": "— End of listings —",
        "sent_moderation": "✅ *Sent for moderation!*\nWe'll reply within 24h.",
        "btn_contact": "💬 Contact",
        "btn_fav": "❤️ Favourite",
        "btn_tour_model": "👗 Model — going on tour",
        "btn_tour_host": "🏨 I host models",
        "type_prompt": "Listing type:",
        "contact_prompt": "📞 Contact:\n\n_@username or +33 6 12 34 56 78_",
        "need_one_photo": "⚠️ Send at least one photo before finishing.",
        "cancelled": "Cancelled.",
    },
}


# =========================================================
# DB SCHEMA POSITIONS
# =========================================================
DB_COLS = {
    "id": 0,
    "type": 1,
    "region": 2,
    "city": 3,
    "name": 4,
    "age": 5,
    "height": 6,
    "weight": 7,
    "measurements": 8,
    "nationality": 9,
    "languages": 10,
    "incall": 11,
    "price_15min": 12,
    "price_20min": 13,
    "price_30min": 14,
    "price_45min": 15,
    "price_1h": 16,
    "price_1h30": 17,
    "price_2h": 18,
    "price_3h": 19,
    "price_soiree": 20,
    "price_nuit": 21,
    "hair": 22,
    "availability": 23,
    "description": 24,
    "contact": 25,
    "photos": 26,
    "ad_title": 27,
    "ad_desc": 28,
    "tour_who": 29,
    "tour_from": 30,
    "tour_date_from": 31,
    "tour_date_to": 32,
    "tour_notes": 33,
    "is_vip": 34,
    "user_id": 35,
    "created_at": 36,
    "expires_at": 37,
    "source": 38,
}


# =========================================================
# GLOBAL PENDING STORAGE
# =========================================================
pending_ads: Dict[str, Dict[str, Any]] = {}


# =========================================================
# UTILS
# =========================================================
def lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "fr")


def tx(key: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    return T.get(lang(context), T["fr"]).get(key, key)


def escape_md(text: Any) -> str:
    if text is None:
        return "-"
    text = str(text)
    for ch in ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]:
        text = text.replace(ch, f"\\{ch}")
    return text


def get_now_iso() -> str:
    return datetime.utcnow().isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def make_pending_key(user_id: int) -> str:
    return f"{user_id}_{int(datetime.utcnow().timestamp() * 1000)}"


def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    if cleaned.startswith("+") and 10 <= len(cleaned) <= 16:
        return True
    if cleaned.startswith("0") and 9 <= len(cleaned) <= 14:
        return True
    return False


def validate_contact(contact: str) -> bool:
    return (contact.startswith("@") and len(contact) >= 3) or validate_phone(contact)


def validate_age(age_str: str) -> bool:
    age = safe_int(age_str, -1)
    return 18 <= age <= 65


def validate_height(h_str: str) -> bool:
    h = safe_int(h_str, -1)
    return 140 <= h <= 200


def validate_weight(w_str: str) -> bool:
    w = safe_int(w_str, -1)
    return 40 <= w <= 120


def normalize_contact_url(contact: str) -> Optional[str]:
    if not contact:
        return None
    contact = contact.strip()
    if contact.startswith("@"):
        return f"https://t.me/{contact[1:]}"
    if contact.startswith("https://t.me/"):
        return contact
    return None


def parse_prices(text: str) -> Dict[str, str]:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    slots = ["15min", "20min", "30min", "45min", "1h", "1h30", "2h", "3h", "soiree", "nuit"]
    prices: Dict[str, str] = {}

    for i, slot in enumerate(slots):
        if i >= len(lines):
            break
        nums = re.findall(r"\d+", lines[i])
        if nums:
            val = nums[0]
            prices[slot] = "0" if val == "0" else f"{val}€"

    return prices


def format_price_summary(prices: Dict[str, str]) -> str:
    labels = {
        "15min": "15min", "20min": "20min", "30min": "30min", "45min": "45min",
        "1h": "1h", "1h30": "1h30", "2h": "2h", "3h": "3h",
        "soiree": "Soirée", "nuit": "Nuit",
    }
    lines = []
    for key in ["15min", "20min", "30min", "45min", "1h", "1h30", "2h", "3h", "soiree", "nuit"]:
        value = prices.get(key)
        if value and value != "0":
            lines.append(f"• {labels[key]}: {value}")
    return "\n".join(lines)


def reset_flow(context: ContextTypes.DEFAULT_TYPE, keep_lang: bool = True) -> None:
    saved_lang = context.user_data.get("lang", "fr") if keep_lang else None
    context.user_data.clear()
    if keep_lang and saved_lang:
        context.user_data["lang"] = saved_lang


def get_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def reply_target(update: Update) -> Message:
    if update.message:
        return update.message
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message
    raise RuntimeError("No reply target available")


# =========================================================
# DATABASE
# =========================================================
def init_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS annonces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            region TEXT,
            city TEXT,
            name TEXT,
            age TEXT,
            height TEXT,
            weight TEXT,
            measurements TEXT,
            nationality TEXT,
            languages TEXT,
            incall TEXT,
            price_15min TEXT,
            price_20min TEXT,
            price_30min TEXT,
            price_45min TEXT,
            price_1h TEXT,
            price_1h30 TEXT,
            price_2h TEXT,
            price_3h TEXT,
            price_soiree TEXT,
            price_nuit TEXT,
            hair TEXT,
            availability TEXT,
            description TEXT,
            contact TEXT,
            photos TEXT,
            ad_title TEXT,
            ad_desc TEXT,
            tour_who TEXT,
            tour_from TEXT,
            tour_date_from TEXT,
            tour_date_to TEXT,
            tour_notes TEXT,
            is_vip INTEGER DEFAULT 0,
            user_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            source TEXT DEFAULT 'bot'
        )
        """
    )
    conn.commit()
    conn.close()


def save_ad(ad: Dict[str, Any], is_vip: bool = False) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    prices = ad.get("prices", {})
    expires_at = (datetime.utcnow() + timedelta(days=AD_TTL_DAYS)).isoformat()

    cur.execute(
        """
        INSERT INTO annonces (
            type, region, city, name, age, height, weight, measurements,
            nationality, languages, incall,
            price_15min, price_20min, price_30min, price_45min,
            price_1h, price_1h30, price_2h, price_3h, price_soiree, price_nuit,
            hair, availability, description,
            contact, photos, ad_title, ad_desc,
            tour_who, tour_from, tour_date_from, tour_date_to, tour_notes,
            is_vip, user_id, expires_at, source
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            ad.get("type", "model"),
            ad.get("region", "-"),
            ad.get("city", "-"),
            ad.get("name", "-"),
            ad.get("age", "-"),
            ad.get("height", "-"),
            ad.get("weight", "-"),
            ad.get("measurements", "-"),
            ad.get("nationality", "-"),
            ad.get("languages", "-"),
            ad.get("incall", "-"),
            prices.get("15min", "-"),
            prices.get("20min", "-"),
            prices.get("30min", "-"),
            prices.get("45min", "-"),
            prices.get("1h", "-"),
            prices.get("1h30", "-"),
            prices.get("2h", "-"),
            prices.get("3h", "-"),
            prices.get("soiree", "-"),
            prices.get("nuit", "-"),
            ad.get("hair", "-"),
            ad.get("availability", "-"),
            ad.get("description", "-"),
            ad.get("contact", "-"),
            ",".join(ad.get("photos", [])),
            ad.get("ad_title", "-"),
            ad.get("ad_desc", "-"),
            ad.get("tour_who", "-"),
            ad.get("tour_from", "-"),
            ad.get("tour_date_from", "-"),
            ad.get("tour_date_to", "-"),
            ad.get("tour_notes", "-"),
            1 if is_vip else 0,
            ad.get("user_id"),
            expires_at,
            ad.get("source", "bot"),
        )
    )
    ad_id = cur.lastrowid
    conn.commit()
    conn.close()
    return ad_id


def get_ads(city: str, ad_type: str, limit: int = 10) -> List[tuple]:
    conn = get_db_connection()
    cur = conn.cursor()
    now = get_now_iso()

    if ad_type == "all":
        cur.execute(
            """
            SELECT * FROM annonces
            WHERE city=? AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY is_vip DESC, created_at DESC LIMIT ?
            """,
            (city, now, limit),
        )
    else:
        cur.execute(
            """
            SELECT * FROM annonces
            WHERE city=? AND type=? AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY is_vip DESC, created_at DESC LIMIT ?
            """,
            (city, ad_type, now, limit),
        )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_ad_by_id(ad_id: int) -> Optional[tuple]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM annonces WHERE id=?", (ad_id,))
    row = cur.fetchone()
    conn.close()
    return row


def delete_ad(ad_id: int) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM annonces WHERE id=?", (ad_id,))
    conn.commit()
    conn.close()


def set_vip(ad_id: int, enabled: bool) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE annonces SET is_vip=? WHERE id=?", (1 if enabled else 0, ad_id))
    conn.commit()
    conn.close()


def get_db_stats() -> tuple[int, int, int, int]:
    conn = get_db_connection()
    cur = conn.cursor()
    now = get_now_iso()
    day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()

    cur.execute("SELECT COUNT(*) FROM annonces WHERE expires_at IS NULL OR expires_at > ?", (now,))
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM annonces WHERE is_vip=1 AND (expires_at IS NULL OR expires_at > ?)", (now,))
    vip = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM annonces WHERE created_at > ?", (day_ago,))
    today = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM annonces WHERE source='site' AND (expires_at IS NULL OR expires_at > ?)", (now,))
    from_site = cur.fetchone()[0]

    conn.close()
    return total, vip, today, from_site


# =========================================================
# KEYBOARDS
# =========================================================
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        ]
    ])


def main_menu_kb(context: ContextTypes.DEFAULT_TYPE, user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(tx("btn_browse", context), callback_data="go_browse")],
        [
            InlineKeyboardButton(tx("btn_model", context), callback_data="go_model"),
            InlineKeyboardButton(tx("btn_tour", context), callback_data="go_tour"),
        ],
        [InlineKeyboardButton(tx("btn_ad", context), callback_data="go_ad")],
        [InlineKeyboardButton(tx("btn_site", context), url=MINIAPP_URL)],
        [InlineKeyboardButton(tx("btn_support", context), url=SUPPORT_URL)],
        [InlineKeyboardButton(tx("btn_agency", context), url=VMODLS_URL)],
    ]
    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton(tx("btn_admin", context), callback_data="go_admin")])
    return InlineKeyboardMarkup(rows)


def cancel_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(tx("btn_cancel", context), callback_data="go_menu")]])


def skip_cancel_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(tx("btn_skip", context), callback_data="skip"),
            InlineKeyboardButton(tx("btn_cancel", context), callback_data="go_menu"),
        ]
    ])


def region_kb(context: ContextTypes.DEFAULT_TYPE, prefix: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(REGION_KEYS), 2):
        row: List[InlineKeyboardButton] = []
        for j in range(2):
            if i + j < len(REGION_KEYS):
                row.append(InlineKeyboardButton(REGION_KEYS[i + j], callback_data=f"{prefix}_r_{i+j}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(tx("btn_back", context), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)


def city_kb(context: ContextTypes.DEFAULT_TYPE, region_name: str, prefix: str) -> InlineKeyboardMarkup:
    cities = REGIONS.get(region_name, [])
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for idx, city in enumerate(cities):
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_c_{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(tx("btn_back", context), callback_data=f"{prefix}_back_region")])
    return InlineKeyboardMarkup(rows)


def hair_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    options = [
        ("👱 Blonde", "hair_blonde"),
        ("🟤 Brune", "hair_brune"),
        ("🔴 Rousse", "hair_rousse"),
        ("⬛ Noire", "hair_noire"),
        ("🌰 Châtain", "hair_chatain"),
        ("🎨 Colorée", "hair_coloree"),
        ("✂️ Courte", "hair_courte"),
    ]
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for label, data in options:
        row.append(InlineKeyboardButton(label, callback_data=data))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(tx("btn_cancel", context), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)


def incall_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Incall uniquement", callback_data="incall_in")],
        [InlineKeyboardButton("🚗 Outcall uniquement", callback_data="incall_out")],
        [InlineKeyboardButton("🏠🚗 Incall + Outcall", callback_data="incall_both")],
        [InlineKeyboardButton(tx("btn_cancel", context), callback_data="go_menu")],
    ])


def languages_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    options = [
        ("🇫🇷 Français", "ml_fr"), ("🇬🇧 Anglais", "ml_en"),
        ("🇷🇺 Russe", "ml_ru"), ("🇪🇸 Espagnol", "ml_es"),
        ("🇮🇹 Italien", "ml_it"), ("🇩🇪 Allemand", "ml_de"),
        ("🇵🇹 Portugais", "ml_pt"), ("🇸🇦 Arabe", "ml_ar"),
        ("🇺🇦 Ukrainien", "ml_uk"), ("🇯🇵 Japonais", "ml_jp"),
    ]
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for label, data in options:
        row.append(InlineKeyboardButton(label, callback_data=data))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton("✅ Confirmer", callback_data="ml_done"),
        InlineKeyboardButton(tx("btn_cancel", context), callback_data="go_menu"),
    ])
    return InlineKeyboardMarkup(rows)


def availability_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕐 24h/24", callback_data="avail_24h")],
        [InlineKeyboardButton("☀️ En journée", callback_data="avail_day"), InlineKeyboardButton("🌙 En soirée", callback_data="avail_evening")],
        [InlineKeyboardButton("🌃 Nuits uniquement", callback_data="avail_night")],
        [InlineKeyboardButton("📅 Weekends", callback_data="avail_weekend"), InlineKeyboardButton("📞 Sur rendez-vous", callback_data="avail_rdv")],
        [InlineKeyboardButton(tx("btn_cancel", context), callback_data="go_menu")],
    ])


def browse_type_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    label_models = "👗 Modèles" if lang(context) == "fr" else "👗 Models"
    label_tours = "✈️ En Tour" if lang(context) == "fr" else "✈️ On Tour"
    label_ads = "📢 Annonces" if lang(context) == "fr" else "📢 Ads"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label_models, callback_data="brt_model")],
        [InlineKeyboardButton(label_tours, callback_data="brt_tour")],
        [InlineKeyboardButton(label_ads, callback_data="brt_ad")],
        [InlineKeyboardButton(tx("btn_back", context), callback_data="go_browse")],
    ])


def moderation_kb(ad_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{ad_key}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{ad_key}"),
        ],
        [InlineKeyboardButton("⭐️ Одобрить как VIP", callback_data=f"mod_vip_{ad_key}")],
    ])


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ожидают модерации", callback_data="adm_pending")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🗂 Все анкеты", callback_data="adm_all")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="go_menu")],
    ])


def admin_ad_kb(ad_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐️ VIP вкл/выкл", callback_data=f"adm_vip_{ad_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{ad_id}"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="adm_all")],
    ])


def ad_action_kb(ad_id: int, contact: str, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(tx("btn_fav", context), callback_data=f"fav_{ad_id}")]
    url = normalize_contact_url(contact)
    if url:
        buttons.append(InlineKeyboardButton(tx("btn_contact", context), url=url))
    return InlineKeyboardMarkup([buttons])


# =========================================================
# FORMATTING
# =========================================================
def build_admin_notification(ad: Dict[str, Any], source: str = "бот") -> str:
    flow = ad.get("type", ad.get("flow", "model"))
    type_labels = {"model": "👗 Профиль модели", "tour": "✈️ Тур", "ad": "📢 Объявление"}
    lines = [
        "🔔 *НОВАЯ ЗАЯВКА НА МОДЕРАЦИЮ*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📌 Тип: {type_labels.get(flow, '📋 Анкета')}",
        f"📍 Город: {escape_md(ad.get('city', '-'))}",
        f"👤 Имя: {escape_md(ad.get('name', '-'))}",
        f"🎂 Возраст: {escape_md(ad.get('age', '-'))}",
    ]

    if flow == "model":
        lines += [
            f"🌍 Нац.: {escape_md(ad.get('nationality', '-'))}",
            f"📏 Рост: {escape_md(ad.get('height', '-'))} см  ⚖️ Вес: {escape_md(ad.get('weight', '-'))} кг",
            f"📐 Параметры: {escape_md(ad.get('measurements', '-'))}",
            f"💇 Волосы: {escape_md(ad.get('hair', '-'))}",
            f"🗣 Языки: {escape_md(ad.get('languages', '-'))}",
            f"🏠 {escape_md(ad.get('incall', '-'))}",
            f"🕐 Доступность: {escape_md(ad.get('availability', '-'))}",
        ]
        prices = ad.get("prices", {})
        summary = format_price_summary(prices)
        if summary:
            lines.append(f"💶 Тарифы:\n{escape_md(summary)}")
        if ad.get("description"):
            lines.append(f"📝 О себе: {escape_md(ad.get('description', '-'))}")
    elif flow == "tour":
        lines += [
            f"🛫 Откуда: {escape_md(ad.get('tour_from', '-'))}",
            f"📅 Даты: {escape_md(ad.get('tour_date_from', '-'))} → {escape_md(ad.get('tour_date_to', '-'))}",
            f"📝 Заметки: {escape_md(ad.get('tour_notes', '-'))}",
        ]
    else:
        lines += [
            f"📝 Заголовок: {escape_md(ad.get('ad_title', '-'))}",
            f"📋 Описание: {escape_md(ad.get('ad_desc', '-'))}",
        ]

    lines += [
        f"📞 Контакт: {escape_md(ad.get('contact', '-'))}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📥 Источник: {escape_md(source)}",
    ]
    return "\n".join(lines)


def format_ad(row: tuple, context: ContextTypes.DEFAULT_TYPE) -> str:
    c = DB_COLS
    ad_type = row[c["type"]]
    city = row[c["city"]]
    name = row[c["name"]]
    age = row[c["age"]]
    height = row[c["height"]]
    weight = row[c["weight"]]
    measurements = row[c["measurements"]]
    nationality = row[c["nationality"]]
    languages = row[c["languages"]]
    incall = row[c["incall"]]
    contact = row[c["contact"]]
    description = row[c["description"]]
    tour_who = row[c["tour_who"]]
    tour_date_from = row[c["tour_date_from"]]
    tour_date_to = row[c["tour_date_to"]]
    tour_notes = row[c["tour_notes"]]
    ad_title = row[c["ad_title"]]
    ad_desc = row[c["ad_desc"]]
    is_vip = row[c["is_vip"]]
    price_1h = row[c["price_1h"]]
    price_nuit = row[c["price_nuit"]]

    vip = "⭐️ VIP | " if is_vip else ""

    if ad_type == "model":
        lines = [
            f"{vip}👗 *{escape_md(name)}*, {escape_md(age)} ans — {escape_md(city)}",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"📏 {escape_md(height)} cm  ⚖️ {escape_md(weight)} kg  📐 {escape_md(measurements)}",
            f"🌍 {escape_md(nationality)}  🗣 {escape_md(languages)}",
            f"🏠 {escape_md(incall)}",
        ]
        if price_1h and price_1h != "-":
            lines.append(f"💶 1h: *{escape_md(price_1h)}*")
        if price_nuit and price_nuit not in ["-", "0"]:
            lines.append(f"🌙 Nuit: *{escape_md(price_nuit)}*")
        if description and description != "-":
            lines.append(f"📝 {escape_md(description)}")
        lines.append(f"📞 {escape_md(contact)}")
        return "\n".join(lines)

    if ad_type == "tour":
        who_label = "👗 Modèle" if tour_who == "model" else "🏨 Hôte"
        lines = [
            f"{vip}✈️ *En Tour* — {who_label}",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"📍 {escape_md(city)}",
            f"📅 {escape_md(tour_date_from)} → {escape_md(tour_date_to)}",
            f"👤 {escape_md(name)}",
        ]
        if tour_notes and tour_notes != "-":
            lines.append(f"📝 {escape_md(tour_notes)}")
        lines.append(f"📞 {escape_md(contact)}")
        return "\n".join(lines)

    lines = [
        f"{vip}📢 *{escape_md(ad_title)}*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📍 {escape_md(city)}",
        f"📋 {escape_md(ad_desc)}",
        f"📞 {escape_md(contact)}",
    ]
    return "\n".join(lines)


# =========================================================
# TELEGRAM SAFE SENDERS
# =========================================================
async def safe_edit_or_reply(q: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    try:
        await q.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest:
        await q.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)


async def safe_user_notify(bot, chat_id: int, text: str, parse_mode: Optional[str] = None) -> None:
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    except Forbidden:
        logger.warning("Cannot message user %s", chat_id)
    except TelegramError as e:
        logger.error("Failed to message user %s: %s", chat_id, e)


# =========================================================
# START / MENU
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_flow(context, keep_lang=False)
    msg = reply_target(update)
    await msg.reply_text(
        "💋 *Amour Annonce*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "La plateforme №1 pour les modèles\n"
        "et professionnels en France 🇫🇷\n\n"
        "👇 Ouvrez le site ou choisissez votre langue :",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌸 Ouvrir Amour Annonce", url=MINIAPP_URL)],
            [
                InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            ],
        ])
    )
    return CHOOSE_LANG


async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["lang"] = q.data.replace("lang_", "")
    await safe_edit_or_reply(q, escape_md(tx("welcome", context)), main_menu_kb(context, q.from_user.id))
    return MAIN_MENU


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    text = escape_md(tx("welcome", context))
    kb = main_menu_kb(context, user_id)

    if update.callback_query:
        q = update.callback_query
        await q.answer()
        await safe_edit_or_reply(q, text, kb)
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2)
    return MAIN_MENU


# =========================================================
# BROWSE
# =========================================================
async def go_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await safe_edit_or_reply(q, escape_md(tx("choose_region", context)), region_kb(context, "br"))
    return BR_REGION


async def browse_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = safe_int(q.data.replace("br_r_", ""), -1)
    if idx < 0 or idx >= len(REGION_KEYS):
        return BR_REGION
    region = REGION_KEYS[idx]
    context.user_data["br_region"] = region
    await safe_edit_or_reply(q, f"{escape_md(region)}\n\n{escape_md(tx('choose_city', context))}", city_kb(context, region, "br"))
    return BR_CITY


async def browse_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "br_back_region":
        return await go_browse(update, context)
    idx = safe_int(q.data.replace("br_c_", ""), -1)
    region = context.user_data.get("br_region", "")
    cities = REGIONS.get(region, [])
    if idx < 0 or idx >= len(cities):
        return BR_CITY
    city = cities[idx]
    context.user_data["br_city"] = city
    await safe_edit_or_reply(q, f"📍 *{escape_md(city)}*\n\n{escape_md(tx('type_prompt', context))}", browse_type_kb(context))
    return BR_TYPE


async def browse_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "go_browse":
        return await go_browse(update, context)

    mapping = {"brt_model": "model", "brt_tour": "tour", "brt_ad": "ad"}
    ad_type = mapping.get(q.data, "all")
    city = context.user_data.get("br_city", "")
    ads = get_ads(city, ad_type)

    if not ads:
        await safe_edit_or_reply(
            q,
            escape_md(tx("no_ads", context)),
            InlineKeyboardMarkup([[InlineKeyboardButton(tx("btn_back", context), callback_data="go_browse")]])
        )
        return MAIN_MENU

    await safe_edit_or_reply(q, f"📍 *{escape_md(city)}* — {len(ads)} annonce\(s\)", None)

    for row in ads:
        caption = format_ad(row, context)
        photos_raw = row[DB_COLS["photos"]] or ""
        photos = [p for p in photos_raw.split(",") if p]
        ad_id = row[DB_COLS["id"]]
        contact = row[DB_COLS["contact"]]
        try:
            if photos:
                await q.message.reply_photo(photos[0], caption=caption, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await q.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN_V2)
            await q.message.reply_text("⬆️", reply_markup=ad_action_kb(ad_id, contact, context))
        except TelegramError as e:
            logger.error("Browse send error: %s", e)

    await q.message.reply_text(
        escape_md(tx("end_ads", context)),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tx("btn_back", context), callback_data="go_browse")],
            [InlineKeyboardButton("🏠 Menu", callback_data="go_menu")],
        ])
    )
    return MAIN_MENU


# =========================================================
# MODEL FLOW
# =========================================================
async def go_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    saved_lang = context.user_data.get("lang", "fr")
    reset_flow(context, keep_lang=False)
    context.user_data["lang"] = saved_lang
    context.user_data["flow"] = "model"
    context.user_data["selected_langs"] = []
    await safe_edit_or_reply(
        q,
        "👗 *Déposer mon profil*\n\n📍 Étape 1/15 — Choisissez votre région :",
        region_kb(context, "m")
    )
    return M_REGION


async def model_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = safe_int(q.data.replace("m_r_", ""), -1)
    if idx < 0 or idx >= len(REGION_KEYS):
        return M_REGION
    region = REGION_KEYS[idx]
    context.user_data["region"] = region
    await safe_edit_or_reply(q, f"📍 Étape 1/15 — {escape_md(region)}\n\nChoisissez votre ville :", city_kb(context, region, "m"))
    return M_CITY


async def model_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "m_back_region":
        return await go_model(update, context)
    idx = safe_int(q.data.replace("m_c_", ""), -1)
    region = context.user_data.get("region", "")
    cities = REGIONS.get(region, [])
    if idx < 0 or idx >= len(cities):
        return M_CITY
    city = cities[idx]
    context.user_data["city"] = city
    await safe_edit_or_reply(
        q,
        f"✅ Ville: *{escape_md(city)}*\n\n👤 Étape 2/15 — Votre prénom :\n\n_Exemple: Sofia, Marie, Anna..._",
        cancel_kb(context),
    )
    return M_NAME


async def model_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not 2 <= len(name) <= 30:
        await update.message.reply_text("⚠️ Le prénom doit contenir entre 2 et 30 caractères.", reply_markup=cancel_kb(context))
        return M_NAME
    context.user_data["name"] = name
    await update.message.reply_text(
        f"✅ Prénom: *{escape_md(name)}*\n\n🎂 Étape 3/15 — Votre âge :\n\n_Entrez un nombre entre 18 et 65_",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=cancel_kb(context),
    )
    return M_AGE


async def model_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    age_str = update.message.text.strip()
    if not validate_age(age_str):
        await update.message.reply_text("⚠️ Âge invalide. Entrez un nombre entre 18 et 65.", reply_markup=cancel_kb(context))
        return M_AGE
    context.user_data["age"] = age_str
    await update.message.reply_text(
        f"✅ Âge: *{escape_md(age_str)} ans*\n\n🌍 Étape 4/15 — Votre nationalité :",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=cancel_kb(context),
    )
    return M_NATIONALITY


async def model_nationality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 2:
        await update.message.reply_text("⚠️ Veuillez entrer votre nationalité.", reply_markup=cancel_kb(context))
        return M_NATIONALITY
    context.user_data["nationality"] = value
    await update.message.reply_text(
        f"✅ Nationalité: *{escape_md(value)}*\n\n📏 Étape 5/15 — Votre taille en cm :",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=cancel_kb(context),
    )
    return M_HEIGHT


async def model_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_height(value):
        await update.message.reply_text("⚠️ Taille invalide. Entrez un nombre entre 140 et 200.", reply_markup=cancel_kb(context))
        return M_HEIGHT
    context.user_data["height"] = value
    await update.message.reply_text(
        f"✅ Taille: *{escape_md(value)} cm*\n\n⚖️ Étape 6/15 — Votre poids en kg :",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=cancel_kb(context),
    )
    return M_WEIGHT


async def model_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_weight(value):
        await update.message.reply_text("⚠️ Poids invalide. Entrez un nombre entre 40 et 120.", reply_markup=cancel_kb(context))
        return M_WEIGHT
    context.user_data["weight"] = value
    await update.message.reply_text(
        f"✅ Poids: *{escape_md(value)} kg*\n\n📐 Étape 7/15 — Vos mensurations :\n\n_Exemple: 90C — 60 — 90_",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=cancel_kb(context),
    )
    return M_MEASUREMENTS


async def model_measurements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 3:
        await update.message.reply_text("⚠️ Format invalide. Exemple: 90C — 60 — 90", reply_markup=cancel_kb(context))
        return M_MEASUREMENTS
    context.user_data["measurements"] = value
    await update.message.reply_text(
        f"✅ Mensurations: *{escape_md(value)}*\n\n💇 Étape 8/15 — Couleur de cheveux :",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=hair_kb(context),
    )
    return M_HAIR


async def model_hair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    hair_map = {
        "hair_blonde": "Blonde", "hair_brune": "Brune", "hair_rousse": "Rousse",
        "hair_noire": "Noire", "hair_chatain": "Châtain", "hair_coloree": "Colorée",
        "hair_courte": "Courte",
    }
    hair = hair_map.get(q.data, "Autre")
    context.user_data["hair"] = hair
    await safe_edit_or_reply(
        q,
        f"✅ Cheveux: *{escape_md(hair)}*\n\n🏠 Étape 9/15 — Type de service :",
        incall_kb(context),
    )
    return M_INCALL


async def model_incall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mapping = {
        "incall_in": "Incall uniquement",
        "incall_out": "Outcall uniquement",
        "incall_both": "Incall + Outcall",
    }
    incall = mapping.get(q.data, "-")
    context.user_data["incall"] = incall
    context.user_data["selected_langs"] = []
    await safe_edit_or_reply(
        q,
        f"✅ Service: *{escape_md(incall)}*\n\n🗣 Étape 10/15 — Langues parlées :\n\n_Sélectionnez une ou plusieurs langues, puis appuyez sur ✅ Confirmer_",
        languages_kb(context),
    )
    return M_LANGUAGES


async def model_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_map = {
        "ml_fr": "Français", "ml_en": "Anglais", "ml_ru": "Russe", "ml_es": "Espagnol",
        "ml_it": "Italien", "ml_de": "Allemand", "ml_pt": "Portugais", "ml_ar": "Arabe",
        "ml_uk": "Ukrainien", "ml_jp": "Japonais",
    }

    if q.data == "ml_done":
        selected = context.user_data.get("selected_langs", [])
        if not selected:
            await q.answer("⚠️ Sélectionnez au moins une langue!", show_alert=True)
            return M_LANGUAGES
        langs_str = ", ".join(selected)
        context.user_data["languages"] = langs_str
        await safe_edit_or_reply(
            q,
            f"✅ Langues: *{escape_md(langs_str)}*\n\n🕐 Étape 11/15 — Vos disponibilités :",
            availability_kb(context),
        )
        return M_AVAILABILITY

    selected = context.user_data.get("selected_langs", [])
    lang_name = lang_map.get(q.data)
    if lang_name:
        if lang_name in selected:
            selected.remove(lang_name)
            await q.answer(f"❌ Retiré: {lang_name}")
        else:
            selected.append(lang_name)
            await q.answer(f"✅ Ajouté: {lang_name}")
        context.user_data["selected_langs"] = selected
    return M_LANGUAGES


async def model_availability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mapping = {
        "avail_24h": "24h/24",
        "avail_day": "En journée",
        "avail_evening": "En soirée",
        "avail_night": "Nuits uniquement",
        "avail_weekend": "Weekends",
        "avail_rdv": "Sur rendez-vous",
    }
    value = mapping.get(q.data, "-")
    context.user_data["availability"] = value
    await safe_edit_or_reply(
        q,
        "✅ Disponibilités: *{}*\n\n💶 Étape 12/15 — Vos tarifs :\n\nEntrez vos prix *ligne par ligne* :\n\n```\n15min: 80\n20min: 100\n30min: 150\n45min: 200\n1h: 300\n1h30: 420\n2h: 550\n3h: 750\nSoirée: 1200\nNuit: 1800\n```\n_Laissez 0 si vous n'offrez pas ce créneau._".format(escape_md(value)),
        cancel_kb(context),
    )
    return M_PRICES


async def model_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = parse_prices(update.message.text.strip())
    if not prices:
        await update.message.reply_text("⚠️ Format invalide. Réessayez.", reply_markup=cancel_kb(context))
        return M_PRICES
    context.user_data["prices"] = prices
    summary = format_price_summary(prices)
    await update.message.reply_text(
        f"✅ Tarifs enregistrés:\n{summary}\n\n📝 Étape 13/15 — Description :",
        reply_markup=cancel_kb(context),
    )
    return M_DESCRIPTION


async def model_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if len(desc) < 20:
        await update.message.reply_text("⚠️ Description trop courte. Minimum 20 caractères.", reply_markup=cancel_kb(context))
        return M_DESCRIPTION
    context.user_data["description"] = desc
    await update.message.reply_text(
        "✅ Description enregistrée.\n\n📞 Étape 14/15 — Votre contact :\n\n@username ou téléphone",
        reply_markup=cancel_kb(context),
    )
    return M_CONTACT


async def model_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()
    if not validate_contact(contact):
        await update.message.reply_text("⚠️ Format invalide. Utilisez @pseudo ou téléphone.", reply_markup=cancel_kb(context))
        return M_CONTACT
    context.user_data["contact"] = contact
    context.user_data["photos"] = []
    await update.message.reply_text(
        f"✅ Contact: {contact}\n\n📸 Étape 15/15 — Photos : envoyez vos photos puis /done",
        reply_markup=cancel_kb(context),
    )
    return M_PHOTOS


# =========================================================
# TOUR FLOW
# =========================================================
async def go_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    saved_lang = context.user_data.get("lang", "fr")
    reset_flow(context, keep_lang=False)
    context.user_data["lang"] = saved_lang
    context.user_data["flow"] = "tour"
    text = "✈️ *En Tour*\n\nVous êtes :" if lang(context) == "fr" else "✈️ *On Tour*\n\nYou are:"
    await safe_edit_or_reply(
        q,
        text,
        InlineKeyboardMarkup([
            [InlineKeyboardButton(tx("btn_tour_model", context), callback_data="tour_who_model")],
            [InlineKeyboardButton(tx("btn_tour_host", context), callback_data="tour_who_host")],
            [InlineKeyboardButton("🔍 Tour → @loveparis777", url=SUPPORT_URL)],
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
        await safe_edit_or_reply(q, "🛫 Votre ville de départ :", cancel_kb(context))
        return T_FROM_CITY
    await safe_edit_or_reply(q, escape_md(tx("choose_region", context)), region_kb(context, "t"))
    return T_TO_REGION


async def tour_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_from"] = update.message.text.strip()
    await update.message.reply_text(tx("choose_region", context), reply_markup=region_kb(context, "t"))
    return T_TO_REGION


async def tour_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = safe_int(q.data.replace("t_r_", ""), -1)
    if idx < 0 or idx >= len(REGION_KEYS):
        return T_TO_REGION
    region = REGION_KEYS[idx]
    context.user_data["region"] = region
    await safe_edit_or_reply(q, f"{escape_md(region)}\n\nChoisissez la ville de destination :", city_kb(context, region, "t"))
    return T_TO_CITY


async def tour_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "t_back_region":
        return await safe_edit_or_reply(q, escape_md(tx("choose_region", context)), region_kb(context, "t")) or T_TO_REGION
    idx = safe_int(q.data.replace("t_c_", ""), -1)
    region = context.user_data.get("region", "")
    cities = REGIONS.get(region, [])
    if idx < 0 or idx >= len(cities):
        return T_TO_CITY
    context.user_data["city"] = cities[idx]
    await safe_edit_or_reply(q, f"✅ Destination: *{escape_md(cities[idx])}*\n\n📅 Date d'arrivée :", cancel_kb(context))
    return T_DATE_FROM


async def tour_date_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_date_from"] = update.message.text.strip()
    await update.message.reply_text("📅 Date de départ :", reply_markup=cancel_kb(context))
    return T_DATE_TO


async def tour_date_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_date_to"] = update.message.text.strip()
    await update.message.reply_text("👤 Votre prénom :", reply_markup=cancel_kb(context))
    return T_NAME


async def tour_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("📝 Notes (ou passer) :", reply_markup=skip_cancel_kb(context))
    return T_NOTES


async def tour_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tour_notes"] = update.message.text.strip()
    await update.message.reply_text(tx("contact_prompt", context), parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb(context))
    return T_CONTACT


async def skip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["tour_notes"] = "-"
    await safe_edit_or_reply(q, escape_md(tx("contact_prompt", context)), cancel_kb(context))
    return T_CONTACT


async def tour_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()
    if not validate_contact(contact):
        await update.message.reply_text("⚠️ Format invalide.", reply_markup=cancel_kb(context))
        return T_CONTACT
    context.user_data["contact"] = contact
    context.user_data["photos"] = []
    await update.message.reply_text(f"📸 Photos (max {MAX_PHOTOS}) → /done quand terminé", reply_markup=cancel_kb(context))
    return T_PHOTOS


# =========================================================
# AD FLOW
# =========================================================
async def go_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    saved_lang = context.user_data.get("lang", "fr")
    reset_flow(context, keep_lang=False)
    context.user_data["lang"] = saved_lang
    context.user_data["flow"] = "ad"
    await safe_edit_or_reply(q, escape_md(tx("choose_region", context)), region_kb(context, "a"))
    return A_REGION


async def ad_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = safe_int(q.data.replace("a_r_", ""), -1)
    if idx < 0 or idx >= len(REGION_KEYS):
        return A_REGION
    region = REGION_KEYS[idx]
    context.user_data["region"] = region
    await safe_edit_or_reply(q, f"{escape_md(region)}\n\n{escape_md(tx('choose_city', context))}", city_kb(context, region, "a"))
    return A_CITY


async def ad_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "a_back_region":
        return await go_ad(update, context)
    idx = safe_int(q.data.replace("a_c_", ""), -1)
    region = context.user_data.get("region", "")
    cities = REGIONS.get(region, [])
    if idx < 0 or idx >= len(cities):
        return A_CITY
    context.user_data["city"] = cities[idx]
    await safe_edit_or_reply(q, "📝 Titre de l'annonce :", cancel_kb(context))
    return A_TITLE


async def ad_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_title"] = update.message.text.strip()
    await update.message.reply_text("📋 Description :", reply_markup=cancel_kb(context))
    return A_DESC


async def ad_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ad_desc"] = update.message.text.strip()
    await update.message.reply_text(tx("contact_prompt", context), parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb(context))
    return A_CONTACT


async def ad_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()
    if not validate_contact(contact):
        await update.message.reply_text("⚠️ Format invalide.", reply_markup=cancel_kb(context))
        return A_CONTACT
    context.user_data["contact"] = contact
    context.user_data["photos"] = []
    await update.message.reply_text(f"📸 Photos (max {MAX_PHOTOS}) → /done quand terminé", reply_markup=cancel_kb(context))
    return A_PHOTOS


# =========================================================
# PHOTOS + SUBMIT
# =========================================================
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"⚠️ Maximum {MAX_PHOTOS} photos. Envoyez /done")
        return
    file_id = update.message.photo[-1].file_id
    photos.append(file_id)
    context.user_data["photos"] = photos
    await update.message.reply_text(f"✅ Photo {len(photos)}/{MAX_PHOTOS} — Continuez ou /done")


async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])
    if not photos:
        await update.message.reply_text(tx("need_one_photo", context))
        return None

    user_id = update.effective_user.id
    flow = context.user_data.get("flow", "model")
    context.user_data["type"] = flow
    context.user_data["user_id"] = user_id
    context.user_data["source"] = "bot"
    ad_key = make_pending_key(user_id)
    pending_ads[ad_key] = dict(context.user_data)

    await update.message.reply_text(
        tx("sent_moderation", context),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_kb(context, user_id),
    )

    ad = pending_ads[ad_key]
    notification = build_admin_notification(ad, source="бот Telegram")
    try:
        await context.bot.send_photo(ADMIN_ID, photos[0], caption=notification, parse_mode=ParseMode.MARKDOWN_V2)
        if len(photos) > 1:
            media = [InputMediaPhoto(media=p) for p in photos[1:10]]
            await context.bot.send_media_group(ADMIN_ID, media)
        await context.bot.send_message(ADMIN_ID, "👇 *Выбери действие:*", parse_mode=ParseMode.MARKDOWN, reply_markup=moderation_kb(ad_key))
    except TelegramError as e:
        logger.error("Failed to notify admin: %s", e)

    reset_flow(context)
    return ConversationHandler.END


# =========================================================
# MODERATION + CHANNEL PUBLISH
# =========================================================
async def publish_to_channel(context: ContextTypes.DEFAULT_TYPE, ad: Dict[str, Any], is_vip: bool = False) -> None:
    flow = ad.get("type", "model")
    city = ad.get("city", "-")
    city_tag = re.sub(r"[^a-zA-Z0-9_]+", "_", city.lower())
    vip = "⭐️ VIP | " if is_vip else ""
    vip_tag = "#vip " if is_vip else ""
    prices = ad.get("prices", {})

    if flow == "model":
        lines = [
            f"{vip}👗 *{escape_md(ad.get('name', '-'))}, {escape_md(ad.get('age', '-'))} ans* — {escape_md(city)}",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"📏 {escape_md(ad.get('height', '-'))} cm  ⚖️ {escape_md(ad.get('weight', '-'))} kg",
            f"🌍 {escape_md(ad.get('nationality', '-'))}  🗣 {escape_md(ad.get('languages', '-'))}",
            f"🏠 {escape_md(ad.get('incall', '-'))}",
        ]
        if prices.get("1h") and prices["1h"] != "0":
            lines.append(f"💶 1h: *{escape_md(prices['1h'])}*")
        if prices.get("nuit") and prices["nuit"] not in ["0", "-"]:
            lines.append(f"🌙 Nuit: *{escape_md(prices['nuit'])}*")
        if ad.get("description") and ad["description"] != "-":
            lines.append(f"📝 {escape_md(str(ad['description'])[:220])}")
        lines.append(f"📞 {escape_md(ad.get('contact', '-'))}")
        lines.append(f"\n{vip_tag}#{city_tag} #modele #amourannonce")
        caption = "\n".join(lines)
    elif flow == "tour":
        who = "Modèle" if ad.get("tour_who") == "model" else "Hôte"
        caption = (
            f"{vip}✈️ *En Tour — {escape_md(who)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 {escape_md(city)}\n"
            f"📅 {escape_md(ad.get('tour_date_from', '-'))} → {escape_md(ad.get('tour_date_to', '-'))}\n"
            f"👤 {escape_md(ad.get('name', '-'))}\n"
            f"📝 {escape_md(ad.get('tour_notes', '-'))}\n"
            f"📞 {escape_md(ad.get('contact', '-'))}\n\n"
            f"{vip_tag}#{city_tag} #tour #amourannonce"
        )
    else:
        caption = (
            f"{vip}📢 *{escape_md(ad.get('ad_title', '-'))}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 {escape_md(city)}\n"
            f"📋 {escape_md(ad.get('ad_desc', '-'))}\n"
            f"📞 {escape_md(ad.get('contact', '-'))}\n\n"
            f"{vip_tag}#{city_tag} #annonce #amourannonce"
        )

    photos = ad.get("photos", [])
    try:
        if photos:
            await context.bot.send_photo(CHANNEL_ID, photos[0], caption=caption, parse_mode=ParseMode.MARKDOWN_V2)
            if len(photos) > 1:
                await context.bot.send_media_group(CHANNEL_ID, [InputMediaPhoto(media=p) for p in photos[1:10]])
        else:
            await context.bot.send_message(CHANNEL_ID, caption, parse_mode=ParseMode.MARKDOWN_V2)
    except TelegramError as e:
        logger.error("Channel publish error: %s", e)


async def moderation_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔️ Доступ запрещён.", show_alert=True)
        return

    parts = q.data.split("_", 2)
    if len(parts) != 3:
        return
    action = parts[1]
    ad_key = parts[2]
    ad = pending_ads.get(ad_key)
    if not ad:
        await q.edit_message_text("⚠️ Анкета не найдена (уже обработана?).")
        return

    if action == "reject":
        if ad.get("user_id"):
            msg = "❌ Votre annonce a été refusée." if ad.get("lang", "fr") == "fr" else "❌ Your listing was rejected."
            await safe_user_notify(context.bot, ad["user_id"], msg)
        pending_ads.pop(ad_key, None)
        await q.edit_message_text("❌ Заявка отклонена.")
        return

    is_vip = action == "vip"
    ad_id = save_ad(ad, is_vip=is_vip)
    await publish_to_channel(context, ad, is_vip=is_vip)

    if ad.get("user_id"):
        msg = "✅ Votre annonce a été publiée!" if ad.get("lang", "fr") == "fr" else "✅ Your listing is published!"
        if is_vip:
            msg += "\n⭐️ *Statut VIP accordé!*"
        await safe_user_notify(context.bot, ad["user_id"], msg, parse_mode=ParseMode.MARKDOWN)

    pending_ads.pop(ad_key, None)
    await q.edit_message_text(f"✅ Анкета одобрена и опубликована!\n🆔 ID: {ad_id} | {'VIP' if is_vip else 'standard'}")


# =========================================================
# ADMIN
# =========================================================
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
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_menu_kb(),
    )
    return ADMIN_MENU


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return ADMIN_MENU

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
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_menu_kb(),
        )
        return ADMIN_MENU

    if data == "adm_stats":
        return await admin_menu(Update(update.update_id, callback_query=q), context)

    if data == "adm_pending":
        if not pending_ads:
            await q.edit_message_text("✅ Нет заявок на модерации.", reply_markup=admin_menu_kb())
            return ADMIN_MENU
        text = f"⏳ *Заявок на модерации: {len(pending_ads)}*\n\n"
        for key, ad in pending_ads.items():
            source = "🌐 сайт" if ad.get("source") == "site" else "📱 бот"
            text += f"• {ad.get('type','?')} | {ad.get('city','-')} | {ad.get('name','-')} | {source}\n"
        await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu_kb())
        return ADMIN_MENU

    if data == "adm_all":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, type, city, name, is_vip
            FROM annonces
            WHERE expires_at IS NULL OR expires_at > ?
            ORDER BY created_at DESC LIMIT 20
            """,
            (get_now_iso(),),
        )
        rows = cur.fetchall()
        conn.close()
        if not rows:
            await q.edit_message_text("Нет анкет.", reply_markup=admin_menu_kb())
            return ADMIN_MENU
        kb = []
        for ad_id, ad_type, city, name, is_vip in rows:
            vip_icon = "⭐️ " if is_vip else ""
            kb.append([InlineKeyboardButton(f"{vip_icon}{ad_type[:1].upper()} | {city} | {name}", callback_data=f"adm_view_{ad_id}")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="go_admin")])
        await q.edit_message_text("🗂 *Активные анкеты (последние 20):*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return ADMIN_MENU

    if data.startswith("adm_view_"):
        ad_id = safe_int(data.replace("adm_view_", ""), -1)
        row = get_ad_by_id(ad_id)
        if not row:
            await q.edit_message_text("Не найдено.", reply_markup=admin_menu_kb())
            return ADMIN_MENU
        await q.edit_message_text(format_ad(row, context), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=admin_ad_kb(ad_id))
        return ADMIN_MENU

    if data.startswith("adm_vip_"):
        ad_id = safe_int(data.replace("adm_vip_", ""), -1)
        row = get_ad_by_id(ad_id)
        if row:
            new_status = not bool(row[DB_COLS["is_vip"]])
            set_vip(ad_id, new_status)
            row = get_ad_by_id(ad_id)
            await q.answer("⭐️ VIP обновлён", show_alert=True)
            await q.edit_message_text(format_ad(row, context), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=admin_ad_kb(ad_id))
        return ADMIN_MENU

    if data.startswith("adm_del_"):
        ad_id = safe_int(data.replace("adm_del_", ""), -1)
        delete_ad(ad_id)
        await q.answer("🗑 Удалено!", show_alert=True)
        await q.edit_message_text("🗑 Анкета удалена.", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    return ADMIN_MENU


# =========================================================
# CANCEL / MISC
# =========================================================
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_flow(context)
    if update.callback_query:
        await update.callback_query.answer()
        return await show_menu(update, context)
    await update.message.reply_text(tx("cancelled", context), reply_markup=lang_keyboard())
    return CHOOSE_LANG


async def fav_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("❤️ Ajouté aux favoris", show_alert=False)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)


# =========================================================
# MAIN
# =========================================================
def build_application() -> Application:
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(show_menu, pattern="^go_menu$"),
        ],
        states={
            CHOOSE_LANG: [CallbackQueryHandler(choose_lang, pattern="^lang_")],
            MAIN_MENU: [
                CallbackQueryHandler(go_browse, pattern="^go_browse$"),
                CallbackQueryHandler(go_model, pattern="^go_model$"),
                CallbackQueryHandler(go_tour, pattern="^go_tour$"),
                CallbackQueryHandler(go_ad, pattern="^go_ad$"),
                CallbackQueryHandler(admin_menu, pattern="^(go_admin|adm_).*"),
            ],

            BR_REGION: [CallbackQueryHandler(browse_region, pattern="^br_r_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            BR_CITY: [CallbackQueryHandler(browse_city, pattern="^(br_c_|br_back_region)"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            BR_TYPE: [CallbackQueryHandler(browse_type, pattern="^(brt_|go_browse)"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],

            M_REGION: [CallbackQueryHandler(model_region, pattern="^m_r_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_CITY: [CallbackQueryHandler(model_city, pattern="^(m_c_|m_back_region)"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_name), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_age), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_NATIONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_nationality), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_height), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_weight), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_MEASUREMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_measurements), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_HAIR: [CallbackQueryHandler(model_hair, pattern="^hair_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_INCALL: [CallbackQueryHandler(model_incall, pattern="^incall_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_LANGUAGES: [CallbackQueryHandler(model_languages, pattern="^ml_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_AVAILABILITY: [CallbackQueryHandler(model_availability, pattern="^avail_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_PRICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_prices), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_description), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_contact), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_PHOTOS: [MessageHandler(filters.PHOTO, receive_photo), CommandHandler("done", done_photos), CommandHandler("cancel", cancel_handler), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],

            T_WHO: [CallbackQueryHandler(tour_who, pattern="^tour_who_")],
            T_FROM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_from_city), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_TO_REGION: [CallbackQueryHandler(tour_region, pattern="^t_r_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_TO_CITY: [CallbackQueryHandler(tour_city, pattern="^(t_c_|t_back_region)"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_from), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_to), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_name), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_notes), CallbackQueryHandler(skip_handler, pattern="^skip$"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_contact), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            T_PHOTOS: [MessageHandler(filters.PHOTO, receive_photo), CommandHandler("done", done_photos), CommandHandler("cancel", cancel_handler), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],

            A_REGION: [CallbackQueryHandler(ad_region, pattern="^a_r_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            A_CITY: [CallbackQueryHandler(ad_city, pattern="^(a_c_|a_back_region)"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            A_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_title), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            A_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_desc), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            A_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_contact), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            A_PHOTOS: [MessageHandler(filters.PHOTO, receive_photo), CommandHandler("done", done_photos), CommandHandler("cancel", cancel_handler), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],

            ADMIN_MENU: [CallbackQueryHandler(admin_menu, pattern="^(go_admin|adm_).*"), CallbackQueryHandler(show_menu, pattern="^go_menu$")],
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
    app.add_handler(CallbackQueryHandler(fav_handler, pattern="^fav_"))
    app.add_error_handler(error_handler)
    return app


def main() -> None:
    app = build_application()
    logger.info("🚀 Bot Amour Annonce Ultra Pro started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
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
    for idx, city in enumerate(cities):
        # Используем индекс вместо названия города чтобы избежать лимита 64 байта
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_c_{idx}"))
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
    # ml_ prefix to avoid conflict with interface language callbacks lang_fr/lang_en
    options = [
        ("🇫🇷 Français", "ml_fr"), ("🇬🇧 Anglais", "ml_en"),
        ("🇷🇺 Russe", "ml_ru"), ("🇪🇸 Espagnol", "ml_es"),
        ("🇮🇹 Italien", "ml_it"), ("🇩🇪 Allemand", "ml_de"),
        ("🇵🇹 Portugais", "ml_pt"), ("🇸🇦 Arabe", "ml_ar"),
        ("🇺🇦 Ukrainien", "ml_uk"), ("🇯🇵 Japonais", "ml_jp"),
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
        InlineKeyboardButton("✅ Confirmer", callback_data="ml_done"),
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
    context.user_data["flow"] = None
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        return CHOOSE_LANG
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
    idx = int(q.data.replace("br_c_", ""))
    region = context.user_data.get("br_region", "")
    cities = REGIONS.get(region, [])
    city = cities[idx] if idx < len(cities) else "?"
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
    # Полный сброс данных перед началом нового flow
    context.user_data.clear()
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
    idx = int(q.data.replace("m_c_", ""))
    region = context.user_data.get("region", "")
    cities = REGIONS.get(region, [])
    city = cities[idx] if idx < len(cities) else "?"
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

    # ml_ prefix для языков модели, чтобы не конфликтовать с lang_ интерфейса
    lang_map = {
        "ml_fr": "Français", "ml_en": "Anglais",
        "ml_ru": "Russe", "ml_es": "Espagnol",
        "ml_it": "Italien", "ml_de": "Allemand",
        "ml_pt": "Portugais", "ml_ar": "Arabe",
        "ml_uk": "Ukrainien", "ml_jp": "Japonais",
    }

    if q.data == "ml_done":
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
            await q.answer(f"❌ Retiré: {lang_name}")
        else:
            selected.append(lang_name)
            await q.answer(f"✅ Ajouté: {lang_name}")
        context.user_data["selected_langs"] = selected
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
    context.user_data.clear()
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
    idx = int(q.data.replace("t_c_", ""))
    region = context.user_data.get("region", "")
    cities = REGIONS.get(region, [])
    city = cities[idx] if idx < len(cities) else "?"
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
    context.user_data.clear()
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
    idx = int(q.data.replace("a_c_", ""))
    region = context.user_data.get("region", "")
    cities = REGIONS.get(region, [])
    city = cities[idx] if idx < len(cities) else "?"
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
                CallbackQueryHandler(cancel_handler, pattern="^go_menu$"),
            ],
            M_CITY:         [CallbackQueryHandler(model_city, pattern="^(m_c_|m_back_region)"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, model_name), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_AGE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, model_age), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_NATIONALITY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, model_nationality), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_HEIGHT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, model_height), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_WEIGHT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, model_weight), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_MEASUREMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_measurements), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_HAIR:         [CallbackQueryHandler(model_hair, pattern="^hair_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_INCALL:       [CallbackQueryHandler(model_incall, pattern="^incall_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_LANGUAGES:    [CallbackQueryHandler(model_languages, pattern="^ml_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_AVAILABILITY: [CallbackQueryHandler(model_availability, pattern="^avail_"), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_PRICES:       [MessageHandler(filters.TEXT & ~filters.COMMAND, model_prices), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_DESCRIPTION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, model_description), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
            M_CONTACT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, model_contact), CommandHandler("start", start), CallbackQueryHandler(cancel_handler, pattern="^go_menu$")],
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
