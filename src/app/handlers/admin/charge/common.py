from aiogram import Router
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.bot_i18n import guess_lang_from_telegram, normalize_lang, set_cached_lang

router = Router()

GB = 1024 * 1024 * 1024


async def _admin_lang(session: AsyncSession, tg_user) -> str:
    try:
        u = await crud.get_user(session, tg_user.id)
        lang = normalize_lang(getattr(u, "language", None)) if u else guess_lang_from_telegram(getattr(tg_user, "language_code", None))
        set_cached_lang(int(tg_user.id), lang)
        return lang
    except Exception:
        return guess_lang_from_telegram(getattr(tg_user, "language_code", None))
