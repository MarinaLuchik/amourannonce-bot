"""
Amour Annonce — Production Bot v2
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
SUPPORT_URL = "https://t.me/loveparis777"
VMODLS_URL  = "https://t.me/VModls"
MINIAPP_URL = "https://www.amourannonce.com"
DB_PATH     = os.getenv("DB_PATH", "amour.db")
MAX_PHOTOS  = 8
MAX_ACTIVE  = 3

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger("amour")

# ─── REGIONS ──────────────────────────────────────────────────────────────────
# Париж — отдельный ключ, сразу районы
PARIS_DISTRICTS = [
    "Paris 1er — Louvre", "Paris 2e — Bourse", "Paris 3e — Marais",
    "Paris 4e — Île Saint-Louis", "Paris 5e — Quartier Latin",
    "Paris 6e — Saint-Germain", "Paris 7e — Eiffel / Invalides",
    "Paris 8e — Champs-Élysées", "Paris 9e — Opéra",
    "Paris 10e — Canal Saint-Martin", "Paris 11e — Bastille",
    "Paris 12e — Bercy", "Paris 13e — Place d'Italie",
    "Paris 14e — Montparnasse", "Paris 15e — Convention",
    "Paris 16e — Trocadéro", "Paris 17e — Batignolles",
    "Paris 18e — Montmartre", "Paris 19e — La Villette",
    "Paris 20e — Belleville",
]

REGIONS: Dict[str, List[str]] = {
    "🗼 Paris": PARIS_DISTRICTS,
    "🏙 Île-de-France": [
        "Boulogne-Billancourt", "Neuilly-sur-Seine", "Levallois-Perret",
        "Issy-les-Moulineaux", "Courbevoie", "La Défense", "Puteaux",
        "Saint-Cloud", "Vincennes", "Montreuil", "Saint-Denis",
        "Versailles", "Saint-Germain-en-Laye", "Créteil", "Cergy",
        "Melun", "Évry-Courcouronnes", "Fontainebleau",
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
    "🍇 Bourgogne": ["Dijon", "Besançon", "Belfort"],
    "🌿 Normandie": ["Rouen", "Caen", "Le Havre", "Deauville", "Cherbourg"],
    "🏛 Hauts-de-France": ["Lille", "Amiens", "Dunkerque", "Valenciennes"],
    "🌊 Bretagne": ["Rennes", "Brest", "Quimper", "Saint-Malo", "Lorient", "Vannes"],
    "🌺 Centre-Val de Loire": ["Tours", "Orléans", "Blois"],
}

# ─── OPTIONS ──────────────────────────────────────────────────────────────────
HAIR_OPTS = [
    ("👱 Blonde","Blonde"), ("🟤 Brune","Brune"), ("🔴 Rousse","Rousse"),
    ("⬛ Noire","Noire"), ("🌰 Châtain","Châtain"), ("🎨 Colorée","Colorée"),
]
EYE_OPTS = [
    ("🔵 Bleus","Bleus"), ("🟢 Verts","Verts"), ("🟤 Marron","Marron"),
    ("🟠 Noisette","Noisette"), ("⚫ Noirs","Noirs"),
]
INCALL_OPTS = [
    ("🏠 Incall uniquement","Incall uniquement"),
    ("🚗 Outcall uniquement","Outcall uniquement"),
    ("🏠🚗 Incall + Outcall","Incall + Outcall"),
]
AVAIL_OPTS = [
    ("🕐 24h/24","24h/24"), ("☀️ En journée","En journée"),
    ("🌙 En soirée","En soirée"), ("🌃 Nuits uniquement","Nuits uniquement"),
    ("📅 Weekends","Weekends"), ("📞 Sur rendez-vous","Sur rendez-vous"),
]
BODY_OPTS = [
    ("✨ Fine","Fine"), ("💪 Sportive","Sportive"),
    ("🍑 Pulpeuse","Pulpeuse"), ("💎 Élancée","Élancée"),
]
BREAST_OPTS = [("💎 Naturelle","Naturelle"), ("✨ Silicone","Silicone")]
YESNO_OPTS  = [("✅ Oui","Oui"), ("❌ Non","Non")]
LANG_OPTS   = [
    ("🇫🇷 Français","Français"), ("🇬🇧 Anglais","Anglais"),
    ("🇷🇺 Russe","Russe"), ("🇪🇸 Espagnol","Espagnol"),
    ("🇮🇹 Italien","Italien"), ("🇩🇪 Allemand","Allemand"),
    ("🇵🇹 Portugais","Portugais"), ("🇸🇦 Arabe","Arabe"),
    ("🇺🇦 Ukrainien","Ukrainien"),
]
PRICE_SLOTS = [
    ("15min","15 min"), ("20min","20 min"), ("30min","30 min"),
    ("45min","45 min"), ("1h","1h"), ("1h30","1h30"),
    ("2h","2h"), ("soiree","Soirée"), ("nuit","Nuit"),
]

# ─── STATES ───────────────────────────────────────────────────────────────────
(
    ST_LANG, ST_MENU,
    # Browse
    ST_BR_REGION, ST_BR_CITY, ST_BR_TYPE, ST_BR_FILTER,
    # Model posting flow
    ST_M_REGION, ST_M_CITY,
    ST_M_NAME, ST_M_AGE, ST_M_ORIGIN, ST_M_HEIGHT, ST_M_WEIGHT,
    ST_M_MEAS, ST_M_HAIR, ST_M_EYES, ST_M_LANGS,
    ST_M_BODY, ST_M_BREAST, ST_M_SMOKER, ST_M_TATTOOS,
    ST_M_INCALL, ST_M_AVAIL, ST_M_PRICES, ST_M_DESC,
    ST_M_CONTACT, ST_M_PHOTOS, ST_M_PREVIEW,
    # Ad posting flow
    ST_A_REGION, ST_A_CITY, ST_A_TITLE, ST_A_DESC,
    ST_A_CONTACT, ST_A_PHOTOS, ST_A_PREVIEW,
    # Admin
    ST_ADMIN,
) = range(36)

# ─── TEXTS ────────────────────────────────────────────────────────────────────
TX = {
    "fr": {
        "greeting":  "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPlateforme privée premium pour modèles et annonces en France 🇫🇷\n\nChoisissez votre langue :",
        "welcome":   "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nQue souhaitez-vous faire ?",
        "btn_browse":  "🔍 Voir les annonces",
        "btn_model":   "👗 Déposer mon profil",
        "btn_ad":      "📢 Publier une annonce",
        "btn_site":    "🌐 Ouvrir le site",
        "btn_support": "💬 Support — @loveparis777",
        "btn_agency":  "🌟 Agence — @VModls",
        "btn_admin":   "🔐 Admin",
        "btn_back":    "◀️ Retour",
        "btn_menu":    "🏠 Menu principal",
        "btn_cancel":  "✖️ Annuler",
        "btn_skip":    "⏭ Passer",
        "btn_done":    "✅ Terminer",
        "btn_send":    "✅ Envoyer en modération",
        "choose_region": "📍 Choisissez votre région :",
        "choose_city":   "🏙 Choisissez votre ville :",
        "choose_paris":  "🗼 Paris — choisissez votre arrondissement :",
        "choose_type":   "Que souhaitez-vous faire dans <b>{city}</b> ?",
        "btn_see_ads":   "🔍 Voir les annonces",
        "btn_see_models":"👗 Voir les profils",
        "filter_title":  "🔎 Filtres — <b>{city}</b>",
        "filter_all":  "🔎 Tout voir",
        "filter_vip":  "⭐ VIP",
        "filter_new":  "🆕 Récents",
        "filter_in":   "🏠 Incall",
        "filter_out":  "🚗 Outcall",
        "filter_bl":   "👱 Blonde",
        "filter_br":   "🟤 Brune",
        "no_results":  "😔 Aucune annonce pour le moment dans cette ville.",
        "results_end": "— Fin des résultats —",
        "contact_btn": "💬 Contacter",
        "ask_name":    "👤 <b>Étape 1</b> — Votre prénom :\n<i>Exemple: Sofia, Marie...</i>",
        "ask_age":     "🎂 <b>Étape 2</b> — Votre âge :\n<i>Entre 18 et 65</i>",
        "ask_origin":  "🌍 <b>Étape 3</b> — Votre nationalité :\n<i>Exemple: Ukrainienne, Russe, Française...</i>",
        "ask_height":  "📏 <b>Étape 4</b> — Votre taille en cm :\n<i>Exemple: 168</i>",
        "ask_weight":  "⚖️ <b>Étape 5</b> — Votre poids en kg :\n<i>Exemple: 55</i>",
        "ask_meas":    "📐 <b>Étape 6</b> — Vos mensurations :\n<i>Format: Bonnet — Taille — Hanches\nExemple: 90C — 60 — 90</i>",
        "ask_hair":    "💇 <b>Étape 7</b> — Couleur de cheveux :",
        "ask_eyes":    "👁 <b>Étape 8</b> — Couleur des yeux :",
        "ask_langs":   "🗣 <b>Étape 9</b> — Langues parlées :\n<i>Sélectionnez une ou plusieurs langues, puis confirmez</i>",
        "btn_langs_ok":"✅ Confirmer les langues",
        "ask_body":    "✨ <b>Étape 10</b> — Silhouette :",
        "ask_breast":  "💎 <b>Étape 11</b> — Poitrine :",
        "ask_smoker":  "🚬 <b>Étape 12</b> — Fumeuse ?",
        "ask_tattoos": "🖋 <b>Étape 13</b> — Tatouages ?",
        "ask_incall":  "🏠 <b>Étape 14</b> — Type de service :",
        "ask_avail":   "🕐 <b>Étape 15</b> — Disponibilités :",
        "ask_prices":  "💶 <b>Étape 16</b> — Vos tarifs\n\nEntrez les prix ligne par ligne :\n<code>15min: 80\n20min: 100\n30min: 150\n45min: 200\n1h: 300\n1h30: 420\n2h: 550\nSoirée: 1200\nNuit: 1800</code>\n\n<i>Entrez 0 si non disponible</i>",
        "ask_desc":    "📝 <b>Étape 17</b> — À propos de vous :\n<i>Minimum 20 caractères</i>",
        "ask_contact": "📞 <b>Étape 18</b> — Votre contact :\n<i>@telegram, numéro (+33...) ou lien</i>",
        "ask_photos":  f"📸 <b>Étape 19</b> — Vos photos (1–{MAX_PHOTOS})\nEnvoyez vos photos puis appuyez sur ✅ Terminer",
        "preview_hdr": "👁 <b>Aperçu avant envoi</b>\n━━━━━━━━━━━━━━━━━━\nVérifiez vos informations :",
        "sent_ok":     "✅ <b>Envoyé en modération !</b>\nNous vous répondrons sous 24h.",
        "ad_title":    "📝 <b>Titre</b> de votre annonce :\n<i>Exemple: Massage relaxant Paris 8e</i>",
        "ad_desc":     "📋 <b>Description</b> de votre annonce :\n<i>Décrivez votre service en détail</i>",
        "ad_contact":  "📞 Votre contact :\n<i>@telegram, numéro ou lien</i>",
        "ad_photos":   f"📸 Photos de votre annonce (1–{MAX_PHOTOS})\nPuis appuyez sur ✅ Terminer",
        "err_short":   "⚠️ Trop court. Réessayez.",
        "err_long":    "⚠️ Texte trop long (max 1200 caractères).",
        "err_age":     "⚠️ Âge invalide. Entrez un nombre entre 18 et 65.",
        "err_height":  "⚠️ Taille invalide. Entre 140 et 200 cm.",
        "err_weight":  "⚠️ Poids invalide. Entre 40 et 120 kg.",
        "err_contact": "⚠️ Contact invalide.\n• @username Telegram\n• +33 6 12 34 56 78\n• https://lien",
        "err_photo":   "⚠️ Ajoutez au moins une photo.",
        "err_langs":   "⚠️ Sélectionnez au moins une langue.",
        "err_limit":   f"⚠️ Limite : {MAX_ACTIVE} publications actives maximum.",
        "photos_only": "📸 Envoyez des photos uniquement.",
        "photo_count": "📸 Photo {n}/{max} ajoutée. Continuez ou appuyez sur ✅ Terminer.",
    },
    "en": {
        "greeting":  "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nPrivate premium platform for models and ads in France 🇫🇷\n\nChoose your language:",
        "welcome":   "💋 <b>Amour Annonce</b>\n━━━━━━━━━━━━━━━━━━\nWhat would you like to do?",
        "btn_browse":  "🔍 Browse listings",
        "btn_model":   "👗 Post my profile",
        "btn_ad":      "📢 Post an ad",
        "btn_site":    "🌐 Open website",
        "btn_support": "💬 Support — @loveparis777",
        "btn_agency":  "🌟 Agency — @VModls",
        "btn_admin":   "🔐 Admin",
        "btn_back":    "◀️ Back",
        "btn_menu":    "🏠 Main menu",
        "btn_cancel":  "✖️ Cancel",
        "btn_skip":    "⏭ Skip",
        "btn_done":    "✅ Finish",
        "btn_send":    "✅ Send for moderation",
        "choose_region": "📍 Choose your region:",
        "choose_city":   "🏙 Choose your city:",
        "choose_paris":  "🗼 Paris — choose your district:",
        "choose_type":   "What would you like to do in <b>{city}</b>?",
        "btn_see_ads":   "🔍 Browse listings",
        "btn_see_models":"👗 Browse profiles",
        "filter_title":  "🔎 Filters — <b>{city}</b>",
        "filter_all":  "🔎 View all",
        "filter_vip":  "⭐ VIP",
        "filter_new":  "🆕 Recent",
        "filter_in":   "🏠 Incall",
        "filter_out":  "🚗 Outcall",
        "filter_bl":   "👱 Blonde",
        "filter_br":   "🟤 Brunette",
        "no_results":  "😔 No listings in this city yet.",
        "results_end": "— End of results —",
        "contact_btn": "💬 Contact",
        "ask_name":    "👤 <b>Step 1</b> — Your display name:\n<i>Example: Sofia, Marie...</i>",
        "ask_age":     "🎂 <b>Step 2</b> — Your age:\n<i>Between 18 and 65</i>",
        "ask_origin":  "🌍 <b>Step 3</b> — Your nationality:\n<i>Example: Ukrainian, Russian, French...</i>",
        "ask_height":  "📏 <b>Step 4</b> — Your height in cm:\n<i>Example: 168</i>",
        "ask_weight":  "⚖️ <b>Step 5</b> — Your weight in kg:\n<i>Example: 55</i>",
        "ask_meas":    "📐 <b>Step 6</b> — Your measurements:\n<i>Format: Cup — Waist — Hips\nExample: 90C — 60 — 90</i>",
        "ask_hair":    "💇 <b>Step 7</b> — Hair color:",
        "ask_eyes":    "👁 <b>Step 8</b> — Eye color:",
        "ask_langs":   "🗣 <b>Step 9</b> — Spoken languages:\n<i>Select one or more, then confirm</i>",
        "btn_langs_ok":"✅ Confirm languages",
        "ask_body":    "✨ <b>Step 10</b> — Body type:",
        "ask_breast":  "💎 <b>Step 11</b> — Breast type:",
        "ask_smoker":  "🚬 <b>Step 12</b> — Smoker?",
        "ask_tattoos": "🖋 <b>Step 13</b> — Tattoos?",
        "ask_incall":  "🏠 <b>Step 14</b> — Service type:",
        "ask_avail":   "🕐 <b>Step 15</b> — Availability:",
        "ask_prices":  "💶 <b>Step 16</b> — Your rates\n\nEnter prices line by line:\n<code>15min: 80\n20min: 100\n30min: 150\n45min: 200\n1h: 300\n1h30: 420\n2h: 550\nEvening: 1200\nNight: 1800</code>\n\n<i>Enter 0 if not available</i>",
        "ask_desc":    "📝 <b>Step 17</b> — About you:\n<i>Minimum 20 characters</i>",
        "ask_contact": "📞 <b>Step 18</b> — Your contact:\n<i>@telegram, phone (+33...) or link</i>",
        "ask_photos":  f"📸 <b>Step 19</b> — Your photos (1–{MAX_PHOTOS})\nSend your photos then press ✅ Finish",
        "preview_hdr": "👁 <b>Preview before sending</b>\n━━━━━━━━━━━━━━━━━━\nCheck your information:",
        "sent_ok":     "✅ <b>Sent for moderation!</b>\nWe'll reply within 24h.",
        "ad_title":    "📝 <b>Title</b> of your ad:\n<i>Example: Relaxing massage Paris 8</i>",
        "ad_desc":     "📋 <b>Description</b> of your ad:\n<i>Describe your service in detail</i>",
        "ad_contact":  "📞 Your contact:\n<i>@telegram, phone or link</i>",
        "ad_photos":   f"📸 Ad photos (1–{MAX_PHOTOS})\nThen press ✅ Finish",
        "err_short":   "⚠️ Too short. Please try again.",
        "err_long":    "⚠️ Text too long (max 1200 characters).",
        "err_age":     "⚠️ Invalid age. Enter a number between 18 and 65.",
        "err_height":  "⚠️ Invalid height. Between 140 and 200 cm.",
        "err_weight":  "⚠️ Invalid weight. Between 40 and 120 kg.",
        "err_contact": "⚠️ Invalid contact.\n• @username Telegram\n• +33 6 12 34 56 78\n• https://link",
        "err_photo":   "⚠️ Add at least one photo.",
        "err_langs":   "⚠️ Select at least one language.",
        "err_limit":   f"⚠️ Limit: {MAX_ACTIVE} active listings maximum.",
        "photos_only": "📸 Please send photos only.",
        "photo_count": "📸 Photo {n}/{max} added. Continue or press ✅ Finish.",
    },
}

# ─── DATABASE ─────────────────────────────────────────────────────────────────
class DB:
    def __init__(self, path):
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
                username TEXT)""")
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS listing_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER, file_id TEXT, sort_order INTEGER DEFAULT 0)""")

    def upsert_user(self, uid, uname, lang=None):
        with closing(self._conn()) as c, c:
            if c.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone():
                if lang:
                    c.execute("UPDATE users SET username=?,language=? WHERE user_id=?", (uname,lang,uid))
                else:
                    c.execute("UPDATE users SET username=? WHERE user_id=?", (uname,uid))
            else:
                c.execute("INSERT INTO users (user_id,username,language) VALUES (?,?,?)", (uid,uname,lang or "fr"))

    def get_lang(self, uid):
        if not uid: return "fr"
        with closing(self._conn()) as c:
            row = c.execute("SELECT language FROM users WHERE user_id=?", (uid,)).fetchone()
            return row["language"] if row else "fr"

    def create_listing(self, data, photos):
        expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
        with closing(self._conn()) as c, c:
            cur = c.execute("""INSERT INTO listings
                (flow,user_id,username,region,city,name,age,origin,height,weight,measurements,
                hair,eyes,languages,body_type,breast_type,smoker,tattoos,incall,availability,
                prices_json,description,contact,ad_title,ad_desc,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data.get("flow",""), data.get("user_id"), data.get("username",""),
                 data.get("region",""), data.get("city",""), data.get("name",""),
                 data.get("age",""), data.get("origin",""), data.get("height",""),
                 data.get("weight",""), data.get("measurements",""), data.get("hair",""),
                 data.get("eyes",""), data.get("languages",""), data.get("body_type",""),
                 data.get("breast_type",""), data.get("smoker",""), data.get("tattoos",""),
                 data.get("incall",""), data.get("availability",""),
                 json.dumps(data.get("prices",{}), ensure_ascii=False),
                 data.get("description",""), data.get("contact",""),
                 data.get("ad_title",""), data.get("ad_desc",""), expires))
            lid = int(cur.lastrowid)
            for i, fid in enumerate(photos[:MAX_PHOTOS]):
                c.execute("INSERT INTO listing_media (listing_id,file_id,sort_order) VALUES (?,?,?)", (lid,fid,i))
            return lid

    def get(self, lid):
        with closing(self._conn()) as c:
            return c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()

    def media(self, lid):
        with closing(self._conn()) as c:
            return [r["file_id"] for r in c.execute(
                "SELECT file_id FROM listing_media WHERE listing_id=? ORDER BY sort_order", (lid,)).fetchall()]

    def update_status(self, lid, status, is_vip=None):
        with closing(self._conn()) as c, c:
            if is_vip is None:
                c.execute("UPDATE listings SET status=? WHERE id=?", (status,lid))
            else:
                c.execute("UPDATE listings SET status=?,is_vip=? WHERE id=?", (status,1 if is_vip else 0,lid))

    def delete(self, lid):
        with closing(self._conn()) as c, c:
            c.execute("DELETE FROM listing_media WHERE listing_id=?", (lid,))
            c.execute("DELETE FROM listings WHERE id=?", (lid,))

    def browse(self, city, flow, vip=False, recent=False, incall=None, hair=None, limit=20):
        q = "SELECT * FROM listings WHERE status='approved' AND city=? AND flow=? AND (expires_at IS NULL OR expires_at>?)"
        p = [city, flow, datetime.utcnow().isoformat()]
        if vip: q += " AND is_vip=1"
        if recent:
            q += " AND created_at>?"; p.append((datetime.utcnow()-timedelta(days=7)).isoformat())
        if incall: q += " AND incall LIKE ?"; p.append(f"%{incall}%")
        if hair: q += " AND hair LIKE ?"; p.append(f"%{hair}%")
        q += " ORDER BY is_vip DESC,created_at DESC LIMIT ?"; p.append(limit)
        with closing(self._conn()) as c:
            return c.execute(q, p).fetchall()

    def count_active(self, uid):
        with closing(self._conn()) as c:
            return int(c.execute(
                "SELECT COUNT(*) c FROM listings WHERE user_id=? AND status IN ('pending','approved')", (uid,)
            ).fetchone()["c"])

    def pending(self):
        with closing(self._conn()) as c:
            return c.execute("SELECT * FROM listings WHERE status='pending' ORDER BY id DESC").fetchall()

    def all_active(self, limit=30):
        with closing(self._conn()) as c:
            return c.execute(
                "SELECT * FROM listings WHERE status='approved' ORDER BY is_vip DESC,created_at DESC LIMIT ?",
                (limit,)).fetchall()

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
            if now - _spam.get(uid, 0) < 0.8:
                if update.callback_query:
                    await update.callback_query.answer()
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

def t(ctx, key, **kw):
    lg = ctx.user_data.get("lang", "fr")
    txt = TX.get(lg, TX["fr"]).get(key, key)
    return txt.format(**kw) if kw else txt

def s(v): return html.escape(str(v or ""))

def get_uname(update):
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

def valid_contact(v):
    v = v.strip()
    cleaned = re.sub(r'[\s\-\(\)]', '', v)
    return (
        (v.startswith("@") and len(v) > 2) or
        (cleaned.startswith('+') and len(cleaned) >= 10) or
        (cleaned.startswith('0') and len(cleaned) >= 9) or
        v.startswith("http")
    )

def contact_url(v):
    v = (v or "").strip()
    if v.startswith("http"): return v
    if v.startswith("@"): return f"https://t.me/{v[1:]}"
    digits = re.sub(r"[^\d+]", "", v)
    if digits: return f"https://wa.me/{digits.lstrip('+')}"
    return None

def parse_prices(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    prices = {}
    for i, (key, _) in enumerate(PRICE_SLOTS):
        if i >= len(lines): break
        nums = re.findall(r"\d+", lines[i])
        prices[key] = nums[0] if nums else "0"
    return prices

def price_line(prices):
    parts = []
    for key, label in PRICE_SLOTS:
        v = prices.get(key)
        if v and v != "0": parts.append(f"{label}: {v}€")
    return " | ".join(parts) if parts else "—"

def dr(ctx):
    if "draft" not in ctx.user_data:
        ctx.user_data["draft"] = {
            "flow":"", "region":"", "city":"",
            "name":"", "age":"", "origin":"", "height":"", "weight":"", "measurements":"",
            "hair":"", "eyes":"", "languages":"", "body_type":"", "breast_type":"",
            "smoker":"", "tattoos":"", "incall":"", "availability":"", "prices":{},
            "description":"", "contact":"", "photos":[],
            "ad_title":"", "ad_desc":"",
        }
    return ctx.user_data["draft"]

def reset(ctx):
    for k in ("draft", "ml_sel", "br_region", "br_city", "br_flow"):
        ctx.user_data.pop(k, None)

async def eor(q, text, kb=None):
    """Edit or reply safely."""
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except BadRequest:
        await q.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def send_album(bot, chat_id, photos, caption, kb=None):
    photos = (photos or [])[:MAX_PHOTOS]
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
def kb_main(ctx, uid=None):
    rows = [
        [InlineKeyboardButton(t(ctx,"btn_browse"), callback_data="go_browse")],
        [InlineKeyboardButton(t(ctx,"btn_model"),  callback_data="go_model"),
         InlineKeyboardButton(t(ctx,"btn_ad"),     callback_data="go_ad")],
        [InlineKeyboardButton(t(ctx,"btn_site"),   web_app=WebAppInfo(url=MINIAPP_URL))],
        [InlineKeyboardButton(t(ctx,"btn_support"), url=SUPPORT_URL)],
        [InlineKeyboardButton(t(ctx,"btn_agency"),  url=VMODLS_URL)],
    ]
    if uid == ADMIN_ID:
        rows.append([InlineKeyboardButton(t(ctx,"btn_admin"), callback_data="go_admin")])
    return InlineKeyboardMarkup(rows)

def kb_regions(ctx, prefix):
    keys = list(REGIONS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i+j < len(keys):
                row.append(InlineKeyboardButton(keys[i+j], callback_data=f"{prefix}_r_{i+j}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx,"btn_menu"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def kb_cities(ctx, region, prefix):
    cities = REGIONS.get(region, [])
    rows, row = [], []
    for i, city in enumerate(cities):
        row.append(InlineKeyboardButton(city, callback_data=f"{prefix}_c_{i}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx,"btn_back"), callback_data=f"{prefix}_back_region")])
    return InlineKeyboardMarkup(rows)

def kb_options(opts, prefix, ctx):
    rows, row = [], []
    for i, opt in enumerate(opts):
        row.append(InlineKeyboardButton(opt[0], callback_data=f"{prefix}_{i}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(t(ctx,"btn_cancel"), callback_data="go_menu")])
    return InlineKeyboardMarkup(rows)

def kb_langs(ctx):
    sel = ctx.user_data.get("ml_sel", [])
    rows, row = [], []
    for i, opt in enumerate(LANG_OPTS):
        mark = "✅ " if i in sel else ""
        row.append(InlineKeyboardButton(mark+opt[0], callback_data=f"ml_{i}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([
        InlineKeyboardButton(t(ctx,"btn_langs_ok"), callback_data="ml_done"),
        InlineKeyboardButton(t(ctx,"btn_cancel"), callback_data="go_menu"),
    ])
    return InlineKeyboardMarkup(rows)

def kb_cancel(ctx):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(ctx,"btn_cancel"), callback_data="go_menu")]])

def kb_photos(ctx):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(ctx,"btn_done"), callback_data="photos_done"),
        InlineKeyboardButton(t(ctx,"btn_cancel"), callback_data="go_menu"),
    ]])

def kb_preview(ctx):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(ctx,"btn_send"), callback_data="submit"),
        InlineKeyboardButton(t(ctx,"btn_cancel"), callback_data="go_menu"),
    ]])

def kb_listing(ctx, contact):
    rows = []
    url = contact_url(contact)
    if url: rows.append([InlineKeyboardButton(t(ctx,"contact_btn"), url=url)])
    rows.append([InlineKeyboardButton(t(ctx,"btn_support"), url=SUPPORT_URL)])
    return InlineKeyboardMarkup(rows)

def kb_br_type(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx,"btn_see_models"), callback_data="br_type_model"),
         InlineKeyboardButton(t(ctx,"btn_see_ads"),    callback_data="br_type_annonce")],
        [InlineKeyboardButton(t(ctx,"btn_back"), callback_data="br_back_city")],
    ])

def kb_filter(ctx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx,"filter_all"), callback_data="f_all")],
        [InlineKeyboardButton(t(ctx,"filter_vip"), callback_data="f_vip"),
         InlineKeyboardButton(t(ctx,"filter_new"), callback_data="f_new")],
        [InlineKeyboardButton(t(ctx,"filter_in"),  callback_data="f_in"),
         InlineKeyboardButton(t(ctx,"filter_out"), callback_data="f_out")],
        [InlineKeyboardButton(t(ctx,"filter_bl"),  callback_data="f_bl"),
         InlineKeyboardButton(t(ctx,"filter_br"),  callback_data="f_br")],
        [InlineKeyboardButton(t(ctx,"btn_back"), callback_data="br_back_type")],
    ])

def kb_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Заявки на модерации", callback_data="adm_pending")],
        [InlineKeyboardButton("🗂 Активные публикации", callback_data="adm_active")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="go_menu")],
    ])

def kb_mod(lid, contact):
    rows = [
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_ok_{lid}"),
         InlineKeyboardButton("⭐ VIP", callback_data=f"mod_vip_{lid}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_rej_{lid}"),
         InlineKeyboardButton("🗑 Удалить", callback_data=f"mod_del_{lid}")],
    ]
    url = contact_url(contact)
    if url: rows.append([InlineKeyboardButton("💬 Связаться с автором", url=url)])
    return InlineKeyboardMarkup(rows)

# ─── FORMATTERS ───────────────────────────────────────────────────────────────
def fmt_model(row, lang="fr"):
    vip = "⭐️ VIP | " if row["is_vip"] else ""
    prices = json.loads(row["prices_json"] or "{}")
    return (
        f"{vip}👗 <b>{s(row['name'])}</b>, {s(row['age'])} ans — {s(row['city'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌍 {s(row['origin'])}\n"
        f"📏 {s(row['height'])} cm • ⚖️ {s(row['weight'])} kg • 📐 {s(row['measurements'])}\n"
        f"💇 {s(row['hair'])} • 👁 {s(row['eyes'])}\n"
        f"✨ {s(row['body_type'])} • 💎 {s(row['breast_type'])}\n"
        f"🗣 {s(row['languages'])}\n"
        f"🏠 {s(row['incall'])} • 🕐 {s(row['availability'])}\n"
        f"💶 {s(price_line(prices))}\n\n"
        f"📝 {s(row['description'])}\n"
        f"📞 {s(row['contact'])}"
    )

def fmt_annonce(row):
    vip = "⭐️ VIP | " if row["is_vip"] else ""
    return (
        f"{vip}📢 <b>{s(row['ad_title'])}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📍 {s(row['city'])}\n"
        f"📋 {s(row['ad_desc'])}\n"
        f"📞 {s(row['contact'])}"
    )

def fmt_draft(d, lang="fr"):
    flow = d.get("flow","")
    if flow == "annonce":
        return (f"📢 <b>{s(d['ad_title'])}</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"📍 {s(d['city'])}\n📋 {s(d['ad_desc'])}\n📞 {s(d['contact'])}")
    prices = d.get("prices",{})
    return (
        f"👗 <b>{s(d['name'])}</b>, {s(d['age'])} ans — {s(d['city'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌍 {s(d['origin'])}\n"
        f"📏 {s(d['height'])} cm • ⚖️ {s(d['weight'])} kg • 📐 {s(d['measurements'])}\n"
        f"💇 {s(d['hair'])} • 👁 {s(d['eyes'])}\n"
        f"✨ {s(d['body_type'])} • 💎 {s(d['breast_type'])}\n"
        f"🗣 {s(d['languages'])}\n"
        f"🏠 {s(d['incall'])} • 🕐 {s(d['availability'])}\n"
        f"💶 {s(price_line(prices))}\n\n"
        f"📝 {s(d['description'])}\n"
        f"📞 {s(d['contact'])}"
    )

def fmt_admin(row):
    prices = json.loads(row["prices_json"] or "{}")
    return (
        f"🔔 <b>Новая заявка #{row['id']}</b>\n━━━━━━━━━━━━━━━━━━\n"
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
        f"📢 {s(row['ad_title'])}: {s(row['ad_desc'])}\n"
        f"User: @{s(row['username'])} | ID: <code>{s(row['user_id'])}</code>"
    )

# ─── START / MENU ─────────────────────────────────────────────────────────────
@safe_handler
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reset(ctx)
    u = update.effective_user
    if u: db.upsert_user(u.id, get_uname(update))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(TX["fr"]["btn_site"], web_app=WebAppInfo(url=MINIAPP_URL))],
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
    await eor(q, TX[lg]["welcome"], kb_main(ctx, q.from_user.id))
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
    txt = t(ctx, "welcome")
    if update.callback_query:
        await update.callback_query.answer()
        await eor(update.callback_query, txt, kb)
    elif update.message:
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    return ST_MENU

# ─── BROWSE ───────────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_browse(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await eor(q, t(ctx,"choose_region"), kb_regions(ctx,"br"))
    return ST_BR_REGION

@safe_handler
async def cb_br_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "br_back_region":
        return await cb_go_browse(update, ctx)
    idx = int(q.data.replace("br_r_",""))
    keys = list(REGIONS.keys())
    if idx >= len(keys): return await cb_go_browse(update, ctx)
    region = keys[idx]
    ctx.user_data["br_region"] = region
    # Если Париж — показываем районы сразу с нужным заголовком
    if region == "🗼 Paris":
        await eor(q, t(ctx,"choose_paris"), kb_cities(ctx, region, "br"))
    else:
        await eor(q, f"{s(region)}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, region, "br"))
    return ST_BR_CITY

@safe_handler
async def cb_br_city(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "br_back_region":
        return await cb_go_browse(update, ctx)
    idx = int(q.data.replace("br_c_",""))
    region = ctx.user_data.get("br_region","")
    cities = REGIONS.get(region,[])
    if idx >= len(cities): return await cb_go_browse(update, ctx)
    city = cities[idx]
    ctx.user_data["br_city"] = city
    await eor(q, t(ctx,"choose_type",city=city), kb_br_type(ctx))
    return ST_BR_TYPE

@safe_handler
async def cb_br_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "br_back_city":
        # Вернуться к выбору города
        region = ctx.user_data.get("br_region","")
        if region == "🗼 Paris":
            await eor(q, t(ctx,"choose_paris"), kb_cities(ctx, region, "br"))
        else:
            await eor(q, f"{s(region)}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, region, "br"))
        return ST_BR_CITY
    flow = q.data.replace("br_type_","")
    ctx.user_data["br_flow"] = flow
    city = ctx.user_data.get("br_city","")
    await eor(q, t(ctx,"filter_title",city=city), kb_filter(ctx))
    return ST_BR_FILTER

@safe_handler
async def cb_br_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "br_back_type":
        city = ctx.user_data.get("br_city","")
        await eor(q, t(ctx,"choose_type",city=city), kb_br_type(ctx))
        return ST_BR_TYPE
    city = ctx.user_data.get("br_city","")
    flow = ctx.user_data.get("br_flow","model")
    filters_map = {
        "f_all": {}, "f_vip": {"vip":True}, "f_new": {"recent":True},
        "f_in":  {"incall":"Incall"}, "f_out": {"incall":"Outcall"},
        "f_bl":  {"hair":"Blonde"},   "f_br":  {"hair":"Brune"},
    }
    kw = filters_map.get(q.data, {})
    rows = db.browse(city, flow, **kw)
    back_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(ctx,"btn_back"), callback_data="br_back_type")],
        [InlineKeyboardButton(t(ctx,"btn_menu"), callback_data="go_menu")],
    ])
    if not rows:
        await eor(q, t(ctx,"no_results"), back_kb)
        return ST_BR_FILTER
    await eor(q, f"📍 <b>{s(city)}</b> — {len(rows)} résultat(s)", back_kb)
    lang = ctx.user_data.get("lang","fr")
    for row in rows:
        caption = fmt_model(row, lang) if flow == "model" else fmt_annonce(row)
        await send_album(ctx.bot, q.message.chat_id, db.media(row["id"]),
                         caption, kb_listing(ctx, row["contact"]))
    await q.message.reply_text(t(ctx,"results_end"), parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t(ctx,"btn_back"), callback_data="br_back_type")],
            [InlineKeyboardButton(t(ctx,"btn_menu"), callback_data="go_menu")],
        ]))
    return ST_BR_FILTER

# ─── MODEL FLOW ───────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_model(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    reset(ctx); dr(ctx)["flow"] = "model"
    await eor(q, t(ctx,"choose_region"), kb_regions(ctx,"mr"))
    return ST_M_REGION

@safe_handler
async def cb_mr_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "mr_back_region":
        return await cb_go_model(update, ctx)
    idx = int(q.data.replace("mr_r_",""))
    keys = list(REGIONS.keys())
    if idx >= len(keys): return await cb_go_model(update, ctx)
    region = keys[idx]
    dr(ctx)["region"] = region
    if region == "🗼 Paris":
        await eor(q, t(ctx,"choose_paris"), kb_cities(ctx, region, "mr"))
    else:
        await eor(q, f"{s(region)}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, region, "mr"))
    return ST_M_CITY

@safe_handler
async def cb_mr_city(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "mr_back_region":
        return await cb_go_model(update, ctx)
    idx = int(q.data.replace("mr_c_",""))
    region = dr(ctx).get("region","")
    cities = REGIONS.get(region,[])
    if idx >= len(cities): return await cb_go_model(update, ctx)
    dr(ctx)["city"] = cities[idx]
    await q.message.reply_text(t(ctx,"ask_name"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_NAME

# Текстовые шаги модели
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
    await update.message.reply_text(t(ctx,"ask_meas"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_MEAS

@safe_handler
async def txt_m_meas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if len(v) < 3: await update.message.reply_text(t(ctx,"err_short")); return ST_M_MEAS
    dr(ctx)["measurements"] = v
    await update.message.reply_text(t(ctx,"ask_hair"), parse_mode=ParseMode.HTML,
                                    reply_markup=kb_options(HAIR_OPTS,"hair",ctx))
    return ST_M_HAIR

@safe_handler
async def cb_m_hair(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["hair"] = HAIR_OPTS[int(q.data.replace("hair_",""))][1]
    await eor(q, t(ctx,"ask_eyes"), kb_options(EYE_OPTS,"eye",ctx))
    return ST_M_EYES

@safe_handler
async def cb_m_eyes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["eyes"] = EYE_OPTS[int(q.data.replace("eye_",""))][1]
    ctx.user_data["ml_sel"] = []
    await eor(q, t(ctx,"ask_langs"), kb_langs(ctx))
    return ST_M_LANGS

@safe_handler
async def cb_m_langs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sel = ctx.user_data.get("ml_sel", [])
    if q.data == "ml_done":
        if not sel:
            await q.answer(t(ctx,"err_langs"), show_alert=True); return ST_M_LANGS
        dr(ctx)["languages"] = ", ".join(LANG_OPTS[i][1] for i in sel)
        await eor(q, t(ctx,"ask_body"), kb_options(BODY_OPTS,"body",ctx))
        return ST_M_BODY
    idx = int(q.data.replace("ml_",""))
    if idx in sel: sel.remove(idx)
    else: sel.append(idx)
    ctx.user_data["ml_sel"] = sel
    try: await q.edit_reply_markup(kb_langs(ctx))
    except Exception: pass
    return ST_M_LANGS

@safe_handler
async def cb_m_body(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["body_type"] = BODY_OPTS[int(q.data.replace("body_",""))][1]
    await eor(q, t(ctx,"ask_breast"), kb_options(BREAST_OPTS,"breast",ctx))
    return ST_M_BREAST

@safe_handler
async def cb_m_breast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["breast_type"] = BREAST_OPTS[int(q.data.replace("breast_",""))][1]
    await eor(q, t(ctx,"ask_smoker"), kb_options(YESNO_OPTS,"smoker",ctx))
    return ST_M_SMOKER

@safe_handler
async def cb_m_smoker(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["smoker"] = YESNO_OPTS[int(q.data.replace("smoker_",""))][1]
    await eor(q, t(ctx,"ask_tattoos"), kb_options(YESNO_OPTS,"tattoo",ctx))
    return ST_M_TATTOOS

@safe_handler
async def cb_m_tattoos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["tattoos"] = YESNO_OPTS[int(q.data.replace("tattoo_",""))][1]
    await eor(q, t(ctx,"ask_incall"), kb_options(INCALL_OPTS,"incall",ctx))
    return ST_M_INCALL

@safe_handler
async def cb_m_incall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["incall"] = INCALL_OPTS[int(q.data.replace("incall_",""))][1]
    await eor(q, t(ctx,"ask_avail"), kb_options(AVAIL_OPTS,"avail",ctx))
    return ST_M_AVAIL

@safe_handler
async def cb_m_avail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    dr(ctx)["availability"] = AVAIL_OPTS[int(q.data.replace("avail_",""))][1]
    await q.message.reply_text(t(ctx,"ask_prices"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_M_PRICES

@safe_handler
async def txt_m_prices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    prices = parse_prices(update.message.text)
    dr(ctx)["prices"] = prices
    await update.message.reply_text(
        f"✅ {s(price_line(prices))}\n\n{t(ctx,'ask_desc')}",
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

# ─── AD FLOW ──────────────────────────────────────────────────────────────────
@safe_handler
async def cb_go_ad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    reset(ctx); dr(ctx)["flow"] = "annonce"
    await eor(q, t(ctx,"choose_region"), kb_regions(ctx,"ar"))
    return ST_A_REGION

@safe_handler
async def cb_ar_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "ar_back_region":
        return await cb_go_ad(update, ctx)
    idx = int(q.data.replace("ar_r_",""))
    keys = list(REGIONS.keys())
    if idx >= len(keys): return await cb_go_ad(update, ctx)
    region = keys[idx]
    dr(ctx)["region"] = region
    if region == "🗼 Paris":
        await eor(q, t(ctx,"choose_paris"), kb_cities(ctx, region, "ar"))
    else:
        await eor(q, f"{s(region)}\n\n{t(ctx,'choose_city')}", kb_cities(ctx, region, "ar"))
    return ST_A_CITY

@safe_handler
async def cb_ar_city(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "ar_back_region":
        return await cb_go_ad(update, ctx)
    idx = int(q.data.replace("ar_c_",""))
    region = dr(ctx).get("region","")
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
    await update.message.reply_text(t(ctx,"ad_contact"), parse_mode=ParseMode.HTML, reply_markup=kb_cancel(ctx))
    return ST_A_CONTACT

@safe_handler
async def txt_a_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    if not valid_contact(v): await update.message.reply_text(t(ctx,"err_contact")); return ST_A_CONTACT
    dr(ctx)["contact"] = v
    await update.message.reply_text(t(ctx,"ad_photos"), parse_mode=ParseMode.HTML, reply_markup=kb_photos(ctx))
    return ST_A_PHOTOS

# ─── PHOTOS / PREVIEW / SUBMIT ────────────────────────────────────────────────
@safe_handler
async def receive_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photos = dr(ctx).get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"⚠️ Maximum {MAX_PHOTOS} photos."); return
    photos.append(update.message.photo[-1].file_id)
    dr(ctx)["photos"] = photos
    await update.message.reply_text(
        t(ctx,"photo_count",n=len(photos),max=MAX_PHOTOS),
        parse_mode=ParseMode.HTML, reply_markup=kb_photos(ctx))

@safe_handler
async def photos_fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(ctx,"photos_only"), reply_markup=kb_photos(ctx))

@safe_handler
async def cb_photos_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    d = dr(ctx)
    if not d.get("photos"):
        await q.answer(t(ctx,"err_photo"), show_alert=True); return
    lang = ctx.user_data.get("lang","fr")
    preview = f"{t(ctx,'preview_hdr')}\n\n{fmt_draft(d, lang)}"
    try:
        await eor(q, preview, kb_preview(ctx))
    except Exception:
        await q.message.reply_text(preview, parse_mode=ParseMode.HTML, reply_markup=kb_preview(ctx))
    return ST_M_PREVIEW if d.get("flow") == "model" else ST_A_PREVIEW

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
    await eor(q, t(ctx,"sent_ok"), kb_main(ctx, u.id))
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
    await eor(q, text, kb_admin())
    return ST_ADMIN

@safe_handler
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Доступ запрещён."); return
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
            await eor(q, "✅ Нет заявок на модерации.", kb_admin()); return ST_ADMIN
        lines = ["📋 <b>Заявки на модерации</b>\n"]
        for r in rows[:25]:
            title = r["name"] or r["ad_title"] or "—"
            lines.append(f"#{r['id']} • {s(r['flow'])} • {s(r['city'])} • {s(title)}")
        await eor(q, "\n".join(lines), kb_admin())
        return ST_ADMIN

    if q.data == "adm_active":
        rows = db.all_active()
        if not rows:
            await eor(q, "Нет активных публикаций.", kb_admin()); return ST_ADMIN
        lines = ["🗂 <b>Активные публикации</b>\n"]
        for r in rows:
            vip = "⭐ " if r["is_vip"] else ""
            title = r["name"] or r["ad_title"] or "—"
            lines.append(f"#{r['id']} • {vip}{s(r['flow'])} • {s(r['city'])} • {s(title)}")
        await eor(q, "\n".join(lines), kb_admin())
        return ST_ADMIN

    return ST_ADMIN

@safe_handler
async def cb_moderation(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.answer("⛔️", show_alert=True); return
    parts = q.data.split("_")
    action = parts[1]; lid = int(parts[2])
    row = db.get(lid)
    if not row:
        await eor(q, "⚠️ Заявка не найдена."); return

    if action == "rej":
        db.update_status(lid, "rejected")
        await eor(q, f"❌ Заявка #{lid} отклонена.")
        if row["user_id"]:
            try:
                lg = db.get_lang(row["user_id"])
                msg = "❌ Votre publication a été refusée." if lg=="fr" else "❌ Your publication was rejected."
                await ctx.bot.send_message(row["user_id"], msg)
            except Exception: pass
        return

    if action == "del":
        db.delete(lid)
        await eor(q, f"🗑 Заявка #{lid} удалена.")
        return

    is_vip = action == "vip"
    db.update_status(lid, "approved", is_vip=is_vip)
    fresh = db.get(lid)
    if fresh:
        lg = db.get_lang(fresh["user_id"]) if fresh["user_id"] else "fr"
        caption = fmt_model(fresh, lg) if fresh["flow"]=="model" else fmt_annonce(fresh)
        await send_album(ctx.bot, CHANNEL_ID, db.media(lid), caption)
    await eor(q, f"✅ Заявка #{lid} опубликована{' ⭐ VIP' if is_vip else ''}.")
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
def build_app():
    app = Application.builder().token(BOT_TOKEN).build()

    cancel_h = CallbackQueryHandler(cb_go_menu, pattern=r"^go_menu$")
    photo_h  = MessageHandler(filters.PHOTO, receive_photo)
    photo_fb = MessageHandler(filters.TEXT & ~filters.COMMAND, photos_fallback)
    done_h   = CallbackQueryHandler(cb_photos_done, pattern=r"^photos_done$")
    submit_h = CallbackQueryHandler(cb_submit, pattern=r"^submit$")

    photos_state  = [photo_h, photo_fb, done_h, cancel_h]
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
                CallbackQueryHandler(cb_go_ad,     pattern=r"^go_ad$"),
                CallbackQueryHandler(cb_go_admin,  pattern=r"^go_admin$"),
            ],

            # Browse
            ST_BR_REGION: [
                CallbackQueryHandler(cb_br_region, pattern=r"^(br_r_\d+|br_back_region)$"),
                cancel_h,
            ],
            ST_BR_CITY: [
                CallbackQueryHandler(cb_br_city, pattern=r"^(br_c_\d+|br_back_region)$"),
                cancel_h,
            ],
            ST_BR_TYPE: [
                CallbackQueryHandler(cb_br_type, pattern=r"^(br_type_model|br_type_annonce|br_back_city)$"),
                cancel_h,
            ],
            ST_BR_FILTER: [
                CallbackQueryHandler(cb_br_filter, pattern=r"^(f_all|f_vip|f_new|f_in|f_out|f_bl|f_br|br_back_type)$"),
                cancel_h,
            ],

            # Model flow
            ST_M_REGION:  [CallbackQueryHandler(cb_mr_region, pattern=r"^(mr_r_\d+|mr_back_region)$"), cancel_h],
            ST_M_CITY:    [CallbackQueryHandler(cb_mr_city,   pattern=r"^(mr_c_\d+|mr_back_region)$"), cancel_h],
            ST_M_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_name), cancel_h],
            ST_M_AGE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_age), cancel_h],
            ST_M_ORIGIN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_origin), cancel_h],
            ST_M_HEIGHT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_height), cancel_h],
            ST_M_WEIGHT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_weight), cancel_h],
            ST_M_MEAS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_meas), cancel_h],
            ST_M_HAIR:    [CallbackQueryHandler(cb_m_hair,    pattern=r"^hair_\d+$"), cancel_h],
            ST_M_EYES:    [CallbackQueryHandler(cb_m_eyes,    pattern=r"^eye_\d+$"), cancel_h],
            ST_M_LANGS:   [CallbackQueryHandler(cb_m_langs,   pattern=r"^(ml_\d+|ml_done)$"), cancel_h],
            ST_M_BODY:    [CallbackQueryHandler(cb_m_body,    pattern=r"^body_\d+$"), cancel_h],
            ST_M_BREAST:  [CallbackQueryHandler(cb_m_breast,  pattern=r"^breast_\d+$"), cancel_h],
            ST_M_SMOKER:  [CallbackQueryHandler(cb_m_smoker,  pattern=r"^smoker_\d+$"), cancel_h],
            ST_M_TATTOOS: [CallbackQueryHandler(cb_m_tattoos, pattern=r"^tattoo_\d+$"), cancel_h],
            ST_M_INCALL:  [CallbackQueryHandler(cb_m_incall,  pattern=r"^incall_\d+$"), cancel_h],
            ST_M_AVAIL:   [CallbackQueryHandler(cb_m_avail,   pattern=r"^avail_\d+$"), cancel_h],
            ST_M_PRICES:  [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_prices), cancel_h],
            ST_M_DESC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_desc), cancel_h],
            ST_M_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, txt_m_contact), cancel_h],
            ST_M_PHOTOS:  photos_state,
            ST_M_PREVIEW: preview_state,

            # Ad flow
            ST_A_REGION:  [CallbackQueryHandler(cb_ar_region, pattern=r"^(ar_r_\d+|ar_back_region)$"), cancel_h],
            ST_A_CITY:    [CallbackQueryHandler(cb_ar_city,   pattern=r"^(ar_c_\d+|ar_back_region)$"), cancel_h],
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
    # Модерация — вне ConversationHandler, работает всегда
    app.add_handler(CallbackQueryHandler(cb_moderation, pattern=r"^mod_(ok|vip|rej|del)_\d+$"))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(cleanup_job, interval=3600, first=60)

    return app

def main():
    app = build_app()
    logger.info("🚀 Amour Annonce запущен")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
