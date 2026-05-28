from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_purchase.common import logger
from app.api.schemas import CancelOrderRequest, validate_request
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription, UserDiscount


async def handle_cancel_order(request: web.Request):
    """
    Cancel a pending order and refund credit/discounts.
    Body: { order_id: int }
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(CancelOrderRequest, data)
    if error:
        return web.json_response(error, status=400)

    order_id = validated.order_id

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        sub = await session.get(Subscription, order_id)
        if not sub:
            return web.json_response({"ok": False, "error": "order_not_found"}, status=404)
        if sub.user_id != user.id:
            return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
        if sub.receipt_message_id is not None or (sub.status or "") not in ("draft", "pending"):
            return web.json_response({"ok": False, "error": "cannot_cancel"}, status=400)

        if sub.credit_used and sub.credit_used > 0:
            await crud.add_credit(session, user.id, sub.credit_used)

        if sub.applied_discount_ids:
            try:
                id_list = [int(x) for x in sub.applied_discount_ids.split(",") if x.strip().isdigit()]
                if id_list:
                    res = await session.execute(select(UserDiscount).filter(UserDiscount.id.in_(id_list)))
                    discounts = res.scalars().all()
                    for d in discounts:
                        d.used = False
            except Exception as e:
                logger.error(f"Failed to restore discounts: {e}")

        await crud.delete_subscription(session, order_id)

        resp = web.json_response({"ok": True, "message": "order_cancelled"})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
