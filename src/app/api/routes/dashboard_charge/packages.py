from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import CHARGE_PRESET_PACKAGES, PAYMENT_CARD_HOLDER, PAYMENT_CARD_NUMBER
from app.database import crud
from app.database.models import AsyncSessionLocal

from .common import *  # noqa: F403


async def handle_get_charge_packages(request: web.Request):
    """Get available charge packages and payment info.

    VIP-exclusive packages are only listed for VIP members (flows/charge.py
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

    packages_list = []
    for name, info in CHARGE_PRESET_PACKAGES.items():
        vip_only = bool(info.get("vip_only"))
        if vip_only and not is_vip:
            continue
        packages_list.append({
            "name": name,
            "price": info.get("price", 0),
            "gb": info.get("gb", 0),
            "days": info.get("days", 0),
            "vip_only": vip_only,
            "discount_percent": info.get("discount_percent", 0),
            "badge_label": info.get("badge_label", None),
            "badge_type": info.get("badge_type", "event")  # event, vip, vip-tag, or custom
        })
    
    # Sort by price
    packages_list.sort(key=lambda x: x["price"])
    
    resp = web.json_response({
        "ok": True,
        "packages": packages_list,
        "payment": {
            "card_number": PAYMENT_CARD_NUMBER,
            "card_holder": PAYMENT_CARD_HOLDER
        }
    })
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp


