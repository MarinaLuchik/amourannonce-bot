"""
Amour Annonce — Production Bot
FR/EN users | RU admin | SQLite | Railway-ready
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
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8549540559:AAEd3EllVX0oQnaRUooL54krXwSwg5Iz_wA")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "@amourannonce")
ADMIN_ID    = int(os.getenv("ADMIN_ID", "2021397237"))
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/loveparis777")
VMODLS_URL  = os.getenv("VMODLS_URL", "https://t.me/VModls")
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://www.amourannonce.com")
DB_PATH     = os.getenv("DB_PATH", "amour.db")
MAX_PHOTOS  = min(int(os.getenv("MAX_PHOTOS", "8")), 10)
MAX_ACTIVE  = int(os.getenv("MAX_ACTIVE_PER_USER", "3"))
CLEANUP_SEC = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "3600"))

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger("amour")

# ─── REGIONS ──────────────────────────────────────────────────────────────────
REGIONS: Dict[str, List[str]] = {
    "🗼 Paris — Centre & Luxe (1-10)": [
        "Paris 1er — Louvre", "Paris 2e — Bourse", "Paris 3e — Marais",
        "Paris 4e — Île Saint-Louis", "Paris 5e — Quartier Latin",
        "Paris 6e — Saint-Germain", "Paris 7e — Eiffel",
        "Paris 8e — Champs-Élysées", "Paris 9e — Opéra", "Paris 10e — Canal St-Martin",
    ],
    "🗼 Paris — Est & Sud (11-15)": [
        "Paris 11e — Bastille", "Paris 12e — Bercy",
        "Paris 13e — Place d'Italie", "Paris 14e — Montparnasse", "Paris 15e — Convention",
    ],
    "🗼 Paris — Ouest & Nord (16-20)": [
        "Paris 16e — Trocadéro", "Paris 17e — Batignolles",
        "Paris 18e — Montmartre", "Paris 19e — La Villette", "Paris 20e — Belleville",
    ],
    "🏙 Île-de-France — Proche banlieue": [
        "Boulogne-Billancourt", "Neuilly-sur-Seine", "Levallois-Perret",
        "Issy-les-Moulineaux", "Courbevoie", "La Défense", "Puteaux",
        "Saint-Cloud", "Vincennes", "Saint-Mandé", "Montreuil",
        "Bagnolet", "Saint-Denis", "Aubervilliers", "Pantin", "Créteil",
    ],
    "🏙 Île-de-France — Grande banlieue": [
        "Versailles", "Saint-Germain-en-Laye", "Massy",
        "Évry-Courcouronnes", "Pontoise", "Cergy", "Melun", "Fontainebleau",
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
        "Toulouse", "Montpellier", "Perpignan", "Nîmes", "Sète", "Béziers",
    ],
    "🍷 Nouvelle-Aquitaine": [
        "Bordeaux", "Biarritz", "Arcachon", "Bayonne", "La Rochelle",
        "Pau", "Limoges", "Poitiers",
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
    ("👱 Blonde", "Blonde"), ("🟤 Brune", "Brune"),
    ("🔴 Rousse", "Rousse"), ("⬛ Noire", "Noire"),
    ("🌰 Châtain", "Châtain"), ("🎨 Colorée", "Colorée"),
]
EYE_OPTIONS = [
    ("🔵 Bleus", "Bleus"), ("🟢 Verts", "Verts"),
    ("🟤 Marron", "Marron"), ("🟠 Noisette", "Noisette"), ("⚫ Noirs", "Noirs"),
]
INCALL_OPTIONS = [
    ("🏠 Incall uniquement", "Incall uniquement"),
    ("🚗 Outcall uniquement", "Outcall uniquement"),
    ("🏠🚗 Incall + Outcall", "Incall + Outcall"),
]
AVAILABILITY_OPTIONS = [
    ("🕐 24h/24", "24h/24"), ("☀️ En journée", "En journée"),
    ("🌙 En soirée", "En soirée"), ("🌃 Nuits uniquement", "Nuits uniquement"),
    ("📅 Weekends", "Weekends"), ("📞 Sur rendez-vous", "Sur rendez-vous"),
]
BODY_OPTIONS = [
    ("✨ Fine", "Fine"), ("💪 Sportive", "Sportive"),
    ("🍑 Pulpeuse", "Pulpeuse"), ("💎 Élancée", "Élancée"),
]
BREAST_OPTIONS = [("💎 Naturelle", "Naturelle"), ("✨ Silicone", "Silicone")]
YESNO_OPTIONS  = [("✅ Oui", "Oui"), ("❌ Non", "Non")]
LANG_OPTIONS   = [
    ("🇫🇷 Français", "Français"), ("🇬🇧 Anglais", "Anglais"),
    ("🇷🇺 Russe", "Russe"), ("🇪🇸 Espagnol", "Espagnol"),
    ("🇮🇹 Italien", "Italien"), ("🇩🇪 Allemand", "Allemand"),
    ("🇵🇹 Portugais", "Portugais"), ("🇸🇦 Arabe", "Arabe"),
    ("🇺🇦 Ukrainien", "Ukrainien"),
]
PRICE_SLOTS = [
    ("15min","15 min"), ("20min","20 min"), ("30min","30 min"),
    ("45min","45 min"), ("1h","1h"), ("1h30","1h30"),
    ("2h","2h"), ("soiree","Soirée"), ("nuit","Nuit"),
]

# ─── TEXTS ────────────────────────────────────────────────────────────────────
TX = {
    "fr": {
        "greeting":    "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPlateforme privée premium pour modèles et annonces en France 🇫🇷\n\nChoisissez votre langue :",
        "welcome":     "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nQue souhaitez-vous faire ?",
        "site":        "🌐 Ouvrir le site",
        "support":     "💬 Support — @loveparis777",
        "agency":      "🌟 Agence — @VModls",
        "annonces":    "📢 Voir les annonces",
        "tours":       "✈️ Tours",
        "model_post":  "👗 Déposer mon profil",
        "tour_search": "🔍 Chercher un tour → @loveparis777",
        "admin":       "🔐 Admin Panel",
        "back":        "◀️ Retour",
        "menu":        "🏠 Menu",
        "cancel":      "✖️ Annuler",
        "skip":        "⏭ Passer",
        "done":        "✅ Terminer",
        "send":        "✅ Envoyer en modération",
        "choose_region": "📍 Choisissez votre région :",
        "choose_city":   "🏙 Choisissez votre ville :",
        "what_next":   "📍 <b>{city}</b>\n━━━━━━━━━━━━━━━━━━\nQue souhaitez-vous faire ?",
        "ask_name":    "👤 Votre prénom :\n<i>Exemple: Sofia, Marie...</i>",
        "ask_age":     "🎂 Votre âge :\n<i>Entre 18 et 65</i>",
        "ask_origin":  "🌍 Votre origine / nationalité :\n<i>Exemple: Ukrainienne, Russe...</i>",
        "ask_height":  "📏 Votre taille en cm :\n<i>Exemple: 168</i>",
        "ask_weight":  "⚖️ Votre poids en kg :\n<i>Exemple: 55</i>",
        "ask_measurements": "📐 Vos mensurations :\n<i>Format: Bonnet — Taille — Hanches\nExemple: 90C — 60 — 90</i>",
        "ask_hair":    "💇 Couleur de cheveux :",
        "ask_eyes":    "👁 Couleur des yeux :",
        "ask_langs":   "🗣 Langues parlées :\n<i>Sélectionnez une ou plusieurs langues</i>",
        "confirm_langs": "✅ Confirmer les langues",
        "ask_body":    "✨ Type de silhouette :",
        "ask_breast":  "💎 Type de poitrine :",
        "ask_smoker":  "🚬 Fumeuse ?",
        "ask_tattoos": "🖋 Tatouages ?",
        "ask_incall":  "🏠 Type de service :",
        "ask_avail":   "🕐 Disponibilités :",
        "ask_prices":  (
            "💶 <b>Vos tarifs</b>\n\n"
            "Entrez vos prix, un par ligne :\n"
            "<code>15min: 80\n20min: 100\n30min: 150\n45min: 200\n"
            "1h: 300\n1h30: 420\n2h: 550\nSoirée: 1200\nNuit: 1800</code>\n\n"
            "<i>👉 Chiffres uniquement — 0 si non disponible</i>"
        ),
        "ask_desc":    "📝 Décrivez-vous en quelques mots :\n<i>Minimum 20 caractères</i>",
        "ask_contact": "📞 Votre contact :\n<i>@telegram, numéro ou lien</i>",
        "ask_photos":  f"📸 Envoyez vos photos (1–{MAX_PHOTOS})\nQuand vous avez terminé → appuyez sur ✅ Terminer",
        "preview":     "👁 <b>Aperçu avant envoi</b>\n━━━━━━━━━━━━━━━━━━\nVérifiez vos informations.",
        "sent":        "✅ <b>Envoyé en modération !</b>\nNous vous répondrons sous 24h.",
        "no_results":  "😔 Aucun résultat pour le moment.",
        "end":         "— Fin des résultats —",
        "contact_btn": "💬 Contacter",
        "vip":         "⭐️ VIP",
        "tour_who":    "Vous êtes :",
        "tour_model":  "👗 Je suis modèle — je pars en tour",
        "tour_host":   "🏨 J'accueille des modèles",
        "tour_from":   "🛫 Votre ville de départ :\n<i>Exemple: Moscou, Kiev...</i>",
        "tour_date_from": "📅 Date d'arrivée :\n<i>Exemple: 15.04</i>",
        "tour_date_to":   "📅 Date de départ :\n<i>Exemple: 20.04</i>",
        "tour_notes":  "📝 Notes / conditions :\n<i>Tarifs, logement, etc.</i>",
        "ad_title":    "📝 Titre de l'annonce :\n<i>Exemple: Massage relaxant Paris 8e</i>",
        "ad_desc":     "📋 Description :\n<i>Décrivez votre service</i>",
        "err_short":   "⚠️ Valeur trop courte. Réessayez.",
        "err_long":    "⚠️ Texte trop long. Maximum 1200 caractères.",
        "err_age":     "⚠️ Âge invalide. Entrez un nombre entre 18 et 65.",
        "err_height":  "⚠️ Taille invalide. Entre 140 et 200 cm.",
        "err_weight":  "⚠️ Poids invalide. Entre 40 et 120 kg.",
        "err_contact": "⚠️ Contact invalide.\n• @username\n• +33 6 12 34 56 78\n• https://lien",
        "err_photo":   "⚠️ Ajoutez au moins une photo.",
        "err_langs":   "⚠️ Sélectionnez au moins une langue.",
        "err_limit":   f"⚠️ Limite atteinte : {MAX_ACTIVE} publications actives maximum.",
        "photos_only": "📸 Veuillez envoyer des photos uniquement.",
        "filter_all":  "🔎 Tout voir",
        "filter_vip":  "⭐ VIP",
        "filter_new":  "🆕 Récents",
        "filter_in":   "🏠 Incall",
        "filter_out":  "🚗 Outcall",
        "filter_bl":   "👱 Blonde",
        "filter_br":   "🟤 Brune",
        "filter_mod":  "👗 Modèles",
        "filter_host": "🏨 Hôtes",
    },
    "en": {
        "greeting":    "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPrivate premium platform for models and ads in France 🇫🇷\n\nChoose your language:",
        "welcome":     "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nWhat would you like to do?",
        "site":        "🌐 Open website",
        "support":     "💬 Support — @loveparis777",
        "agency":      "🌟 Agency — @VModls",
        "annonces":    "📢 Browse listings",
        "tours":       "✈️ Tours",
        "model_post":  "👗 Post my profile",
        "tour_search": "🔍 Looking for a tour → @loveparis777",
        "admin":       "🔐 Admin Panel",
        "back":        "◀️ Back",
        "menu":        "🏠 Menu",
        "cancel":      "✖️ Cancel",
        "skip":        "⏭ Skip",
        "done":        "✅ Finish",
        "send":        "✅ Send for moderation",
        "choose_region": "📍 Choose your region:",
        "choose_city":   "🏙 Choose your city:",
        "what_next":   "📍 <b>{city}</b>\n━━━━━━━━━━━━━━━━━━\nWhat would you like to do?",
        "ask_name":    "👤 Your display name:\n<i>Example: Sofia, Marie...</i>",
        "ask_age":     "🎂 Your age:\n<i>Between 18 and 65</i>",
        "ask_origin":  "🌍 Your origin / nationality:\n<i>Example: Ukrainian, Russian...</i>",
        "ask_height":  "📏 Your height in cm:\n<i>Example: 168</i>",
        "ask_weight":  "⚖️ Your weight in kg:\n<i>Example: 55</i>",
        "ask_measurements": "📐 Your measurements:\n<i>Format: Cup — Waist — Hips\nExample: 90C — 60 — 90</i>",
        "ask_hair":    "💇 Hair color:",
        "ask_eyes":    "👁 Eye color:",
        "ask_langs":   "🗣 Spoken languages:\n<i>Select one or more</i>",
        "confirm_langs": "✅ Confirm languages",
        "ask_body":    "✨ Body type:",
        "ask_breast":  "💎 Breast type:",
        "ask_smoker":  "🚬 Smoker?",
        "ask_tattoos": "🖋 Tattoos?",
        "ask_incall":  "🏠 Service type:",
        "ask_avail":   "🕐 Availability:",
        "ask_prices":  (
            "💶 <b>Your rates</b>\n\n"
            "Enter prices line by line:\n"
            "<code>15min: 80\n20min: 100\n30min: 150\n45min: 200\n"
            "1h: 300\n1h30: 420\n2h: 550\nEvening: 1200\nNight: 1800</code>\n\n"
            "<i>👉 Numbers only — 0 if not available</i>"
        ),
        "ask_desc":    "📝 Describe yourself:\n<i>Minimum 20 characters</i>",
        "ask_contact": "📞 Your contact:\n<i>@telegram, phone or link</i>",
        "ask_photos":  f"📸 Send your photos (1–{MAX_PHOTOS})\nWhen done → press ✅ Finish",
        "preview":     "👁 <b>Preview before sending</b>\n━━━━━━━━━━━━━━━━━━\nCheck your information.",
        "sent":        "✅ <b>Sent for moderation!</b>\nWe'll reply within 24h.",
        "no_results":  "😔 No results yet.",
        "end":         "— End of results —",
        "contact_btn": "💬 Contact",
        "vip":         "⭐️ VIP",
        "tour_who":    "You are:",
        "tour_model":  "👗 I am a model — going on tour",
        "tour_host":   "🏨 I host models",
        "tour_from":   "🛫 Your departure city:\n<i>Example: Moscow, Kiev...</i>",
        "tour_date_from": "📅 Arrival date:\n<i>Example: 15.04</i>",
        "tour_date_to":   "📅 Departure date:\n<i>Example: 20.04</i>",
        "tour_notes":  "📝 Notes / conditions:\n<i>Rates, accommodation, etc.</i>",
        "ad_title":    "📝 Ad title:\n<i>Example: Relaxing massage Paris 8</i>",
        "ad_desc":     "📋 Description:\n<i>Describe your service</i>",
        "err_short":   "⚠️ Too short. Please try again.",
        "err_long":    "⚠️ Text too long. Maximum 1200 characters.",
        "err_age":     "⚠️ Invalid age. Enter a number between 18 and 65.",
        "err_height":  "⚠️ Invalid height. Between 140 and 200 cm.",
        "err_weight":  "⚠️ Invalid weight. Between 40 and 120 kg.",
        "err_contact": "⚠️ Invalid contact.\n• @username\n• +33 6 12 34 56 78\n• https://link",
        "err_photo":   "⚠️ Add at least one photo.",
        "err_langs":   "⚠️ Select at least one language.",
        "err_limit":   f"⚠️ Limit reached: {MAX_ACTIVE} active listings maximum.",
        "photos_only": "📸 Please send photos only.",
        "filter_all":  "🔎 View all",
        "filter_vip":  "⭐ VIP",
        "filter_new":  "🆕 Recent",
        "filter_in":   "🏠 Incall",
        "filter_out":  "🚗 Outcall",
        "filter_bl":   "👱 Blonde",
        "filter_br":   "🟤 Brunette",
        "filter_mod":  "👗 Models",
        "filter_host": "🏨 Hosts",
    },
}

# ─── STATES ───────────────────────────────────────────────────────────────────
(
    ST_LANG, ST_MENU,
    ST_PICK_REGION, ST_PICK_CITY, ST_CITY_MENU,
    ST_ADS_FILTER, ST_TOUR_FILTER,
    ST_M_REGION, ST_M_CITY,
    ST_M_NAME, ST_M_AGE, ST_M_ORIGIN, ST_M_HEIGHT, ST_M_WEIGHT,
    ST_M_MEAS, ST_M_HAIR, ST_M_EYES, ST_M_LANGS, ST_M_BODY,
    ST_M_BREAST, ST_M_SMOKER, ST_M_TATTOOS, ST_M_INCALL,
    ST_M_AVAIL, ST_M_PRICES, ST_M_DESC, ST_M_CONTACT,
    ST_M_PHOTOS, ST_M_PREVIEW,
    ST_T_REGION, ST_T_CITY, ST_T_WHO, ST_T_FROM,
    ST_T_DATEFROM, ST_T_DATETO, ST_T_NAME, ST_T_NOTES,
    ST_T_CONTACT, ST_T_PHOTOS, ST_T_PREVIEW,
    ST_A_REGION, ST_A_CITY, ST_A_TITLE, ST_A_DESC,
    ST_A_CONTACT, ST_A_PHOTOS, ST_A_PREVIEW,
    ST_ADMIN,
) = range(48)

# ─── DATABASE ─────────────────────────────────────────────────────────────────
class DB:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with closing(self._conn()) as c, c:
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'fr',
                username TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT DEFAULT 'pending', is_vip INTEGER DEFAULT 0,
                flow TEXT, user_id INTEGER, username TEXT,
                region TEXT, city TEXT, name TEXT, age TEXT, origin TEXT,
                height TEXT, weight TEXT, measurements TEXT,
                hair TEXT, eyes TEXT, languages TEXT,
                body_type TEXT, breast_type TEXT, smoker TEXT, tattoos TEXT,
                incall TEXT, availability TEXT, prices_json TEXT,
                description TEXT, contact TEXT,
                ad_title TEXT, ad_desc TEXT,
                tour_who TEXT, tour_from TEXT,
                tour_date_from TEXT, tour_date_to TEXT, tour_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS listing_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER, file_id TEXT, sort_order INTEGER DEFAULT 0)""")

    def upsert_user(self, uid: int, uname: str, lang: Optional[str] = None):
        with closing(self._conn()) as c, c:
            exists = c.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone()
            if exists:
                if lang:
                    c.execute("UPDATE users SET username=?,language=? WHERE user_id=?", (uname, lang, uid))
                else:
                    c.execute("UPDATE users SET username=? WHERE user_id=?", (uname, uid))
            else:
                c.execute("INSERT INTO users (user_id,username,language) VALUES (?,?,?)", (uid, uname, lang or "fr"))

    def get_lang(self, uid: Optional[int]) -> str:
        if not uid:
            return "fr"
        with closing(self._conn()) as c:
            row = c.execute("SELECT language FROM users WHERE user_id=?", (uid,)).fetchone()
            return row["language"] if row else "fr"

    def create_listing(self, data: Dict, photos: List[str]) -> int:
        expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
        with closing(self._conn()) as c, c:
            cur = c.execute("""INSERT INTO listings
                (flow,user_id,username,region,city,name,age,origin,height,weight,measurements,
                hair,eyes,languages,body_type,breast_type,smoker,tattoos,incall,availability,
                prices_json,description,contact,ad_title,ad_desc,
                tour_who,tour_from,tour_date_from,tour_date_to,tour_notes,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data.get("flow",""), data.get("user_id"), data.get("username",""),
                 data.get("region",""), data.get("city",""),
                 data.get("name",""), data.get("age",""), data.get("origin",""),
                 data.get("height",""), data.get("weight",""), data.get("measurements",""),
                 data.get("hair",""), data.get("eyes",""),
                 data.get("languages",""), data.get("body_type",""),
                 data.get("breast_type",""), data.get("smoker",""), data.get("tattoos",""),
                 data.get("incall",""), data.get("availability",""),
                 json.dumps(data.get("prices",{}), ensure_ascii=False),
                 data.get("description",""), data.get("contact",""),
                 data.get("ad_title",""), data.get("ad_desc",""),
                 data.get("tour_who",""), data.get("tour_from",""),
                 data.get("tour_date_from",""), data.get("tour_date_to",""),
                 data.get("tour_notes",""), expires))
            lid = int(cur.lastrowid)
            for i, fid in enumerate(photos[:MAX_PHOTOS]):
                c.execute("INSERT INTO listing_media (listing_id,file_id,sort_order) VALUES (?,?,?)", (lid,fid,i))
            return lid

    def get(self, lid: int):
        with closing(self._conn()) as c:
            return c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()

    def media(self, lid: int) -> List[str]:
        with closing(self._conn()) as c:
            return [r["file_id"] for r in c.execute(
                "SELECT file_id FROM listing_media WHERE listing_id=? ORDER BY sort_order,id", (lid,)).fetchall()]

    def update_status(self, lid: int, status: str, is_vip: Optional[bool] = None):
        with closing(self._conn()) as c, c:
            if is_vip is None:
                c.execute("UPDATE listings SET status=? WHERE id=?", (status, lid))
            else:
                c.execute("UPDATE listings SET status=?,is_vip=? WHERE id=?", (status, 1 if is_vip else 0, lid))

    def delete(self, lid: int):
        with closing(self._conn()) as c, c:
            c.execute("DELETE FROM listing_media WHERE listing_id=?", (lid,))
            c.execute("DELETE FROM listings WHERE id=?", (lid,))

    def pending(self):
        with closing(self._conn()) as c:
            return c.execute("SELECT * FROM listings WHERE status='pending' ORDER BY id DESC").fetchall()

    def browse(self, city: str, flow: str, vip=False, recent=False,
               tour_who=None, incall=None, hair=None, limit=20):
        q = "SELECT * FROM listings WHERE status='approved' AND city=? AND flow=? AND (expires_at IS NULL OR expires_at>?)"
        p: List[Any] = [city, flow, datetime.utcnow().isoformat()]
        if vip: q += " AND is_vip=1"
        if recent:
            q += " AND created_at>?"; p.append((datetime.utcnow()-timedelta(days=7)).isoformat())
        if tour_who: q += " AND tour_who=?"; p.append(tour_who)
        if incall: q += " AND incall LIKE ?"; p.append(f"%{incall}%")
        if hair: q += " AND hair LIKE ?"; p.append(f"%{hair}%")
        q += " ORDER BY is_vip DESC,created_at DESC LIMIT ?"; p.append(limit)
        with closing(self._conn()) as c:
            return c.execute(q, p).fetchall()

    def count_active(self, uid: int) -> int:
        with closing(self._conn()) as c:
            return int(c.execute(
                "SELECT COUNT(*) c FROM listings WHERE user_id=? AND status IN ('pending','approved')", (uid,)
            ).fetchone()["c"])

    def stats(self):
        with closing(self._conn()) as c:
            return {
                "pending":  int(c.execute("SELECT COUNT(*) c FROM listings WHERE status='pending'").fetchone()["c"]),
                "approved": int(c.execute("SELECT COUNT(*) c FROM listings WHERE status='approved'").fetchone()["c"]),
                "vip":      int(c.execute("SELECT COUNT(*) c FROM listings WHERE is_vip=1 AND status='approved'").fetchone()["c"]),
                "today":    int(c.execute("SELECT COUNT(*) c FROM listings WHERE created_at>?",
                                ((datetime.utcnow()-timedelta(hours=24)).isoformat(),)).fetchone()["c"]),
            }

    def cleanup(self):
        with closing(self._conn()) as c, c:
            ids = [r["id"] for r in c.execute(
                "SELECT id FROM listings WHERE expires_at IS NOT NULL AND expires_at<?",
                (datetime.utcnow().isoformat(),)).fetchall()]
            for i in ids:
                c.execute("DELETE FROM listing_media WHERE listing_id=?", (i,))
            c.execute("DELETE FROM listings WHERE expires_at IS NOT NULL AND expires_at<?",
                      (datetime.utcnow().isoformat(),))

db = DB(DB_PATH)

# ─── HELPERS ──────────────────────────────────────────────────────────────────
_spam: Dict[int, float] = {}

def safe_handler(fn):
    @wraps(fn)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE, *a, **kw):
        try:
            uid = update.effective_user.id if update.effective_user else 0
            now = time.time()
            if now - _spam.get(uid, 0) < 1.0:
                return
            _spam[uid] = now
            return await fn(update, ctx, *a, **kw)
        except Exception as e:
            logger.exception("Error in %s: %s", fn.__name__, e)
            try:
                await ctx.bot.send_message(ADMIN_ID, f"🚨 {fn.__name__}: {str(e)[:500]}")
            except Exception:
                pass
    return wrapper

def t(ctx: ContextTypes.DEFAULT_TYPE, key: str, **kw) -> str:
    lg = ctx.user_data.get("lang", "fr")
    txt = TX.get(lg, TX["fr"]).get(key, key)
    return txt.format(**kw) if kw else txt

def s(v) -> str:
    return html.escape(str(v or ""))

def get_uname(update: Update) -> str:
    u = update.effective_user
    if not u: return ""
    return u.username or " ".join(filter(None, [u.first_name, u.last_name]))

def valid_age(v): 
    try: return 18 <= int(v) <= 65
    except: return False

def valid_height(v):
    try: return 140 <= int(v) <= 200
    except: return False

def valid_weight(v):
    try: return 40 <= int(v) <= 120
    except: return False

def valid_contact(v: str) -> bool:
    v = v.strip()
    cleaned = re.sub(r'[\s\-\(\)]', '', v)
    return (
        (v.startswith("@") and len(v) > 2) or
        (cleaned.startswith('+') and len(cleaned) >= 10) or
        (cleaned.startswith('0') and len(cleaned) >= 9) or
        v.startswith("http")
    )

def contact_url(v: str) -> Optional[str]:
    v = v.strip()
    if v.startswith("http"): return v
    if v.startswith("@"): return f"https://t.me/{v[1:]}"
    digits = re.sub(r"[^\d+]", "", v)
    if digits: return f"https://wa.me/{digits.lstrip('+')}"
    return None

def parse_prices(text: str) -> Dict[str, str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    prices = {}
    for i, (key, _) in enumerate(PRICE_SLOTS):
        if i >= len(lines): break
        nums = re.findall(r"\d+", lines[i])
        prices[key] = nums[0] if nums else "0"
    return prices

def price_line(prices: Dict) -> str:
    parts = []
    for key, label in PRICE_SLOTS:
        v = prices.get(key)
        if v and v != "0":
            parts.append(f"{label}: {v}€")
    return " | ".join(parts) if parts else "—"

def dr(ctx: ContextTypes.DEFAULT_TYPE) -> Dict:
    if "draft" not in ctx.user_data:
        ctx.user_data["draft"] = {
            "flow":"", "region":"", "city":"", "name":"", "age":"",
            "origin":"", "height":"", "weight":"", "measurements":"",
            "hair":"", "eyes":"", "languages":"", "langs_list":[],
            "body_type":"", "breast_type":"", "smoker":"", "tattoos":"",
            "incall":"", "availability":"", "prices":{},
            "description":"", "contact":"", "photos":[],
            "ad_title":"", "ad_desc":"",
            "tour_who":"", "tour_from":"", "tour_date_from":"",
            "tour_date_to":"", "tour_notes":"",
        }
    return ctx.user_data["draft"]

def reset(ctx: ContextTypes.DEFAULT_TYPE):
    for k in ("draft", "browse_region", "browse_city", "ml_sel"):
        ctx.user_data.pop(k, None)

async def edit_or_reply(q, text: str, kb=None):
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except BadRequest:
        await q.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def send_album(bot, chat_id, photos: List[str], caption: str, kb=None):
    photos = photos[:MAX_PHOTOS]
    if not photos:
        await bot.send_message(chat_id, caption, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if len(photos) == 1:
        await bot.send_photo(chat_id, photos[0], caption=caption, parse_mode=ParseMode.HTML)
        if kb: await bot.send_message(chat_id, "·", reply_markup=kb)
        return
    media = [InputMediaPhoto(photos[0], caption=caption, parse_mode=ParseMode.HTML)] + \
            [InputMediaPhoto(p) for p in photos[1:]]
    await bot.send_media_group(chat_id, media)
    if kb: await bot.send_message(chat_id, "·", reply_markup=kb)

# ─── KEYBOARDS ────────────────────────────────────────────────────────────────
def kb_main(ctx, uid=None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(t(ctx,"annonces"), callback_data="go_browse")],
        [InlineKeyboardButton(t(ctx,"model_post"), callback_data="go_model"),
         InlineKeyboardButton(t(ctx,"tours"), callback_data="go_tour")],
        [InlineKeyboardButton(t(ctx,"site"), web_app=WebAppInfo(url=MINIAPP_URL))],
        [InlineKeyboardButton(t(ctx,"support"), url=SUPPORT_URL)],
        [InlineKeyboardButton(t(ctx,"agency"), url=VMODLS_URL)],
    ]
    if uid == ADMIN_ID:
        rows.append([InlineKeyboardButton(t(ctx,"admin"), callback_data="go_admin")])
    return InlineKeyboardMarkup(rows)

def kb_regions(ctx, prefix: str) -> InlineKeyboardMarkup:
    keys = list(REGIONS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i+j < len(keys):
                row.append(InlineKeyboardButton(keys[i+j], callback_data=f"{prefix}_r_{i+j}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx,"menu"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def kb_cities(ctx, region: str, prefix: str) -> InlineKeyboardMarkup:
    cities = REGIONS.get(region, [])
    rows, row = [], []
    for i, city in enumerate(cities):
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_c_{i}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx,"back"), callback_data=f"{prefix}_back")])
    return InlineKeyboardMarkup(rows)

def kb_options(options, prefix: str, ctx) -> InlineKeyboardMarkup:
    rows, row = [], []
    for i, opt in enumerate(options):
        row.append(InlineKeyboardButton(opt[0], callback_data=f"{prefix}_{i}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx,"cancel"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def kb_langs(ctx) -> InlineKeyboardMarkup:
    rows, row = [], []
    sel = ctx.user_data.get("ml_sel", [])
    for i, opt in enumerate(LANG_OPTIONS):
        mark = "✅ " if i in sel else ""
        row.append(InlineKeyboardButton(mark+opt[0], callback_data=f"ml_{i}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([
        InlineKeyboardButton(t(ctx,"confirm_langs"), callback_data="ml_done"),
        InlineKeyboardButton(t(ctx,"cancel"), callback_data="go_menu"),
    ])
    return InlineKeyboardMarkup(rows)

def kb_city_menu(ctx) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx,"annonces"), callback_data="city_ads"),
         InlineKeyboardButton(t(ctx,"tours"), callback_data="city_tours")],
        [InlineKeyboardButton(t(ctx,"tour_search"), url=SUPPORT_URL)],
        [InlineKeyboardButton(t(ctx,"back"), callback_data="go_browse")],
    ])

def kb_ads_filter(ctx) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx,"filter_all"), callback_data="af_all")],
        [InlineKeyboardButton(t(ctx,"filter_vip"), callback_data="af_vip"),
         InlineKeyboardButton(t(ctx,"filter_new"), callback_data="af_new")],
        [InlineKeyboardButton(t(ctx,"filter_in"), callback_data="af_in"),
         InlineKeyboardButton(t(ctx,"filter_out"), callback_data="af_out")],
        [InlineKeyboardButton(t(ctx,"filter_bl"), callback_data="af_bl"),
         InlineKeyboardButton(t(ctx,"filter_br"), callback_data="af_br")],
        [InlineKeyboardButton(t(ctx,"back"), callback_data="back_city")],
    ])

def kb_tours_filter(ctx) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx,"filter_all"), callback_data="tf_all")],
        [InlineKeyboardButton(t(ctx,"filter_mod"), callback_data="tf_mod"),
         InlineKeyboardButton(t(ctx,"filter_host"), callback_data="tf_host")],
        [InlineKeyboardButton(t(ctx,"filter_vip"), callback_data="tf_vip"),
         InlineKeyboardButton(t(ctx,"filter_new"), callback_data="tf_new")],
        [InlineKeyboardButton(t(ctx,"back"), callback_data="back_city")],
    ])

def kb_cancel(ctx) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(ctx,"cancel"), callback_data="go_menu")]])

def kb_skip_cancel(ctx) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(ctx,"skip"), callback_data="skip_notes"),
        InlineKeyboardButton(t(ctx,"cancel"), callback_data="go_menu"),
    ]])

def kb_photos(ctx) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(ctx,"done"), callback_data="photos_done"),
        InlineKeyboardButton(t(ctx,"cancel"), callback_data="go_menu"),
    ]])

def kb_preview(ctx) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(ctx,"send"), callback_data="submit"),
        InlineKeyboardButton(t(ctx,"cancel"), callback_data="go_menu"),
    ]])

def kb_listing(ctx, contact: str) -> InlineKeyboardMarkup:
    rows = []
    url = contact_url(contact)
    if url: rows.append([InlineKeyboardButton(t(ctx,"contact_btn"), url=url)])
    rows.append([InlineKeyboardButton(t(ctx,"support"), url=SUPPORT_URL)])
    return InlineKeyboardMarkup(rows)

def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Заявки", callback_data="adm_pending"),
         InlineKeyboardButton("🗂 Активные", callback_data="adm_active")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🏠 Меню", callback_data="go_menu")],
    ])

def kb_mod(lid: int, contact: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_ok_{lid}"),
         InlineKeyboardButton("⭐ VIP", callback_data=f"adm_vip_{lid}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_rej_{lid}"),
         InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{lid}")],
    ]
    url = contact_url(contact)
    if url: rows.append([InlineKeyboardButton("💬 Связаться", url=url)])
    return InlineKeyboardMarkup(rows)

# ─── FORMATTERS ───────────────────────────────────────────────────────────────
def fmt_listing(row, lang: str) -> str:
    vip = "⭐️ VIP | " if row["is_vip"] else ""
    flow = row["flow"]
    prices = json.loads(row["prices_json"] or "{}")
    if flow == "annonce":
        return f"{vip}<b>{s(row['ad_title'])}</b>\n━━━━━━━━━━━━━━━━━━\n📍 {s(row['city'])}\n📋 {s(row['ad_desc'])}\n📞 {s(row['contact'])}"
    if flow == "tour":
        role = ("👗 Modèle" if lang=="fr" else "👗 Model") if row["tour_who"]=="model" else ("🏨 Hôte" if lang=="fr" else "🏨 Host")
        return (f"{vip}✈️ <b>Tour</b> — {s(role)}\n━━━━━━━━━━━━━━━━━━\n"
                f"📍 {s(row['city'])} • 👤 {s(row['name'])}\n"
                f"🛫 {s(row['tour_from'])}\n📅 {s(row['tour_date_from'])} → {s(row['tour_date_to'])}\n"
                f"📝 {s(row['tour_notes'])}\n📞 {s(row['contact'])}")
    return (f"{vip}👗 <b>{s(row['name'])}</b>, {s(row['age'])}\n━━━━━━━━━━━━━━━━━━\n"
            f"📍 {s(row['city'])} • 🌍 {s(row['origin'])}\n"
            f"📏 {s(row['height'])} cm • ⚖️ {s(row['weight'])} kg • 📐 {s(row['measurements'])}\n"
            f"💇 {s(row['hair'])} • 👁 {s(row['eyes'])}\n"
            f"✨ {s(row['body_type'])} • 💎 {s(row['breast_type'])}\n"
            f"🗣 {s(row['languages'])}\n🏠 {s(row['incall'])} • 🕐 {s(row['availability'])}\n"
            f"💶 {s(price_line(prices))}\n\n📝 {s(row['description'])}\n📞 {s(row['contact'])}")

def fmt_draft(d: Dict, lang: str) -> str:
    flow = d.get("flow","")
    prices = d.get("prices",{})
    if flow == "annonce":
        return (f"<b>{s(d['ad_title'])}</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"📍 {s(d['city'])}\n📋 {s(d['ad_desc'])}\n📞 {s(d['contact'])}")
    if flow == "tour":
        role = ("👗 Modèle" if lang=="fr" else "👗 Model") if d.get("tour_who")=="model" else "🏨 Hôte"
        return (f"✈️ <b>Tour</b> — {s(role)}\n━━━━━━━━━━━━━━━━━━\n"
                f"📍 {s(d['city'])} • 👤 {s(d['name'])}\n🛫 {s(d['tour_from'])}\n"
                f"📅 {s(d['tour_date_from'])} → {s(d['tour_date_to'])}\n"
                f"📝 {s(d['tour_notes'])}\n📞 {s(d['contact'])}")
    return (f"👗 <b>{s(d['name'])}</b>, {s(d['age'])}\n━━━━━━━━━━━━━━━━━━\n"
            f"📍 {s(d['city'])} • 🌍 {s(d['origin'])}\n"
            f"📏 {s(d['height'])} cm • ⚖️ {s(d['weight'])} kg • 📐 {s(d['measurements'])}\n"
            f"💇 {s(d['hair'])} • 👁 {s(d['eyes'])}\n"
            f"✨ {s(d['body_type'])} • 💎 {s(d['breast_type'])}\n"
            f"🗣 {s(d['languages'])}\n🏠 {s(d['incall'])} • 🕐 {s(d['availability'])}\n"
            f"💶 {s(price_line(prices))}\n\n📝 {s(d['description'])}\n📞 {s(d['contact'])}")

def fmt_admin(row) -> str:
    prices = json.loads(row["prices_json"] or "{}")
    return (f"🔔 <b>Новая заявка #{row['id']}</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"Тип: <b>{s(row['flow'])}</b>\n"
            f"👤 {s(row['name'] or row['ad_title'])} | {s(row['age'])}\n"
            f"📍 {s(row['city'])} ({s(row['region'])})\n"
            f"🌍 {s(row['origin'])}\n"
            f"📏 {s(row['height'])} cm | ⚖️ {s(row['weight'])} kg\n"
            f"📐 {s(row['measurements'])}\n"
            f"💇 {s(row['hair'])} | 👁 {s(row['eyes'])}\n"
            f"✨ {s(row['body_type'])} | 💎 {s(row['breast_type'])}\n"
            f"🚬 {s(row['smoker'])} | 🖋 {s(row['tattoos'])}\n"
            f"🗣 {s(row['languages'])}\n"
            f"🏠 {s(row['incall'])} | 🕐 {s(row['availability'])}\n"
            f"💶 {s(price_line(prices))}\n"
            f"📝 {s(row['description'])}\n"
            f"📞 {s(row['contact'])}\n"
            f"✈️ {s(row['tour_who'])} | 🛫 {s(row['tour_from'])}\n"
            f"📅 {s(row['tour_date_from'])} → {s(row['tour_date_to'])}\n"
            f"📋 {s(row['ad_title'])}: {s(row['ad_desc'])}\n"
            f"User: @{s(row['username'])} | ID: <code>{s(row['user_id'])}</code>")

# ─── START / MENU ─────────────────────────────────────────────────────────────
@safe_handler
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reset(ctx)
    u = update.effective_user
    if u: db.upsert_user(u.id, get_uname(update))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(TX["fr"]["site"], web_app=WebAppInfo(url=MINIAPP_URL))],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ])
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg:
        await msg.reply_text(TX["fr"]["greeting"], parse_mode=ParseMode.HTML, reply_markup=kb)
    return ST_LANG

@safe_handler
async def cb_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lg = q.data.replace("lang_","")
    ctx.user_data["lang"] = lg
    db.upsert_user(q.from_user.id, get_uname(update), lg)
    await edit_or_reply(q, TX[lg]["welcome"], kb_main(ctx, q.from_user.id))
    return ST_MENU

@safe_handler
async def show_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reset(ctx)
    u = update.effective_user
    if u:
        if "lang" not in ctx.user_data:
            ctx.user_data["lang"] = db.get_lang(u.id)
        db.upsert_user(u.id, get_uname(update))
    kb = kb_main(ctx, u.id if u else None)
    if update.callback_query:
        await update.callback_query.answer()
        await edit_or_reply(update.callback_query, t(ctx,"welcome"), kb)
    elif update.message:
        await update.message.reply_text(t(ctx,"welcome"), parse_mode=ParseMode.HTML, reply_markup=kb)
    return ST_MENU

# ─── BROWSE ───────────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_browse(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await edit_or_reply(q, t(ctx,"choose_region"), kb_regions(ctx,"br"))
    return ST_PICK_REGION

@safe_handler
async def cb_br_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    idx = int(q.data.replace("br_r_",""))
    keys = list(REGIONS.keys())
    if idx >= len(keys): return await show_menu(update, ctx)
    region = keys[idx]
    ctx.user_data["browse_region"] = region
    await edit_or_reply(q, f"{s(region)}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, region, "br"))
    return ST_PICK_CITY

@safe_handler
async def cb_br_city(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "br_back":
        return await cb_go_browse(update, ctx)
    idx = int(q.data.replace("br_c_",""))
    region = ctx.user_data.get("browse_region","")
    cities = REGIONS.get(region,[])
    if idx >= len(cities): return await cb_go_browse(update, ctx)
    city = cities[idx]
    ctx.user_data["browse_city"] = city
    await edit_or_reply(q, t(ctx,"what_next",city=city), kb_city_menu(ctx))
    return ST_CITY_MENU

@safe_handler
async def cb_city_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    city = ctx.user_data.get("browse_city","")
    if q.data == "back_city":
        await edit_or_reply(q, t(ctx,"what_next",city=city), kb_city_menu(ctx))
        return ST_CITY_MENU
    if q.data == "city_ads":
        await edit_or_reply(q, f"📢 <b>{s(city)}</b>", kb_ads_filter(ctx))
        return ST_ADS_FILTER
    if q.data == "city_tours":
        await edit_or_reply(q, f"✈️ <b>{s(city)}</b>", kb_tours_filter(ctx))
        return ST_TOUR_FILTER
    return ST_CITY_MENU

async def _show_results(update: Update, ctx: ContextTypes.DEFAULT_TYPE, flow: str, **kw):
    q = update.callback_query; await q.answer()
    city = ctx.user_data.get("browse_city","")
    rows = db.browse(city, flow, **kw)
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(ctx,"back"), callback_data="back_city")]])
    if not rows:
        await edit_or_reply(q, t(ctx,"no_results"), back_kb)
        return ST_MENU
    await edit_or_reply(q, f"📍 <b>{s(city)}</b> — {len(rows)} résultat(s)", back_kb)
    for row in rows:
        await send_album(ctx.bot, q.message.chat_id,
                         db.media(row["id"]),
                         fmt_listing(row, ctx.user_data.get("lang","fr")),
                         kb_listing(ctx, row["contact"]))
    await q.message.reply_text(t(ctx,"end"), parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t(ctx,"back"), callback_data="back_city")],
            [InlineKeyboardButton(t(ctx,"menu"), callback_data="go_menu")],
        ]))
    return ST_MENU

@safe_handler
async def cb_ads_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    m = {"af_all":{},"af_vip":{"vip":True},"af_new":{"recent":True},
         "af_in":{"incall":"Incall"},"af_out":{"incall":"Outcall"},
         "af_bl":{"hair":"Blonde"},"af_br":{"hair":"Brune"}}
    if q.data in m: return await _show_results(update, ctx, "annonce", **m[q.data])
    return await cb_city_menu(update, ctx)

@safe_handler
async def cb_tour_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    m = {"tf_all":{},"tf_vip":{"vip":True},"tf_new":{"recent":True},
         "tf_mod":{"tour_who":"model"},"tf_host":{"tour_who":"host"}}
    if q.data in m: return await _show_results(update, ctx, "tour", **m[q.data])
    return await cb_city_menu(update, ctx)

# ─── MODEL FLOW ───────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_model(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    reset(ctx); dr(ctx)["flow"] = "model"
    await edit_or_reply(q, t(ctx,"choose_region"), kb_regions(ctx,"mr"))
    return ST_M_REGION

@safe_handler
async def cb_mr_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    idx = int(q.data.replace("mr_r_",""))
    keys = list(REGIONS.keys())
    if idx >= len(keys): return await show_menu(update, ctx)
    dr(ctx)["region"] = keys[idx]
    await edit_or_reply(q, f"{s(keys[idx])}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, keys[idx], "mr"))
    return ST_M_CITY

@safe_handler
async def cb_mr_city(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "mr_back": return await cb_go_model(update, ctx)
    idx = int(q.data.replace("mr_c_",""))
    region = dr(ctx)["region"]
    cities = REGIONS.get(region,[])
    if idx >= len(cities): return await cb_go_model(update, ctx)
    dr(ctx)["city"] = cities[idx]
    await edit_or_reply(q, f"✅ {s(cities[idx])}")
    await q.message.reply_text(t(ctx,"ask_name"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_NAME

@safe_handler
async def txt_m_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if len(v) < 2: await update.message.reply_text(t(ctx,"err_short")); return ST_M_NAME
    if len(v) > 80: await update.message.reply_text(t(ctx,"err_long")); return ST_M_NAME
    dr(ctx)["name"] = v
    await update.message.reply_text(t(ctx,"ask_age"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_AGE

@safe_handler
async def txt_m_age(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not valid_age(v): await update.message.reply_text(t(ctx,"err_age")); return ST_M_AGE
    dr(ctx)["age"] = v
    await update.message.reply_text(t(ctx,"ask_origin"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_ORIGIN

@safe_handler
async def txt_m_origin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if len(v) < 2: await update.message.reply_text(t(ctx,"err_short")); return ST_M_ORIGIN
    dr(ctx)["origin"] = v
    await update.message.reply_text(t(ctx,"ask_height"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_HEIGHT

@safe_handler
async def txt_m_height(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not valid_height(v): await update.message.reply_text(t(ctx,"err_height")); return ST_M_HEIGHT
    dr(ctx)["height"] = v
    await update.message.reply_text(t(ctx,"ask_weight"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_WEIGHT

@safe_handler
async def txt_m_weight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not valid_weight(v): await update.message.reply_text(t(ctx,"err_weight")); return ST_M_WEIGHT
    dr(ctx)["weight"] = v
    await update.message.reply_text(t(ctx,"ask_measurements"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_MEAS

@safe_handler
async def txt_m_meas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if len(v) < 3: await update.message.reply_text(t(ctx,"err_short")); return ST_M_MEAS
    dr(ctx)["measurements"] = v
    await update.message.reply_text(t(ctx,"ask_hair"), parse_mode=ParseMode.HTML, reply_markup=kb_options(HAIR_OPTIONS,"hair",ctx))
    return ST_M_HAIR

@safe_handler
async def cb_m_hair(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["hair"] = HAIR_OPTIONS[int(q.data.replace("hair_",""))][1]
    await edit_or_reply(q, t(ctx,"ask_eyes"), kb_options(EYE_OPTIONS,"eye",ctx))
    return ST_M_EYES

@safe_handler
async def cb_m_eyes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["eyes"] = EYE_OPTIONS[int(q.data.replace("eye_",""))][1]
    ctx.user_data["ml_sel"] = []
    await edit_or_reply(q, t(ctx,"ask_langs"), kb_langs(ctx))
    return ST_M_LANGS

@safe_handler
async def cb_m_langs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sel = ctx.user_data.get("ml_sel", [])
    if q.data == "ml_done":
        if not sel:
            await q.answer(t(ctx,"err_langs"), show_alert=True); return ST_M_LANGS
        langs = ", ".join(LANG_OPTIONS[i][1] for i in sel)
        dr(ctx)["languages"] = langs
        await edit_or_reply(q, t(ctx,"ask_body"), kb_options(BODY_OPTIONS,"body",ctx))
        return ST_M_BODY
    idx = int(q.data.replace("ml_",""))
    if idx in sel: sel.remove(idx)
    else: sel.append(idx)
    ctx.user_data["ml_sel"] = sel
    # Обновляем клавиатуру чтобы показать выбранные
    await q.edit_reply_markup(kb_langs(ctx))
    return ST_M_LANGS

@safe_handler
async def cb_m_body(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["body_type"] = BODY_OPTIONS[int(q.data.replace("body_",""))][1]
    await edit_or_reply(q, t(ctx,"ask_breast"), kb_options(BREAST_OPTIONS,"breast",ctx))
    return ST_M_BREAST

@safe_handler
async def cb_m_breast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["breast_type"] = BREAST_OPTIONS[int(q.data.replace("breast_",""))][1]
    await edit_or_reply(q, t(ctx,"ask_smoker"), kb_options(YESNO_OPTIONS,"smoker",ctx))
    return ST_M_SMOKER

@safe_handler
async def cb_m_smoker(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["smoker"] = YESNO_OPTIONS[int(q.data.replace("smoker_",""))][1]
    await edit_or_reply(q, t(ctx,"ask_tattoos"), kb_options(YESNO_OPTIONS,"tattoo",ctx))
    return ST_M_TATTOOS

@safe_handler
async def cb_m_tattoos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["tattoos"] = YESNO_OPTIONS[int(q.data.replace("tattoo_",""))][1]
    await edit_or_reply(q, t(ctx,"ask_incall"), kb_options(INCALL_OPTIONS,"incall",ctx))
    return ST_M_INCALL

@safe_handler
async def cb_m_incall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["incall"] = INCALL_OPTIONS[int(q.data.replace("incall_",""))][1]
    await edit_or_reply(q, t(ctx,"ask_avail"), kb_options(AVAILABILITY_OPTIONS,"avail",ctx))
    return ST_M_AVAIL

@safe_handler
async def cb_m_avail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["availability"] = AVAILABILITY_OPTIONS[int(q.data.replace("avail_",""))][1]
    await q.message.reply_text(t(ctx,"ask_prices"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_PRICES

@safe_handler
async def txt_m_prices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    prices = parse_prices(update.message.text)
    dr(ctx)["prices"] = prices
    summary = price_line(prices)
    await update.message.reply_text(
        f"✅ {s(summary)}\n\n{t(ctx,'ask_desc')}",
        parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_DESC

@safe_handler
async def txt_m_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if len(v) < 20: await update.message.reply_text(t(ctx,"err_short")); return ST_M_DESC
    if len(v) > 1200: await update.message.reply_text(t(ctx,"err_long")); return ST_M_DESC
    dr(ctx)["description"] = v
    await update.message.reply_text(t(ctx,"ask_contact"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_CONTACT

@safe_handler
async def txt_m_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not valid_contact(v): await update.message.reply_text(t(ctx,"err_contact")); return ST_M_CONTACT
    dr(ctx)["contact"] = v
    await update.message.reply_text(t(ctx,"ask_photos"), parse_mode=ParseMode.HTML, reply_markup=kb_photos(ctx))
    return ST_M_PHOTOS

# ─── TOUR FLOW ────────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_tour(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    reset(ctx); dr(ctx)["flow"] = "tour"
    await edit_or_reply(q, t(ctx,"choose_region"), kb_regions(ctx,"tr"))
    return ST_T_REGION

@safe_handler
async def cb_tr_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    idx = int(q.data.replace("tr_r_",""))
    keys = list(REGIONS.keys())
    if idx >= len(keys): return await show_menu(update, ctx)
    dr(ctx)["region"] = keys[idx]
    await edit_or_reply(q, f"{s(keys[idx])}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, keys[idx], "tr"))
    return ST_T_CITY

@safe_handler
async def cb_tr_city(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "tr_back": return await cb_go_tour(update, ctx)
    idx = int(q.data.replace("tr_c_",""))
    region = dr(ctx)["region"]
    cities = REGIONS.get(region,[])
    if idx >= len(cities): return await cb_go_tour(update, ctx)
    dr(ctx)["city"] = cities[idx]
    lg = ctx.user_data.get("lang","fr")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx,"tour_model"), callback_data="twho_model")],
        [InlineKeyboardButton(t(ctx,"tour_host"),  callback_data="twho_host")],
        [InlineKeyboardButton(t(ctx,"cancel"), callback_data="go_menu")],
    ])
    await edit_or_reply(q, t(ctx,"tour_who"), kb)
    return ST_T_WHO

@safe_handler
async def cb_t_who(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["tour_who"] = q.data.replace("twho_","")
    await q.message.reply_text(t(ctx,"tour_from"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_T_FROM

@safe_handler
async def txt_t_from(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dr(ctx)["tour_from"] = update.message.text.strip()
    await update.message.reply_text(t(ctx,"tour_date_from"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_T_DATEFROM

@safe_handler
async def txt_t_datefrom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dr(ctx)["tour_date_from"] = update.message.text.strip()
    await update.message.reply_text(t(ctx,"tour_date_to"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_T_DATETO

@safe_handler
async def txt_t_dateto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dr(ctx)["tour_date_to"] = update.message.text.strip()
    await update.message.reply_text(t(ctx,"ask_name"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_T_NAME

@safe_handler
async def txt_t_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dr(ctx)["name"] = update.message.text.strip()
    await update.message.reply_text(t(ctx,"tour_notes"), parse_mode=ParseMode.HTML, reply_markup=kb_skip_cancel(ctx))
    return ST_T_NOTES

@safe_handler
async def txt_t_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dr(ctx)["tour_notes"] = update.message.text.strip()
    await update.message.reply_text(t(ctx,"ask_contact"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_T_CONTACT

@safe_handler
async def cb_skip_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["tour_notes"] = "—"
    await q.message.reply_text(t(ctx,"ask_contact"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_T_CONTACT

@safe_handler
async def txt_t_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not valid_contact(v): await update.message.reply_text(t(ctx,"err_contact")); return ST_T_CONTACT
    dr(ctx)["contact"] = v
    await update.message.reply_text(t(ctx,"ask_photos"), parse_mode=ParseMode.HTML, reply_markup=kb_photos(ctx))
    return ST_T_PHOTOS

# ─── AD FLOW ──────────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_ad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    reset(ctx); dr(ctx)["flow"] = "annonce"
    await edit_or_reply(q, t(ctx,"choose_region"), kb_regions(ctx,"ar"))
    return ST_A_REGION

@safe_handler
async def cb_ar_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    idx = int(q.data.replace("ar_r_",""))
    keys = list(REGIONS.keys())
    if idx >= len(keys): return await show_menu(update, ctx)
    dr(ctx)["region"] = keys[idx]
    await edit_or_reply(q, f"{s(keys[idx])}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, keys[idx], "ar"))
    return ST_A_CITY

@safe_handler
async def cb_ar_city(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "ar_back": return await cb_go_ad(update, ctx)
    idx = int(q.data.replace("ar_c_",""))
    region = dr(ctx)["region"]
    cities = REGIONS.get(region,[])
    if idx >= len(cities): return await cb_go_ad(update, ctx)
    dr(ctx)["city"] = cities[idx]
    await q.message.reply_text(t(ctx,"ad_title"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_A_TITLE

@safe_handler
async def txt_a_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if len(v) < 3: await update.message.reply_text(t(ctx,"err_short")); return ST_A_TITLE
    dr(ctx)["ad_title"] = v
    await update.message.reply_text(t(ctx,"ad_desc"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_A_DESC

@safe_handler
async def txt_a_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if len(v) < 5: await update.message.reply_text(t(ctx,"err_short")); return ST_A_DESC
    dr(ctx)["ad_desc"] = v
    await update.message.reply_text(t(ctx,"ask_contact"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_A_CONTACT

@safe_handler
async def txt_a_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not valid_contact(v): await update.message.reply_text(t(ctx,"err_contact")); return ST_A_CONTACT
    dr(ctx)["contact"] = v
    await update.message.reply_text(t(ctx,"ask_photos"), parse_mode=ParseMode.HTML, reply_markup=kb_photos(ctx))
    return ST_A_PHOTOS

# ─── PHOTOS / PREVIEW / SUBMIT ────────────────────────────────────────────────
@safe_handler
async def receive_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photos = dr(ctx).get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"⚠️ Max {MAX_PHOTOS} photos.")
        return
    photos.append(update.message.photo[-1].file_id)
    dr(ctx)["photos"] = photos
    await update.message.reply_text(f"📸 {len(photos)}/{MAX_PHOTOS}", reply_markup=kb_photos(ctx))

@safe_handler
async def photos_fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(ctx,"photos_only"))

@safe_handler
async def cb_photos_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    d = dr(ctx)
    if not d.get("photos"):
        await q.answer(t(ctx,"err_photo"), show_alert=True); return
    lang = ctx.user_data.get("lang","fr")
    preview_text = f"{t(ctx,'preview')}\n\n{fmt_draft(d, lang)}"
    try:
        await edit_or_reply(q, preview_text, kb_preview(ctx))
    except Exception:
        await q.message.reply_text(preview_text, parse_mode=ParseMode.HTML, reply_markup=kb_preview(ctx))
    flow = d.get("flow","")
    if flow == "model": return ST_M_PREVIEW
    if flow == "tour":  return ST_T_PREVIEW
    return ST_A_PREVIEW

@safe_handler
async def cb_submit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    d = dr(ctx)
    u = update.effective_user
    if not u: return await show_menu(update, ctx)
    if db.count_active(u.id) >= MAX_ACTIVE:
        await q.answer(t(ctx,"err_limit"), show_alert=True); return
    d["user_id"] = u.id
    d["username"] = get_uname(update)
    lid = db.create_listing(d, d.get("photos",[]))
    row = db.get(lid)
    if row:
        await send_album(ctx.bot, ADMIN_ID, db.media(lid), fmt_admin(row), kb_mod(lid, row["contact"]))
    await edit_or_reply(q, t(ctx,"sent"), kb_main(ctx, u.id))
    reset(ctx)
    return ST_MENU

# ─── ADMIN ────────────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔️ Доступ запрещён", show_alert=True); return ST_MENU
    stats = db.stats()
    text = (f"🔐 <b>Панель администратора</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"⏳ На модерации: <b>{stats['pending']}</b>\n"
            f"✅ Активных: <b>{stats['approved']}</b>\n"
            f"⭐ VIP: <b>{stats['vip']}</b>\n"
            f"🆕 За 24ч: <b>{stats['today']}</b>")
    await edit_or_reply(q, text, kb_admin())
    return ST_ADMIN

@safe_handler
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Доступ запрещён."); return ST_MENU
    stats = db.stats()
    text = (f"🔐 <b>Панель администратора</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"⏳ На модерации: <b>{stats['pending']}</b>\n"
            f"✅ Активных: <b>{stats['approved']}</b>\n"
            f"⭐ VIP: <b>{stats['vip']}</b>\n"
            f"🆕 За 24ч: <b>{stats['today']}</b>")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_admin())
    return ST_ADMIN

@safe_handler
async def cb_admin_actions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔️", show_alert=True); return ST_ADMIN

    if q.data == "adm_stats":
        return await cb_go_admin(update, ctx)

    if q.data == "adm_pending":
        rows = db.pending()
        if not rows:
            await edit_or_reply(q, "✅ Нет заявок на модерации.", kb_admin()); return ST_ADMIN
        lines = ["📋 <b>Заявки на модерации</b>\n"]
        for r in rows[:25]:
            title = r["name"] or r["ad_title"] or "—"
            lines.append(f"#{r['id']} • {s(r['flow'])} • {s(r['city'])} • {s(title)}")
        await edit_or_reply(q, "\n".join(lines), kb_admin())
        return ST_ADMIN

    if q.data == "adm_active":
        rows = db.browse("", "model") + db.browse("", "tour") + db.browse("", "annonce")
        # Получаем все активные из БД напрямую
        with closing(db._conn()) as c:
            rows = c.execute(
                "SELECT * FROM listings WHERE status='approved' ORDER BY is_vip DESC, created_at DESC LIMIT 30"
            ).fetchall()
        if not rows:
            await edit_or_reply(q, "Нет активных публикаций.", kb_admin()); return ST_ADMIN
        lines = ["🗂 <b>Активные публикации</b>\n"]
        for r in rows:
            vip = "⭐ " if r["is_vip"] else ""
            title = r["name"] or r["ad_title"] or "—"
            lines.append(f"#{r['id']} • {vip}{s(r['flow'])} • {s(r['city'])} • {s(title)}")
        await edit_or_reply(q, "\n".join(lines), kb_admin())
        return ST_ADMIN

    return ST_ADMIN

@safe_handler
async def cb_moderation(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔️", show_alert=True); return

    parts = q.data.split("_")  # adm_ok_123 → ['adm','ok','123']
    if len(parts) < 3: return
    action = parts[1]
    lid = int(parts[2])
    row = db.get(lid)
    if not row:
        await edit_or_reply(q, "⚠️ Заявка не найдена."); return

    if action == "rej":
        db.update_status(lid, "rejected")
        await edit_or_reply(q, f"❌ Заявка #{lid} отклонена.")
        if row["user_id"]:
            try:
                lg = db.get_lang(row["user_id"])
                msg = "❌ Votre publication a été refusée." if lg=="fr" else "❌ Your publication was rejected."
                await ctx.bot.send_message(row["user_id"], msg)
            except Exception: pass
        return

    if action == "del":
        db.delete(lid)
        await edit_or_reply(q, f"🗑 Заявка #{lid} удалена.")
        return

    is_vip = action == "vip"
    db.update_status(lid, "approved", is_vip=is_vip)
    fresh = db.get(lid)
    if fresh:
        lg = db.get_lang(fresh["user_id"]) if fresh["user_id"] else "fr"
        await send_album(ctx.bot, CHANNEL_ID, db.media(lid), fmt_listing(fresh, lg))
    await edit_or_reply(q, f"✅ Заявка #{lid} опубликована{' как VIP ⭐' if is_vip else ''}.")
    if row["user_id"]:
        try:
            lg = db.get_lang(row["user_id"])
            msg = "✅ Votre publication est en ligne !" if lg=="fr" else "✅ Your publication is live!"
            if is_vip: msg += "\n⭐ VIP"
            await ctx.bot.send_message(row["user_id"], msg)
        except Exception: pass

# ─── COMMON ───────────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reset(ctx)
    return await show_menu(update, ctx)

@safe_handler
async def unknown_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Utilisez /start")

async def cleanup_job(ctx: ContextTypes.DEFAULT_TYPE):
    db.cleanup()

async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    exc = ctx.error
    if isinstance(exc, RetryAfter):
        await asyncio.sleep(float(exc.retry_after)); return
    if isinstance(exc, (TimedOut, NetworkError)):
        logger.warning("Transient: %s", exc); return
    logger.exception("Unhandled: %s", exc)
    try: await ctx.bot.send_message(ADMIN_ID, f"🚨 BOT ERROR:\n{str(exc)[:800]}")
    except Exception: pass

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # Общий обработчик для фото и preview во всех flow
    photo_h = MessageHandler(filters.PHOTO, receive_photo)
    photo_fb = MessageHandler(filters.TEXT & ~filters.COMMAND, photos_fallback)
    photos_done_h = CallbackQueryHandler(cb_photos_done, pattern=r"^photos_done$")
    cancel_h = CallbackQueryHandler(cb_go_menu, pattern=r"^go_menu$")
    submit_h = CallbackQueryHandler(cb_submit, pattern=r"^submit$")

    photos_state = [photo_h, photo_fb, photos_done_h, cancel_h]
    preview_state = [submit_h, cancel_h]

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(cb_go_menu, pattern=r"^go_menu$"),
        ],
        states={
            ST_LANG: [CallbackQueryHandler(cb_lang, pattern=r"^lang_(fr|en)$")],

            ST_MENU: [
                CallbackQueryHandler(cb_go_browse, pattern=r"^go_browse$"),
                CallbackQueryHandler(cb_go_model,  pattern=r"^go_model$"),
                CallbackQueryHandler(cb_go_tour,   pattern=r"^go_tour$"),
                CallbackQueryHandler(cb_go_ad,     pattern=r"^go_ad$"),
                CallbackQueryHandler(cb_go_admin,  pattern=r"^go_admin$"),
            ],

            # Browse
            ST_PICK_REGION: [CallbackQueryHandler(cb_br_region, pattern=r"^br_r_\d+$"), cancel_h],
            ST_PICK_CITY:   [CallbackQueryHandler(cb_br_city, pattern=r"^(br_c_\d+|br_back)$"), cancel_h],
            ST_CITY_MENU:   [CallbackQueryHandler(cb_city_menu, pattern=r"^(city_ads|city_tours|back_city|go_browse)$"), cancel_h],
            ST_ADS_FILTER:  [CallbackQueryHandler(cb_ads_filter, pattern=r"^(af_all|af_vip|af_new|af_in|af_out|af_bl|af_br|back_city)$"), cancel_h],
            ST_TOUR_FILTER: [CallbackQueryHandler(cb_tour_filter, pattern=r"^(tf_all|tf_vip|tf_new|tf_mod|tf_host|back_city)$"), cancel_h],

            # Model flow
            ST_M_REGION:  [CallbackQueryHandler(cb_mr_region, pattern=r"^mr_r_\d+$"), cancel_h],
            ST_M_CITY:    [CallbackQueryHandler(cb_mr_city, pattern=r"^(mr_c_\d+|mr_back)$"), cancel_h],
            ST_M_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_name), cancel_h],
            ST_M_AGE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_age), cancel_h],
            ST_M_ORIGIN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_origin), cancel_h],
            ST_M_HEIGHT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_height), cancel_h],
            ST_M_WEIGHT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_weight), cancel_h],
            ST_M_MEAS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_meas), cancel_h],
            ST_M_HAIR:    [CallbackQueryHandler(cb_m_hair, pattern=r"^hair_\d+$"), cancel_h],
            ST_M_EYES:    [CallbackQueryHandler(cb_m_eyes, pattern=r"^eye_\d+$"), cancel_h],
            ST_M_LANGS:   [CallbackQueryHandler(cb_m_langs, pattern=r"^(ml_\d+|ml_done)$"), cancel_h],
            ST_M_BODY:    [CallbackQueryHandler(cb_m_body, pattern=r"^body_\d+$"), cancel_h],
            ST_M_BREAST:  [CallbackQueryHandler(cb_m_breast, pattern=r"^breast_\d+$"), cancel_h],
            ST_M_SMOKER:  [CallbackQueryHandler(cb_m_smoker, pattern=r"^smoker_\d+$"), cancel_h],
            ST_M_TATTOOS: [CallbackQueryHandler(cb_m_tattoos, pattern=r"^tattoo_\d+$"), cancel_h],
            ST_M_INCALL:  [CallbackQueryHandler(cb_m_incall, pattern=r"^incall_\d+$"), cancel_h],
            ST_M_AVAIL:   [CallbackQueryHandler(cb_m_avail, pattern=r"^avail_\d+$"), cancel_h],
            ST_M_PRICES:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_prices), cancel_h],
            ST_M_DESC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_desc), cancel_h],
            ST_M_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_contact), cancel_h],
            ST_M_PHOTOS:  photos_state,
            ST_M_PREVIEW: preview_state,

            # Tour flow
            ST_T_REGION:   [CallbackQueryHandler(cb_tr_region, pattern=r"^tr_r_\d+$"), cancel_h],
            ST_T_CITY:     [CallbackQueryHandler(cb_tr_city, pattern=r"^(tr_c_\d+|tr_back)$"), cancel_h],
            ST_T_WHO:      [CallbackQueryHandler(cb_t_who, pattern=r"^twho_(model|host)$"), cancel_h],
            ST_T_FROM:     [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_t_from), cancel_h],
            ST_T_DATEFROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_t_datefrom), cancel_h],
            ST_T_DATETO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_t_dateto), cancel_h],
            ST_T_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_t_name), cancel_h],
            ST_T_NOTES:    [
                MessageHandler(filters.TEXT & ~filters.COMMAND, txt_t_notes),
                CallbackQueryHandler(cb_skip_notes, pattern=r"^skip_notes$"),
                cancel_h,
            ],
            ST_T_CONTACT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_t_contact), cancel_h],
            ST_T_PHOTOS:   photos_state,
            ST_T_PREVIEW:  preview_state,

            # Ad flow
            ST_A_REGION:  [CallbackQueryHandler(cb_ar_region, pattern=r"^ar_r_\d+$"), cancel_h],
            ST_A_CITY:    [CallbackQueryHandler(cb_ar_city, pattern=r"^(ar_c_\d+|ar_back)$"), cancel_h],
            ST_A_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_a_title), cancel_h],
            ST_A_DESC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_a_desc), cancel_h],
            ST_A_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_a_contact), cancel_h],
            ST_A_PHOTOS:  photos_state,
            ST_A_PREVIEW: preview_state,

            # Admin
            ST_ADMIN: [
                CallbackQueryHandler(cb_admin_actions, pattern=r"^adm_(pending|active|stats)$"),
                cancel_h,
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(cb_go_menu, pattern=r"^go_menu$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    # Модерация — вне ConversationHandler чтобы работать из любого состояния
    app.add_handler(CallbackQueryHandler(cb_moderation, pattern=r"^adm_(ok|vip|rej|del)_\d+$"))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))
    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(cleanup_job, interval=CLEANUP_SEC, first=60)

    return app

def main():
    app = build_app()
    logger.info("🚀 Amour Annonce запущен")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
