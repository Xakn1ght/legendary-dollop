"""Mission achievements for the Profile page — list + one-time 1GB claims.

Thin wrappers over services/achievements.py (conditions and minting live
there); this module only does auth and error → HTTP mapping.
"""
import logging
import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services import achievements as ach
from app.services.flows.errors import FlowError

logger = logging.getLogger(__name__)

_ERROR_STATUS = {
    "unknown_achievement": 404,
    "requires_purchase": 403,
    "not_completed": 400,
    "already_claimed": 409,
}


async def handle_dashboard_achievements(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            data = await ach.snapshot(session, user)
            resp = web.json_response({"ok": True, **data})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error building achievements snapshot: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_dashboard_achievements_claim(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    key = str(data.get("key") or "")

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            try:
                coupon = await ach.claim(session, user, key)
            except FlowError as e:
                return web.json_response(
                    {"ok": False, "error": e.code}, status=_ERROR_STATUS.get(e.code, 400)
                )
            resp = web.json_response({
                "ok": True,
                "coupon": {
                    "id": coupon.id,
                    "coupon_type": coupon.coupon_type,
                    "gb": ach.REWARD_GB,
                    "expires_at": coupon.expires_at.isoformat() if coupon.expires_at else None,
                },
            })
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error claiming achievement: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
