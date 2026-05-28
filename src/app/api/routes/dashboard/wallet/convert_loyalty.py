from aiohttp import web

from app.api.deps import _verify_webapp_auth


async def handle_dashboard_wallet_convert_loyalty(request: web.Request):
    """Convert loyalty points to subscription credit (webapp version of bot flow)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    resp = web.json_response({"ok": False, "error": "loyalty_disabled"}, status=410)
    if new_session_token:
        resp.set_cookie(
            "tma_session",
            new_session_token,
            max_age=86400,
            httponly=True,
            secure=True,
            samesite="Lax",
            path="/",
        )
    return resp
