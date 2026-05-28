import logging
import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def handle_dashboard_wallet_cashout(request: web.Request):
    """Create a cashout (withdrawal) request for wallet credit."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    amount = data.get("amount")
    destination = (data.get("destination") or "").strip() or None
    try:
        amount_int = int(str(amount).replace(",", "").replace("٬", "").strip())
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_amount"}, status=400)

    if amount_int <= 0:
        return web.json_response({"ok": False, "error": "invalid_amount"}, status=400)

    if destination and len(destination) < 8:
        return web.json_response({"ok": False, "error": "invalid_destination"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            req = await crud.create_cashout_request(session, user.id, amount_int, destination)
            if not req:
                try:
                    has_paid = await crud.has_active_paid_subscription(session, user.id)
                except Exception:
                    has_paid = False
                if not has_paid:
                    return web.json_response({"ok": False, "error": "requires_active_paid_subscription"}, status=400)
                if int(getattr(user, "credit", 0) or 0) < amount_int:
                    return web.json_response({"ok": False, "error": "insufficient_credit"}, status=400)
                return web.json_response({"ok": False, "error": "cannot_create"}, status=400)

            await session.refresh(user)

            resp = web.json_response(
                {
                    "ok": True,
                    "request_id": req.id,
                    "amount": req.amount,
                    "destination": req.destination,
                    "credit_remaining": int(getattr(user, "credit", 0) or 0),
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error creating cashout request: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
