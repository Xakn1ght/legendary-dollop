from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import (
    PAYMENT_CARD_HOLDER,
    PAYMENT_CARD_NUMBER,
    PLANS,
    VIP_PURCHASE_DISCOUNT_ENABLED,
    VIP_PURCHASE_DISCOUNT_PERCENT,
)
from app.database import crud
from app.database.models import AsyncSessionLocal

from .common import *  # noqa: F403


async def handle_get_charge_packages(request: web.Request):
    """Get available charge packages and payment info.

    Plan parity (2026-07-18, Pasha: "same exact plans for charge that we have
    for purchase"): the separate charge catalog is retired — a top-up IS one
    of the purchase PLANS applied to an existing sub, so this serves the same
    list as /purchase/plans. VIP-exclusive plans are only listed for VIP
    members (flows/charge.py enforces the same rule on the money path).
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
    for name, info in PLANS.items():
        vip_only = bool(info.get("vip_only"))
        if vip_only and not is_vip:
            continue
        try:
            min_months = max(1, int(info.get("min_months") or 1))
        except Exception:
            min_months = 1
        packages_list.append({
            "name": name,
            "name_en": info.get("name_en"),
            # Monthly figures — the client scales ×months and orders
            # "<name>@Nm"; flows/charge.py re-resolves authoritatively.
            "price": info.get("price", 0),
            "gb": info.get("gb", 0),
            "days": int(info.get("days") or 35),
            "vip_only": vip_only,
            "min_months": min_months,
            "discount_percent": info.get("discount_percent", 0),
            "badge_label": info.get("badge_label", None),
            "badge_type": info.get("badge_type", "event")  # event, vip, vip-tag, or custom
        })

    # Sort by price
    packages_list.sort(key=lambda x: x["price"])

    # Pricing parity law (2026-07-12): the VIP % applies to charges exactly
    # like purchases (flows/charge.py discounts the order server-side); the
    # frontends exempt vip_only bundles from displaying it.
    vip_discount_percent = (
        VIP_PURCHASE_DISCOUNT_PERCENT
        if (is_vip and VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0)
        else 0
    )

    resp = web.json_response({
        "ok": True,
        "packages": packages_list,
        "vip_discount_percent": vip_discount_percent,
        "payment": {
            "card_number": PAYMENT_CARD_NUMBER,
            "card_holder": PAYMENT_CARD_HOLDER
        }
    })
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp


