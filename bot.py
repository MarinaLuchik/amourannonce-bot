"""
Amour Annonce — ULTRA PRO BUSINESS bot.py

Features
- FR + EN user interface
- RU-only admin panel
- Regions / cities across France + all Paris districts
- Flows: annonces / tours / model looking for tour
- Album moderation, preview before submit
- Contact buttons (Telegram / WhatsApp / URL)
- SQLite persistence
- Anti-spam, active listing limit, cleanup
- Railway friendly
"""

import asyncio
import html
import json
import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN", "8549540559:AAEd3EllVX0oQnaRUooL54krXwSwg5Iz_wA")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1003761619638")
ADMIN_ID = int(os.getenv("ADMIN_ID", "2021397237"))
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/loveparis777")
VMODLS_URL = os.getenv("VMODLS_URL", "https://t.me/VModls")
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://www.amourannonce.com")
DB_PATH = os.getenv("DB_PATH", "amour_annonce_ultra_business.db")
MAX_PHOTOS = min(int(os.getenv("MAX_PHOTOS", "8")), 10)
MAX_ACTIVE_PER_USER = int(os.getenv("MAX_ACTIVE_PER_USER", "3"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "3600"))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("amour_annonce_ultra_business")

# ─────────────────────────────────────────────────────────────
# REGIONS / OPTIONS
# ─────────────────────────────────────────────────────────────

REGIONS: Dict[str, List[str]] = {
    "🗼 Paris — Centre & Luxe": [
        "Paris 1er — Louvre / Centre",
        "Paris 2e — Bourse",
        "Paris 3e — Marais",
        "Paris 4e — Île Saint-Louis",
        "Paris 5e — Quartier Latin",
        "Paris 6e — Saint-Germain-des-Prés",
        "Paris 7e — Eiffel / Invalides",
        "Paris 8e — Champs-Élysées",
        "Paris 9e — Opéra",
        "Paris 10e — Canal Saint-Martin",
        "Paris 11e — Bastille",
        "Paris 12e — Bercy",
        "Paris 13e — Place d’Italie",
        "Paris 14e — Montparnasse",
        "Paris 15e — Convention",
        "Paris 16e — Trocadéro",
        "Paris 17e — Batignolles",
        "Paris 18e — Montmartre",
        "Paris 19e — La Villette",
        "Paris 20e — Belleville",
    ],
    "🏙 Île-de-France — Proche banlieue": [
        "Boulogne-Billancourt", "Neuilly-sur-Seine", "Levallois-Perret",
        "Issy-les-Moulineaux", "Courbevoie", "La Défense", "Puteaux",
        "Saint-Cloud", "Vincennes", "Saint-Mandé", "Montreuil",
        "Bagnolet", "Saint-Denis", "Aubervilliers", "Pantin",
        "Les Lilas", "Nogent-sur-Marne", "Créteil",
    ],
    "🏙 Île-de-France — Grande banlieue": [
        "Versailles", "Saint-Germain-en-Laye", "Massy", "Évry-Courcouronnes",
        "Pontoise", "Cergy", "Melun", "Fontainebleau", "Meaux",
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
    "🌸 Occitanie": [
        "Toulouse", "Montpellier", "Perpignan", "Nîmes",
        "Sète", "Béziers", "Montauban",
    ],
    "🍷 Nouvelle-Aquitaine": [
        "Bordeaux", "Biarritz", "Arcachon", "Bayonne", "La Rochelle",
        "Pau", "Périgueux", "Limoges", "Poitiers",
    ],
    "⚓ Pays de la Loire": ["Nantes", "Angers", "Le Mans", "Saint-Nazaire"],
    "🥨 Grand Est": ["Strasbourg", "Reims", "Metz", "Nancy", "Mulhouse", "Colmar"],
    "🍇 Bourgogne-Franche-Comté": ["Dijon", "Besançon", "Belfort"],
    "🌿 Normandie": ["Rouen", "Caen", "Le Havre", "Deauville", "Cherbourg"],
    "🏛 Hauts-de-France": ["Lille", "Amiens", "Dunkerque", "Valenciennes"],
    "🌊 Bretagne": ["Rennes", "Brest", "Quimper", "Saint-Malo", "Lorient", "Vannes"],
    "🌺 Centre-Val de Loire": ["Tours", "Orléans", "Blois"],
}

HAIR_OPTIONS = [
    ("👱 Blonde", "Blonde", "Blonde"),
    ("🟤 Brune", "Brune", "Brunette"),
    ("🔴 Rousse", "Rousse", "Red hair"),
    ("⬛ Noire", "Noire", "Black hair"),
    ("🌰 Châtain", "Châtain", "Brown hair"),
    ("🎨 Colorée", "Colorée", "Colored"),
]

EYE_OPTIONS = [
    ("🔵 Bleus", "Bleus", "Blue"),
    ("🟢 Verts", "Verts", "Green"),
    ("🟤 Marron", "Marron", "Brown"),
    ("🟠 Noisette", "Noisette", "Hazel"),
    ("⚫ Noirs", "Noirs", "Black"),
]

INCALL_OPTIONS = [
    ("🏠 Incall uniquement", "Incall uniquement", "Incall only"),
    ("🚗 Outcall uniquement", "Outcall uniquement", "Outcall only"),
    ("🏠🚗 Incall + Outcall", "Incall + Outcall", "Incall + Outcall"),
]

AVAILABILITY_OPTIONS = [
    ("🕐 24h/24", "24h/24", "24/7"),
    ("☀️ En journée", "En journée", "Daytime"),
    ("🌙 En soirée", "En soirée", "Evening"),
    ("🌃 Nuits uniquement", "Nuits uniquement", "Nights only"),
    ("📅 Weekends", "Weekends", "Weekends"),
    ("📞 Sur rendez-vous", "Sur rendez-vous", "By appointment"),
]

BODY_TYPE_OPTIONS = [
    ("✨ Fine", "Fine", "Slim"),
    ("💪 Sportive", "Sportive", "Athletic"),
    ("🍑 Pulpeuse", "Pulpeuse", "Curvy"),
    ("💎 Élancée", "Élancée", "Tall / Elegant"),
]

YES_NO_OPTIONS = [
    ("✅ Oui", "Oui", "Yes"),
    ("❌ Non", "Non", "No"),
]

LANG_OPTIONS = [
    ("🇫🇷 Français", "Français", "French"),
    ("🇬🇧 Anglais", "Anglais", "English"),
    ("🇷🇺 Russe", "Russe", "Russian"),
    ("🇪🇸 Espagnol", "Espagnol", "Spanish"),
    ("🇮🇹 Italien", "Italien", "Italian"),
    ("🇩🇪 Allemand", "Allemand", "German"),
    ("🇵🇹 Portugais", "Portugais", "Portuguese"),
    ("🇸🇦 Arabe", "Arabe", "Arabic"),
    ("🇺🇦 Ukrainien", "Ukrainien", "Ukrainian"),
]

PRICE_SLOTS = [
    ("15min", "15 min"),
    ("20min", "20 min"),
    ("30min", "30 min"),
    ("45min", "45 min"),
    ("1h", "1h"),
    ("1h30", "1h30"),
    ("2h", "2h"),
    ("soiree", "Soirée"),
    ("nuit", "Nuit"),
]

# ─────────────────────────────────────────────────────────────
# TEXTS
# ─────────────────────────────────────────────────────────────

TEXTS = {
    "fr": {
        "greeting": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPlateforme privée premium pour annonces, tours et profils.\n\nChoisissez votre langue.",
        "welcome": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nChoisissez une option.",
        "site": "🌐 Ouvrir le site",
        "contact_admin": "💬 Contacter l’administration",
        "annonces": "📢 Annonces",
        "tours": "✈️ Tours",
        "tour_request": "👗 Je suis modèle — je cherche un tour",
        "admin": "🔐 Admin Panel",
        "back": "◀️ Retour",
        "menu": "🏠 Menu",
        "cancel": "✖️ Annuler",
        "skip": "⏭ Passer",
        "done": "✅ Terminer",
        "send": "✅ Envoyer",
        "choose_region": "📍 Choisissez votre région :",
        "choose_city": "🏙 Choisissez votre ville / arrondissement :",
        "what_next": "📍 <b>{city}</b>\n━━━━━━━━━━━━━━━━━━\nQue souhaitez-vous faire ?",
        "ads_filters": "📢 <b>Annonces — {city}</b>\nChoisissez un filtre :",
        "tour_filters": "✈️ <b>Tours — {city}</b>\nChoisissez un filtre :",
        "filter_all": "🔎 Tout voir",
        "filter_vip": "⭐ VIP",
        "filter_recent": "🆕 Récent",
        "filter_incall": "🏠 Incall",
        "filter_outcall": "🚗 Outcall",
        "filter_blonde": "👱 Blonde",
        "filter_brune": "🟤 Brune",
        "filter_hosts": "🏨 Hôtes",
        "filter_models_tour": "👗 Modèles",
        "contact_model": "💬 Contacter le profil",
        "empty_results": "😔 Aucun résultat pour le moment.",
        "results_end": "— Fin des résultats —",
        "tour_intro": "Bonjour ✨\n\nCommençons votre publication.",
        "ask_name": "👤 Votre prénom / nom d’annonce :",
        "ask_age": "🎂 Votre âge :\n<i>18–65</i>",
        "ask_origin": "🌍 Votre origine :",
        "ask_height": "📏 Votre taille en cm :",
        "ask_weight": "⚖️ Votre poids en kg :",
        "ask_measurements": "📐 Vos mensurations :\n<i>Ex: 90C - 60 - 90</i>",
        "ask_hair": "💇 Couleur de cheveux :",
        "ask_eyes": "👁 Couleur des yeux :",
        "ask_languages": "🗣 Langues parlées :",
        "confirm_languages": "✅ Confirmer les langues",
        "ask_body_type": "✨ Type de silhouette :",
        "ask_breast": "💎 Poitrine :",
        "ask_smoker": "🚬 Fumeuse ?",
        "ask_tattoos": "🖋 Tatouages ?",
        "ask_incall": "🏠 Type de service :",
        "ask_availability": "🕐 Disponibilités :",
        "ask_prices": "💶 Vos tarifs\n\nEntrez 9 lignes dans cet ordre:\n15 min:\n20 min:\n30 min:\n45 min:\n1h:\n1h30:\n2h:\nSoirée:\nNuit:\n\n👉 chiffres uniquement\n👉 0 = non disponible",
        "ask_desc": "📝 Décrivez-vous :",
        "ask_contact": "📞 Votre contact :\n<i>@telegram ou téléphone ou lien</i>",
        "ask_photos": f"📸 Envoyez vos photos (1–{MAX_PHOTOS}). Puis appuyez sur ✅ Terminer.",
        "preview_title": "👁 <b>Aperçu avant envoi</b>",
        "sent_moderation": "✅ Votre publication a été envoyée en modération.",
        "need_photo": "⚠️ Ajoutez au moins une photo.",
        "invalid_age": "⚠️ Âge invalide. Entrez un nombre entre 18 et 65.",
        "invalid_height": "⚠️ Taille invalide. Entrez un nombre entre 140 et 200.",
        "invalid_weight": "⚠️ Poids invalide. Entrez un nombre entre 40 et 120.",
        "invalid_contact": "⚠️ Contact invalide. Entrez un @username, un numéro ou un lien.",
        "invalid_short": "⚠️ Veuillez renseigner une valeur valide.",
        "too_long": "⚠️ Texte trop long.",
        "tour_ask_from": "🛫 Votre ville de départ :",
        "tour_ask_date_from": "📅 Date d’arrivée :",
        "tour_ask_date_to": "📅 Date de départ :",
        "tour_ask_notes": "📝 Notes / conditions :",
        "tour_ask_title": "📝 Titre de l’annonce :",
        "tour_ask_ad_desc": "📋 Description de l’annonce :",
        "tour_who_prompt": "Sélectionnez votre type :",
        "limit_reached": f"⚠️ Limite atteinte : {MAX_ACTIVE_PER_USER} publications actives/pending maximum.",
        "photos_only": "📸 Veuillez envoyer uniquement des photos.",
        "unknown": "Utilisez /start",
    },
    "en": {
        "greeting": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPrivate premium platform for ads, tours and profiles.\n\nChoose your language.",
        "welcome": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPlease choose an option.",
        "site": "🌐 Open website",
        "contact_admin": "💬 Contact administration",
        "annonces": "📢 Ads",
        "tours": "✈️ Tours",
        "tour_request": "👗 I am a model — looking for a tour",
        "admin": "🔐 Admin Panel",
        "back": "◀️ Back",
        "menu": "🏠 Menu",
        "cancel": "✖️ Cancel",
        "skip": "⏭ Skip",
        "done": "✅ Finish",
        "send": "✅ Send",
        "choose_region": "📍 Choose your region:",
        "choose_city": "🏙 Choose your city / district:",
        "what_next": "📍 <b>{city}</b>\n━━━━━━━━━━━━━━━━━━\nWhat would you like to do?",
        "ads_filters": "📢 <b>Ads — {city}</b>\nChoose a filter:",
        "tour_filters": "✈️ <b>Tours — {city}</b>\nChoose a filter:",
        "filter_all": "🔎 View all",
        "filter_vip": "⭐ VIP",
        "filter_recent": "🆕 Recent",
        "filter_incall": "🏠 Incall",
        "filter_outcall": "🚗 Outcall",
        "filter_blonde": "👱 Blonde",
        "filter_brune": "🟤 Brunette",
        "filter_hosts": "🏨 Hosts",
        "filter_models_tour": "👗 Models",
        "contact_model": "💬 Contact profile",
        "empty_results": "😔 No results yet.",
        "results_end": "— End of results —",
        "tour_intro": "Hello ✨\n\nLet's create your publication.",
        "ask_name": "👤 Your display name:",
        "ask_age": "🎂 Your age:\n<i>18–65</i>",
        "ask_origin": "🌍 Your origin:",
        "ask_height": "📏 Your height in cm:",
        "ask_weight": "⚖️ Your weight in kg:",
        "ask_measurements": "📐 Your measurements:\n<i>Ex: 90C - 60 - 90</i>",
        "ask_hair": "💇 Hair color:",
        "ask_eyes": "👁 Eye color:",
        "ask_languages": "🗣 Spoken languages:",
        "confirm_languages": "✅ Confirm languages",
        "ask_body_type": "✨ Body type:",
        "ask_breast": "💎 Breast type:",
        "ask_smoker": "🚬 Smoker?",
        "ask_tattoos": "🖋 Tattoos?",
        "ask_incall": "🏠 Service type:",
        "ask_availability": "🕐 Availability:",
        "ask_prices": "💶 Your rates\n\nEnter 9 lines in this order:\n15 min:\n20 min:\n30 min:\n45 min:\n1h:\n1h30:\n2h:\nEvening:\nNight:\n\n👉 numbers only\n👉 0 = not available",
        "ask_desc": "📝 Describe yourself:",
        "ask_contact": "📞 Your contact:\n<i>@telegram or phone or link</i>",
        "ask_photos": f"📸 Send your photos (1–{MAX_PHOTOS}). Then press ✅ Finish.",
        "preview_title": "👁 <b>Preview before sending</b>",
        "sent_moderation": "✅ Your publication was sent for moderation.",
        "need_photo": "⚠️ Please add at least one photo.",
        "invalid_age": "⚠️ Invalid age. Enter a number between 18 and 65.",
        "invalid_height": "⚠️ Invalid height. Enter a number between 140 and 200.",
        "invalid_weight": "⚠️ Invalid weight. Enter a number between 40 and 120.",
        "invalid_contact": "⚠️ Invalid contact. Enter a @username, number or link.",
        "invalid_short": "⚠️ Please enter a valid value.",
        "too_long": "⚠️ Text is too long.",
        "tour_ask_from": "🛫 Your departure city:",
        "tour_ask_date_from": "📅 Arrival date:",
        "tour_ask_date_to": "📅 Departure date:",
        "tour_ask_notes": "📝 Notes / conditions:",
        "tour_ask_title": "📝 Ad title:",
        "tour_ask_ad_desc": "📋 Ad description:",
        "tour_who_prompt": "Select your type:",
        "limit_reached": f"⚠️ Limit reached: maximum {MAX_ACTIVE_PER_USER} active/pending listings.",
        "photos_only": "📸 Please send photos only.",
        "unknown": "Use /start",
    }
}

# ─────────────────────────────────────────────────────────────
# STATES
# ─────────────────────────────────────────────────────────────

(
    LANG_CHOOSE,
    MAIN_MENU,
    PICK_REGION_FOR_MENU,
    PICK_CITY_FOR_MENU,
    BROWSE_MENU,
    BROWSE_AD_FILTER,
    BROWSE_TOUR_FILTER,
    MODEL_REGION,
    MODEL_CITY,
    MODEL_NAME,
    MODEL_AGE,
    MODEL_ORIGIN,
    MODEL_HEIGHT,
    MODEL_WEIGHT,
    MODEL_MEASUREMENTS,
    MODEL_HAIR,
    MODEL_EYES,
    MODEL_LANGS,
    MODEL_BODY,
    MODEL_BREAST,
    MODEL_SMOKER,
    MODEL_TATTOOS,
    MODEL_INCALL,
    MODEL_AVAILABILITY,
    MODEL_PRICES,
    MODEL_DESC,
    MODEL_CONTACT,
    MODEL_PHOTOS,
    MODEL_PREVIEW,
    TOUR_REGION,
    TOUR_CITY,
    TOUR_WHO,
    TOUR_FROM,
    TOUR_DATE_FROM,
    TOUR_DATE_TO,
    TOUR_NAME,
    TOUR_NOTES,
    TOUR_CONTACT,
    TOUR_PHOTOS,
    TOUR_PREVIEW,
    AD_REGION,
    AD_CITY,
    AD_TITLE,
    AD_DESC,
    AD_CONTACT,
    AD_PHOTOS,
    AD_PREVIEW,
    ADMIN_MENU,
) = range(48)

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────

class DB:
    def __init__(self, path: str):
        self.path = path
        self.init()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        with closing(self.connect()) as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'fr',
                    username TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT DEFAULT 'pending',
                    is_vip INTEGER DEFAULT 0,
                    flow TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    region TEXT,
                    city TEXT,
                    name TEXT,
                    age TEXT,
                    origin TEXT,
                    height TEXT,
                    weight TEXT,
                    measurements TEXT,
                    hair TEXT,
                    eyes TEXT,
                    languages TEXT,
                    body_type TEXT,
                    breast_type TEXT,
                    smoker TEXT,
                    tattoos TEXT,
                    incall TEXT,
                    availability TEXT,
                    prices_json TEXT,
                    description TEXT,
                    contact TEXT,
                    ad_title TEXT,
                    ad_desc TEXT,
                    tour_who TEXT,
                    tour_from TEXT,
                    tour_date_from TEXT,
                    tour_date_to TEXT,
                    tour_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listing_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0
                )
            """)

    def upsert_user(self, user_id: int, username: str, language: Optional[str] = None):
        with closing(self.connect()) as conn, conn:
            exists = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
            if exists:
                if language:
                    conn.execute("UPDATE users SET username=?, language=? WHERE user_id=?", (username, language, user_id))
                else:
                    conn.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
            else:
                conn.execute(
                    "INSERT INTO users (user_id, username, language) VALUES (?, ?, ?)",
                    (user_id, username, language or "fr")
                )

    def get_lang(self, user_id: Optional[int]) -> str:
        if not user_id:
            return "fr"
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT language FROM users WHERE user_id=?", (user_id,)).fetchone()
            return row["language"] if row else "fr"

    def create_listing(self, data: Dict[str, Any], media_ids: List[str]) -> int:
        with closing(self.connect()) as conn, conn:
            expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
            cur = conn.execute("""
                INSERT INTO listings (
                    status,is_vip,flow,user_id,username,region,city,name,age,origin,height,weight,measurements,
                    hair,eyes,languages,body_type,breast_type,smoker,tattoos,incall,availability,prices_json,
                    description,contact,ad_title,ad_desc,tour_who,tour_from,tour_date_from,tour_date_to,tour_notes,expires_at
                ) VALUES (
                    'pending',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
            """, (
                1 if data.get("is_vip") else 0,
                data.get("flow", ""),
                data.get("user_id"),
                data.get("username", ""),
                data.get("region", ""),
                data.get("city", ""),
                data.get("name", ""),
                data.get("age", ""),
                data.get("origin", ""),
                data.get("height", ""),
                data.get("weight", ""),
                data.get("measurements", ""),
                data.get("hair", ""),
                data.get("eyes", ""),
                data.get("languages", ""),
                data.get("body_type", ""),
                data.get("breast_type", ""),
                data.get("smoker", ""),
                data.get("tattoos", ""),
                data.get("incall", ""),
                data.get("availability", ""),
                json.dumps(data.get("prices", {}), ensure_ascii=False),
                data.get("description", ""),
                data.get("contact", ""),
                data.get("ad_title", ""),
                data.get("ad_desc", ""),
                data.get("tour_who", ""),
                data.get("tour_from", ""),
                data.get("tour_date_from", ""),
                data.get("tour_date_to", ""),
                data.get("tour_notes", ""),
                expires_at,
            ))
            listing_id = int(cur.lastrowid)
            for i, file_id in enumerate(media_ids[:10]):
                conn.execute(
                    "INSERT INTO listing_media (listing_id,file_id,sort_order) VALUES (?,?,?)",
                    (listing_id, file_id, i),
                )
            return listing_id

    def get_listing(self, listing_id: int):
        with closing(self.connect()) as conn:
            return conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()

    def get_media(self, listing_id: int) -> List[str]:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                "SELECT file_id FROM listing_media WHERE listing_id=? ORDER BY sort_order,id",
                (listing_id,)
            ).fetchall()
            return [r["file_id"] for r in rows]

    def update_status(self, listing_id: int, status: str, is_vip: Optional[bool] = None):
        with closing(self.connect()) as conn, conn:
            if is_vip is None:
                conn.execute("UPDATE listings SET status=? WHERE id=?", (status, listing_id))
            else:
                conn.execute("UPDATE listings SET status=?, is_vip=? WHERE id=?", (status, 1 if is_vip else 0, listing_id))

    def delete_listing(self, listing_id: int):
        with closing(self.connect()) as conn, conn:
            conn.execute("DELETE FROM listing_media WHERE listing_id=?", (listing_id,))
            conn.execute("DELETE FROM listings WHERE id=?", (listing_id,))

    def pending(self):
        with closing(self.connect()) as conn:
            return conn.execute("SELECT * FROM listings WHERE status='pending' ORDER BY id DESC").fetchall()

    def all_active(self, limit: int = 50):
        with closing(self.connect()) as conn:
            return conn.execute("""
                SELECT * FROM listings
                WHERE status='approved' AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY is_vip DESC, created_at DESC
                LIMIT ?
            """, (datetime.utcnow().isoformat(), limit)).fetchall()

    def count_user_active(self, user_id: int) -> int:
        with closing(self.connect()) as conn:
            row = conn.execute("""
                SELECT COUNT(*) c FROM listings
                WHERE user_id=? AND status IN ('pending','approved')
            """, (user_id,)).fetchone()
            return int(row["c"])

    def cleanup_expired(self):
        with closing(self.connect()) as conn, conn:
            expired = conn.execute(
                "SELECT id FROM listings WHERE expires_at IS NOT NULL AND expires_at < ?",
                (datetime.utcnow().isoformat(),)
            ).fetchall()
            for row in expired:
                conn.execute("DELETE FROM listing_media WHERE listing_id=?", (row["id"],))
            conn.execute(
                "DELETE FROM listings WHERE expires_at IS NOT NULL AND expires_at < ?",
                (datetime.utcnow().isoformat(),)
            )

    def browse(self, city: str, flow: str, vip_only: bool = False, recent_only: bool = False,
               tour_who: Optional[str] = None, incall_contains: Optional[str] = None,
               hair_contains: Optional[str] = None, limit: int = 20):
        query = """
            SELECT * FROM listings
            WHERE status='approved'
              AND city=?
              AND flow=?
              AND (expires_at IS NULL OR expires_at > ?)
        """
        params: List[Any] = [city, flow, datetime.utcnow().isoformat()]
        if vip_only:
            query += " AND is_vip=1"
        if recent_only:
            query += " AND created_at > ?"
            params.append((datetime.utcnow() - timedelta(days=7)).isoformat())
        if tour_who:
            query += " AND tour_who=?"
            params.append(tour_who)
        if incall_contains:
            query += " AND incall LIKE ?"
            params.append(f"%{incall_contains}%")
        if hair_contains:
            query += " AND hair LIKE ?"
            params.append(f"%{hair_contains}%")
        query += " ORDER BY is_vip DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with closing(self.connect()) as conn:
            return conn.execute(query, params).fetchall()

    def stats(self):
        with closing(self.connect()) as conn:
            result = {}
            result["pending"] = int(conn.execute("SELECT COUNT(*) c FROM listings WHERE status='pending'").fetchone()["c"])
            result["approved"] = int(conn.execute("SELECT COUNT(*) c FROM listings WHERE status='approved'").fetchone()["c"])
            result["vip"] = int(conn.execute("SELECT COUNT(*) c FROM listings WHERE status='approved' AND is_vip=1").fetchone()["c"])
            result["today"] = int(conn.execute(
                "SELECT COUNT(*) c FROM listings WHERE created_at > ?",
                ((datetime.utcnow() - timedelta(days=1)).isoformat(),)
            ).fetchone()["c"])
            return result

db = DB(DB_PATH)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

USER_LAST_ACTION: Dict[int, float] = {}

def anti_spam(user_id: int, delay: float = 1.2) -> bool:
    now = time.time()
    last = USER_LAST_ACTION.get(user_id, 0.0)
    if now - last < delay:
        return False
    USER_LAST_ACTION[user_id] = now
    return True

def safe_handler(fn):
    @wraps(fn)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            user = update.effective_user
            if user and not anti_spam(user.id):
                return
            return await fn(update, context, *args, **kwargs)
        except Exception as exc:
            logger.exception("Handler error in %s: %s", fn.__name__, exc)
            try:
                user = update.effective_user
                if user:
                    lang = context.user_data.get("lang", "fr")
                    msg = "⚠️ Une erreur est survenue. Réessayez." if lang == "fr" else "⚠️ Something went wrong. Please try again."
                    await context.bot.send_message(chat_id=user.id, text=msg)
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 BOT ERROR in {fn.__name__}\n{str(exc)[:800]}")
            except Exception:
                pass
    return wrapper

def get_lang_from_ctx(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("lang", "fr")

def t(ctx: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
    lang = get_lang_from_ctx(ctx)
    txt = TEXTS.get(lang, TEXTS["fr"]).get(key, key)
    return txt.format(**kwargs) if kwargs else txt

def safe(value: Any) -> str:
    return html.escape(str(value or ""))

def get_username(update: Update) -> str:
    u = update.effective_user
    if not u:
        return ""
    return u.username or " ".join([x for x in [u.first_name, u.last_name] if x]).strip()

def validate_age(v: str) -> bool:
    try:
        return 18 <= int(v) <= 65
    except Exception:
        return False

def validate_height(v: str) -> bool:
    try:
        return 140 <= int(v) <= 200
    except Exception:
        return False

def validate_weight(v: str) -> bool:
    try:
        return 40 <= int(v) <= 120
    except Exception:
        return False

def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    return (cleaned.startswith('+') and len(cleaned) >= 10) or (cleaned.startswith('0') and len(cleaned) >= 9)

def valid_contact(value: str) -> bool:
    return (
        (value.startswith("@") and len(value) > 2) or
        validate_phone(value) or
        value.startswith("http://") or
        value.startswith("https://")
    )

def clean_contact_url(contact: str) -> Optional[str]:
    if not contact:
        return None
    contact = contact.strip()
    if contact.startswith("http://") or contact.startswith("https://"):
        return contact
    if contact.startswith("@"):
        return f"https://t.me/{contact[1:]}"
    if validate_phone(contact):
        digits = re.sub(r"[^\d+]", "", contact)
        return f"https://wa.me/{digits.lstrip('+')}" if digits else None
    return None

def parse_prices(text: str) -> Dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    prices: Dict[str, str] = {}
    for idx, slot in enumerate(PRICE_SLOTS):
        if idx >= len(lines):
            break
        nums = re.findall(r"\d+", lines[idx])
        prices[slot[0]] = nums[0] if nums else "0"
    return prices

def price_summary(prices: Dict[str, str]) -> str:
    out = []
    for key, label in PRICE_SLOTS:
        value = prices.get(key)
        if value and value != "0":
            out.append(f"{label}: {value}€")
    return " | ".join(out) if out else "-"

def too_long(value: str, limit: int = 1200) -> bool:
    return len(value.strip()) > limit

def draft(ctx: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    if "draft" not in ctx.user_data:
        ctx.user_data["draft"] = {
            "flow": "",
            "region": "",
            "city": "",
            "name": "",
            "age": "",
            "origin": "",
            "height": "",
            "weight": "",
            "measurements": "",
            "hair": "",
            "eyes": "",
            "languages": [],
            "body_type": "",
            "breast_type": "",
            "smoker": "",
            "tattoos": "",
            "incall": "",
            "availability": "",
            "prices": {},
            "description": "",
            "contact": "",
            "photos": [],
            "ad_title": "",
            "ad_desc": "",
            "tour_who": "",
            "tour_from": "",
            "tour_date_from": "",
            "tour_date_to": "",
            "tour_notes": "",
        }
    return ctx.user_data["draft"]

def reset_draft(ctx: ContextTypes.DEFAULT_TYPE):
    for key in ("draft", "browse_region", "browse_city", "selected_lang_codes"):
        ctx.user_data.pop(key, None)

async def safe_edit_or_reply(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest:
        await query.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def send_album(bot, chat_id, photo_ids: List[str], caption: str, reply_markup=None):
    photo_ids = photo_ids[:10]
    if not photo_ids:
        await bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return
    if len(photo_ids) == 1:
        await bot.send_photo(chat_id=chat_id, photo=photo_ids[0], caption=caption, parse_mode=ParseMode.HTML)
        if reply_markup:
            await bot.send_message(chat_id=chat_id, text=" ", reply_markup=reply_markup)
        return
    media = []
    for i, file_id in enumerate(photo_ids):
        if i == 0:
            media.append(InputMediaPhoto(media=file_id, caption=caption, parse_mode=ParseMode.HTML))
        else:
            media.append(InputMediaPhoto(media=file_id))
    await bot.send_media_group(chat_id=chat_id, media=media)
    if reply_markup:
        await bot.send_message(chat_id=chat_id, text=" ", reply_markup=reply_markup)

def choice_label(option_tuple, lang_code: str) -> str:
    return option_tuple[1] if lang_code == "fr" else option_tuple[2]

# ─────────────────────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────────────────────

def main_menu_keyboard(ctx: ContextTypes.DEFAULT_TYPE, user_id: Optional[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(t(ctx, "annonces"), callback_data="pick_city_menu")],
        [InlineKeyboardButton(t(ctx, "tours"), callback_data="go_tour_flow")],
        [InlineKeyboardButton(t(ctx, "tour_request"), callback_data="flow_tour_request")],
        [InlineKeyboardButton(t(ctx, "contact_admin"), url=SUPPORT_URL)],
        [InlineKeyboardButton(t(ctx, "site"), web_app=WebAppInfo(url=MINIAPP_URL))],
    ]
    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton(t(ctx, "admin"), callback_data="go_admin")])
    return InlineKeyboardMarkup(rows)

def region_keyboard(ctx: ContextTypes.DEFAULT_TYPE, prefix: str) -> InlineKeyboardMarkup:
    keys = list(REGIONS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                row.append(InlineKeyboardButton(keys[i + j], callback_data=f"{prefix}_r_{i+j}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx, "menu"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def city_keyboard(ctx: ContextTypes.DEFAULT_TYPE, region: str, prefix: str) -> InlineKeyboardMarkup:
    cities = REGIONS.get(region, [])
    rows, row = [], []
    for idx, city in enumerate(cities):
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_c_{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx, "back"), callback_data=f"{prefix}_back_region")])
    return InlineKeyboardMarkup(rows)

def simple_rows(options, prefix: str, ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    rows, row = [], []
    for idx, item in enumerate(options):
        row.append(InlineKeyboardButton(item[0], callback_data=f"{prefix}_{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def languages_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    rows, row = [], []
    for idx, item in enumerate(LANG_OPTIONS):
        row.append(InlineKeyboardButton(item[0], callback_data=f"ml_{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(t(ctx, "confirm_languages"), callback_data="ml_done"),
        InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu"),
    ])
    return InlineKeyboardMarkup(rows)

def city_action_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "annonces"), callback_data="browse_ads")],
        [InlineKeyboardButton(t(ctx, "tours"), callback_data="browse_tours")],
        [InlineKeyboardButton(t(ctx, "tour_request"), callback_data="flow_tour_request_city")],
        [InlineKeyboardButton(t(ctx, "contact_admin"), url=SUPPORT_URL)],
        [InlineKeyboardButton(t(ctx, "back"), callback_data="pick_city_menu")],
    ])

def ads_filter_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "filter_all"), callback_data="ads_all")],
        [InlineKeyboardButton(t(ctx, "filter_vip"), callback_data="ads_vip"),
         InlineKeyboardButton(t(ctx, "filter_recent"), callback_data="ads_recent")],
        [InlineKeyboardButton(t(ctx, "filter_incall"), callback_data="ads_incall"),
         InlineKeyboardButton(t(ctx, "filter_outcall"), callback_data="ads_outcall")],
        [InlineKeyboardButton(t(ctx, "filter_blonde"), callback_data="ads_blonde"),
         InlineKeyboardButton(t(ctx, "filter_brune"), callback_data="ads_brune")],
        [InlineKeyboardButton(t(ctx, "back"), callback_data="back_city_actions")],
    ])

def tours_filter_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "filter_all"), callback_data="tours_all")],
        [InlineKeyboardButton(t(ctx, "filter_models_tour"), callback_data="tours_model"),
         InlineKeyboardButton(t(ctx, "filter_hosts"), callback_data="tours_host")],
        [InlineKeyboardButton(t(ctx, "filter_vip"), callback_data="tours_vip"),
         InlineKeyboardButton(t(ctx, "filter_recent"), callback_data="tours_recent")],
        [InlineKeyboardButton(t(ctx, "back"), callback_data="back_city_actions")],
    ])

def preview_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "send"), callback_data="submit_confirm")],
        [InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu")],
    ])

def photo_stage_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "done"), callback_data="photos_done")],
        [InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu")],
    ])

def listing_actions_keyboard(ctx: ContextTypes.DEFAULT_TYPE, contact: str) -> InlineKeyboardMarkup:
    rows = []
    url = clean_contact_url(contact)
    if url:
        rows.append([InlineKeyboardButton(t(ctx, "contact_model"), url=url)])
    rows.append([InlineKeyboardButton(t(ctx, "contact_admin"), url=SUPPORT_URL)])
    return InlineKeyboardMarkup(rows)

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Заявки на модерации", callback_data="adm_pending")],
        [InlineKeyboardButton("🗂 Активные публикации", callback_data="adm_active")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="go_menu")],
    ])

def moderation_keyboard(listing_id: int, author_contact: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👁 Открыть", callback_data=f"adm_view_{listing_id}")],
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_approve_{listing_id}"),
         InlineKeyboardButton("⭐ VIP", callback_data=f"adm_vip_{listing_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_reject_{listing_id}"),
         InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_delete_{listing_id}")],
    ]
    url = clean_contact_url(author_contact)
    if url:
        rows.append([InlineKeyboardButton("💬 Связаться с автором", url=url)])
    return InlineKeyboardMarkup(rows)

# ─────────────────────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────────────────────

def build_listing_text(row, lang_code: str) -> str:
    vip = "⭐ VIP | " if row["is_vip"] else ""
    flow = row["flow"]
    prices = json.loads(row["prices_json"] or "{}")

    if flow == "annonce":
        return (
            f"{vip}<b>{safe(row['ad_title'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(row['city'])}\n"
            f"📋 {safe(row['ad_desc'])}\n"
            f"📞 {safe(row['contact'])}"
        )

    if flow == "tour":
        role_label = row["tour_who"]
        if row["tour_who"] == "model":
            role_label = "👗 Modèle" if lang_code == "fr" else "👗 Model"
        elif row["tour_who"] == "host":
            role_label = "🏨 Hôte" if lang_code == "fr" else "🏨 Host"
        return (
            f"{vip}✈️ <b>Tours</b> — {safe(role_label)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(row['city'])}\n"
            f"👤 {safe(row['name'])}\n"
            f"🛫 {safe(row['tour_from'])}\n"
            f"📅 {safe(row['tour_date_from'])} → {safe(row['tour_date_to'])}\n"
            f"📝 {safe(row['tour_notes'])}\n"
            f"📞 {safe(row['contact'])}"
        )

    return (
        f"{vip}👗 <b>{safe(row['name'])}</b>, {safe(row['age'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📍 {safe(row['city'])}\n"
        f"🌍 {safe(row['origin'])}\n"
        f"📏 {safe(row['height'])} cm • ⚖️ {safe(row['weight'])} kg\n"
        f"📐 {safe(row['measurements'])}\n"
        f"💇 {safe(row['hair'])} • 👁 {safe(row['eyes'])}\n"
        f"✨ {safe(row['body_type'])} • 💎 {safe(row['breast_type'])}\n"
        f"🚬 {safe(row['smoker'])} • 🖋 {safe(row['tattoos'])}\n"
        f"🗣 {safe(row['languages'])}\n"
        f"🏠 {safe(row['incall'])}\n"
        f"🕐 {safe(row['availability'])}\n"
        f"💶 {safe(price_summary(prices))}\n\n"
        f"📝 {safe(row['description'])}\n"
        f"📞 {safe(row['contact'])}"
    )

def build_draft_preview(data: Dict[str, Any], lang_code: str) -> str:
    if data["flow"] == "annonce":
        return (
            f"<b>{safe(data['ad_title'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(data['city'])}\n"
            f"📋 {safe(data['ad_desc'])}\n"
            f"📞 {safe(data['contact'])}"
        )

    if data["flow"] == "tour":
        who_label = "👗 Modèle" if data.get("tour_who") == "model" and lang_code == "fr" else \
                    "👗 Model" if data.get("tour_who") == "model" else \
                    "🏨 Hôte" if data.get("tour_who") == "host" and lang_code == "fr" else \
                    "🏨 Host" if data.get("tour_who") == "host" else "-"
        return (
            f"✈️ <b>Tours</b> — {safe(who_label)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(data['city'])}\n"
            f"👤 {safe(data['name'])}\n"
            f"🛫 {safe(data['tour_from'])}\n"
            f"📅 {safe(data['tour_date_from'])} → {safe(data['tour_date_to'])}\n"
            f"📝 {safe(data['tour_notes'])}\n"
            f"📞 {safe(data['contact'])}"
        )

    return (
        f"👗 <b>{safe(data['name'])}</b>, {safe(data['age'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📍 {safe(data['city'])}\n"
        f"🌍 {safe(data['origin'])}\n"
        f"📏 {safe(data['height'])} cm • ⚖️ {safe(data['weight'])} kg\n"
        f"📐 {safe(data['measurements'])}\n"
        f"💇 {safe(data['hair'])} • 👁 {safe(data['eyes'])}\n"
        f"✨ {safe(data['body_type'])} • 💎 {safe(data['breast_type'])}\n"
        f"🚬 {safe(data['smoker'])} • 🖋 {safe(data['tattoos'])}\n"
        f"🗣 {safe(', '.join(data['languages']))}\n"
        f"🏠 {safe(data['incall'])}\n"
        f"🕐 {safe(data['availability'])}\n"
        f"💶 {safe(price_summary(data['prices']))}\n\n"
        f"📝 {safe(data['description'])}\n"
        f"📞 {safe(data['contact'])}"
    )

def build_admin_preview(row) -> str:
    prices = json.loads(row["prices_json"] or "{}")
    return (
        f"🔔 <b>Новая заявка #{row['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Тип: {safe(row['flow'])}\n"
        f"User: {safe(row['username'])}\n"
        f"User ID: <code>{safe(row['user_id'])}</code>\n"
        f"Регион: {safe(row['region'])}\n"
        f"Город: {safe(row['city'])}\n"
        f"Имя: {safe(row['name'] or row['ad_title'])}\n"
        f"Возраст: {safe(row['age'])}\n"
        f"Происхождение: {safe(row['origin'])}\n"
        f"Рост: {safe(row['height'])}\n"
        f"Вес: {safe(row['weight'])}\n"
        f"Параметры: {safe(row['measurements'])}\n"
        f"Волосы: {safe(row['hair'])}\n"
        f"Глаза: {safe(row['eyes'])}\n"
        f"Языки: {safe(row['languages'])}\n"
        f"Силуэт: {safe(row['body_type'])}\n"
        f"Poitrine: {safe(row['breast_type'])}\n"
        f"Smoker: {safe(row['smoker'])}\n"
        f"Tattoos: {safe(row['tattoos'])}\n"
        f"Формат: {safe(row['incall'])}\n"
        f"Доступность: {safe(row['availability'])}\n"
        f"Цены: {safe(price_summary(prices))}\n"
        f"Описание: {safe(row['description'])}\n"
        f"Контакт: {safe(row['contact'])}\n"
        f"Tour who: {safe(row['tour_who'])}\n"
        f"From: {safe(row['tour_from'])}\n"
        f"Dates: {safe(row['tour_date_from'])} → {safe(row['tour_date_to'])}\n"
        f"Notes: {safe(row['tour_notes'])}\n"
        f"Заголовок: {safe(row['ad_title'])}\n"
        f"Текст объявления: {safe(row['ad_desc'])}"
    )

# ─────────────────────────────────────────────────────────────
# START / MENU
# ─────────────────────────────────────────────────────────────

@safe_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_draft(context)
    user = update.effective_user
    if user:
        db.upsert_user(user.id, get_username(update))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(TEXTS["fr"]["site"], web_app=WebAppInfo(url=MINIAPP_URL))],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ])
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg:
        await msg.reply_text(TEXTS["fr"]["greeting"], parse_mode=ParseMode.HTML, reply_markup=kb)
    return LANG_CHOOSE

@safe_handler
async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_code = q.data.replace("lang_", "")
    context.user_data["lang"] = lang_code
    db.upsert_user(q.from_user.id, get_username(update), lang_code)
    await safe_edit_or_reply(q, TEXTS[lang_code]["welcome"], main_menu_keyboard(context, q.from_user.id))
    return MAIN_MENU

@safe_handler
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        db.upsert_user(user.id, get_username(update))
        if "lang" not in context.user_data:
            context.user_data["lang"] = db.get_lang(user.id)
    text = t(context, "welcome")
    kb = main_menu_keyboard(context, user.id if user else None)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit_or_reply(update.callback_query, text, kb)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return MAIN_MENU

# ─────────────────────────────────────────────────────────────
# BROWSE
# ─────────────────────────────────────────────────────────────

@safe_handler
async def pick_city_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await safe_edit_or_reply(q, t(context, "choose_region"), region_keyboard(context, "pick"))
    return PICK_REGION_FOR_MENU

@safe_handler
async def picked_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("pick_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    context.user_data["browse_region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "pick"))
    return PICK_CITY_FOR_MENU

@safe_handler
async def picked_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "pick_back_region":
        return await pick_city_menu(update, context)
    idx = int(q.data.replace("pick_c_", ""))
    region = context.user_data.get("browse_region", "")
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await show_menu(update, context)
    city = cities[idx]
    context.user_data["browse_city"] = city
    await safe_edit_or_reply(q, t(context, "what_next", city=city), city_action_keyboard(context))
    return BROWSE_MENU

@safe_handler
async def city_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    city = context.user_data.get("browse_city", "")
    if q.data == "back_city_actions":
        await safe_edit_or_reply(q, t(context, "what_next", city=city), city_action_keyboard(context))
        return BROWSE_MENU
    if q.data == "browse_ads":
        await safe_edit_or_reply(q, t(context, "ads_filters", city=city), ads_filter_keyboard(context))
        return BROWSE_AD_FILTER
    if q.data == "browse_tours":
        await safe_edit_or_reply(q, t(context, "tour_filters", city=city), tours_filter_keyboard(context))
        return BROWSE_TOUR_FILTER
    if q.data == "flow_tour_request_city":
        d = draft(context)
        d["flow"] = "model"
        d["region"] = context.user_data.get("browse_region", "")
        d["city"] = city
        await safe_edit_or_reply(q, t(context, "tour_intro"))
        await q.message.reply_text(t(context, "ask_name"), parse_mode=ParseMode.HTML)
        return MODEL_NAME
    return BROWSE_MENU

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE, flow: str, **filters_kwargs):
    q = update.callback_query
    await q.answer()
    city = context.user_data.get("browse_city", "")
    rows = db.browse(city, flow, **filters_kwargs)
    if not rows:
        await safe_edit_or_reply(q, t(context, "empty_results"), InlineKeyboardMarkup([[InlineKeyboardButton(t(context, "back"), callback_data="back_city_actions")]]))
        return MAIN_MENU
    await safe_edit_or_reply(q, f"📍 <b>{safe(city)}</b> — {len(rows)}", InlineKeyboardMarkup([[InlineKeyboardButton(t(context, "back"), callback_data="back_city_actions")]]))
    for row in rows:
        await send_album(context.bot, q.message.chat_id, db.get_media(row["id"]), build_listing_text(row, get_lang_from_ctx(context)), listing_actions_keyboard(context, row["contact"]))
    await q.message.reply_text(t(context, "results_end"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(t(context, "back"), callback_data="back_city_actions")],
        [InlineKeyboardButton(t(context, "menu"), callback_data="go_menu")]
    ]))
    return MAIN_MENU

@safe_handler
async def browse_ads_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    mapping = {
        "ads_all": {},
        "ads_vip": {"vip_only": True},
        "ads_recent": {"recent_only": True},
        "ads_incall": {"incall_contains": "Incall"},
        "ads_outcall": {"incall_contains": "Outcall"},
        "ads_blonde": {"hair_contains": "Blonde"},
        "ads_brune": {"hair_contains": "Brune"},
    }
    if q.data in mapping:
        return await show_results(update, context, "annonce", **mapping[q.data])
    return await city_actions(update, context)

@safe_handler
async def browse_tours_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    mapping = {
        "tours_all": {},
        "tours_vip": {"vip_only": True},
        "tours_recent": {"recent_only": True},
        "tours_model": {"tour_who": "model"},
        "tours_host": {"tour_who": "host"},
    }
    if q.data in mapping:
        return await show_results(update, context, "tour", **mapping[q.data])
    return await city_actions(update, context)

# ─────────────────────────────────────────────────────────────
# MODEL FLOW
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_model_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    reset_draft(context)
    d = draft(context)
    d["flow"] = "model"
    await safe_edit_or_reply(q, t(context, "tour_intro"), region_keyboard(context, "mr"))
    return MODEL_REGION

@safe_handler
async def model_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("mr_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    draft(context)["region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "mr"))
    return MODEL_CITY

@safe_handler
async def model_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "mr_back_region":
        return await go_model_request(update, context)
    idx = int(q.data.replace("mr_c_", ""))
    region = draft(context)["region"]
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await go_model_request(update, context)
    draft(context)["city"] = cities[idx]
    await safe_edit_or_reply(q, f"📍 <b>{safe(cities[idx])}</b>")
    await q.message.reply_text(t(context, "ask_name"), parse_mode=ParseMode.HTML)
    return MODEL_NAME

@safe_handler
async def model_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 2:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_NAME
    if too_long(value, 80):
        await update.message.reply_text(t(context, "too_long"))
        return MODEL_NAME
    draft(context)["name"] = value
    await update.message.reply_text(t(context, "ask_age"), parse_mode=ParseMode.HTML)
    return MODEL_AGE

@safe_handler
async def model_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_age(value):
        await update.message.reply_text(t(context, "invalid_age"))
        return MODEL_AGE
    draft(context)["age"] = value
    await update.message.reply_text(t(context, "ask_origin"), parse_mode=ParseMode.HTML)
    return MODEL_ORIGIN

@safe_handler
async def model_origin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 2:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_ORIGIN
    draft(context)["origin"] = value
    await update.message.reply_text(t(context, "ask_height"), parse_mode=ParseMode.HTML)
    return MODEL_HEIGHT

@safe_handler
async def model_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_height(value):
        await update.message.reply_text(t(context, "invalid_height"))
        return MODEL_HEIGHT
    draft(context)["height"] = value
    await update.message.reply_text(t(context, "ask_weight"), parse_mode=ParseMode.HTML)
    return MODEL_WEIGHT

@safe_handler
async def model_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_weight(value):
        await update.message.reply_text(t(context, "invalid_weight"))
        return MODEL_WEIGHT
    draft(context)["weight"] = value
    await update.message.reply_text(t(context, "ask_measurements"), parse_mode=ParseMode.HTML)
    return MODEL_MEASUREMENTS

@safe_handler
async def model_measurements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 3:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_MEASUREMENTS
    draft(context)["measurements"] = value
    await update.message.reply_text(t(context, "ask_hair"), parse_mode=ParseMode.HTML, reply_markup=simple_rows(HAIR_OPTIONS, "hair", context))
    return MODEL_HAIR

@safe_handler
async def model_hair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("hair_", ""))
    draft(context)["hair"] = choice_label(HAIR_OPTIONS[idx], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_eyes"), simple_rows(EYE_OPTIONS, "eyes", context))
    return MODEL_EYES

@safe_handler
async def model_eyes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("eyes_", ""))
    draft(context)["eyes"] = choice_label(EYE_OPTIONS[idx], get_lang_from_ctx(context))
    context.user_data["selected_lang_codes"] = []
    await safe_edit_or_reply(q, t(context, "ask_languages"), languages_keyboard(context))
    return MODEL_LANGS

@safe_handler
async def model_langs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    selected = context.user_data.get("selected_lang_codes", [])
    if q.data == "ml_done":
        if not selected:
            await q.answer("Sélectionnez au moins une langue" if get_lang_from_ctx(context) == "fr" else "Select at least one language", show_alert=True)
            return MODEL_LANGS
        labels = [choice_label(LANG_OPTIONS[idx], get_lang_from_ctx(context)) for idx in selected]
        draft(context)["languages"] = labels
        await safe_edit_or_reply(q, t(context, "ask_body_type"), simple_rows(BODY_TYPE_OPTIONS, "body", context))
        return MODEL_BODY
    idx = int(q.data.replace("ml_", ""))
    if idx in selected:
        selected.remove(idx)
    else:
        selected.append(idx)
    context.user_data["selected_lang_codes"] = selected
    return MODEL_LANGS

@safe_handler
async def model_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["body_type"] = choice_label(BODY_TYPE_OPTIONS[int(q.data.replace("body_", ""))], get_lang_from_ctx(context))
    opts = [("💎 Naturelle", "Naturelle", "Natural"), ("✨ Silicone", "Silicone", "Silicone")]
    await safe_edit_or_reply(q, t(context, "ask_breast"), simple_rows(opts, "breast", context))
    return MODEL_BREAST

@safe_handler
async def model_breast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    opts = [("💎 Naturelle", "Naturelle", "Natural"), ("✨ Silicone", "Silicone", "Silicone")]
    draft(context)["breast_type"] = choice_label(opts[int(q.data.replace("breast_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_smoker"), simple_rows(YES_NO_OPTIONS, "smoker", context))
    return MODEL_SMOKER

@safe_handler
async def model_smoker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["smoker"] = choice_label(YES_NO_OPTIONS[int(q.data.replace("smoker_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_tattoos"), simple_rows(YES_NO_OPTIONS, "tattoos", context))
    return MODEL_TATTOOS

@safe_handler
async def model_tattoos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["tattoos"] = choice_label(YES_NO_OPTIONS[int(q.data.replace("tattoos_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_incall"), simple_rows(INCALL_OPTIONS, "incall", context))
    return MODEL_INCALL

@safe_handler
async def model_incall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["incall"] = choice_label(INCALL_OPTIONS[int(q.data.replace("incall_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_availability"), simple_rows(AVAILABILITY_OPTIONS, "avail", context))
    return MODEL_AVAILABILITY

@safe_handler
async def model_availability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["availability"] = choice_label(AVAILABILITY_OPTIONS[int(q.data.replace("avail_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_prices"))
    await q.message.reply_text(t(context, "ask_prices"), parse_mode=ParseMode.HTML)
    return MODEL_PRICES

@safe_handler
async def model_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = parse_prices(update.message.text)
    if not prices:
        await update.message.reply_text(t(context, "ask_prices"))
        return MODEL_PRICES
    draft(context)["prices"] = prices
    await update.message.reply_text(t(context, "ask_desc"), parse_mode=ParseMode.HTML)
    return MODEL_DESC

@safe_handler
async def model_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 10:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_DESC
    if too_long(value):
        await update.message.reply_text(t(context, "too_long"))
        return MODEL_DESC
    draft(context)["description"] = value
    await update.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return MODEL_CONTACT

@safe_handler
async def model_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not valid_contact(value):
        await update.message.reply_text(t(context, "invalid_contact"))
        return MODEL_CONTACT
    draft(context)["contact"] = value
    draft(context)["photos"] = []
    await update.message.reply_text(t(context, "ask_photos"), parse_mode=ParseMode.HTML, reply_markup=photo_stage_keyboard(context))
    return MODEL_PHOTOS

# ─────────────────────────────────────────────────────────────
# TOUR FLOW
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_tour_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    reset_draft(context)
    draft(context)["flow"] = "tour"
    await safe_edit_or_reply(q, t(context, "choose_region"), region_keyboard(context, "tr"))
    return TOUR_REGION

@safe_handler
async def tour_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("tr_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    draft(context)["region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "tr"))
    return TOUR_CITY

@safe_handler
async def tour_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "tr_back_region":
        return await go_tour_flow(update, context)
    idx = int(q.data.replace("tr_c_", ""))
    region = draft(context)["region"]
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await go_tour_flow(update, context)
    draft(context)["city"] = cities[idx]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👗 Je suis modèle" if get_lang_from_ctx(context) == "fr" else "👗 I am a model", callback_data="tourwho_model")],
        [InlineKeyboardButton("🏨 J'accueille des modèles" if get_lang_from_ctx(context) == "fr" else "🏨 I host models", callback_data="tourwho_host")],
        [InlineKeyboardButton(t(context, "cancel"), callback_data="go_menu")]
    ])
    await safe_edit_or_reply(q, t(context, "tour_who_prompt"), kb)
    return TOUR_WHO

@safe_handler
async def tour_who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["tour_who"] = q.data.replace("tourwho_", "")
    await safe_edit_or_reply(q, t(context, "tour_ask_from"))
    await q.message.reply_text(t(context, "tour_ask_from"), parse_mode=ParseMode.HTML)
    return TOUR_FROM

@safe_handler
async def tour_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_from"] = update.message.text.strip()
    await update.message.reply_text(t(context, "tour_ask_date_from"), parse_mode=ParseMode.HTML)
    return TOUR_DATE_FROM

@safe_handler
async def tour_date_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_date_from"] = update.message.text.strip()
    await update.message.reply_text(t(context, "tour_ask_date_to"), parse_mode=ParseMode.HTML)
    return TOUR_DATE_TO

@safe_handler
async def tour_date_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_date_to"] = update.message.text.strip()
    await update.message.reply_text(t(context, "ask_name"), parse_mode=ParseMode.HTML)
    return TOUR_NAME

@safe_handler
async def tour_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["name"] = update.message.text.strip()
    await update.message.reply_text(t(context, "tour_ask_notes"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(t(context, "skip"), callback_data="tour_skip_notes")],
        [InlineKeyboardButton(t(context, "cancel"), callback_data="go_menu")]
    ]))
    return TOUR_NOTES

@safe_handler
async def tour_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_notes"] = update.message.text.strip()
    await update.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return TOUR_CONTACT

@safe_handler
async def tour_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["tour_notes"] = "-"
    await safe_edit_or_reply(q, t(context, "ask_contact"))
    await q.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return TOUR_CONTACT

@safe_handler
async def tour_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not valid_contact(value):
        await update.message.reply_text(t(context, "invalid_contact"))
        return TOUR_CONTACT
    draft(context)["contact"] = value
    draft(context)["photos"] = []
    await update.message.reply_text(t(context, "ask_photos"), parse_mode=ParseMode.HTML, reply_markup=photo_stage_keyboard(context))
    return TOUR_PHOTOS

# ─────────────────────────────────────────────────────────────
# AD FLOW
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_ad_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    reset_draft(context)
    draft(context)["flow"] = "annonce"
    await safe_edit_or_reply(q, t(context, "choose_region"), region_keyboard(context, "ad"))
    return AD_REGION

@safe_handler
async def ad_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("ad_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    draft(context)["region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "ad"))
    return AD_CITY

@safe_handler
async def ad_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "ad_back_region":
        return await go_ad_flow(update, context)
    idx = int(q.data.replace("ad_c_", ""))
    region = draft(context)["region"]
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await go_ad_flow(update, context)
    draft(context)["city"] = cities[idx]
    await safe_edit_or_reply(q, t(context, "tour_ask_title"))
    await q.message.reply_text(t(context, "tour_ask_title"), parse_mode=ParseMode.HTML)
    return AD_TITLE

@safe_handler
async def ad_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 3:
        await update.message.reply_text(t(context, "invalid_short"))
        return AD_TITLE
    draft(context)["ad_title"] = value
    await update.message.reply_text(t(context, "tour_ask_ad_desc"), parse_mode=ParseMode.HTML)
    return AD_DESC

@safe_handler
async def ad_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 5:
        await update.message.reply_text(t(context, "invalid_short"))
        return AD_DESC
    draft(context)["ad_desc"] = value
    await update.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return AD_CONTACT

@safe_handler
async def ad_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not valid_contact(value):
        await update.message.reply_text(t(context, "invalid_contact"))
        return AD_CONTACT
    draft(context)["contact"] = value
    draft(context)["photos"] = []
    await update.message.reply_text(t(context, "ask_photos"), parse_mode=ParseMode.HTML, reply_markup=photo_stage_keyboard(context))
    return AD_PHOTOS

# ─────────────────────────────────────────────────────────────
# PHOTOS / PREVIEW / SUBMIT
# ─────────────────────────────────────────────────────────────

@safe_handler
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = draft(context)
    photos = d.get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"⚠️ Maximum {MAX_PHOTOS} photos.")
        return
    photos.append(update.message.photo[-1].file_id)
    d["photos"] = photos
    await update.message.reply_text(f"📸 {len(photos)}/{MAX_PHOTOS}")

@safe_handler
async def photos_text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(context, "photos_only"))

@safe_handler
async def photos_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = draft(context)
    if not d.get("photos"):
        await q.answer(t(context, "need_photo"), show_alert=True)
        return
    preview = build_draft_preview(d, get_lang_from_ctx(context))
    await safe_edit_or_reply(q, f"{t(context, 'preview_title')}\n\n{preview}", preview_keyboard(context))
    flow = d.get("flow")
    if flow == "model":
        return MODEL_PREVIEW
    if flow == "tour":
        return TOUR_PREVIEW
    return AD_PREVIEW

@safe_handler
async def submit_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = draft(context)
    user = update.effective_user
    if not user:
        return await show_menu(update, context)
    d["user_id"] = user.id
    d["username"] = get_username(update)

    if db.count_user_active(user.id) >= MAX_ACTIVE_PER_USER:
        await q.answer(t(context, "limit_reached"), show_alert=True)
        return

    listing_id = db.create_listing(d, d.get("photos", []))
    row = db.get_listing(listing_id)
    if row:
        await send_album(context.bot, ADMIN_ID, db.get_media(listing_id), build_admin_preview(row), moderation_keyboard(listing_id, row["contact"]))
    await safe_edit_or_reply(q, t(context, "sent_moderation"), main_menu_keyboard(context, user.id))
    reset_draft(context)
    return MAIN_MENU

# ─────────────────────────────────────────────────────────────
# ADMIN
# ─────────────────────────────────────────────────────────────

@safe_handler
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id != ADMIN_ID:
        if q:
            await q.answer("Доступ запрещён", show_alert=True)
        return MAIN_MENU
    stats = db.stats()
    text = (
        "🔐 <b>Панель администратора</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"⏳ На модерации: <b>{stats['pending']}</b>\n"
        f"✅ Активных: <b>{stats['approved']}</b>\n"
        f"⭐ VIP: <b>{stats['vip']}</b>\n"
        f"🆕 За 24ч: <b>{stats['today']}</b>"
    )
    if q:
        await q.answer()
        await safe_edit_or_reply(q, text, admin_menu_keyboard())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=admin_menu_keyboard())
    return ADMIN_MENU

@safe_handler
async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("Доступ запрещён", show_alert=True)
        return ADMIN_MENU

    if q.data == "adm_stats":
        return await admin_panel(update, context)

    if q.data == "adm_pending":
        rows = db.pending()
        if not rows:
            await safe_edit_or_reply(q, "✅ Нет заявок на модерации.", admin_menu_keyboard())
            return ADMIN_MENU
        lines = ["📋 <b>Заявки на модерации</b>\n"]
        for r in rows[:25]:
            title = r["name"] or r["ad_title"] or "-"
            lines.append(f"#{r['id']} • {safe(r['flow'])} • {safe(r['city'])} • {safe(title)}")
        await safe_edit_or_reply(q, "\n".join(lines), admin_menu_keyboard())
        return ADMIN_MENU

    if q.data == "adm_active":
        rows = db.all_active()
        if not rows:
            await safe_edit_or_reply(q, "Нет активных публикаций.", admin_menu_keyboard())
            return ADMIN_MENU
        lines = ["🗂 <b>Активные публикации</b>\n"]
        for r in rows[:30]:
            vip = "⭐ " if r["is_vip"] else ""
            title = r["name"] or r["ad_title"] or "-"
            lines.append(f"#{r['id']} • {vip}{safe(r['flow'])} • {safe(r['city'])} • {safe(title)}")
        await safe_edit_or_reply(q, "\n".join(lines), admin_menu_keyboard())
        return ADMIN_MENU

    return ADMIN_MENU

@safe_handler
async def admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        return
    parts = q.data.split("_")
    if len(parts) < 3:
        return
    listing_id = int(parts[2])
    row = db.get_listing(listing_id)
    if not row:
        await safe_edit_or_reply(q, "⚠️ Заявка не найдена.")
        return
    await send_album(context.bot, ADMIN_ID, db.get_media(listing_id), build_admin_preview(row), moderation_keyboard(listing_id, row["contact"]))

@safe_handler
async def moderation_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("Доступ запрещён", show_alert=True)
        return
    parts = q.data.split("_")
    if len(parts) < 3:
        return
    _, action, listing_id_raw = parts
    listing_id = int(listing_id_raw)
    row = db.get_listing(listing_id)
    if not row:
        await safe_edit_or_reply(q, "⚠️ Заявка не найдена.")
        return

    if action == "reject":
        db.update_status(listing_id, "rejected")
        await safe_edit_or_reply(q, f"❌ Заявка #{listing_id} отклонена.")
        if row["user_id"]:
            try:
                lang_code = db.get_lang(row["user_id"])
                msg = "❌ Votre publication a été refusée." if lang_code == "fr" else "❌ Your publication was rejected."
                await context.bot.send_message(chat_id=row["user_id"], text=msg)
            except Exception:
                pass
        return

    if action == "delete":
        db.delete_listing(listing_id)
        await safe_edit_or_reply(q, f"🗑 Заявка #{listing_id} удалена.")
        return

    is_vip = action == "vip"
    db.update_status(listing_id, "approved", is_vip=is_vip)
    fresh_row = db.get_listing(listing_id)
    if fresh_row:
        text = build_listing_text(fresh_row, db.get_lang(fresh_row["user_id"]) if fresh_row["user_id"] else "fr")
        await send_album(context.bot, CHANNEL_ID, db.get_media(listing_id), text, listing_actions_keyboard(context, fresh_row["contact"]))
    await safe_edit_or_reply(q, f"✅ Заявка #{listing_id} опубликована{' как VIP' if is_vip else ''}.")
    if row["user_id"]:
        try:
            lang_code = db.get_lang(row["user_id"])
            msg = "✅ Votre publication est en ligne." if lang_code == "fr" else "✅ Your publication is live."
            if is_vip:
                msg += "\n⭐ VIP"
            await context.bot.send_message(chat_id=row["user_id"], text=msg)
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────
# COMMON
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_draft(context)
    return await show_menu(update, context)

@safe_handler
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(t(context, "unknown"))

async def cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    db.cleanup_expired()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    exc = context.error
    if isinstance(exc, RetryAfter):
        logger.warning("RetryAfter %s", exc.retry_after)
        await asyncio.sleep(float(exc.retry_after))
        return
    if isinstance(exc, (TimedOut, NetworkError)):
        logger.warning("Transient error: %s", exc)
        return
    logger.exception("Unhandled error: %s", exc)
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 BOT ERROR:\n{str(exc)[:800]}")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────

def build_app() -> Application:
    if BOT_TOKEN == "PASTE_BOT_TOKEN":
        raise RuntimeError("BOT_TOKEN not configured")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
        ],
        states={
            LANG_CHOOSE: [CallbackQueryHandler(choose_lang, pattern=r"^lang_(fr|en)$")],
            MAIN_MENU: [
                CallbackQueryHandler(pick_city_menu, pattern=r"^pick_city_menu$"),
                CallbackQueryHandler(go_tour_flow, pattern=r"^go_tour_flow$"),
                CallbackQueryHandler(go_model_request, pattern=r"^flow_tour_request$"),
                CallbackQueryHandler(admin_panel, pattern=r"^go_admin$"),
            ],
            PICK_REGION_FOR_MENU: [
                CallbackQueryHandler(picked_region, pattern=r"^pick_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            PICK_CITY_FOR_MENU: [
                CallbackQueryHandler(picked_city, pattern=r"^(pick_c_\d+|pick_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            BROWSE_MENU: [
                CallbackQueryHandler(city_actions, pattern=r"^(browse_ads|browse_tours|flow_tour_request_city|back_city_actions)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            BROWSE_AD_FILTER: [
                CallbackQueryHandler(browse_ads_filter, pattern=r"^(ads_all|ads_vip|ads_recent|ads_incall|ads_outcall|ads_blonde|ads_brune|back_city_actions)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            BROWSE_TOUR_FILTER: [
                CallbackQueryHandler(browse_tours_filter, pattern=r"^(tours_all|tours_model|tours_host|tours_vip|tours_recent|back_city_actions)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_REGION: [
                CallbackQueryHandler(model_region, pattern=r"^mr_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_CITY: [
                CallbackQueryHandler(model_city, pattern=r"^(mr_c_\d+|mr_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_name)],
            MODEL_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_age)],
            MODEL_ORIGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_origin)],
            MODEL_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_height)],
            MODEL_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_weight)],
            MODEL_MEASUREMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_measurements)],
            MODEL_HAIR: [
                CallbackQueryHandler(model_hair, pattern=r"^hair_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_EYES: [
                CallbackQueryHandler(model_eyes, pattern=r"^eyes_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_LANGS: [
                CallbackQueryHandler(model_langs, pattern=r"^(ml_\d+|ml_done)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_BODY: [
                CallbackQueryHandler(model_body, pattern=r"^body_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_BREAST: [
                CallbackQueryHandler(model_breast, pattern=r"^breast_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_SMOKER: [
                CallbackQueryHandler(model_smoker, pattern=r"^smoker_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_TATTOOS: [
                CallbackQueryHandler(model_tattoos, pattern=r"^tattoos_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_INCALL: [
                CallbackQueryHandler(model_incall, pattern=r"^incall_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_AVAILABILITY: [
                CallbackQueryHandler(model_availability, pattern=r"^avail_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_PRICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_prices)],
            MODEL_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_desc)],
            MODEL_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_contact)],
            MODEL_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photos_text_fallback),
                CallbackQueryHandler(photos_done, pattern=r"^photos_done$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_PREVIEW: [
                CallbackQueryHandler(submit_confirm, pattern=r"^submit_confirm$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_REGION: [
                CallbackQueryHandler(tour_region, pattern=r"^tr_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_CITY: [
                CallbackQueryHandler(tour_city, pattern=r"^(tr_c_\d+|tr_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_WHO: [
                CallbackQueryHandler(tour_who, pattern=r"^tourwho_(model|host)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_from)],
            TOUR_DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_from)],
            TOUR_DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_to)],
            TOUR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_name)],
            TOUR_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tour_notes),
                CallbackQueryHandler(tour_skip_notes, pattern=r"^tour_skip_notes$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_contact)],
            TOUR_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photos_text_fallback),
                CallbackQueryHandler(photos_done, pattern=r"^photos_done$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_PREVIEW: [
                CallbackQueryHandler(submit_confirm, pattern=r"^submit_confirm$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_REGION: [
                CallbackQueryHandler(ad_region, pattern=r"^ad_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_CITY: [
                CallbackQueryHandler(ad_city, pattern=r"^(ad_c_\d+|ad_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_title)],
            AD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_desc)],
            AD_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_contact)],
            AD_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photos_text_fallback),
                CallbackQueryHandler(photos_done, pattern=r"^photos_done$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_PREVIEW: [
                CallbackQueryHandler(submit_confirm, pattern=r"^submit_confirm$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            ADMIN_MENU: [
                CallbackQueryHandler(admin_actions, pattern=r"^adm_(pending|active|stats)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(go_ad_flow, pattern=r"^browse_ads$"))
    app.add_handler(CallbackQueryHandler(go_tour_flow, pattern=r"^browse_tours$"))
    app.add_handler(CallbackQueryHandler(admin_view, pattern=r"^adm_view_\d+$"))
    app.add_handler(CallbackQueryHandler(moderation_action, pattern=r"^adm_(approve|vip|reject|delete)_\d+$"))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(cleanup_job, interval=CLEANUP_INTERVAL_SECONDS, first=10)

    return app

def main():
    app = build_app()
    logger.info("Amour Annonce ULTRA PRO BUSINESS started")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
'''

out = Path("/mnt/data/amour_annonce_ultra_pro_business.py")
out.write_text(code, encoding="utf-8")

import py_compile
py_compile.compile(str(out), doraise=True)

print(f"Saved: {out}")
print(f"Lines: {len(code.splitlines())}")
    InlineKeyboardMarkup,
    InputMediaPhoto,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN", "8549540559:AAEd3EllVX0oQnaRUooL54krXwSwg5Iz_wA")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1003761619638")
ADMIN_ID = int(os.getenv("ADMIN_ID", "2021397237"))
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/loveparis777")
VMODLS_URL = os.getenv("VMODLS_URL", "https://t.me/VModls")
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://www.amourannonce.com")
DB_PATH = os.getenv("DB_PATH", "amour_annonce_ultra_business.db")
MAX_PHOTOS = min(int(os.getenv("MAX_PHOTOS", "8")), 10)
MAX_ACTIVE_PER_USER = int(os.getenv("MAX_ACTIVE_PER_USER", "3"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "3600"))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("amour_annonce_ultra_business")

# ─────────────────────────────────────────────────────────────
# REGIONS / OPTIONS
# ─────────────────────────────────────────────────────────────

REGIONS: Dict[str, List[str]] = {
    "🗼 Paris — Centre & Luxe": [
        "Paris 1er — Louvre / Centre",
        "Paris 2e — Bourse",
        "Paris 3e — Marais",
        "Paris 4e — Île Saint-Louis",
        "Paris 5e — Quartier Latin",
        "Paris 6e — Saint-Germain-des-Prés",
        "Paris 7e — Eiffel / Invalides",
        "Paris 8e — Champs-Élysées",
        "Paris 9e — Opéra",
        "Paris 10e — Canal Saint-Martin",
        "Paris 11e — Bastille",
        "Paris 12e — Bercy",
        "Paris 13e — Place d’Italie",
        "Paris 14e — Montparnasse",
        "Paris 15e — Convention",
        "Paris 16e — Trocadéro",
        "Paris 17e — Batignolles",
        "Paris 18e — Montmartre",
        "Paris 19e — La Villette",
        "Paris 20e — Belleville",
    ],
    "🏙 Île-de-France — Proche banlieue": [
        "Boulogne-Billancourt", "Neuilly-sur-Seine", "Levallois-Perret",
        "Issy-les-Moulineaux", "Courbevoie", "La Défense", "Puteaux",
        "Saint-Cloud", "Vincennes", "Saint-Mandé", "Montreuil",
        "Bagnolet", "Saint-Denis", "Aubervilliers", "Pantin",
        "Les Lilas", "Nogent-sur-Marne", "Créteil",
    ],
    "🏙 Île-de-France — Grande banlieue": [
        "Versailles", "Saint-Germain-en-Laye", "Massy", "Évry-Courcouronnes",
        "Pontoise", "Cergy", "Melun", "Fontainebleau", "Meaux",
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
    "🌸 Occitanie": [
        "Toulouse", "Montpellier", "Perpignan", "Nîmes",
        "Sète", "Béziers", "Montauban",
    ],
    "🍷 Nouvelle-Aquitaine": [
        "Bordeaux", "Biarritz", "Arcachon", "Bayonne", "La Rochelle",
        "Pau", "Périgueux", "Limoges", "Poitiers",
    ],
    "⚓ Pays de la Loire": ["Nantes", "Angers", "Le Mans", "Saint-Nazaire"],
    "🥨 Grand Est": ["Strasbourg", "Reims", "Metz", "Nancy", "Mulhouse", "Colmar"],
    "🍇 Bourgogne-Franche-Comté": ["Dijon", "Besançon", "Belfort"],
    "🌿 Normandie": ["Rouen", "Caen", "Le Havre", "Deauville", "Cherbourg"],
    "🏛 Hauts-de-France": ["Lille", "Amiens", "Dunkerque", "Valenciennes"],
    "🌊 Bretagne": ["Rennes", "Brest", "Quimper", "Saint-Malo", "Lorient", "Vannes"],
    "🌺 Centre-Val de Loire": ["Tours", "Orléans", "Blois"],
}

HAIR_OPTIONS = [
    ("👱 Blonde", "Blonde", "Blonde"),
    ("🟤 Brune", "Brune", "Brunette"),
    ("🔴 Rousse", "Rousse", "Red hair"),
    ("⬛ Noire", "Noire", "Black hair"),
    ("🌰 Châtain", "Châtain", "Brown hair"),
    ("🎨 Colorée", "Colorée", "Colored"),
]

EYE_OPTIONS = [
    ("🔵 Bleus", "Bleus", "Blue"),
    ("🟢 Verts", "Verts", "Green"),
    ("🟤 Marron", "Marron", "Brown"),
    ("🟠 Noisette", "Noisette", "Hazel"),
    ("⚫ Noirs", "Noirs", "Black"),
]

INCALL_OPTIONS = [
    ("🏠 Incall uniquement", "Incall uniquement", "Incall only"),
    ("🚗 Outcall uniquement", "Outcall uniquement", "Outcall only"),
    ("🏠🚗 Incall + Outcall", "Incall + Outcall", "Incall + Outcall"),
]

AVAILABILITY_OPTIONS = [
    ("🕐 24h/24", "24h/24", "24/7"),
    ("☀️ En journée", "En journée", "Daytime"),
    ("🌙 En soirée", "En soirée", "Evening"),
    ("🌃 Nuits uniquement", "Nuits uniquement", "Nights only"),
    ("📅 Weekends", "Weekends", "Weekends"),
    ("📞 Sur rendez-vous", "Sur rendez-vous", "By appointment"),
]

BODY_TYPE_OPTIONS = [
    ("✨ Fine", "Fine", "Slim"),
    ("💪 Sportive", "Sportive", "Athletic"),
    ("🍑 Pulpeuse", "Pulpeuse", "Curvy"),
    ("💎 Élancée", "Élancée", "Tall / Elegant"),
]

YES_NO_OPTIONS = [
    ("✅ Oui", "Oui", "Yes"),
    ("❌ Non", "Non", "No"),
]

LANG_OPTIONS = [
    ("🇫🇷 Français", "Français", "French"),
    ("🇬🇧 Anglais", "Anglais", "English"),
    ("🇷🇺 Russe", "Russe", "Russian"),
    ("🇪🇸 Espagnol", "Espagnol", "Spanish"),
    ("🇮🇹 Italien", "Italien", "Italian"),
    ("🇩🇪 Allemand", "Allemand", "German"),
    ("🇵🇹 Portugais", "Portugais", "Portuguese"),
    ("🇸🇦 Arabe", "Arabe", "Arabic"),
    ("🇺🇦 Ukrainien", "Ukrainien", "Ukrainian"),
]

PRICE_SLOTS = [
    ("15min", "15 min"),
    ("20min", "20 min"),
    ("30min", "30 min"),
    ("45min", "45 min"),
    ("1h", "1h"),
    ("1h30", "1h30"),
    ("2h", "2h"),
    ("soiree", "Soirée"),
    ("nuit", "Nuit"),
]

# ─────────────────────────────────────────────────────────────
# TEXTS
# ─────────────────────────────────────────────────────────────

TEXTS = {
    "fr": {
        "greeting": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPlateforme privée premium pour annonces, tours et profils.\n\nChoisissez votre langue.",
        "welcome": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nChoisissez une option.",
        "site": "🌐 Ouvrir le site",
        "contact_admin": "💬 Contacter l’administration",
        "annonces": "📢 Annonces",
        "tours": "✈️ Tours",
        "tour_request": "👗 Je suis modèle — je cherche un tour",
        "admin": "🔐 Admin Panel",
        "back": "◀️ Retour",
        "menu": "🏠 Menu",
        "cancel": "✖️ Annuler",
        "skip": "⏭ Passer",
        "done": "✅ Terminer",
        "send": "✅ Envoyer",
        "choose_region": "📍 Choisissez votre région :",
        "choose_city": "🏙 Choisissez votre ville / arrondissement :",
        "what_next": "📍 <b>{city}</b>\n━━━━━━━━━━━━━━━━━━\nQue souhaitez-vous faire ?",
        "ads_filters": "📢 <b>Annonces — {city}</b>\nChoisissez un filtre :",
        "tour_filters": "✈️ <b>Tours — {city}</b>\nChoisissez un filtre :",
        "filter_all": "🔎 Tout voir",
        "filter_vip": "⭐ VIP",
        "filter_recent": "🆕 Récent",
        "filter_incall": "🏠 Incall",
        "filter_outcall": "🚗 Outcall",
        "filter_blonde": "👱 Blonde",
        "filter_brune": "🟤 Brune",
        "filter_hosts": "🏨 Hôtes",
        "filter_models_tour": "👗 Modèles",
        "contact_model": "💬 Contacter le profil",
        "empty_results": "😔 Aucun résultat pour le moment.",
        "results_end": "— Fin des résultats —",
        "tour_intro": "Bonjour ✨\n\nCommençons votre publication.",
        "ask_name": "👤 Votre prénom / nom d’annonce :",
        "ask_age": "🎂 Votre âge :\n<i>18–65</i>",
        "ask_origin": "🌍 Votre origine :",
        "ask_height": "📏 Votre taille en cm :",
        "ask_weight": "⚖️ Votre poids en kg :",
        "ask_measurements": "📐 Vos mensurations :\n<i>Ex: 90C - 60 - 90</i>",
        "ask_hair": "💇 Couleur de cheveux :",
        "ask_eyes": "👁 Couleur des yeux :",
        "ask_languages": "🗣 Langues parlées :",
        "confirm_languages": "✅ Confirmer les langues",
        "ask_body_type": "✨ Type de silhouette :",
        "ask_breast": "💎 Poitrine :",
        "ask_smoker": "🚬 Fumeuse ?",
        "ask_tattoos": "🖋 Tatouages ?",
        "ask_incall": "🏠 Type de service :",
        "ask_availability": "🕐 Disponibilités :",
        "ask_prices": "💶 Vos tarifs\n\nEntrez 9 lignes dans cet ordre:\n15 min:\n20 min:\n30 min:\n45 min:\n1h:\n1h30:\n2h:\nSoirée:\nNuit:\n\n👉 chiffres uniquement\n👉 0 = non disponible",
        "ask_desc": "📝 Décrivez-vous :",
        "ask_contact": "📞 Votre contact :\n<i>@telegram ou téléphone ou lien</i>",
        "ask_photos": f"📸 Envoyez vos photos (1–{MAX_PHOTOS}). Puis appuyez sur ✅ Terminer.",
        "preview_title": "👁 <b>Aperçu avant envoi</b>",
        "sent_moderation": "✅ Votre publication a été envoyée en modération.",
        "need_photo": "⚠️ Ajoutez au moins une photo.",
        "invalid_age": "⚠️ Âge invalide. Entrez un nombre entre 18 et 65.",
        "invalid_height": "⚠️ Taille invalide. Entrez un nombre entre 140 et 200.",
        "invalid_weight": "⚠️ Poids invalide. Entrez un nombre entre 40 et 120.",
        "invalid_contact": "⚠️ Contact invalide. Entrez un @username, un numéro ou un lien.",
        "invalid_short": "⚠️ Veuillez renseigner une valeur valide.",
        "too_long": "⚠️ Texte trop long.",
        "tour_ask_from": "🛫 Votre ville de départ :",
        "tour_ask_date_from": "📅 Date d’arrivée :",
        "tour_ask_date_to": "📅 Date de départ :",
        "tour_ask_notes": "📝 Notes / conditions :",
        "tour_ask_title": "📝 Titre de l’annonce :",
        "tour_ask_ad_desc": "📋 Description de l’annonce :",
        "tour_who_prompt": "Sélectionnez votre type :",
        "limit_reached": f"⚠️ Limite atteinte : {MAX_ACTIVE_PER_USER} publications actives/pending maximum.",
        "photos_only": "📸 Veuillez envoyer uniquement des photos.",
        "unknown": "Utilisez /start",
    },
    "en": {
        "greeting": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPrivate premium platform for ads, tours and profiles.\n\nChoose your language.",
        "welcome": "💎 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPlease choose an option.",
        "site": "🌐 Open website",
        "contact_admin": "💬 Contact administration",
        "annonces": "📢 Ads",
        "tours": "✈️ Tours",
        "tour_request": "👗 I am a model — looking for a tour",
        "admin": "🔐 Admin Panel",
        "back": "◀️ Back",
        "menu": "🏠 Menu",
        "cancel": "✖️ Cancel",
        "skip": "⏭ Skip",
        "done": "✅ Finish",
        "send": "✅ Send",
        "choose_region": "📍 Choose your region:",
        "choose_city": "🏙 Choose your city / district:",
        "what_next": "📍 <b>{city}</b>\n━━━━━━━━━━━━━━━━━━\nWhat would you like to do?",
        "ads_filters": "📢 <b>Ads — {city}</b>\nChoose a filter:",
        "tour_filters": "✈️ <b>Tours — {city}</b>\nChoose a filter:",
        "filter_all": "🔎 View all",
        "filter_vip": "⭐ VIP",
        "filter_recent": "🆕 Recent",
        "filter_incall": "🏠 Incall",
        "filter_outcall": "🚗 Outcall",
        "filter_blonde": "👱 Blonde",
        "filter_brune": "🟤 Brunette",
        "filter_hosts": "🏨 Hosts",
        "filter_models_tour": "👗 Models",
        "contact_model": "💬 Contact profile",
        "empty_results": "😔 No results yet.",
        "results_end": "— End of results —",
        "tour_intro": "Hello ✨\n\nLet's create your publication.",
        "ask_name": "👤 Your display name:",
        "ask_age": "🎂 Your age:\n<i>18–65</i>",
        "ask_origin": "🌍 Your origin:",
        "ask_height": "📏 Your height in cm:",
        "ask_weight": "⚖️ Your weight in kg:",
        "ask_measurements": "📐 Your measurements:\n<i>Ex: 90C - 60 - 90</i>",
        "ask_hair": "💇 Hair color:",
        "ask_eyes": "👁 Eye color:",
        "ask_languages": "🗣 Spoken languages:",
        "confirm_languages": "✅ Confirm languages",
        "ask_body_type": "✨ Body type:",
        "ask_breast": "💎 Breast type:",
        "ask_smoker": "🚬 Smoker?",
        "ask_tattoos": "🖋 Tattoos?",
        "ask_incall": "🏠 Service type:",
        "ask_availability": "🕐 Availability:",
        "ask_prices": "💶 Your rates\n\nEnter 9 lines in this order:\n15 min:\n20 min:\n30 min:\n45 min:\n1h:\n1h30:\n2h:\nEvening:\nNight:\n\n👉 numbers only\n👉 0 = not available",
        "ask_desc": "📝 Describe yourself:",
        "ask_contact": "📞 Your contact:\n<i>@telegram or phone or link</i>",
        "ask_photos": f"📸 Send your photos (1–{MAX_PHOTOS}). Then press ✅ Finish.",
        "preview_title": "👁 <b>Preview before sending</b>",
        "sent_moderation": "✅ Your publication was sent for moderation.",
        "need_photo": "⚠️ Please add at least one photo.",
        "invalid_age": "⚠️ Invalid age. Enter a number between 18 and 65.",
        "invalid_height": "⚠️ Invalid height. Enter a number between 140 and 200.",
        "invalid_weight": "⚠️ Invalid weight. Enter a number between 40 and 120.",
        "invalid_contact": "⚠️ Invalid contact. Enter a @username, number or link.",
        "invalid_short": "⚠️ Please enter a valid value.",
        "too_long": "⚠️ Text is too long.",
        "tour_ask_from": "🛫 Your departure city:",
        "tour_ask_date_from": "📅 Arrival date:",
        "tour_ask_date_to": "📅 Departure date:",
        "tour_ask_notes": "📝 Notes / conditions:",
        "tour_ask_title": "📝 Ad title:",
        "tour_ask_ad_desc": "📋 Ad description:",
        "tour_who_prompt": "Select your type:",
        "limit_reached": f"⚠️ Limit reached: maximum {MAX_ACTIVE_PER_USER} active/pending listings.",
        "photos_only": "📸 Please send photos only.",
        "unknown": "Use /start",
    }
}

# ─────────────────────────────────────────────────────────────
# STATES
# ─────────────────────────────────────────────────────────────

(
    LANG_CHOOSE,
    MAIN_MENU,
    PICK_REGION_FOR_MENU,
    PICK_CITY_FOR_MENU,
    BROWSE_MENU,
    BROWSE_AD_FILTER,
    BROWSE_TOUR_FILTER,
    MODEL_REGION,
    MODEL_CITY,
    MODEL_NAME,
    MODEL_AGE,
    MODEL_ORIGIN,
    MODEL_HEIGHT,
    MODEL_WEIGHT,
    MODEL_MEASUREMENTS,
    MODEL_HAIR,
    MODEL_EYES,
    MODEL_LANGS,
    MODEL_BODY,
    MODEL_BREAST,
    MODEL_SMOKER,
    MODEL_TATTOOS,
    MODEL_INCALL,
    MODEL_AVAILABILITY,
    MODEL_PRICES,
    MODEL_DESC,
    MODEL_CONTACT,
    MODEL_PHOTOS,
    MODEL_PREVIEW,
    TOUR_REGION,
    TOUR_CITY,
    TOUR_WHO,
    TOUR_FROM,
    TOUR_DATE_FROM,
    TOUR_DATE_TO,
    TOUR_NAME,
    TOUR_NOTES,
    TOUR_CONTACT,
    TOUR_PHOTOS,
    TOUR_PREVIEW,
    AD_REGION,
    AD_CITY,
    AD_TITLE,
    AD_DESC,
    AD_CONTACT,
    AD_PHOTOS,
    AD_PREVIEW,
    ADMIN_MENU,
) = range(48)

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────

class DB:
    def __init__(self, path: str):
        self.path = path
        self.init()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        with closing(self.connect()) as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'fr',
                    username TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT DEFAULT 'pending',
                    is_vip INTEGER DEFAULT 0,
                    flow TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    region TEXT,
                    city TEXT,
                    name TEXT,
                    age TEXT,
                    origin TEXT,
                    height TEXT,
                    weight TEXT,
                    measurements TEXT,
                    hair TEXT,
                    eyes TEXT,
                    languages TEXT,
                    body_type TEXT,
                    breast_type TEXT,
                    smoker TEXT,
                    tattoos TEXT,
                    incall TEXT,
                    availability TEXT,
                    prices_json TEXT,
                    description TEXT,
                    contact TEXT,
                    ad_title TEXT,
                    ad_desc TEXT,
                    tour_who TEXT,
                    tour_from TEXT,
                    tour_date_from TEXT,
                    tour_date_to TEXT,
                    tour_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listing_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0
                )
            """)

    def upsert_user(self, user_id: int, username: str, language: Optional[str] = None):
        with closing(self.connect()) as conn, conn:
            exists = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
            if exists:
                if language:
                    conn.execute("UPDATE users SET username=?, language=? WHERE user_id=?", (username, language, user_id))
                else:
                    conn.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
            else:
                conn.execute(
                    "INSERT INTO users (user_id, username, language) VALUES (?, ?, ?)",
                    (user_id, username, language or "fr")
                )

    def get_lang(self, user_id: Optional[int]) -> str:
        if not user_id:
            return "fr"
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT language FROM users WHERE user_id=?", (user_id,)).fetchone()
            return row["language"] if row else "fr"

    def create_listing(self, data: Dict[str, Any], media_ids: List[str]) -> int:
        with closing(self.connect()) as conn, conn:
            expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
            cur = conn.execute("""
                INSERT INTO listings (
                    status,is_vip,flow,user_id,username,region,city,name,age,origin,height,weight,measurements,
                    hair,eyes,languages,body_type,breast_type,smoker,tattoos,incall,availability,prices_json,
                    description,contact,ad_title,ad_desc,tour_who,tour_from,tour_date_from,tour_date_to,tour_notes,expires_at
                ) VALUES (
                    'pending',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
            """, (
                1 if data.get("is_vip") else 0,
                data.get("flow", ""),
                data.get("user_id"),
                data.get("username", ""),
                data.get("region", ""),
                data.get("city", ""),
                data.get("name", ""),
                data.get("age", ""),
                data.get("origin", ""),
                data.get("height", ""),
                data.get("weight", ""),
                data.get("measurements", ""),
                data.get("hair", ""),
                data.get("eyes", ""),
                data.get("languages", ""),
                data.get("body_type", ""),
                data.get("breast_type", ""),
                data.get("smoker", ""),
                data.get("tattoos", ""),
                data.get("incall", ""),
                data.get("availability", ""),
                json.dumps(data.get("prices", {}), ensure_ascii=False),
                data.get("description", ""),
                data.get("contact", ""),
                data.get("ad_title", ""),
                data.get("ad_desc", ""),
                data.get("tour_who", ""),
                data.get("tour_from", ""),
                data.get("tour_date_from", ""),
                data.get("tour_date_to", ""),
                data.get("tour_notes", ""),
                expires_at,
            ))
            listing_id = int(cur.lastrowid)
            for i, file_id in enumerate(media_ids[:10]):
                conn.execute(
                    "INSERT INTO listing_media (listing_id,file_id,sort_order) VALUES (?,?,?)",
                    (listing_id, file_id, i),
                )
            return listing_id

    def get_listing(self, listing_id: int):
        with closing(self.connect()) as conn:
            return conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()

    def get_media(self, listing_id: int) -> List[str]:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                "SELECT file_id FROM listing_media WHERE listing_id=? ORDER BY sort_order,id",
                (listing_id,)
            ).fetchall()
            return [r["file_id"] for r in rows]

    def update_status(self, listing_id: int, status: str, is_vip: Optional[bool] = None):
        with closing(self.connect()) as conn, conn:
            if is_vip is None:
                conn.execute("UPDATE listings SET status=? WHERE id=?", (status, listing_id))
            else:
                conn.execute("UPDATE listings SET status=?, is_vip=? WHERE id=?", (status, 1 if is_vip else 0, listing_id))

    def delete_listing(self, listing_id: int):
        with closing(self.connect()) as conn, conn:
            conn.execute("DELETE FROM listing_media WHERE listing_id=?", (listing_id,))
            conn.execute("DELETE FROM listings WHERE id=?", (listing_id,))

    def pending(self):
        with closing(self.connect()) as conn:
            return conn.execute("SELECT * FROM listings WHERE status='pending' ORDER BY id DESC").fetchall()

    def all_active(self, limit: int = 50):
        with closing(self.connect()) as conn:
            return conn.execute("""
                SELECT * FROM listings
                WHERE status='approved' AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY is_vip DESC, created_at DESC
                LIMIT ?
            """, (datetime.utcnow().isoformat(), limit)).fetchall()

    def count_user_active(self, user_id: int) -> int:
        with closing(self.connect()) as conn:
            row = conn.execute("""
                SELECT COUNT(*) c FROM listings
                WHERE user_id=? AND status IN ('pending','approved')
            """, (user_id,)).fetchone()
            return int(row["c"])

    def cleanup_expired(self):
        with closing(self.connect()) as conn, conn:
            expired = conn.execute(
                "SELECT id FROM listings WHERE expires_at IS NOT NULL AND expires_at < ?",
                (datetime.utcnow().isoformat(),)
            ).fetchall()
            for row in expired:
                conn.execute("DELETE FROM listing_media WHERE listing_id=?", (row["id"],))
            conn.execute(
                "DELETE FROM listings WHERE expires_at IS NOT NULL AND expires_at < ?",
                (datetime.utcnow().isoformat(),)
            )

    def browse(self, city: str, flow: str, vip_only: bool = False, recent_only: bool = False,
               tour_who: Optional[str] = None, incall_contains: Optional[str] = None,
               hair_contains: Optional[str] = None, limit: int = 20):
        query = """
            SELECT * FROM listings
            WHERE status='approved'
              AND city=?
              AND flow=?
              AND (expires_at IS NULL OR expires_at > ?)
        """
        params: List[Any] = [city, flow, datetime.utcnow().isoformat()]
        if vip_only:
            query += " AND is_vip=1"
        if recent_only:
            query += " AND created_at > ?"
            params.append((datetime.utcnow() - timedelta(days=7)).isoformat())
        if tour_who:
            query += " AND tour_who=?"
            params.append(tour_who)
        if incall_contains:
            query += " AND incall LIKE ?"
            params.append(f"%{incall_contains}%")
        if hair_contains:
            query += " AND hair LIKE ?"
            params.append(f"%{hair_contains}%")
        query += " ORDER BY is_vip DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with closing(self.connect()) as conn:
            return conn.execute(query, params).fetchall()

    def stats(self):
        with closing(self.connect()) as conn:
            result = {}
            result["pending"] = int(conn.execute("SELECT COUNT(*) c FROM listings WHERE status='pending'").fetchone()["c"])
            result["approved"] = int(conn.execute("SELECT COUNT(*) c FROM listings WHERE status='approved'").fetchone()["c"])
            result["vip"] = int(conn.execute("SELECT COUNT(*) c FROM listings WHERE status='approved' AND is_vip=1").fetchone()["c"])
            result["today"] = int(conn.execute(
                "SELECT COUNT(*) c FROM listings WHERE created_at > ?",
                ((datetime.utcnow() - timedelta(days=1)).isoformat(),)
            ).fetchone()["c"])
            return result

db = DB(DB_PATH)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

USER_LAST_ACTION: Dict[int, float] = {}

def anti_spam(user_id: int, delay: float = 1.2) -> bool:
    now = time.time()
    last = USER_LAST_ACTION.get(user_id, 0.0)
    if now - last < delay:
        return False
    USER_LAST_ACTION[user_id] = now
    return True

def safe_handler(fn):
    @wraps(fn)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            user = update.effective_user
            if user and not anti_spam(user.id):
                return
            return await fn(update, context, *args, **kwargs)
        except Exception as exc:
            logger.exception("Handler error in %s: %s", fn.__name__, exc)
            try:
                user = update.effective_user
                if user:
                    lang = context.user_data.get("lang", "fr")
                    msg = "⚠️ Une erreur est survenue. Réessayez." if lang == "fr" else "⚠️ Something went wrong. Please try again."
                    await context.bot.send_message(chat_id=user.id, text=msg)
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 BOT ERROR in {fn.__name__}\n{str(exc)[:800]}")
            except Exception:
                pass
    return wrapper

def get_lang_from_ctx(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("lang", "fr")

def t(ctx: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
    lang = get_lang_from_ctx(ctx)
    txt = TEXTS.get(lang, TEXTS["fr"]).get(key, key)
    return txt.format(**kwargs) if kwargs else txt

def safe(value: Any) -> str:
    return html.escape(str(value or ""))

def get_username(update: Update) -> str:
    u = update.effective_user
    if not u:
        return ""
    return u.username or " ".join([x for x in [u.first_name, u.last_name] if x]).strip()

def validate_age(v: str) -> bool:
    try:
        return 18 <= int(v) <= 65
    except Exception:
        return False

def validate_height(v: str) -> bool:
    try:
        return 140 <= int(v) <= 200
    except Exception:
        return False

def validate_weight(v: str) -> bool:
    try:
        return 40 <= int(v) <= 120
    except Exception:
        return False

def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    return (cleaned.startswith('+') and len(cleaned) >= 10) or (cleaned.startswith('0') and len(cleaned) >= 9)

def valid_contact(value: str) -> bool:
    return (
        (value.startswith("@") and len(value) > 2) or
        validate_phone(value) or
        value.startswith("http://") or
        value.startswith("https://")
    )

def clean_contact_url(contact: str) -> Optional[str]:
    if not contact:
        return None
    contact = contact.strip()
    if contact.startswith("http://") or contact.startswith("https://"):
        return contact
    if contact.startswith("@"):
        return f"https://t.me/{contact[1:]}"
    if validate_phone(contact):
        digits = re.sub(r"[^\d+]", "", contact)
        return f"https://wa.me/{digits.lstrip('+')}" if digits else None
    return None

def parse_prices(text: str) -> Dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    prices: Dict[str, str] = {}
    for idx, slot in enumerate(PRICE_SLOTS):
        if idx >= len(lines):
            break
        nums = re.findall(r"\d+", lines[idx])
        prices[slot[0]] = nums[0] if nums else "0"
    return prices

def price_summary(prices: Dict[str, str]) -> str:
    out = []
    for key, label in PRICE_SLOTS:
        value = prices.get(key)
        if value and value != "0":
            out.append(f"{label}: {value}€")
    return " | ".join(out) if out else "-"

def too_long(value: str, limit: int = 1200) -> bool:
    return len(value.strip()) > limit

def draft(ctx: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    if "draft" not in ctx.user_data:
        ctx.user_data["draft"] = {
            "flow": "",
            "region": "",
            "city": "",
            "name": "",
            "age": "",
            "origin": "",
            "height": "",
            "weight": "",
            "measurements": "",
            "hair": "",
            "eyes": "",
            "languages": [],
            "body_type": "",
            "breast_type": "",
            "smoker": "",
            "tattoos": "",
            "incall": "",
            "availability": "",
            "prices": {},
            "description": "",
            "contact": "",
            "photos": [],
            "ad_title": "",
            "ad_desc": "",
            "tour_who": "",
            "tour_from": "",
            "tour_date_from": "",
            "tour_date_to": "",
            "tour_notes": "",
        }
    return ctx.user_data["draft"]

def reset_draft(ctx: ContextTypes.DEFAULT_TYPE):
    for key in ("draft", "browse_region", "browse_city", "selected_lang_codes"):
        ctx.user_data.pop(key, None)

async def safe_edit_or_reply(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest:
        await query.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def send_album(bot, chat_id, photo_ids: List[str], caption: str, reply_markup=None):
    photo_ids = photo_ids[:10]
    if not photo_ids:
        await bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return
    if len(photo_ids) == 1:
        await bot.send_photo(chat_id=chat_id, photo=photo_ids[0], caption=caption, parse_mode=ParseMode.HTML)
        if reply_markup:
            await bot.send_message(chat_id=chat_id, text=" ", reply_markup=reply_markup)
        return
    media = []
    for i, file_id in enumerate(photo_ids):
        if i == 0:
            media.append(InputMediaPhoto(media=file_id, caption=caption, parse_mode=ParseMode.HTML))
        else:
            media.append(InputMediaPhoto(media=file_id))
    await bot.send_media_group(chat_id=chat_id, media=media)
    if reply_markup:
        await bot.send_message(chat_id=chat_id, text=" ", reply_markup=reply_markup)

def choice_label(option_tuple, lang_code: str) -> str:
    return option_tuple[1] if lang_code == "fr" else option_tuple[2]

# ─────────────────────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────────────────────

def main_menu_keyboard(ctx: ContextTypes.DEFAULT_TYPE, user_id: Optional[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(t(ctx, "annonces"), callback_data="pick_city_menu")],
        [InlineKeyboardButton(t(ctx, "tours"), callback_data="go_tour_flow")],
        [InlineKeyboardButton(t(ctx, "tour_request"), callback_data="flow_tour_request")],
        [InlineKeyboardButton(t(ctx, "contact_admin"), url=SUPPORT_URL)],
        [InlineKeyboardButton(t(ctx, "site"), web_app=WebAppInfo(url=MINIAPP_URL))],
    ]
    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton(t(ctx, "admin"), callback_data="go_admin")])
    return InlineKeyboardMarkup(rows)

def region_keyboard(ctx: ContextTypes.DEFAULT_TYPE, prefix: str) -> InlineKeyboardMarkup:
    keys = list(REGIONS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                row.append(InlineKeyboardButton(keys[i + j], callback_data=f"{prefix}_r_{i+j}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx, "menu"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def city_keyboard(ctx: ContextTypes.DEFAULT_TYPE, region: str, prefix: str) -> InlineKeyboardMarkup:
    cities = REGIONS.get(region, [])
    rows, row = [], []
    for idx, city in enumerate(cities):
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_c_{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx, "back"), callback_data=f"{prefix}_back_region")])
    return InlineKeyboardMarkup(rows)

def simple_rows(options, prefix: str, ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    rows, row = [], []
    for idx, item in enumerate(options):
        row.append(InlineKeyboardButton(item[0], callback_data=f"{prefix}_{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def languages_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    rows, row = [], []
    for idx, item in enumerate(LANG_OPTIONS):
        row.append(InlineKeyboardButton(item[0], callback_data=f"ml_{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(t(ctx, "confirm_languages"), callback_data="ml_done"),
        InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu"),
    ])
    return InlineKeyboardMarkup(rows)

def city_action_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "annonces"), callback_data="browse_ads")],
        [InlineKeyboardButton(t(ctx, "tours"), callback_data="browse_tours")],
        [InlineKeyboardButton(t(ctx, "tour_request"), callback_data="flow_tour_request_city")],
        [InlineKeyboardButton(t(ctx, "contact_admin"), url=SUPPORT_URL)],
        [InlineKeyboardButton(t(ctx, "back"), callback_data="pick_city_menu")],
    ])

def ads_filter_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "filter_all"), callback_data="ads_all")],
        [InlineKeyboardButton(t(ctx, "filter_vip"), callback_data="ads_vip"),
         InlineKeyboardButton(t(ctx, "filter_recent"), callback_data="ads_recent")],
        [InlineKeyboardButton(t(ctx, "filter_incall"), callback_data="ads_incall"),
         InlineKeyboardButton(t(ctx, "filter_outcall"), callback_data="ads_outcall")],
        [InlineKeyboardButton(t(ctx, "filter_blonde"), callback_data="ads_blonde"),
         InlineKeyboardButton(t(ctx, "filter_brune"), callback_data="ads_brune")],
        [InlineKeyboardButton(t(ctx, "back"), callback_data="back_city_actions")],
    ])

def tours_filter_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "filter_all"), callback_data="tours_all")],
        [InlineKeyboardButton(t(ctx, "filter_models_tour"), callback_data="tours_model"),
         InlineKeyboardButton(t(ctx, "filter_hosts"), callback_data="tours_host")],
        [InlineKeyboardButton(t(ctx, "filter_vip"), callback_data="tours_vip"),
         InlineKeyboardButton(t(ctx, "filter_recent"), callback_data="tours_recent")],
        [InlineKeyboardButton(t(ctx, "back"), callback_data="back_city_actions")],
    ])

def preview_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "send"), callback_data="submit_confirm")],
        [InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu")],
    ])

def photo_stage_keyboard(ctx: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx, "done"), callback_data="photos_done")],
        [InlineKeyboardButton(t(ctx, "cancel"), callback_data="go_menu")],
    ])

def listing_actions_keyboard(ctx: ContextTypes.DEFAULT_TYPE, contact: str) -> InlineKeyboardMarkup:
    rows = []
    url = clean_contact_url(contact)
    if url:
        rows.append([InlineKeyboardButton(t(ctx, "contact_model"), url=url)])
    rows.append([InlineKeyboardButton(t(ctx, "contact_admin"), url=SUPPORT_URL)])
    return InlineKeyboardMarkup(rows)

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Заявки на модерации", callback_data="adm_pending")],
        [InlineKeyboardButton("🗂 Активные публикации", callback_data="adm_active")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="go_menu")],
    ])

def moderation_keyboard(listing_id: int, author_contact: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👁 Открыть", callback_data=f"adm_view_{listing_id}")],
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_approve_{listing_id}"),
         InlineKeyboardButton("⭐ VIP", callback_data=f"adm_vip_{listing_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_reject_{listing_id}"),
         InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_delete_{listing_id}")],
    ]
    url = clean_contact_url(author_contact)
    if url:
        rows.append([InlineKeyboardButton("💬 Связаться с автором", url=url)])
    return InlineKeyboardMarkup(rows)

# ─────────────────────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────────────────────

def build_listing_text(row, lang_code: str) -> str:
    vip = "⭐ VIP | " if row["is_vip"] else ""
    flow = row["flow"]
    prices = json.loads(row["prices_json"] or "{}")

    if flow == "annonce":
        return (
            f"{vip}<b>{safe(row['ad_title'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(row['city'])}\n"
            f"📋 {safe(row['ad_desc'])}\n"
            f"📞 {safe(row['contact'])}"
        )

    if flow == "tour":
        role_label = row["tour_who"]
        if row["tour_who"] == "model":
            role_label = "👗 Modèle" if lang_code == "fr" else "👗 Model"
        elif row["tour_who"] == "host":
            role_label = "🏨 Hôte" if lang_code == "fr" else "🏨 Host"
        return (
            f"{vip}✈️ <b>Tours</b> — {safe(role_label)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(row['city'])}\n"
            f"👤 {safe(row['name'])}\n"
            f"🛫 {safe(row['tour_from'])}\n"
            f"📅 {safe(row['tour_date_from'])} → {safe(row['tour_date_to'])}\n"
            f"📝 {safe(row['tour_notes'])}\n"
            f"📞 {safe(row['contact'])}"
        )

    return (
        f"{vip}👗 <b>{safe(row['name'])}</b>, {safe(row['age'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📍 {safe(row['city'])}\n"
        f"🌍 {safe(row['origin'])}\n"
        f"📏 {safe(row['height'])} cm • ⚖️ {safe(row['weight'])} kg\n"
        f"📐 {safe(row['measurements'])}\n"
        f"💇 {safe(row['hair'])} • 👁 {safe(row['eyes'])}\n"
        f"✨ {safe(row['body_type'])} • 💎 {safe(row['breast_type'])}\n"
        f"🚬 {safe(row['smoker'])} • 🖋 {safe(row['tattoos'])}\n"
        f"🗣 {safe(row['languages'])}\n"
        f"🏠 {safe(row['incall'])}\n"
        f"🕐 {safe(row['availability'])}\n"
        f"💶 {safe(price_summary(prices))}\n\n"
        f"📝 {safe(row['description'])}\n"
        f"📞 {safe(row['contact'])}"
    )

def build_draft_preview(data: Dict[str, Any], lang_code: str) -> str:
    if data["flow"] == "annonce":
        return (
            f"<b>{safe(data['ad_title'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(data['city'])}\n"
            f"📋 {safe(data['ad_desc'])}\n"
            f"📞 {safe(data['contact'])}"
        )

    if data["flow"] == "tour":
        who_label = "👗 Modèle" if data.get("tour_who") == "model" and lang_code == "fr" else \
                    "👗 Model" if data.get("tour_who") == "model" else \
                    "🏨 Hôte" if data.get("tour_who") == "host" and lang_code == "fr" else \
                    "🏨 Host" if data.get("tour_who") == "host" else "-"
        return (
            f"✈️ <b>Tours</b> — {safe(who_label)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 {safe(data['city'])}\n"
            f"👤 {safe(data['name'])}\n"
            f"🛫 {safe(data['tour_from'])}\n"
            f"📅 {safe(data['tour_date_from'])} → {safe(data['tour_date_to'])}\n"
            f"📝 {safe(data['tour_notes'])}\n"
            f"📞 {safe(data['contact'])}"
        )

    return (
        f"👗 <b>{safe(data['name'])}</b>, {safe(data['age'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📍 {safe(data['city'])}\n"
        f"🌍 {safe(data['origin'])}\n"
        f"📏 {safe(data['height'])} cm • ⚖️ {safe(data['weight'])} kg\n"
        f"📐 {safe(data['measurements'])}\n"
        f"💇 {safe(data['hair'])} • 👁 {safe(data['eyes'])}\n"
        f"✨ {safe(data['body_type'])} • 💎 {safe(data['breast_type'])}\n"
        f"🚬 {safe(data['smoker'])} • 🖋 {safe(data['tattoos'])}\n"
        f"🗣 {safe(', '.join(data['languages']))}\n"
        f"🏠 {safe(data['incall'])}\n"
        f"🕐 {safe(data['availability'])}\n"
        f"💶 {safe(price_summary(data['prices']))}\n\n"
        f"📝 {safe(data['description'])}\n"
        f"📞 {safe(data['contact'])}"
    )

def build_admin_preview(row) -> str:
    prices = json.loads(row["prices_json"] or "{}")
    return (
        f"🔔 <b>Новая заявка #{row['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Тип: {safe(row['flow'])}\n"
        f"User: {safe(row['username'])}\n"
        f"User ID: <code>{safe(row['user_id'])}</code>\n"
        f"Регион: {safe(row['region'])}\n"
        f"Город: {safe(row['city'])}\n"
        f"Имя: {safe(row['name'] or row['ad_title'])}\n"
        f"Возраст: {safe(row['age'])}\n"
        f"Происхождение: {safe(row['origin'])}\n"
        f"Рост: {safe(row['height'])}\n"
        f"Вес: {safe(row['weight'])}\n"
        f"Параметры: {safe(row['measurements'])}\n"
        f"Волосы: {safe(row['hair'])}\n"
        f"Глаза: {safe(row['eyes'])}\n"
        f"Языки: {safe(row['languages'])}\n"
        f"Силуэт: {safe(row['body_type'])}\n"
        f"Poitrine: {safe(row['breast_type'])}\n"
        f"Smoker: {safe(row['smoker'])}\n"
        f"Tattoos: {safe(row['tattoos'])}\n"
        f"Формат: {safe(row['incall'])}\n"
        f"Доступность: {safe(row['availability'])}\n"
        f"Цены: {safe(price_summary(prices))}\n"
        f"Описание: {safe(row['description'])}\n"
        f"Контакт: {safe(row['contact'])}\n"
        f"Tour who: {safe(row['tour_who'])}\n"
        f"From: {safe(row['tour_from'])}\n"
        f"Dates: {safe(row['tour_date_from'])} → {safe(row['tour_date_to'])}\n"
        f"Notes: {safe(row['tour_notes'])}\n"
        f"Заголовок: {safe(row['ad_title'])}\n"
        f"Текст объявления: {safe(row['ad_desc'])}"
    )

# ─────────────────────────────────────────────────────────────
# START / MENU
# ─────────────────────────────────────────────────────────────

@safe_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_draft(context)
    user = update.effective_user
    if user:
        db.upsert_user(user.id, get_username(update))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(TEXTS["fr"]["site"], web_app=WebAppInfo(url=MINIAPP_URL))],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ])
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg:
        await msg.reply_text(TEXTS["fr"]["greeting"], parse_mode=ParseMode.HTML, reply_markup=kb)
    return LANG_CHOOSE

@safe_handler
async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_code = q.data.replace("lang_", "")
    context.user_data["lang"] = lang_code
    db.upsert_user(q.from_user.id, get_username(update), lang_code)
    await safe_edit_or_reply(q, TEXTS[lang_code]["welcome"], main_menu_keyboard(context, q.from_user.id))
    return MAIN_MENU

@safe_handler
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        db.upsert_user(user.id, get_username(update))
        if "lang" not in context.user_data:
            context.user_data["lang"] = db.get_lang(user.id)
    text = t(context, "welcome")
    kb = main_menu_keyboard(context, user.id if user else None)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit_or_reply(update.callback_query, text, kb)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return MAIN_MENU

# ─────────────────────────────────────────────────────────────
# BROWSE
# ─────────────────────────────────────────────────────────────

@safe_handler
async def pick_city_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await safe_edit_or_reply(q, t(context, "choose_region"), region_keyboard(context, "pick"))
    return PICK_REGION_FOR_MENU

@safe_handler
async def picked_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("pick_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    context.user_data["browse_region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "pick"))
    return PICK_CITY_FOR_MENU

@safe_handler
async def picked_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "pick_back_region":
        return await pick_city_menu(update, context)
    idx = int(q.data.replace("pick_c_", ""))
    region = context.user_data.get("browse_region", "")
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await show_menu(update, context)
    city = cities[idx]
    context.user_data["browse_city"] = city
    await safe_edit_or_reply(q, t(context, "what_next", city=city), city_action_keyboard(context))
    return BROWSE_MENU

@safe_handler
async def city_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    city = context.user_data.get("browse_city", "")
    if q.data == "back_city_actions":
        await safe_edit_or_reply(q, t(context, "what_next", city=city), city_action_keyboard(context))
        return BROWSE_MENU
    if q.data == "browse_ads":
        await safe_edit_or_reply(q, t(context, "ads_filters", city=city), ads_filter_keyboard(context))
        return BROWSE_AD_FILTER
    if q.data == "browse_tours":
        await safe_edit_or_reply(q, t(context, "tour_filters", city=city), tours_filter_keyboard(context))
        return BROWSE_TOUR_FILTER
    if q.data == "flow_tour_request_city":
        d = draft(context)
        d["flow"] = "model"
        d["region"] = context.user_data.get("browse_region", "")
        d["city"] = city
        await safe_edit_or_reply(q, t(context, "tour_intro"))
        await q.message.reply_text(t(context, "ask_name"), parse_mode=ParseMode.HTML)
        return MODEL_NAME
    return BROWSE_MENU

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE, flow: str, **filters_kwargs):
    q = update.callback_query
    await q.answer()
    city = context.user_data.get("browse_city", "")
    rows = db.browse(city, flow, **filters_kwargs)
    if not rows:
        await safe_edit_or_reply(q, t(context, "empty_results"), InlineKeyboardMarkup([[InlineKeyboardButton(t(context, "back"), callback_data="back_city_actions")]]))
        return MAIN_MENU
    await safe_edit_or_reply(q, f"📍 <b>{safe(city)}</b> — {len(rows)}", InlineKeyboardMarkup([[InlineKeyboardButton(t(context, "back"), callback_data="back_city_actions")]]))
    for row in rows:
        await send_album(context.bot, q.message.chat_id, db.get_media(row["id"]), build_listing_text(row, get_lang_from_ctx(context)), listing_actions_keyboard(context, row["contact"]))
    await q.message.reply_text(t(context, "results_end"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(t(context, "back"), callback_data="back_city_actions")],
        [InlineKeyboardButton(t(context, "menu"), callback_data="go_menu")]
    ]))
    return MAIN_MENU

@safe_handler
async def browse_ads_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    mapping = {
        "ads_all": {},
        "ads_vip": {"vip_only": True},
        "ads_recent": {"recent_only": True},
        "ads_incall": {"incall_contains": "Incall"},
        "ads_outcall": {"incall_contains": "Outcall"},
        "ads_blonde": {"hair_contains": "Blonde"},
        "ads_brune": {"hair_contains": "Brune"},
    }
    if q.data in mapping:
        return await show_results(update, context, "annonce", **mapping[q.data])
    return await city_actions(update, context)

@safe_handler
async def browse_tours_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    mapping = {
        "tours_all": {},
        "tours_vip": {"vip_only": True},
        "tours_recent": {"recent_only": True},
        "tours_model": {"tour_who": "model"},
        "tours_host": {"tour_who": "host"},
    }
    if q.data in mapping:
        return await show_results(update, context, "tour", **mapping[q.data])
    return await city_actions(update, context)

# ─────────────────────────────────────────────────────────────
# MODEL FLOW
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_model_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    reset_draft(context)
    d = draft(context)
    d["flow"] = "model"
    await safe_edit_or_reply(q, t(context, "tour_intro"), region_keyboard(context, "mr"))
    return MODEL_REGION

@safe_handler
async def model_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("mr_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    draft(context)["region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "mr"))
    return MODEL_CITY

@safe_handler
async def model_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "mr_back_region":
        return await go_model_request(update, context)
    idx = int(q.data.replace("mr_c_", ""))
    region = draft(context)["region"]
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await go_model_request(update, context)
    draft(context)["city"] = cities[idx]
    await safe_edit_or_reply(q, f"📍 <b>{safe(cities[idx])}</b>")
    await q.message.reply_text(t(context, "ask_name"), parse_mode=ParseMode.HTML)
    return MODEL_NAME

@safe_handler
async def model_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 2:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_NAME
    if too_long(value, 80):
        await update.message.reply_text(t(context, "too_long"))
        return MODEL_NAME
    draft(context)["name"] = value
    await update.message.reply_text(t(context, "ask_age"), parse_mode=ParseMode.HTML)
    return MODEL_AGE

@safe_handler
async def model_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_age(value):
        await update.message.reply_text(t(context, "invalid_age"))
        return MODEL_AGE
    draft(context)["age"] = value
    await update.message.reply_text(t(context, "ask_origin"), parse_mode=ParseMode.HTML)
    return MODEL_ORIGIN

@safe_handler
async def model_origin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 2:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_ORIGIN
    draft(context)["origin"] = value
    await update.message.reply_text(t(context, "ask_height"), parse_mode=ParseMode.HTML)
    return MODEL_HEIGHT

@safe_handler
async def model_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_height(value):
        await update.message.reply_text(t(context, "invalid_height"))
        return MODEL_HEIGHT
    draft(context)["height"] = value
    await update.message.reply_text(t(context, "ask_weight"), parse_mode=ParseMode.HTML)
    return MODEL_WEIGHT

@safe_handler
async def model_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not validate_weight(value):
        await update.message.reply_text(t(context, "invalid_weight"))
        return MODEL_WEIGHT
    draft(context)["weight"] = value
    await update.message.reply_text(t(context, "ask_measurements"), parse_mode=ParseMode.HTML)
    return MODEL_MEASUREMENTS

@safe_handler
async def model_measurements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 3:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_MEASUREMENTS
    draft(context)["measurements"] = value
    await update.message.reply_text(t(context, "ask_hair"), parse_mode=ParseMode.HTML, reply_markup=simple_rows(HAIR_OPTIONS, "hair", context))
    return MODEL_HAIR

@safe_handler
async def model_hair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("hair_", ""))
    draft(context)["hair"] = choice_label(HAIR_OPTIONS[idx], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_eyes"), simple_rows(EYE_OPTIONS, "eyes", context))
    return MODEL_EYES

@safe_handler
async def model_eyes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("eyes_", ""))
    draft(context)["eyes"] = choice_label(EYE_OPTIONS[idx], get_lang_from_ctx(context))
    context.user_data["selected_lang_codes"] = []
    await safe_edit_or_reply(q, t(context, "ask_languages"), languages_keyboard(context))
    return MODEL_LANGS

@safe_handler
async def model_langs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    selected = context.user_data.get("selected_lang_codes", [])
    if q.data == "ml_done":
        if not selected:
            await q.answer("Sélectionnez au moins une langue" if get_lang_from_ctx(context) == "fr" else "Select at least one language", show_alert=True)
            return MODEL_LANGS
        labels = [choice_label(LANG_OPTIONS[idx], get_lang_from_ctx(context)) for idx in selected]
        draft(context)["languages"] = labels
        await safe_edit_or_reply(q, t(context, "ask_body_type"), simple_rows(BODY_TYPE_OPTIONS, "body", context))
        return MODEL_BODY
    idx = int(q.data.replace("ml_", ""))
    if idx in selected:
        selected.remove(idx)
    else:
        selected.append(idx)
    context.user_data["selected_lang_codes"] = selected
    return MODEL_LANGS

@safe_handler
async def model_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["body_type"] = choice_label(BODY_TYPE_OPTIONS[int(q.data.replace("body_", ""))], get_lang_from_ctx(context))
    opts = [("💎 Naturelle", "Naturelle", "Natural"), ("✨ Silicone", "Silicone", "Silicone")]
    await safe_edit_or_reply(q, t(context, "ask_breast"), simple_rows(opts, "breast", context))
    return MODEL_BREAST

@safe_handler
async def model_breast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    opts = [("💎 Naturelle", "Naturelle", "Natural"), ("✨ Silicone", "Silicone", "Silicone")]
    draft(context)["breast_type"] = choice_label(opts[int(q.data.replace("breast_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_smoker"), simple_rows(YES_NO_OPTIONS, "smoker", context))
    return MODEL_SMOKER

@safe_handler
async def model_smoker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["smoker"] = choice_label(YES_NO_OPTIONS[int(q.data.replace("smoker_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_tattoos"), simple_rows(YES_NO_OPTIONS, "tattoos", context))
    return MODEL_TATTOOS

@safe_handler
async def model_tattoos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["tattoos"] = choice_label(YES_NO_OPTIONS[int(q.data.replace("tattoos_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_incall"), simple_rows(INCALL_OPTIONS, "incall", context))
    return MODEL_INCALL

@safe_handler
async def model_incall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["incall"] = choice_label(INCALL_OPTIONS[int(q.data.replace("incall_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_availability"), simple_rows(AVAILABILITY_OPTIONS, "avail", context))
    return MODEL_AVAILABILITY

@safe_handler
async def model_availability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["availability"] = choice_label(AVAILABILITY_OPTIONS[int(q.data.replace("avail_", ""))], get_lang_from_ctx(context))
    await safe_edit_or_reply(q, t(context, "ask_prices"))
    await q.message.reply_text(t(context, "ask_prices"), parse_mode=ParseMode.HTML)
    return MODEL_PRICES

@safe_handler
async def model_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = parse_prices(update.message.text)
    if not prices:
        await update.message.reply_text(t(context, "ask_prices"))
        return MODEL_PRICES
    draft(context)["prices"] = prices
    await update.message.reply_text(t(context, "ask_desc"), parse_mode=ParseMode.HTML)
    return MODEL_DESC

@safe_handler
async def model_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 10:
        await update.message.reply_text(t(context, "invalid_short"))
        return MODEL_DESC
    if too_long(value):
        await update.message.reply_text(t(context, "too_long"))
        return MODEL_DESC
    draft(context)["description"] = value
    await update.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return MODEL_CONTACT

@safe_handler
async def model_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not valid_contact(value):
        await update.message.reply_text(t(context, "invalid_contact"))
        return MODEL_CONTACT
    draft(context)["contact"] = value
    draft(context)["photos"] = []
    await update.message.reply_text(t(context, "ask_photos"), parse_mode=ParseMode.HTML, reply_markup=photo_stage_keyboard(context))
    return MODEL_PHOTOS

# ─────────────────────────────────────────────────────────────
# TOUR FLOW
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_tour_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    reset_draft(context)
    draft(context)["flow"] = "tour"
    await safe_edit_or_reply(q, t(context, "choose_region"), region_keyboard(context, "tr"))
    return TOUR_REGION

@safe_handler
async def tour_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("tr_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    draft(context)["region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "tr"))
    return TOUR_CITY

@safe_handler
async def tour_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "tr_back_region":
        return await go_tour_flow(update, context)
    idx = int(q.data.replace("tr_c_", ""))
    region = draft(context)["region"]
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await go_tour_flow(update, context)
    draft(context)["city"] = cities[idx]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👗 Je suis modèle" if get_lang_from_ctx(context) == "fr" else "👗 I am a model", callback_data="tourwho_model")],
        [InlineKeyboardButton("🏨 J'accueille des modèles" if get_lang_from_ctx(context) == "fr" else "🏨 I host models", callback_data="tourwho_host")],
        [InlineKeyboardButton(t(context, "cancel"), callback_data="go_menu")]
    ])
    await safe_edit_or_reply(q, t(context, "tour_who_prompt"), kb)
    return TOUR_WHO

@safe_handler
async def tour_who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["tour_who"] = q.data.replace("tourwho_", "")
    await safe_edit_or_reply(q, t(context, "tour_ask_from"))
    await q.message.reply_text(t(context, "tour_ask_from"), parse_mode=ParseMode.HTML)
    return TOUR_FROM

@safe_handler
async def tour_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_from"] = update.message.text.strip()
    await update.message.reply_text(t(context, "tour_ask_date_from"), parse_mode=ParseMode.HTML)
    return TOUR_DATE_FROM

@safe_handler
async def tour_date_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_date_from"] = update.message.text.strip()
    await update.message.reply_text(t(context, "tour_ask_date_to"), parse_mode=ParseMode.HTML)
    return TOUR_DATE_TO

@safe_handler
async def tour_date_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_date_to"] = update.message.text.strip()
    await update.message.reply_text(t(context, "ask_name"), parse_mode=ParseMode.HTML)
    return TOUR_NAME

@safe_handler
async def tour_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["name"] = update.message.text.strip()
    await update.message.reply_text(t(context, "tour_ask_notes"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(t(context, "skip"), callback_data="tour_skip_notes")],
        [InlineKeyboardButton(t(context, "cancel"), callback_data="go_menu")]
    ]))
    return TOUR_NOTES

@safe_handler
async def tour_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft(context)["tour_notes"] = update.message.text.strip()
    await update.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return TOUR_CONTACT

@safe_handler
async def tour_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    draft(context)["tour_notes"] = "-"
    await safe_edit_or_reply(q, t(context, "ask_contact"))
    await q.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return TOUR_CONTACT

@safe_handler
async def tour_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not valid_contact(value):
        await update.message.reply_text(t(context, "invalid_contact"))
        return TOUR_CONTACT
    draft(context)["contact"] = value
    draft(context)["photos"] = []
    await update.message.reply_text(t(context, "ask_photos"), parse_mode=ParseMode.HTML, reply_markup=photo_stage_keyboard(context))
    return TOUR_PHOTOS

# ─────────────────────────────────────────────────────────────
# AD FLOW
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_ad_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    reset_draft(context)
    draft(context)["flow"] = "annonce"
    await safe_edit_or_reply(q, t(context, "choose_region"), region_keyboard(context, "ad"))
    return AD_REGION

@safe_handler
async def ad_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.replace("ad_r_", ""))
    regions = list(REGIONS.keys())
    if idx >= len(regions):
        return await show_menu(update, context)
    region = regions[idx]
    draft(context)["region"] = region
    await safe_edit_or_reply(q, f"{safe(region)}\n\n{t(context, 'choose_city')}", city_keyboard(context, region, "ad"))
    return AD_CITY

@safe_handler
async def ad_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "ad_back_region":
        return await go_ad_flow(update, context)
    idx = int(q.data.replace("ad_c_", ""))
    region = draft(context)["region"]
    cities = REGIONS.get(region, [])
    if idx >= len(cities):
        return await go_ad_flow(update, context)
    draft(context)["city"] = cities[idx]
    await safe_edit_or_reply(q, t(context, "tour_ask_title"))
    await q.message.reply_text(t(context, "tour_ask_title"), parse_mode=ParseMode.HTML)
    return AD_TITLE

@safe_handler
async def ad_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 3:
        await update.message.reply_text(t(context, "invalid_short"))
        return AD_TITLE
    draft(context)["ad_title"] = value
    await update.message.reply_text(t(context, "tour_ask_ad_desc"), parse_mode=ParseMode.HTML)
    return AD_DESC

@safe_handler
async def ad_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if len(value) < 5:
        await update.message.reply_text(t(context, "invalid_short"))
        return AD_DESC
    draft(context)["ad_desc"] = value
    await update.message.reply_text(t(context, "ask_contact"), parse_mode=ParseMode.HTML)
    return AD_CONTACT

@safe_handler
async def ad_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not valid_contact(value):
        await update.message.reply_text(t(context, "invalid_contact"))
        return AD_CONTACT
    draft(context)["contact"] = value
    draft(context)["photos"] = []
    await update.message.reply_text(t(context, "ask_photos"), parse_mode=ParseMode.HTML, reply_markup=photo_stage_keyboard(context))
    return AD_PHOTOS

# ─────────────────────────────────────────────────────────────
# PHOTOS / PREVIEW / SUBMIT
# ─────────────────────────────────────────────────────────────

@safe_handler
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = draft(context)
    photos = d.get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"⚠️ Maximum {MAX_PHOTOS} photos.")
        return
    photos.append(update.message.photo[-1].file_id)
    d["photos"] = photos
    await update.message.reply_text(f"📸 {len(photos)}/{MAX_PHOTOS}")

@safe_handler
async def photos_text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(context, "photos_only"))

@safe_handler
async def photos_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = draft(context)
    if not d.get("photos"):
        await q.answer(t(context, "need_photo"), show_alert=True)
        return
    preview = build_draft_preview(d, get_lang_from_ctx(context))
    await safe_edit_or_reply(q, f"{t(context, 'preview_title')}\n\n{preview}", preview_keyboard(context))
    flow = d.get("flow")
    if flow == "model":
        return MODEL_PREVIEW
    if flow == "tour":
        return TOUR_PREVIEW
    return AD_PREVIEW

@safe_handler
async def submit_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = draft(context)
    user = update.effective_user
    if not user:
        return await show_menu(update, context)
    d["user_id"] = user.id
    d["username"] = get_username(update)

    if db.count_user_active(user.id) >= MAX_ACTIVE_PER_USER:
        await q.answer(t(context, "limit_reached"), show_alert=True)
        return

    listing_id = db.create_listing(d, d.get("photos", []))
    row = db.get_listing(listing_id)
    if row:
        await send_album(context.bot, ADMIN_ID, db.get_media(listing_id), build_admin_preview(row), moderation_keyboard(listing_id, row["contact"]))
    await safe_edit_or_reply(q, t(context, "sent_moderation"), main_menu_keyboard(context, user.id))
    reset_draft(context)
    return MAIN_MENU

# ─────────────────────────────────────────────────────────────
# ADMIN
# ─────────────────────────────────────────────────────────────

@safe_handler
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id != ADMIN_ID:
        if q:
            await q.answer("Доступ запрещён", show_alert=True)
        return MAIN_MENU
    stats = db.stats()
    text = (
        "🔐 <b>Панель администратора</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"⏳ На модерации: <b>{stats['pending']}</b>\n"
        f"✅ Активных: <b>{stats['approved']}</b>\n"
        f"⭐ VIP: <b>{stats['vip']}</b>\n"
        f"🆕 За 24ч: <b>{stats['today']}</b>"
    )
    if q:
        await q.answer()
        await safe_edit_or_reply(q, text, admin_menu_keyboard())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=admin_menu_keyboard())
    return ADMIN_MENU

@safe_handler
async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("Доступ запрещён", show_alert=True)
        return ADMIN_MENU

    if q.data == "adm_stats":
        return await admin_panel(update, context)

    if q.data == "adm_pending":
        rows = db.pending()
        if not rows:
            await safe_edit_or_reply(q, "✅ Нет заявок на модерации.", admin_menu_keyboard())
            return ADMIN_MENU
        lines = ["📋 <b>Заявки на модерации</b>\n"]
        for r in rows[:25]:
            title = r["name"] or r["ad_title"] or "-"
            lines.append(f"#{r['id']} • {safe(r['flow'])} • {safe(r['city'])} • {safe(title)}")
        await safe_edit_or_reply(q, "\n".join(lines), admin_menu_keyboard())
        return ADMIN_MENU

    if q.data == "adm_active":
        rows = db.all_active()
        if not rows:
            await safe_edit_or_reply(q, "Нет активных публикаций.", admin_menu_keyboard())
            return ADMIN_MENU
        lines = ["🗂 <b>Активные публикации</b>\n"]
        for r in rows[:30]:
            vip = "⭐ " if r["is_vip"] else ""
            title = r["name"] or r["ad_title"] or "-"
            lines.append(f"#{r['id']} • {vip}{safe(r['flow'])} • {safe(r['city'])} • {safe(title)}")
        await safe_edit_or_reply(q, "\n".join(lines), admin_menu_keyboard())
        return ADMIN_MENU

    return ADMIN_MENU

@safe_handler
async def admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        return
    parts = q.data.split("_")
    if len(parts) < 3:
        return
    listing_id = int(parts[2])
    row = db.get_listing(listing_id)
    if not row:
        await safe_edit_or_reply(q, "⚠️ Заявка не найдена.")
        return
    await send_album(context.bot, ADMIN_ID, db.get_media(listing_id), build_admin_preview(row), moderation_keyboard(listing_id, row["contact"]))

@safe_handler
async def moderation_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("Доступ запрещён", show_alert=True)
        return
    parts = q.data.split("_")
    if len(parts) < 3:
        return
    _, action, listing_id_raw = parts
    listing_id = int(listing_id_raw)
    row = db.get_listing(listing_id)
    if not row:
        await safe_edit_or_reply(q, "⚠️ Заявка не найдена.")
        return

    if action == "reject":
        db.update_status(listing_id, "rejected")
        await safe_edit_or_reply(q, f"❌ Заявка #{listing_id} отклонена.")
        if row["user_id"]:
            try:
                lang_code = db.get_lang(row["user_id"])
                msg = "❌ Votre publication a été refusée." if lang_code == "fr" else "❌ Your publication was rejected."
                await context.bot.send_message(chat_id=row["user_id"], text=msg)
            except Exception:
                pass
        return

    if action == "delete":
        db.delete_listing(listing_id)
        await safe_edit_or_reply(q, f"🗑 Заявка #{listing_id} удалена.")
        return

    is_vip = action == "vip"
    db.update_status(listing_id, "approved", is_vip=is_vip)
    fresh_row = db.get_listing(listing_id)
    if fresh_row:
        text = build_listing_text(fresh_row, db.get_lang(fresh_row["user_id"]) if fresh_row["user_id"] else "fr")
        await send_album(context.bot, CHANNEL_ID, db.get_media(listing_id), text, listing_actions_keyboard(context, fresh_row["contact"]))
    await safe_edit_or_reply(q, f"✅ Заявка #{listing_id} опубликована{' как VIP' if is_vip else ''}.")
    if row["user_id"]:
        try:
            lang_code = db.get_lang(row["user_id"])
            msg = "✅ Votre publication est en ligne." if lang_code == "fr" else "✅ Your publication is live."
            if is_vip:
                msg += "\n⭐ VIP"
            await context.bot.send_message(chat_id=row["user_id"], text=msg)
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────
# COMMON
# ─────────────────────────────────────────────────────────────

@safe_handler
async def go_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_draft(context)
    return await show_menu(update, context)

@safe_handler
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(t(context, "unknown"))

async def cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    db.cleanup_expired()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    exc = context.error
    if isinstance(exc, RetryAfter):
        logger.warning("RetryAfter %s", exc.retry_after)
        await asyncio.sleep(float(exc.retry_after))
        return
    if isinstance(exc, (TimedOut, NetworkError)):
        logger.warning("Transient error: %s", exc)
        return
    logger.exception("Unhandled error: %s", exc)
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 BOT ERROR:\n{str(exc)[:800]}")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────

def build_app() -> Application:
    if BOT_TOKEN == "PASTE_BOT_TOKEN":
        raise RuntimeError("BOT_TOKEN not configured")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
        ],
        states={
            LANG_CHOOSE: [CallbackQueryHandler(choose_lang, pattern=r"^lang_(fr|en)$")],
            MAIN_MENU: [
                CallbackQueryHandler(pick_city_menu, pattern=r"^pick_city_menu$"),
                CallbackQueryHandler(go_tour_flow, pattern=r"^go_tour_flow$"),
                CallbackQueryHandler(go_model_request, pattern=r"^flow_tour_request$"),
                CallbackQueryHandler(admin_panel, pattern=r"^go_admin$"),
            ],
            PICK_REGION_FOR_MENU: [
                CallbackQueryHandler(picked_region, pattern=r"^pick_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            PICK_CITY_FOR_MENU: [
                CallbackQueryHandler(picked_city, pattern=r"^(pick_c_\d+|pick_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            BROWSE_MENU: [
                CallbackQueryHandler(city_actions, pattern=r"^(browse_ads|browse_tours|flow_tour_request_city|back_city_actions)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            BROWSE_AD_FILTER: [
                CallbackQueryHandler(browse_ads_filter, pattern=r"^(ads_all|ads_vip|ads_recent|ads_incall|ads_outcall|ads_blonde|ads_brune|back_city_actions)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            BROWSE_TOUR_FILTER: [
                CallbackQueryHandler(browse_tours_filter, pattern=r"^(tours_all|tours_model|tours_host|tours_vip|tours_recent|back_city_actions)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_REGION: [
                CallbackQueryHandler(model_region, pattern=r"^mr_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_CITY: [
                CallbackQueryHandler(model_city, pattern=r"^(mr_c_\d+|mr_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_name)],
            MODEL_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_age)],
            MODEL_ORIGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_origin)],
            MODEL_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_height)],
            MODEL_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_weight)],
            MODEL_MEASUREMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_measurements)],
            MODEL_HAIR: [
                CallbackQueryHandler(model_hair, pattern=r"^hair_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_EYES: [
                CallbackQueryHandler(model_eyes, pattern=r"^eyes_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_LANGS: [
                CallbackQueryHandler(model_langs, pattern=r"^(ml_\d+|ml_done)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_BODY: [
                CallbackQueryHandler(model_body, pattern=r"^body_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_BREAST: [
                CallbackQueryHandler(model_breast, pattern=r"^breast_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_SMOKER: [
                CallbackQueryHandler(model_smoker, pattern=r"^smoker_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_TATTOOS: [
                CallbackQueryHandler(model_tattoos, pattern=r"^tattoos_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_INCALL: [
                CallbackQueryHandler(model_incall, pattern=r"^incall_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_AVAILABILITY: [
                CallbackQueryHandler(model_availability, pattern=r"^avail_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_PRICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_prices)],
            MODEL_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_desc)],
            MODEL_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_contact)],
            MODEL_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photos_text_fallback),
                CallbackQueryHandler(photos_done, pattern=r"^photos_done$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            MODEL_PREVIEW: [
                CallbackQueryHandler(submit_confirm, pattern=r"^submit_confirm$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_REGION: [
                CallbackQueryHandler(tour_region, pattern=r"^tr_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_CITY: [
                CallbackQueryHandler(tour_city, pattern=r"^(tr_c_\d+|tr_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_WHO: [
                CallbackQueryHandler(tour_who, pattern=r"^tourwho_(model|host)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_from)],
            TOUR_DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_from)],
            TOUR_DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_date_to)],
            TOUR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_name)],
            TOUR_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tour_notes),
                CallbackQueryHandler(tour_skip_notes, pattern=r"^tour_skip_notes$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tour_contact)],
            TOUR_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photos_text_fallback),
                CallbackQueryHandler(photos_done, pattern=r"^photos_done$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            TOUR_PREVIEW: [
                CallbackQueryHandler(submit_confirm, pattern=r"^submit_confirm$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_REGION: [
                CallbackQueryHandler(ad_region, pattern=r"^ad_r_\d+$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_CITY: [
                CallbackQueryHandler(ad_city, pattern=r"^(ad_c_\d+|ad_back_region)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_title)],
            AD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_desc)],
            AD_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_contact)],
            AD_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photos_text_fallback),
                CallbackQueryHandler(photos_done, pattern=r"^photos_done$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            AD_PREVIEW: [
                CallbackQueryHandler(submit_confirm, pattern=r"^submit_confirm$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
            ADMIN_MENU: [
                CallbackQueryHandler(admin_actions, pattern=r"^adm_(pending|active|stats)$"),
                CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(go_menu_callback, pattern=r"^go_menu$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(go_ad_flow, pattern=r"^browse_ads$"))
    app.add_handler(CallbackQueryHandler(go_tour_flow, pattern=r"^browse_tours$"))
    app.add_handler(CallbackQueryHandler(admin_view, pattern=r"^adm_view_\d+$"))
    app.add_handler(CallbackQueryHandler(moderation_action, pattern=r"^adm_(approve|vip|reject|delete)_\d+$"))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(cleanup_job, interval=CLEANUP_INTERVAL_SECONDS, first=10)

    return app

def main():
    app = build_app()
    logger.info("Amour Annonce ULTRA PRO BUSINESS started")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
'''

out = Path("/mnt/data/amour_annonce_ultra_pro_business.py")
out.write_text(code, encoding="utf-8")

import py_compile
py_compile.compile(str(out), doraise=True)

print(f"Saved: {out}")
print(f"Lines: {len(code.splitlines())}")
import textwrap
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut
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
# IMPORTANT:
# Replace with your real values OR use Railway env vars.
# Env vars override fallback values below.
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN")

# INSERT YOUR REAL CURRENT VALUES HERE:
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001234567890"))
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/your_support")
VMODLS_URL = os.getenv("VMODLS_URL", "https://t.me/your_channel")
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://example.com")

DB_PATH = os.getenv("DB_PATH", "amour_annonce.db")

# =========================================================
# REGIONS / CITIES
# Keep / extend this structure to preserve your current geography logic.
# =========================================================

REGIONS: Dict[str, Dict[str, List[str]]] = {
    "france": {
        "label_fr": "France",
        "label_en": "France",
        "cities": [
            "Paris",
            "Lyon",
            "Marseille",
            "Nice",
            "Cannes",
            "Bordeaux",
            "Toulouse",
            "Lille",
            "Metz",
            "Strasbourg",
            "Nantes",
            "Montpellier",
        ],
    },
    "belgium": {
        "label_fr": "Belgique",
        "label_en": "Belgium",
        "cities": [
            "Bruxelles",
            "Anvers",
            "Liège",
            "Bruges",
            "Gand",
        ],
    },
    "switzerland": {
        "label_fr": "Suisse",
        "label_en": "Switzerland",
        "cities": [
            "Genève",
            "Lausanne",
            "Zurich",
            "Bâle",
        ],
    },
    "luxembourg": {
        "label_fr": "Luxembourg",
        "label_en": "Luxembourg",
        "cities": [
            "Luxembourg",
            "Esch-sur-Alzette",
        ],
    },
}

# =========================================================
# TEXTS / I18N
# =========================================================

TEXTS: Dict[str, Dict[str, str]] = {
    "fr": {
        "choose_lang": "Choisissez la langue :",
        "lang_saved": "Langue enregistrée : Français 🇫🇷",
        "welcome": (
            "Bienvenue dans <b>Amour Annonce</b>.\n\n"
            "Choisissez une action ci-dessous."
        ),
        "menu_model": "💎 Devenir modèle",
        "menu_tour": "🛫 Publier un tour",
        "menu_ad": "📣 Publier une annonce",
        "menu_browse": "🔎 Parcourir",
        "menu_contact": "💬 Contact",
        "menu_miniapp": "🌐 Mini App",
        "menu_admin": "🛠 Admin",
        "back": "⬅️ Retour",
        "cancel": "❌ Annuler",
        "done": "✅ Terminer",
        "skip": "⏭ Passer",
        "cancelled": "Action annulée.",
        "ask_name": "Envoyez le prénom / nom à afficher :",
        "ask_age": "Envoyez l'âge :",
        "ask_description": "Envoyez une description :",
        "ask_region": "Choisissez une région :",
        "ask_city": "Choisissez une ville :",
        "ask_contact_hint": (
            "Envoyez le texte du bouton de contact.\n"
            "Exemple : WhatsApp / Telegram / Réserver"
        ),
        "ask_contact_url": "Envoyez l'URL du bouton de contact :",
        "ask_tour_dates": "Envoyez les dates du tour :",
        "ask_category": "Choisissez le type de publication :",
        "ask_photos": (
            "Envoyez maintenant les photos.\n"
            "Vous pouvez envoyer plusieurs photos une par une.\n"
            "Quand c'est fini, appuyez sur ✅ Terminer."
        ),
        "need_one_photo": "Ajoutez au moins une photo avant de terminer.",
        "saved_for_review": "Merci. Votre publication a été envoyée en modération.",
        "choose_browse_type": "Que souhaitez-vous parcourir ?",
        "no_items_found": "Aucune publication trouvée.",
        "published": "✅ Publication approuvée et envoyée au canal.",
        "rejected": "❌ Publication refusée.",
        "admin_panel": "Panneau admin :",
        "admin_only": "Accès réservé à l'administrateur.",
        "unknown": "Commande non reconnue. Utilisez /start",
        "contact_button": "💬 Ouvrir le contact",
        "support_button": "🆘 Support",
        "vmodls_button": "✨ VMODLS",
        "miniapp_button": "🌐 Ouvrir Mini App",
        "browse_models": "💎 Modèles",
        "browse_tours": "🛫 Tours",
        "browse_ads": "📣 Annonces",
        "type_model": "Modèle",
        "type_tour": "Tour",
        "type_ad": "Annonce",
        "submission_received": "Nouvelle soumission reçue.",
        "approve": "✅ Approuver",
        "reject": "❌ Refuser",
        "notify_approved": "Votre publication a été approuvée ✅",
        "notify_rejected": "Votre publication a été refusée ❌",
        "empty_admin_queue": "Aucune soumission en attente.",
        "list_pending": "📋 En attente",
        "stats": "📊 Statistiques",
        "bad_url": "URL invalide. Envoyez un lien commençant par http:// ou https://",
        "bad_age": "Veuillez envoyer un âge valide.",
        "choose_action": "Choisissez une action :",
        "select_language_first": "Choisissez d'abord une langue.",
        "draft_preview": "Prévisualisation de votre publication :",
        "restart": "🔄 Revenir au menu",
    },
    "en": {
        "choose_lang": "Choose language:",
        "lang_saved": "Language saved: English 🇬🇧",
        "welcome": (
            "Welcome to <b>Amour Annonce</b>.\n\n"
            "Choose an action below."
        ),
        "menu_model": "💎 Become a model",
        "menu_tour": "🛫 Publish a tour",
        "menu_ad": "📣 Publish an ad",
        "menu_browse": "🔎 Browse",
        "menu_contact": "💬 Contact",
        "menu_miniapp": "🌐 Mini App",
        "menu_admin": "🛠 Admin",
        "back": "⬅️ Back",
        "cancel": "❌ Cancel",
        "done": "✅ Finish",
        "skip": "⏭ Skip",
        "cancelled": "Action cancelled.",
        "ask_name": "Send the display name:",
        "ask_age": "Send the age:",
        "ask_description": "Send a description:",
        "ask_region": "Choose a region:",
        "ask_city": "Choose a city:",
        "ask_contact_hint": (
            "Send the contact button text.\n"
            "Example: WhatsApp / Telegram / Book now"
        ),
        "ask_contact_url": "Send the contact button URL:",
        "ask_tour_dates": "Send the tour dates:",
        "ask_category": "Choose the publication type:",
        "ask_photos": (
            "Now send photos.\n"
            "You can send multiple photos one by one.\n"
            "When finished, press ✅ Finish."
        ),
        "need_one_photo": "Please add at least one photo before finishing.",
        "saved_for_review": "Thank you. Your publication has been sent for moderation.",
        "choose_browse_type": "What would you like to browse?",
        "no_items_found": "No publications found.",
        "published": "✅ Publication approved and sent to channel.",
        "rejected": "❌ Publication rejected.",
        "admin_panel": "Admin panel:",
        "admin_only": "Admin access only.",
        "unknown": "Unknown command. Use /start",
        "contact_button": "💬 Open contact",
        "support_button": "🆘 Support",
        "vmodls_button": "✨ VMODLS",
        "miniapp_button": "🌐 Open Mini App",
        "browse_models": "💎 Models",
        "browse_tours": "🛫 Tours",
        "browse_ads": "📣 Ads",
        "type_model": "Model",
        "type_tour": "Tour",
        "type_ad": "Ad",
        "submission_received": "New submission received.",
        "approve": "✅ Approve",
        "reject": "❌ Reject",
        "notify_approved": "Your publication has been approved ✅",
        "notify_rejected": "Your publication has been rejected ❌",
        "empty_admin_queue": "No pending submissions.",
        "list_pending": "📋 Pending",
        "stats": "📊 Statistics",
        "bad_url": "Invalid URL. Please send a link starting with http:// or https://",
        "bad_age": "Please send a valid age.",
        "choose_action": "Choose an action:",
        "select_language_first": "Please choose a language first.",
        "draft_preview": "Preview of your publication:",
        "restart": "🔄 Back to menu",
    },
}

# =========================================================
# STATES
# =========================================================

(
    LANG_CHOOSE,
    MAIN_MENU,
    SUB_NAME,
    SUB_AGE,
    SUB_DESC,
    SUB_REGION,
    SUB_CITY,
    SUB_DATES,
    SUB_CONTACT_HINT,
    SUB_CONTACT_URL,
    SUB_PHOTOS,
    BROWSE_TYPE,
    BROWSE_REGION,
    BROWSE_CITY,
) = range(14)

# =========================================================
# DATA MODELS
# =========================================================

@dataclass
class Submission:
    id: int
    user_id: int
    username: str
    language: str
    item_type: str
    name: str
    age: str
    description: str
    region_key: str
    city: str
    tour_dates: str
    contact_label: str
    contact_url: str
    status: str
    created_at: str

# =========================================================
# DATABASE
# =========================================================

class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    language TEXT DEFAULT 'fr',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    language TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    age TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    region_key TEXT NOT NULL,
                    city TEXT NOT NULL,
                    tour_dates TEXT DEFAULT '',
                    contact_label TEXT NOT NULL,
                    contact_url TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS submission_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(submission_id) REFERENCES submissions(id)
                )
                """
            )

    def upsert_user(self, user_id: int, username: str, language: Optional[str] = None) -> None:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                if language is not None:
                    conn.execute(
                        "UPDATE users SET username = ?, language = ? WHERE user_id = ?",
                        (username, language, user_id),
                    )
                else:
                    conn.execute(
                        "UPDATE users SET username = ? WHERE user_id = ?",
                        (username, user_id),
                    )
            else:
                conn.execute(
                    "INSERT INTO users (user_id, username, language) VALUES (?, ?, ?)",
                    (user_id, username, language or "fr"),
                )

    def get_user_language(self, user_id: int) -> str:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return row["language"] if row and row["language"] in ("fr", "en") else "fr"

    def create_submission(
        self,
        user_id: int,
        username: str,
        language: str,
        item_type: str,
        name: str,
        age: str,
        description: str,
        region_key: str,
        city: str,
        tour_dates: str,
        contact_label: str,
        contact_url: str,
        media_file_ids: List[str],
    ) -> int:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO submissions (
                    user_id, username, language, item_type, name, age, description,
                    region_key, city, tour_dates, contact_label, contact_url, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    user_id, username, language, item_type, name, age, description,
                    region_key, city, tour_dates, contact_label, contact_url,
                ),
            )
            submission_id = cur.lastrowid
            for i, file_id in enumerate(media_file_ids):
                conn.execute(
                    """
                    INSERT INTO submission_media (submission_id, file_id, sort_order)
                    VALUES (?, ?, ?)
                    """,
                    (submission_id, file_id, i),
                )
            return int(submission_id)

    def get_submission(self, submission_id: int) -> Optional[Submission]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
            if not row:
                return None
            return Submission(**dict(row))

    def get_submission_media(self, submission_id: int) -> List[str]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT file_id FROM submission_media
                WHERE submission_id = ?
                ORDER BY sort_order ASC, id ASC
                """,
                (submission_id,),
            ).fetchall()
            return [r["file_id"] for r in rows]

    def set_submission_status(self, submission_id: int, status: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE submissions SET status = ? WHERE id = ?",
                (status, submission_id),
            )

    def list_pending_submissions(self) -> List[Submission]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM submissions
                WHERE status = 'pending'
                ORDER BY id ASC
                """
            ).fetchall()
            return [Submission(**dict(r)) for r in rows]

    def browse_items(self, item_type: str, region_key: str, city: str) -> List[Submission]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM submissions
                WHERE status = 'approved'
                  AND item_type = ?
                  AND region_key = ?
                  AND city = ?
                ORDER BY id DESC
                LIMIT 20
                """,
                (item_type, region_key, city),
            ).fetchall()
            return [Submission(**dict(r)) for r in rows]

    def stats(self) -> Dict[str, int]:
        with closing(self._connect()) as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"]
            pending = conn.execute("SELECT COUNT(*) AS c FROM submissions WHERE status='pending'").fetchone()["c"]
            approved = conn.execute("SELECT COUNT(*) AS c FROM submissions WHERE status='approved'").fetchone()["c"]
            rejected = conn.execute("SELECT COUNT(*) AS c FROM submissions WHERE status='rejected'").fetchone()["c"]
            users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            return {
                "users": int(users),
                "total": int(total),
                "pending": int(pending),
                "approved": int(approved),
                "rejected": int(rejected),
            }

db = Database(DB_PATH)

# =========================================================
# HELPERS
# =========================================================

def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["fr"]).get(key, key)

def get_lang(update: Update) -> str:
    if update.effective_user:
        return db.get_user_language(update.effective_user.id)
    return "fr"

def username_of(update: Update) -> str:
    u = update.effective_user
    if not u:
        return ""
    return u.username or f"{u.first_name or ''} {u.last_name or ''}".strip()

def safe_html(text: str) -> str:
    return html.escape(text or "")

def is_admin(user_id: Optional[int]) -> bool:
    return bool(user_id) and int(user_id) == int(ADMIN_ID)

def valid_http_url(value: str) -> bool:
    value = (value or "").strip()
    return value.startswith("http://") or value.startswith("https://")

def user_menu_keyboard(lang: str, user_id: Optional[int]) -> ReplyKeyboardMarkup:
    rows = [
        [t(lang, "menu_model"), t(lang, "menu_tour")],
        [t(lang, "menu_ad"), t(lang, "menu_browse")],
        [t(lang, "menu_contact"), t(lang, "menu_miniapp")],
    ]
    if is_admin(user_id):
        rows.append([t(lang, "menu_admin")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def cancel_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[t(lang, "cancel")]], resize_keyboard=True)

def photo_finish_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[t(lang, "done")], [t(lang, "cancel")]],
        resize_keyboard=True,
    )

def admin_inline_keyboard(submission_id: int, lang: str = "fr") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(lang, "approve"), callback_data=f"approve:{submission_id}"),
                InlineKeyboardButton(t(lang, "reject"), callback_data=f"reject:{submission_id}"),
            ]
        ]
    )

def external_buttons(contact_label: str, contact_url: str, lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(contact_label or t(lang, "contact_button"), url=contact_url)],
        [
            InlineKeyboardButton(t(lang, "support_button"), url=SUPPORT_URL),
            InlineKeyboardButton(t(lang, "vmodls_button"), url=VMODLS_URL),
        ],
        [InlineKeyboardButton(t(lang, "miniapp_button"), url=MINIAPP_URL)],
    ]
    return InlineKeyboardMarkup(buttons)

def region_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for key, data in REGIONS.items():
        label = data["label_fr"] if lang == "fr" else data["label_en"]
        rows.append([InlineKeyboardButton(label, callback_data=f"region:{key}")])
    return InlineKeyboardMarkup(rows)

def city_keyboard(region_key: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(city, callback_data=f"city:{region_key}:{city}")]
        for city in REGIONS.get(region_key, {}).get("cities", [])
    ]
    return InlineKeyboardMarkup(rows)

def browse_type_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "browse_models"), callback_data="browse_type:model")],
            [InlineKeyboardButton(t(lang, "browse_tours"), callback_data="browse_type:tour")],
            [InlineKeyboardButton(t(lang, "browse_ads"), callback_data="browse_type:ad")],
        ]
    )

def format_region(region_key: str, lang: str) -> str:
    data = REGIONS.get(region_key, {})
    return data.get("label_fr") if lang == "fr" else data.get("label_en", region_key)

def build_submission_caption(sub: Submission) -> str:
    lang = sub.language if sub.language in ("fr", "en") else "fr"
    type_label = {
        "model": t(lang, "type_model"),
        "tour": t(lang, "type_tour"),
        "ad": t(lang, "type_ad"),
    }.get(sub.item_type, sub.item_type)

    lines = [
        f"<b>{safe_html(sub.name)}</b>",
        f"• {safe_html(type_label)}",
        f"• {safe_html(format_region(sub.region_key, lang))} / {safe_html(sub.city)}",
    ]
    if sub.age:
        lines.append(f"• {safe_html(sub.age)}")
    if sub.tour_dates:
        lines.append(f"• {safe_html(sub.tour_dates)}")
    if sub.description:
        lines.append("")
        lines.append(safe_html(sub.description))
    return "\n".join(lines)

def build_admin_caption(sub: Submission) -> str:
    return (
        f"🆕 <b>New submission #{sub.id}</b>\n"
        f"User: <code>{sub.user_id}</code> / @{safe_html(sub.username)}\n"
        f"Lang: {safe_html(sub.language)}\n"
        f"Type: {safe_html(sub.item_type)}\n"
        f"Region: {safe_html(sub.region_key)}\n"
        f"City: {safe_html(sub.city)}\n"
        f"Name: {safe_html(sub.name)}\n"
        f"Age: {safe_html(sub.age)}\n"
        f"Tour: {safe_html(sub.tour_dates)}\n"
        f"Contact button: {safe_html(sub.contact_label)}\n"
        f"Contact URL: {safe_html(sub.contact_url)}\n\n"
        f"{safe_html(sub.description)}"
    )

async def send_media_group_safe(bot, chat_id: int, media_file_ids: List[str], caption: str) -> None:
    media: List[InputMediaPhoto] = []
    for i, file_id in enumerate(media_file_ids[:10]):
        if i == 0:
            media.append(InputMediaPhoto(media=file_id, caption=caption, parse_mode=ParseMode.HTML))
        else:
            media.append(InputMediaPhoto(media=file_id))
    await bot.send_media_group(chat_id=chat_id, media=media)

async def notify_user_safe(bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Forbidden:
        logger.warning("Cannot notify user %s: bot blocked or chat unavailable", user_id)
    except Exception as exc:
        logger.exception("Failed to notify user %s: %s", user_id, exc)

async def answer_or_edit(query, text: str, reply_markup=None) -> None:
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest:
        await query.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

def clear_draft(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("draft", None)

def get_draft(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    if "draft" not in context.user_data:
        context.user_data["draft"] = {
            "item_type": "",
            "name": "",
            "age": "",
            "description": "",
            "region_key": "",
            "city": "",
            "tour_dates": "",
            "contact_label": "",
            "contact_url": "",
            "media_file_ids": [],
        }
    return context.user_data["draft"]

# =========================================================
# COMMANDS / START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if user:
        db.upsert_user(user.id, username_of(update))
    clear_draft(context)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Français 🇫🇷", callback_data="setlang:fr"),
                InlineKeyboardButton("English 🇬🇧", callback_data="setlang:en"),
            ]
        ]
    )
    if update.message:
        await update.message.reply_text(TEXTS["fr"]["choose_lang"], reply_markup=keyboard)
    else:
        await update.effective_chat.send_message(TEXTS["fr"]["choose_lang"], reply_markup=keyboard)
    return LANG_CHOOSE

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    user = update.effective_user
    if user:
        db.upsert_user(user.id, username_of(update), language=lang)
    text = t(lang, "lang_saved") + "\n\n" + t(lang, "welcome")
    await answer_or_edit(query, text=text, reply_markup=None)
    await query.message.reply_text(
        t(lang, "choose_action"),
        reply_markup=user_menu_keyboard(lang, user.id if user else None),
    )
    return MAIN_MENU

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    if update.message:
        await update.message.reply_text(
            t(lang, "welcome"),
            parse_mode=ParseMode.HTML,
            reply_markup=user_menu_keyboard(lang, update.effective_user.id if update.effective_user else None),
        )
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    clear_draft(context)
    await update.message.reply_text(
        t(lang, "cancelled"),
        reply_markup=user_menu_keyboard(lang, update.effective_user.id if update.effective_user else None),
    )
    return MAIN_MENU

# =========================================================
# MAIN MENU ACTIONS
# =========================================================

async def main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    text = update.message.text.strip()

    if text == t(lang, "menu_model"):
        draft = get_draft(context)
        draft["item_type"] = "model"
        await update.message.reply_text(t(lang, "ask_name"), reply_markup=cancel_keyboard(lang))
        return SUB_NAME

    if text == t(lang, "menu_tour"):
        draft = get_draft(context)
        draft["item_type"] = "tour"
        await update.message.reply_text(t(lang, "ask_name"), reply_markup=cancel_keyboard(lang))
        return SUB_NAME

    if text == t(lang, "menu_ad"):
        draft = get_draft(context)
        draft["item_type"] = "ad"
        await update.message.reply_text(t(lang, "ask_name"), reply_markup=cancel_keyboard(lang))
        return SUB_NAME

    if text == t(lang, "menu_browse"):
        await update.message.reply_text(t(lang, "choose_browse_type"), reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text(t(lang, "choose_browse_type"), reply_markup=browse_type_keyboard(lang))
        return BROWSE_TYPE

    if text == t(lang, "menu_contact"):
        await update.message.reply_text(
            t(lang, "contact_button"),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(t(lang, "contact_button"), url=SUPPORT_URL)]]
            ),
        )
        return MAIN_MENU

    if text == t(lang, "menu_miniapp"):
        await update.message.reply_text(
            t(lang, "miniapp_button"),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(t(lang, "miniapp_button"), url=MINIAPP_URL)]]
            ),
        )
        return MAIN_MENU

    if text == t(lang, "menu_admin"):
        if not is_admin(update.effective_user.id if update.effective_user else None):
            await update.message.reply_text(t(lang, "admin_only"))
            return MAIN_MENU
        stats = db.stats()
        message = (
            f"{t(lang, 'admin_panel')}\n\n"
            f"Users: {stats['users']}\n"
            f"Total: {stats['total']}\n"
            f"Pending: {stats['pending']}\n"
            f"Approved: {stats['approved']}\n"
            f"Rejected: {stats['rejected']}"
        )
        admin_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(t(lang, "list_pending"), callback_data="admin:pending")],
                [InlineKeyboardButton(t(lang, "stats"), callback_data="admin:stats")],
            ]
        )
        await update.message.reply_text(message, reply_markup=admin_buttons)
        return MAIN_MENU

    await update.message.reply_text(
        t(lang, "choose_action"),
        reply_markup=user_menu_keyboard(lang, update.effective_user.id if update.effective_user else None),
    )
    return MAIN_MENU

# =========================================================
# SUBMISSION FLOW
# =========================================================

async def sub_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    draft = get_draft(context)
    draft["name"] = update.message.text.strip()
    await update.message.reply_text(t(lang, "ask_age"), reply_markup=cancel_keyboard(lang))
    return SUB_AGE

async def sub_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    age = update.message.text.strip()
    if not age.isdigit():
        await update.message.reply_text(t(lang, "bad_age"))
        return SUB_AGE
    draft = get_draft(context)
    draft["age"] = age
    await update.message.reply_text(t(lang, "ask_description"), reply_markup=cancel_keyboard(lang))
    return SUB_DESC

async def sub_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    draft = get_draft(context)
    draft["description"] = update.message.text.strip()
    await update.message.reply_text(t(lang, "ask_region"), reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(t(lang, "ask_region"), reply_markup=region_keyboard(lang))
    return SUB_REGION

async def sub_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_lang(update)
    region_key = query.data.split(":")[1]
    draft = get_draft(context)
    draft["region_key"] = region_key
    await answer_or_edit(query, t(lang, "ask_city"), reply_markup=city_keyboard(region_key))
    return SUB_CITY

async def sub_city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_lang(update)
    parts = query.data.split(":")
    region_key = parts[1]
    city = ":".join(parts[2:])
    draft = get_draft(context)
    draft["region_key"] = region_key
    draft["city"] = city

    if draft["item_type"] == "tour":
        await answer_or_edit(query, t(lang, "ask_tour_dates"))
        await query.message.reply_text(t(lang, "ask_tour_dates"), reply_markup=cancel_keyboard(lang))
        return SUB_DATES

    await answer_or_edit(query, t(lang, "ask_contact_hint"))
    await query.message.reply_text(t(lang, "ask_contact_hint"), reply_markup=cancel_keyboard(lang))
    return SUB_CONTACT_HINT

async def sub_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    draft = get_draft(context)
    draft["tour_dates"] = update.message.text.strip()
    await update.message.reply_text(t(lang, "ask_contact_hint"), reply_markup=cancel_keyboard(lang))
    return SUB_CONTACT_HINT

async def sub_contact_hint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    draft = get_draft(context)
    draft["contact_label"] = update.message.text.strip()
    await update.message.reply_text(t(lang, "ask_contact_url"), reply_markup=cancel_keyboard(lang))
    return SUB_CONTACT_URL

async def sub_contact_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    draft = get_draft(context)
    url = update.message.text.strip()
    if not valid_http_url(url):
        await update.message.reply_text(t(lang, "bad_url"))
        return SUB_CONTACT_URL
    draft["contact_url"] = url
    draft["media_file_ids"] = []
    await update.message.reply_text(t(lang, "ask_photos"), reply_markup=photo_finish_keyboard(lang))
    return SUB_PHOTOS

async def sub_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_lang(update)
    draft = get_draft(context)

    text = (update.message.text or "").strip()
    if text == t(lang, "cancel"):
        return await cancel(update, context)

    if text == t(lang, "done"):
        if not draft["media_file_ids"]:
            await update.message.reply_text(t(lang, "need_one_photo"))
            return SUB_PHOTOS

        user = update.effective_user
        username = username_of(update)
        db.upsert_user(user.id, username, language=lang)

        submission_id = db.create_submission(
            user_id=user.id,
            username=username,
            language=lang,
            item_type=draft["item_type"],
            name=draft["name"],
            age=draft["age"],
            description=draft["description"],
            region_key=draft["region_key"],
            city=draft["city"],
            tour_dates=draft["tour_dates"],
            contact_label=draft["contact_label"],
            contact_url=draft["contact_url"],
            media_file_ids=draft["media_file_ids"],
        )
        sub = db.get_submission(submission_id)
        if sub:
            admin_caption = build_admin_caption(sub)
            media = db.get_submission_media(submission_id)
            try:
                await send_media_group_safe(context.bot, ADMIN_ID, media, admin_caption)
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"Moderation controls for submission #{submission_id}",
                    reply_markup=admin_inline_keyboard(submission_id, "fr"),
                )
            except Exception as exc:
                logger.exception("Failed to send moderation album: %s", exc)

        await update.message.reply_text(
            t(lang, "saved_for_review"),
            reply_markup=user_menu_keyboard(lang, user.id),
        )
        clear_draft(context)
        return MAIN_MENU

    if update.message.photo:
        largest = update.message.photo[-1]
        draft["media_file_ids"].append(largest.file_id)
        await update.message.reply_text(
            f"📸 {len(draft['media_file_ids'])} photo(s) added.",
            reply_markup=photo_finish_keyboard(lang),
        )
        return SUB_PHOTOS

    await update.message.reply_text(t(lang, "ask_photos"), reply_markup=photo_finish_keyboard(lang))
    return SUB_PHOTOS

# =========================================================
# BROWSE FLOW
# =========================================================

async def browse_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_lang(update)
    browse_type = query.data.split(":")[1]
    context.user_data["browse_type"] = browse_type
    await answer_or_edit(query, t(lang, "ask_region"), reply_markup=region_keyboard(lang))
    return BROWSE_REGION

async def browse_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_lang(update)
    region_key = query.data.split(":")[1]
    context.user_data["browse_region"] = region_key
    await answer_or_edit(query, t(lang, "ask_city"), reply_markup=city_keyboard(region_key))
    return BROWSE_CITY

async def browse_city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_lang(update)
    parts = query.data.split(":")
    region_key = parts[1]
    city = ":".join(parts[2:])
    browse_type = context.user_data.get("browse_type", "ad")

    items = db.browse_items(browse_type, region_key, city)
    if not items:
        await answer_or_edit(query, t(lang, "no_items_found"))
        await query.message.reply_text(
            t(lang, "choose_action"),
            reply_markup=user_menu_keyboard(lang, update.effective_user.id if update.effective_user else None),
        )
        return MAIN_MENU

    await answer_or_edit(query, f"{len(items)} item(s) found.")
    for sub in items:
        media_ids = db.get_submission_media(sub.id)
        caption = build_submission_caption(sub)
        try:
            await send_media_group_safe(context.bot, query.message.chat_id, media_ids, caption)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=" ",
                reply_markup=external_buttons(sub.contact_label, sub.contact_url, lang),
            )
        except Exception as exc:
            logger.exception("Failed to display browse item %s: %s", sub.id, exc)

    await query.message.reply_text(
        t(lang, "choose_action"),
        reply_markup=user_menu_keyboard(lang, update.effective_user.id if update.effective_user else None),
    )
    return MAIN_MENU

# =========================================================
# ADMIN FLOW
# =========================================================

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None
    lang = get_lang(update)

    if not is_admin(user_id):
        await query.answer(t(lang, "admin_only"), show_alert=True)
        return

    data = query.data
    if data == "admin:pending":
        pending = db.list_pending_submissions()
        if not pending:
            await answer_or_edit(query, t(lang, "empty_admin_queue"))
            return
        lines = [f"Pending submissions: {len(pending)}", ""]
        for sub in pending[:20]:
            lines.append(f"#{sub.id} | {sub.item_type} | {sub.city} | {sub.name}")
        await answer_or_edit(query, "\n".join(lines))
        return

    if data == "admin:stats":
        stats = db.stats()
        text = textwrap.dedent(
            f"""
            <b>Stats</b>

            Users: {stats['users']}
            Total: {stats['total']}
            Pending: {stats['pending']}
            Approved: {stats['approved']}
            Rejected: {stats['rejected']}
            """
        ).strip()
        await answer_or_edit(query, text)
        return

async def moderate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id if update.effective_user else None
    if not is_admin(user_id):
        await query.answer("Admin only", show_alert=True)
        return

    action, submission_id_raw = query.data.split(":")
    submission_id = int(submission_id_raw)
    sub = db.get_submission(submission_id)
    if not sub:
        await query.answer("Submission not found", show_alert=True)
        return

    if action == "approve":
        try:
            media_ids = db.get_submission_media(submission_id)
            caption = build_submission_caption(sub)
            await send_media_group_safe(context.bot, CHANNEL_ID, media_ids, caption)
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=" ",
                reply_markup=external_buttons(sub.contact_label, sub.contact_url, sub.language),
            )
            db.set_submission_status(submission_id, "approved")
            await query.message.reply_text(f"Submission #{submission_id} approved and published.")
            await notify_user_safe(context.bot, sub.user_id, t(sub.language, "notify_approved"))
        except Exception as exc:
            logger.exception("Failed to publish submission %s: %s", submission_id, exc)
            await query.message.reply_text(f"Publish failed for #{submission_id}: {exc}")
            return

    elif action == "reject":
        db.set_submission_status(submission_id, "rejected")
        await query.message.reply_text(f"Submission #{submission_id} rejected.")
        await notify_user_safe(context.bot, sub.user_id, t(sub.language, "notify_rejected"))

# =========================================================
# FALLBACKS / COMMON
# =========================================================

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_lang(update)
    if update.message:
        await update.message.reply_text(
            t(lang, "unknown"),
            reply_markup=user_menu_keyboard(lang, update.effective_user.id if update.effective_user else None),
        )

async def on_text_during_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Français 🇫🇷", callback_data="setlang:fr"),
                InlineKeyboardButton("English 🇬🇧", callback_data="setlang:en"),
            ]
        ]
    )
    await update.message.reply_text(TEXTS["fr"]["choose_lang"], reply_markup=keyboard)
    return LANG_CHOOSE

async def post_init(application: Application) -> None:
    logger.info("Bot started successfully.")
    try:
        await application.bot.set_my_commands([
            ("start", "Start / restart the bot"),
            ("menu", "Open the main menu"),
            ("cancel", "Cancel current action"),
        ])
    except Exception as exc:
        logger.warning("Could not set commands: %s", exc)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await send_main_menu(update, context)

# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    exc = context.error
    if isinstance(exc, RetryAfter):
        logger.warning("Rate limited. Retry after %s seconds", exc.retry_after)
        await asyncio.sleep(float(exc.retry_after))
        return
    if isinstance(exc, (TimedOut, NetworkError)):
        logger.warning("Transient telegram/network issue: %s", exc)
        return
    logger.exception("Unhandled exception: %s", exc)

    try:
        if isinstance(update, Update):
            user = update.effective_user
            if user and update.effective_chat:
                lang = db.get_user_language(user.id)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "Une erreur temporaire s'est produite. Réessayez."
                        if lang == "fr"
                        else "A temporary error occurred. Please try again."
                    ),
                )
    except Exception:
        logger.exception("Failed to send error notification to user")

# =========================================================
# APP BUILDER
# =========================================================

def build_application() -> Application:
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN":
        raise RuntimeError(
            "BOT_TOKEN is not configured. Set BOT_TOKEN in Railway env vars "
            "or replace the fallback value in bot.py"
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", menu_command),
        ],
        states={
            LANG_CHOOSE: [
                CallbackQueryHandler(set_language, pattern=r"^setlang:(fr|en)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_during_lang),
            ],
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_router),
                CallbackQueryHandler(admin_callback, pattern=r"^admin:(pending|stats)$"),
                CallbackQueryHandler(moderate_callback, pattern=r"^(approve|reject):\d+$"),
                CallbackQueryHandler(browse_type_callback, pattern=r"^browse_type:(model|tour|ad)$"),
            ],
            SUB_NAME: [
                MessageHandler(filters.Regex(r"^❌ Cancel$|^❌ Annuler$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sub_name),
            ],
            SUB_AGE: [
                MessageHandler(filters.Regex(r"^❌ Cancel$|^❌ Annuler$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sub_age),
            ],
            SUB_DESC: [
                MessageHandler(filters.Regex(r"^❌ Cancel$|^❌ Annuler$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sub_desc),
            ],
            SUB_REGION: [
                CallbackQueryHandler(sub_region_callback, pattern=r"^region:[a-z_]+$"),
            ],
            SUB_CITY: [
                CallbackQueryHandler(sub_city_callback, pattern=r"^city:[a-z_]+:.+$"),
            ],
            SUB_DATES: [
                MessageHandler(filters.Regex(r"^❌ Cancel$|^❌ Annuler$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sub_dates),
            ],
            SUB_CONTACT_HINT: [
                MessageHandler(filters.Regex(r"^❌ Cancel$|^❌ Annuler$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sub_contact_hint),
            ],
            SUB_CONTACT_URL: [
                MessageHandler(filters.Regex(r"^❌ Cancel$|^❌ Annuler$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sub_contact_url),
            ],
            SUB_PHOTOS: [
                MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, sub_photos),
            ],
            BROWSE_TYPE: [
                CallbackQueryHandler(browse_type_callback, pattern=r"^browse_type:(model|tour|ad)$"),
            ],
            BROWSE_REGION: [
                CallbackQueryHandler(browse_region_callback, pattern=r"^region:[a-z_]+$"),
            ],
            BROWSE_CITY: [
                CallbackQueryHandler(browse_city_callback, pattern=r"^city:[a-z_]+:.+$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex(r"^❌ Cancel$|^❌ Annuler$"), cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:(pending|stats)$"))
    app.add_handler(CallbackQueryHandler(moderate_callback, pattern=r"^(approve|reject):\d+$"))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_error_handler(error_handler)
    return app

# =========================================================
# MAIN
# =========================================================

def main() -> None:
    app = build_application()
    logger.info("Running polling bot...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
        close_loop=False,
    )

if __name__ == "__main__":
    main()
