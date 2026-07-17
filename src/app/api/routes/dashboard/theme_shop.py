"""Purchasable dashboard themes (bubblegum, 2026-07-15).

GET  /api/dashboard/theme-shop      -> {items: [{key, price, owned}], credit}
POST /api/dashboard/theme-shop/buy  -> {theme} — charges wallet credit and
     permanently unlocks the theme in dashboard_prefs.unlocked_themes.

Thin wrappers over services/flows/theme_shop.py (money logic lives there).
"""
import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.errors import FlowError
from app.services.flows.theme_shop import buy_theme, theme_shop_items


async def handle_theme_shop_get(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            resp = web.json_response({
                "ok": True,
                "items": theme_shop_items(user.dashboard_prefs),
                "credit": int(user.credit or 0),
            })
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_theme_shop_buy(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    theme_key = str(data.get("theme") or "").strip()

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            try:
                result = await buy_theme(session, user, theme_key)
            except FlowError as e:
                # Business outcomes ride HTTP 200: the shell's api() throws on
                # any non-2xx, which reduced insufficient_credit to a generic
                # "something went wrong" toast (Pasha hit this live with a
                # 9k wallet vs the 40k price, 2026-07-15).
                body = {"ok": False, "error": e.code}
                if e.code == "insufficient_credit":
                    body["price"] = getattr(e, "price", None)
                    body["credit"] = getattr(e, "credit", None)
                return web.json_response(body)
            resp = web.json_response({"ok": True, **result})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
