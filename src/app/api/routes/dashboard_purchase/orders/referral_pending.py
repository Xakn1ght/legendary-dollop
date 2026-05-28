import re

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import PLANS
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription


async def handle_validate_referral(request: web.Request):
    """Validate a referral code"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    code = request.query.get("code", "").strip().upper()
    if not code:
        return web.json_response({"ok": False, "error": "missing_code"}, status=400)

    if not re.match(r"^[A-Z0-9]{6}$", code):
        return web.json_response({"ok": True, "valid": False, "reason": "invalid_format"})

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        referrer = await crud.get_user_by_referral_code(session, code)
        if not referrer:
            return web.json_response({"ok": True, "valid": False, "reason": "not_found"})

        if referrer.chat_id == user_chat_id:
            return web.json_response({"ok": True, "valid": False, "reason": "own_code"})

        resp = web.json_response(
            {"ok": True, "valid": True, "referrer_name": referrer.full_name or referrer.username or "User"}
        )
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp


async def handle_get_pending_orders(request: web.Request):
    """Get user's pending orders"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        result = await session.execute(
            select(Subscription)
            .filter(Subscription.user_id == user.id)
            .filter(Subscription.status == "pending")
            .order_by(Subscription.created_at.desc())
        )
        pending_subs = result.scalars().all()

        orders = []
        for sub in pending_subs:
            plan_info = PLANS.get(sub.plan_name, {})
            orders.append(
                {
                    "id": sub.id,
                    "plan": sub.plan_name,
                    "plan_gb": plan_info.get("gb", 0),
                    "service_name": sub.marzban_username,
                    "price": sub.price or plan_info.get("price", 0),
                    "receipt_submitted": sub.receipt_message_id is not None,
                    "created_at": sub.created_at.isoformat() if sub.created_at else None,
                }
            )

        resp = web.json_response({"ok": True, "orders": orders})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
