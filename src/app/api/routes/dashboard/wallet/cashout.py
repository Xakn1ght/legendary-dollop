import logging
import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.cashout import create_cashout
from app.services.flows.errors import FlowError

logger = logging.getLogger(__name__)

_ERROR_STATUS = {"requires_vip_promoter": 403}


async def handle_dashboard_wallet_cashout(request: web.Request):
    """Create a cashout (withdrawal) request for wallet credit.

    Eligibility (VIP-Promoter gate, paid-subscription + credit checks) lives in
    app.services.flows.cashout so every surface shares the same rules.
    """
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

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            try:
                req = await create_cashout(session, user, amount=amount_int, destination=destination)
            except FlowError as e:
                body = {"ok": False, "error": e.code}
                if e.code == "requires_vip_promoter":
                    body["min_active_referrals"] = getattr(e, "min_active_referrals", None)
                    body["active_referrals"] = getattr(e, "active_referrals", None)
                elif e.code == "amount_below_minimum":
                    body["min_amount"] = getattr(e, "min_amount", None)
                return web.json_response(body, status=_ERROR_STATUS.get(e.code, 400))

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
