import logging

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import PAYMENT_CARD_NUMBER, VIP_PLANS
from app.database import crud
from app.database.models import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def handle_vip_plans(request: web.Request):
    """Get available VIP plans with pricing."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            is_vip = await crud.is_user_vip(session, user.id)
            vip_until = user.vip_until.isoformat() if user.vip_until else None

            plans = []
            for plan_id, plan_data in VIP_PLANS.items():
                plans.append(
                    {
                        "id": plan_id,
                        "days": plan_data["days"],
                        "price": plan_data["price"],
                        "label_fa": plan_data["label_fa"],
                        "label_en": plan_data["label_en"],
                        "is_lifetime": plan_data["days"] is None,
                    }
                )

            resp = web.json_response(
                {
                    "ok": True,
                    "is_vip": is_vip,
                    "vip_until": vip_until,
                    "plans": plans,
                    "card_number": PAYMENT_CARD_NUMBER,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        logger.error(f"Error fetching VIP plans: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
