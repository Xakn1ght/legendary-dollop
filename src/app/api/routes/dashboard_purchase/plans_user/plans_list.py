from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.settings import (
    PASARGUARD_IR_TUN_GROUP_ID,
    PAYMENT_CARD_HOLDER,
    PAYMENT_CARD_NUMBER,
    PLANS,
)
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.pricing import get_plan_info


async def handle_get_plans(request: web.Request):
    """Get available subscription plans and payment info.

    VIP-exclusive plans are only listed for VIP members (flows/pricing.py
    enforces the same rule on the money path — this is just the shop window).
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    is_vip = False
    free_test = None
    pro_test = None
    try:
        async with AsyncSessionLocal() as session:
            db_user = await crud.get_user(session, user_chat_id)
            if db_user:
                is_vip = bool(await crud.is_user_vip(session, db_user.id))
                # Trials are shown only while eligible - the button is hidden
                # on cooldown rather than relabelled (same rule as the bot).
                # start_purchase_order re-checks; this is just the shop window.
                from app.core.products import PRO_TEST_PLAN, TEST_PLAN
                from app.services.flows.free_tests import is_free_test_available

                for tier in (TEST_PLAN, PRO_TEST_PLAN):
                    if not await is_free_test_available(session, db_user, tier):
                        continue
                    info = get_plan_info(tier) or {}
                    entry = {"name": tier, "gb": info.get("gb"), "days": info.get("days")}
                    if tier == TEST_PLAN:
                        free_test = entry
                    else:
                        pro_test = entry
    except Exception:
        is_vip = False

    plans_list = []
    for name, info in PLANS.items():
        vip_only = bool(info.get("vip_only"))
        if vip_only and not is_vip:
            continue
        try:
            min_months = max(1, int(info.get("min_months") or 1))
        except Exception:
            min_months = 1
        plans_list.append(
            {
                "name": name,
                "name_en": info.get("name_en"),
                # Monthly figures — the client scales ×months for the 2/3-month
                # tabs and appends "@<n>m" to the plan name at checkout
                # (flows/pricing.py resolves and re-prices authoritatively).
                "price": info["price"],
                "gb": info["gb"],
                "days": int(info.get("days") or 35),
                "vip_only": vip_only,
                "min_months": min_months,
            }
        )

    plans_list.sort(key=lambda x: x["price"])

    resp = web.json_response(
        {
            "ok": True,
            "plans": plans_list,
            # Products that are not PLANS rows. Pro is priced per GB through
            # /custom-quote?route=pro, so only its availability lives here.
            "free_test": free_test,
            "pro_test": pro_test,
            "pro": {"available": bool(PASARGUARD_IR_TUN_GROUP_ID)},
            "payment": {"card_number": PAYMENT_CARD_NUMBER, "card_holder": PAYMENT_CARD_HOLDER},
        }
    )
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp
