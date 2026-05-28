import re

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_purchase.plans_user import _is_username_taken
from app.database.models import AsyncSessionLocal


async def handle_check_service_name(request: web.Request):
    """Check if a service name is available"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    name = request.query.get("name", "").strip()
    if not name:
        return web.json_response({"ok": False, "error": "missing_name"}, status=400)

    if not re.fullmatch(r"[A-Za-z0-9]+", name):
        return web.json_response({"ok": True, "available": False, "reason": "invalid_format"})

    if len(name) < 3 or len(name) > 20:
        return web.json_response({"ok": True, "available": False, "reason": "invalid_length"})

    async with AsyncSessionLocal() as session:
        taken = await _is_username_taken(session, name)

        resp = web.json_response({"ok": True, "available": not taken, "reason": "taken" if taken else None})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
