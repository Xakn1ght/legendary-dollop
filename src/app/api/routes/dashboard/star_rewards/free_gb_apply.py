"""Wallet redemption for free_gb coupons onto an EXISTING subscription.

POST /api/dashboard/coupons/{coupon_id}/apply-gb  {subscription_id}
Adds the coupon's GB to the chosen subscription's panel data limit and
consumes the coupon. The checkout path (attach to a NEW purchase) still
works — this is the "use it now" flow for the wallet
(achievement coupons, season free_gb prizes).
"""

import datetime
import json
import logging

from aiohttp import web
from sqlalchemy import and_
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription
from app.services.marzban import marzban_api

logger = logging.getLogger(__name__)


async def handle_dashboard_coupon_apply_gb(request: web.Request):
    try:
        coupon_id = int(request.match_info["coupon_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_coupon_id"}, status=400)

    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        data = {}
    try:
        subscription_id = int(data.get("subscription_id"))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "subscription_required"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            coupon = await crud.get_coupon_by_id(session, coupon_id)
            if not coupon or coupon.user_id != user.id or coupon.coupon_type != "free_gb":
                return web.json_response({"ok": False, "error": "coupon_not_found"}, status=404)
            if coupon.expires_at and coupon.expires_at < datetime.datetime.utcnow():
                return web.json_response({"ok": False, "error": "coupon_expired"}, status=400)

            try:
                gb = int(json.loads(coupon.payload or "{}").get("gb") or 0)
            except Exception:
                gb = 0
            if gb <= 0:
                return web.json_response({"ok": False, "error": "invalid_coupon"}, status=400)

            sub = (
                await session.execute(
                    select(Subscription).where(
                        and_(Subscription.id == subscription_id, Subscription.user_id == user.id)
                    )
                )
            ).scalars().first()
            if not sub or not sub.marzban_username:
                return web.json_response({"ok": False, "error": "subscription_not_found"}, status=404)

            info = await marzban_api.get_user_info(sub.marzban_username)
            if not info:
                return web.json_response({"ok": False, "error": "panel_user_not_found"}, status=502)

            # Consume FIRST (idempotent active→used gate) so a double-tap can't
            # apply the GB twice; restore if the panel write fails.
            if not await crud.mark_coupon_used(session, coupon.id):
                return web.json_response({"ok": False, "error": "coupon_not_active"}, status=400)

            new_limit = int(info.get("data_limit") or 0) + gb * (1024 ** 3)
            ok = await marzban_api.update_user(sub.marzban_username, {"data_limit": new_limit})
            if not ok:
                await crud.restore_coupon(session, coupon.id)
                return web.json_response({"ok": False, "error": "panel_update_failed"}, status=502)

            resp = web.json_response({
                "ok": True,
                "gb_added": gb,
                "subscription_id": sub.id,
            })
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        logger.error(f"free_gb apply failed for coupon {coupon_id}: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
