import logging

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import StartPurchaseRequest, validate_request
from app.database import crud
from app.database.models import AsyncSessionLocal, Referral
from app.services.flows.errors import FlowError
from app.services.flows.pricing import get_plan_info as _get_plan_info
from app.services.flows.pricing import quote_purchase
from app.services.flows.purchase import start_purchase_order

logger = logging.getLogger(__name__)

# FlowError code → HTTP status; everything else maps to 400.
_ERROR_STATUS = {
    "auto_approve_failed": 502,
}


async def handle_start_purchase(request: web.Request):
    """
    Start a purchase order.
    Body: {
        plan: string (plan name),
        service_name: string (optional, will generate random if not provided),
        auto_renewal: boolean,
        renewal_plan: string (optional, required if auto_renewal is true),
        referral_code: string (optional),
        use_credit: boolean,
        discount_ids: [int] (optional, discount IDs to apply),
        coupon_id: int (optional)
    }
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(StartPurchaseRequest, data)
    if error:
        return web.json_response(error, status=400)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        referrer_id = None
        if validated.referral_code:
            referrer = await crud.get_user_by_referral_code(session, validated.referral_code)
            if not referrer:
                return web.json_response(
                    {"ok": False, "error": "invalid_referral_code", "message": "Referral code not found"}, status=400
                )
            if referrer.chat_id == user_chat_id:
                return web.json_response(
                    {"ok": False, "error": "cannot_use_own_code", "message": "You cannot use your own referral code"},
                    status=400,
                )
            referrer_id = referrer.id
        else:
            result_ref = await session.execute(select(Referral).filter(Referral.referee_id == user.id))
            ref_row = result_ref.scalars().first()
            if ref_row:
                referrer_id = ref_row.referrer_id

        try:
            quote = await quote_purchase(
                session,
                user,
                plan_name=validated.plan,
                renewal_plan=validated.renewal_plan if validated.auto_renewal else None,
                discount_ids=validated.discount_ids or [],
                coupon_id=validated.coupon_id,
                use_credit=validated.use_credit,
            )

            from app.utils.admin_bot_helper import get_user_bot

            result = await start_purchase_order(
                session,
                user,
                quote=quote,
                service_name=validated.service_name or None,
                referrer_id=referrer_id,
                auto_renewal=validated.auto_renewal,
                bot=get_user_bot(),
            )
        except FlowError as e:
            return web.json_response(
                {"ok": False, "error": e.code, "message": str(e)},
                status=_ERROR_STATUS.get(e.code, 400),
            )

        sub = result.subscription
        if result.auto_approved:
            try:
                from app.core.settings import ADMIN_ID
                from app.utils.admin_bot_helper import get_admin_bot

                admin_bot = get_admin_bot()
                if admin_bot:
                    plan_gb = (_get_plan_info(quote.plan_name) or {}).get("gb", 0)
                    admin_text = (
                        "خرید با اعتبار (خودکار)\n\n"
                        f"کاربر: {user.full_name} ({user_chat_id})\n"
                        f"پلن: {quote.plan_name} ({plan_gb} گیگابایت)\n"
                        f"نام سرویس: {sub.marzban_username}\n"
                        f"اعتبار استفاده شده: {quote.credit_used:,} تومان\n"
                        f"شماره سفارش: #{sub.id}"
                    )
                    await admin_bot.send_message(ADMIN_ID, admin_text)
            except Exception:
                pass

        order_payload = {
            "id": sub.id,
            "plan": quote.plan_name,
            "plan_gb": _get_plan_info(quote.plan_name)["gb"],
            "plan_price": quote.plan_price,
            "service_name": sub.marzban_username,
            "auto_renewal": validated.auto_renewal,
            "renewal_plan": quote.renewal_plan,
            "renewal_price": quote.renewal_price,
            "total_price": quote.base_total,
            "discount_percent": quote.discount_percent,
            "discount_amount": quote.discount_amount,
            "coupon": (
                {"id": quote.coupon.id, "type": quote.coupon.coupon_type, "free_gb": quote.coupon.free_gb}
                if quote.coupon
                else None
            ),
            "credit_used": quote.credit_used,
            "final_price": max(0, quote.final_price),
        }
        resp_data = {"ok": True, "order": order_payload}
        if result.auto_approved:
            resp_data["auto_approved"] = True
            order_payload["status"] = "active"

        resp = web.json_response(resp_data)
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
