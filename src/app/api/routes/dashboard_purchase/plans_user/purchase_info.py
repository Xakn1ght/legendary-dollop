from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import (
    GLOBAL_PURCHASE_DISCOUNTS,
    VIP_PURCHASE_DISCOUNT_ENABLED,
    VIP_PURCHASE_DISCOUNT_PERCENT,
)
from app.database import crud
from app.database.models import AsyncSessionLocal, Referral


async def handle_get_user_purchase_info(request: web.Request):
    """Get user info for purchase (credit, discounts, referral status)"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        result_ref = await session.execute(select(Referral).filter(Referral.referee_id == user.id))
        has_referrer = result_ref.scalars().first() is not None

        # OG customers (pre-referral-era allowlist) never need an invite code —
        # the webapp hides the referral field for them.
        try:
            from app.handlers.user.start.common import _is_og_user

            is_og = _is_og_user(user_chat_id, getattr(user, "username", None))
        except Exception:
            is_og = False

        discounts = await crud.get_active_user_discounts(session, user.id)
        discount_list = []
        for d in discounts:
            discount_list.append({"id": d.id, "percent": d.percent, "source": d.source})

        is_vip = await crud.is_user_vip(session, user.id)
        auto_discounts = []
        if is_vip and VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0:
            auto_discounts.append(
                {
                    "type": "vip",
                    "percent": VIP_PURCHASE_DISCOUNT_PERCENT,
                    "label_en": "VIP",
                    "label_fa": "VIP",
                }
            )
        for item in GLOBAL_PURCHASE_DISCOUNTS or []:
            try:
                pct = int(item.get("percent") or 0)
            except Exception:
                pct = 0
            if pct <= 0:
                continue
            auto_discounts.append(
                {
                    "type": "event",
                    "percent": pct,
                    "label_en": str(item.get("label_en") or "Discount"),
                    "label_fa": str(item.get("label_fa") or "تخفیف"),
                }
            )

        info = {
            "credit": user.credit,
            "has_referrer": has_referrer,
            "is_og": is_og,
            "discounts": discount_list,
            "is_vip": is_vip,
            "auto_discounts": auto_discounts,
        }

        resp = web.json_response({"ok": True, "info": info})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
