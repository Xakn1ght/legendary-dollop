from aiogram import Router

from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram

router = Router()


def _lang_for_tg_user(tg_user) -> str:
    return get_cached_lang(tg_user.id) or guess_lang_from_telegram(getattr(tg_user, "language_code", None))
