from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import CancelOrderRequest, validate_request
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.errors import FlowError
from app.services.flows.purchase import cancel_purchase_order

_ERROR_STATUS = {"order_not_found": 404, "unauthorized": 403}


async def handle_cancel_order(request: web.Request):
    """
    Cancel a pending order and refund credit/discounts/coupon.
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

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        try:
            await cancel_purchase_order(session, user, validated.order_id)
        except FlowError as e:
            return web.json_response({"ok": False, "error": e.code}, status=_ERROR_STATUS.get(e.code, 400))

        resp = web.json_response({"ok": True, "message": "order_cancelled"})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
