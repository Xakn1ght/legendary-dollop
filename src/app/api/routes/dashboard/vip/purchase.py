import logging
import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import PAYMENT_CARD_NUMBER, VIP_PLANS
from app.database import crud
from app.database.models import AsyncSessionLocal, VipOrder

logger = logging.getLogger(__name__)


async def handle_vip_purchase(request: web.Request):
    """Create a VIP purchase order."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    plan_id = data.get("plan_id")
    if not plan_id or plan_id not in VIP_PLANS:
        return web.json_response({"ok": False, "error": "invalid_plan"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            plan = VIP_PLANS[plan_id]

            order = VipOrder(
                user_id=user.id,
                plan_id=plan_id,
                days=plan["days"],
                price=plan["price"],
                status="draft",
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            resp = web.json_response(
                {
                    "ok": True,
                    "order_id": order.id,
                    "plan": {
                        "id": plan_id,
                        "days": plan["days"],
                        "price": plan["price"],
                        "label_fa": plan["label_fa"],
                        "label_en": plan["label_en"],
                    },
                    "card_number": PAYMENT_CARD_NUMBER,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error creating VIP order: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
