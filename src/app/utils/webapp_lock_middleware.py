"""Bot guard: pause a user's bot chat while THEIR Mini App is open.

Pairs with services/webapp_presence + the webapp heartbeat. Runs as an outer
middleware so it gates every handler. Fail-open by construction: any error
falls through to normal handling — a Redis hiccup must never brick the bot.
"""
import time

from aiogram import BaseMiddleware
from aiogram.types import Update

from app.services.webapp_presence import clear, is_open
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram, t

# Escape hatches: always allowed, and they CLEAR the lock so a user with a
# stale key can always recover without waiting for the TTL.
_BYPASS_COMMANDS = ("/start", "/cancel")

# One notice per user per this many seconds (avoid spamming on every keypress).
_NOTICE_COOLDOWN = 12
_last_notice: dict[int, float] = {}


def _lang(user) -> str:
    return get_cached_lang(user.id) or guess_lang_from_telegram(getattr(user, "language_code", None))


class WebappLockMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        user = None
        is_callback = False
        if event.message and event.message.from_user:
            user = event.message.from_user
            text = (event.message.text or "").strip()
            first = text.split()[0].split("@")[0] if text else ""
            if first in _BYPASS_COMMANDS:
                await clear(user.id)
                return await handler(event, data)
        elif event.callback_query and event.callback_query.from_user:
            user = event.callback_query.from_user
            is_callback = True
        elif event.edited_message and event.edited_message.from_user:
            user = event.edited_message.from_user

        if user is None:
            return await handler(event, data)

        if not await is_open(user.id):
            return await handler(event, data)

        # Mini App is open → hold the bot. Tell the user (rate-limited) and stop.
        lang = _lang(user)
        if is_callback:
            try:
                await event.callback_query.answer(t(lang, "webapp_open_lock_short"), show_alert=True)
            except Exception:
                pass
            return

        now = time.time()
        last = _last_notice.get(user.id, 0)
        if now - last >= _NOTICE_COOLDOWN:
            _last_notice[user.id] = now
            bot = data.get("bot")
            if bot is not None:
                try:
                    await bot.send_message(user.id, t(lang, "webapp_open_lock"))
                except Exception:
                    pass
        return
