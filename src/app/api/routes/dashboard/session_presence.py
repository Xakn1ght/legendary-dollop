"""Webapp presence heartbeat + close (2026-07-13, Pasha).

The Mini App pings /session/heartbeat while it is VISIBLE; the bot's
WebappLockMiddleware holds the user's bot chat while that key is fresh. On
hide/close the app fires /session/close (sendBeacon, cookie-authed) to lift
the lock immediately instead of waiting for the TTL.
"""
from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.services.webapp_presence import WEBAPP_LOCK_TTL, clear, touch


async def handle_dashboard_session_heartbeat(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    await touch(user_chat_id)
    resp = web.json_response({"ok": True, "ttl": WEBAPP_LOCK_TTL})
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp


async def handle_dashboard_session_close(request: web.Request):
    # sendBeacon can't set an Authorization header — it rides the tma_session
    # cookie, which _verify_webapp_auth accepts.
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        # Never error a close beacon; nothing to unlock if we can't auth.
        return web.json_response({"ok": True})
    await clear(user_chat_id)
    return web.json_response({"ok": True})
