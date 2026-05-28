from .common import *  # noqa: F403


async def handle_cancel_charge(request: web.Request):
    """
    Cancel a pending charge order and refund credit.
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
    if not order_id:
        return web.json_response({"ok": False, "error": "missing_order_id"}, status=400)
    
    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        
        charge_req = await session.get(ChargeRequest, order_id)
        if not charge_req:
            return web.json_response({"ok": False, "error": "order_not_found"}, status=404)
        if charge_req.user_id != user.id:
            return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
        if charge_req.receipt_message_id is not None or charge_req.status not in ("draft", "pending"):
            return web.json_response({"ok": False, "error": "cannot_cancel"}, status=400)
        
        # Delete charge request
        await session.delete(charge_req)
        await session.commit()
        
        resp = web.json_response({"ok": True, "message": "order_cancelled"})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
