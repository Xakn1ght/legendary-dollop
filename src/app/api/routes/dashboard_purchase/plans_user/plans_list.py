from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import PAYMENT_CARD_HOLDER, PAYMENT_CARD_NUMBER, PLANS
from app.database import crud
from app.database.models import AsyncSessionLocal


async def handle_get_plans(request: web.Request):
    """Get available subscription plans and payment info.

    VIP-exclusive plans are only listed for VIP members (flows/pricing.py
    enforces the same rule on the money path — this is just the shop window).
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    is_vip = False
    try:
        async with AsyncSessionLocal() as session:
            db_user = await crud.get_user(session, user_chat_id)
            if db_user:
                is_vip = bool(await crud.is_user_vip(session, db_user.id))
    except Exception:
        is_vip = False

    plans_list = []
    for name, info in PLANS.items():
        vip_only = bool(info.get("vip_only"))
        if vip_only and not is_vip:
            continue
        plans_list.append(
            {
                "name": name,
                "name_en": info.get("name_en"),
                "price": info["price"],
                "gb": info["gb"],
                "vip_only": vip_only,
            }
        )

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
