"""Book-a-next-plan endpoint (2026-07-12, image-6: "add the book button").

Thin wrapper over flows.charge.start_booking_order — the same service the bot
uses. Payment goes through the normal receipt endpoint; at admin approval the
plan is armed as a native PasarGuard next_plan and fires panel-side the moment
the current plan runs out (see services/nextplan.py).
"""
from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import BookPlanRequest, validate_request
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.charge import start_booking_order
from app.services.flows.errors import FlowError

_ERROR_STATUS = {
    "subscription_not_found": 404,
    "unauthorized": 403,
}


async def handle_book_plan(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(BookPlanRequest, data)
    if error:
        return web.json_response(error, status=400)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        try:
            result = await start_booking_order(
                session,
                user,
                subscription_id=validated.subscription_id,
                plan_name=validated.plan_name,
                status="draft",
            )
        except FlowError as e:
            body = {"ok": False, "error": e.code, "message": str(e)}
            return web.json_response(body, status=_ERROR_STATUS.get(e.code, 400))

        resp = web.json_response({
            "ok": True,
            "order": {
                "id": result.charge_request.id,
                "subscription_id": validated.subscription_id,
                "plan_name": validated.plan_name,
                "total_price": result.charge_request.price,
                "final_price": result.final_price,
                "charge_type": "booking",
            },
        })
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
