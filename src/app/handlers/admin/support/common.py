from __future__ import annotations

from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.settings import SUPPORT_CATEGORIES
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram

router = Router()


def _lang_for_tg_user(tg_user) -> str:
    return get_cached_lang(tg_user.id) or guess_lang_from_telegram(
        getattr(tg_user, "language_code", None)
    )


class AdminSupportStates(StatesGroup):
    replying = State()
    choosing_canned_category = State()
    choosing_canned_title = State()
    add_canned_title = State()
    add_canned_body = State()


async def safe_edit_message(
    callback: CallbackQuery, text: str, reply_markup=None
):
    """Safely edit message with fallback to sending new message."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


def _support_main_keyboard(counts: dict) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for cat in SUPPORT_CATEGORIES:
        key = cat["key"]
        label = cat["label"]
        open_count = counts.get(key, 0)
        kb.button(
            text=f"{label} ({open_count})", callback_data=f"admin_sup_cat_{key}"
        )
    kb.button(text="همه تیکت‌ها", callback_data="admin_sup_all")
    kb.button(text="پاسخ‌های آماده", callback_data="admin_sup_canned")
    kb.button(text="تنظیمات", callback_data="admin_sup_settings")
    kb.adjust(2)
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    return kb
