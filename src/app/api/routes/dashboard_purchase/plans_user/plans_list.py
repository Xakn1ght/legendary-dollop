from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import PAYMENT_CARD_HOLDER, PAYMENT_CARD_NUMBER, PLANS


async def handle_get_plans(request: web.Request):
    """Get available subscription plans and payment info"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    plans_list = []
    for name, info in PLANS.items():
        plans_list.append({"name": name, "price": info["price"], "gb": info["gb"]})

    plans_list.sort(key=lambda x: x["price"])

    resp = web.json_response(
        {
            "ok": True,
            "plans": plans_list,
            "payment": {"card_number": PAYMENT_CARD_NUMBER, "card_holder": PAYMENT_CARD_HOLDER},
        }
    )
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp
