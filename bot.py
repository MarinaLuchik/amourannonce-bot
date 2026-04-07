#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Amour Annonce — ULTRA PRO bot.py
Single-file Telegram bot for Railway / GitHub deployment.

Main features:
- FR + EN UI
- Contact via button only
- Album photo moderation + album publishing
- Preserves project constants via env or direct values
- Regions / cities logic
- Flows: model / tour / ad / browse / admin
- Stable async version for python-telegram-bot v21+
- SQLite storage
- Safer error handling to avoid crashes on Railway

Recommended requirements.txt:
python-telegram-bot==21.10

Optional env vars:
BOT_TOKEN = "8549540559:AAEd3EllVX0oQnaRUooL54krXwSwg5Iz_wA"

ADMIN_ID = 2021397237
CHANNEL_ID = -1003761619638

SUPPORT_URL = "https://t.me/loveparis777"
VMODLS_URL = "https://t.me/VModls"
MINIAPP_URL = "https://www.amourannonce.com"
"""
import asyncio
import html
import logging
import os
import sqlite3
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
