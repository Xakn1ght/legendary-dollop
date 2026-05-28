from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal


async def handle_dashboard_challenges(request: web.Request):
    """
    Challenges are disabled.

    This project no longer uses XP / loyalty points / challenge rewards.
    We keep this endpoint so older WebApp builds don't crash.
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        resp = web.json_response(
            {
                "ok": True,
                "challenges": [],
                "user_stats": {
                    "credit": int(getattr(user, "credit", 0) or 0),
                    "stars": int(getattr(user, "stars", 0) or 0),
                    "xp": 0,
                    "loyalty_points": 0,
                },
                "features": {
                    "auto_claim_available": False,
                    "auto_claim_enabled": False,
                },
                "auto_claimed_ids": [],
            }
        )
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp


async def handle_dashboard_challenges_claim(request: web.Request):
    """Challenges are disabled (kept only for backwards-compatibility)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    resp = web.json_response({"ok": False, "error": "challenges_disabled"}, status=410)
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp
