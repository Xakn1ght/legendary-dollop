"""Wallet redemption for the vip_days season coupon (50★ Season Legend).

POST /api/dashboard/coupons/{coupon_id}/redeem-vip
Activates/extends the user's VIP window by the coupon's days and consumes the
coupon. Never spendable at checkout (pricing rejects it there).
"""

import json
import logging

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.subscription_processing import extend_vip_window

logger = logging.getLogger(__name__)


async def handle_dashboard_redeem_vip_days(request: web.Request):
    try:
        coupon_id = int(request.match_info["coupon_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_coupon_id"}, status=400)

    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            coupon = await crud.get_coupon_by_id(session, coupon_id)
            if not coupon or coupon.user_id != user.id or coupon.coupon_type != "vip_days":
                return web.json_response({"ok": False, "error": "coupon_not_found"}, status=404)

            try:
                days = int(json.loads(coupon.payload or "{}").get("days") or 0)
            except Exception:
                days = 0
            if days <= 0:
                return web.json_response({"ok": False, "error": "invalid_coupon"}, status=400)

            # Consume FIRST (idempotent active→used gate) so a double-tap can't
            # grant VIP twice; restore if the grant somehow fails.
            if not await crud.mark_coupon_used(session, coupon.id):
                return web.json_response({"ok": False, "error": "coupon_not_active"}, status=400)
            try:
                await extend_vip_window(session, user, days)
            except Exception:
                await crud.restore_coupon(session, coupon.id)
                raise

            resp = web.json_response({
                "ok": True,
                "vip_until": user.vip_until.isoformat() if user.vip_until else None,
                "days_added": days,
            })
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        logger.error(f"vip_days redemption failed for coupon {coupon_id}: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
