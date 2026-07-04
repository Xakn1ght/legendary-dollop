"""Current user's Telegram profile photo for the dashboard.

Telegram only includes ``photo_url`` in WebApp init data for apps launched
from the attachment menu, so the Mini App can't read the avatar client-side.
This endpoint fetches it via the Bot API instead and caches the bytes on
disk (24h positive / 6h negative) so Telegram isn't hit on every open.
"""

import logging
import time
from pathlib import Path

from aiohttp import web

from app.api.deps import _verify_webapp_auth
from app.utils.admin_bot_helper import resolve_user_bot

_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "avatars"
_TTL_HIT = 24 * 3600
_TTL_MISS = 6 * 3600


def _fresh(path: Path, ttl: int) -> bool:
    try:
        return path.exists() and (time.time() - path.stat().st_mtime) < ttl
    except OSError:
        return False


async def _fetch_from_telegram(bot, chat_id: int) -> bytes | None:
    photos = await bot.get_user_profile_photos(user_id=chat_id, limit=1)
    if not photos or not photos.total_count or not photos.photos:
        return None
    sizes = photos.photos[0]
    # Sizes come smallest→largest; ~320px (index 1) is plenty for a 90px avatar.
    pick = sizes[1] if len(sizes) > 1 else sizes[-1]
    file = await bot.get_file(pick.file_id)
    buf = await bot.download_file(file.file_path)
    return buf.read() if buf else None


async def handle_profile_photo(request: web.Request):
    user_chat_id, _new_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    jpg = _CACHE_DIR / f"{user_chat_id}.jpg"
    miss = _CACHE_DIR / f"{user_chat_id}.none"

    if _fresh(jpg, _TTL_HIT):
        resp = web.FileResponse(path=jpg)
        resp.headers["Cache-Control"] = "private, max-age=3600"
        return resp
    if _fresh(miss, _TTL_MISS):
        return web.json_response({"ok": False, "error": "no_photo"}, status=404)

    try:
        bot = resolve_user_bot(request.app.get("bot"))
        if not bot:
            return web.json_response({"ok": False, "error": "unavailable"}, status=404)
        data = await _fetch_from_telegram(bot, int(user_chat_id))
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not data:
            miss.touch()
            return web.json_response({"ok": False, "error": "no_photo"}, status=404)
        jpg.write_bytes(data)
        if miss.exists():
            miss.unlink()
        return web.Response(
            body=data,
            content_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except Exception as e:  # Bot API/network failure — treat as transient miss
        logging.warning("profile-photo fetch failed for %s: %s", user_chat_id, e)
        return web.json_response({"ok": False, "error": "fetch_failed"}, status=404)
