from app.api.deps import _verify_webapp_auth  # underscore name isn't pulled in by `import *`
from app.services.flows.charge import cancel_charge_order
from app.services.flows.errors import FlowError

from .common import *  # noqa: F403

_ERROR_STATUS = {"order_not_found": 404, "unauthorized": 403}


async def handle_cancel_charge(request: web.Request):
    """
    Cancel a pending charge order and refund any reserved credit.
    Body: { order_id: int }
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    order_id = data.get("order_id")
    if not order_id or not isinstance(order_id, int):
        return web.json_response({"ok": False, "error": "missing_order_id"}, status=400)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        try:
            refunded = await cancel_charge_order(session, user, order_id)
        except FlowError as e:
            return web.json_response({"ok": False, "error": e.code}, status=_ERROR_STATUS.get(e.code, 400))

        resp = web.json_response({"ok": True, "message": "order_cancelled", "credit_refunded": refunded})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
