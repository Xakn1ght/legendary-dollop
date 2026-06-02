import json
import logging
import random
import string
from datetime import datetime

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_purchase.plans_user import _generate_unique_username, _is_username_taken
from app.api.schemas import StartPurchaseRequest, validate_request
from app.core.coupons import discount_price_cap as _discount_price_cap
from app.core.settings import (
    GLOBAL_PURCHASE_DISCOUNTS,
    PLANS,
    VIP_PURCHASE_DISCOUNT_ENABLED,
    VIP_PURCHASE_DISCOUNT_PERCENT,
)
from app.database import crud
from app.database.models import AsyncSessionLocal, Referral, UserDiscount

logger = logging.getLogger(__name__)


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
        discount_ids: [int] (optional, discount IDs to apply)
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

    plan_name = validated.plan
    if plan_name not in PLANS:
        return web.json_response({"ok": False, "error": "invalid_plan", "message": "Selected plan does not exist"}, status=400)

    service_name = validated.service_name or ""
    auto_renewal = validated.auto_renewal
    renewal_plan = validated.renewal_plan
    referral_code = validated.referral_code or ""
    use_credit = validated.use_credit
    discount_ids = validated.discount_ids or []
    coupon_id = validated.coupon_id

    if auto_renewal and (not renewal_plan or renewal_plan not in PLANS):
        return web.json_response({"ok": False, "error": "invalid_renewal_plan", "message": "Invalid renewal plan selected"}, status=400)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        referrer_id = None
        if referral_code:
            referrer = await crud.get_user_by_referral_code(session, referral_code)
            if not referrer:
                return web.json_response({"ok": False, "error": "invalid_referral_code", "message": "Referral code not found"}, status=400)
            if referrer.chat_id == user_chat_id:
                return web.json_response({"ok": False, "error": "cannot_use_own_code", "message": "You cannot use your own referral code"}, status=400)
            referrer_id = referrer.id
        else:
            result_ref = await session.execute(select(Referral).filter(Referral.referee_id == user.id))
            ref_row = result_ref.scalars().first()
            if ref_row:
                referrer_id = ref_row.referrer_id

        if service_name:
            if await _is_username_taken(session, service_name):
                return web.json_response({"ok": False, "error": "service_name_taken", "message": "This service name is already taken"}, status=400)
            marzban_username = service_name
        else:
            base = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            marzban_username = await _generate_unique_username(session, base)

        plan_info = PLANS[plan_name]
        initial_price = plan_info["price"]
        renewal_price = 0

        if auto_renewal and renewal_plan:
            renewal_price = PLANS[renewal_plan]["price"]

        total_price = initial_price + renewal_price

        total_discount_percent = 0
        applied_discount_ids = []

        is_vip = await crud.is_user_vip(session, user.id)
        if is_vip and VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0:
            total_discount_percent += VIP_PURCHASE_DISCOUNT_PERCENT
        for item in GLOBAL_PURCHASE_DISCOUNTS or []:
            try:
                pct = int(item.get("percent") or 0)
            except Exception:
                pct = 0
            if pct > 0:
                total_discount_percent += pct

        if discount_ids:
            discounts = await crud.get_active_user_discounts(session, user.id)
            for d in discounts:
                if d.id in discount_ids:
                    total_discount_percent += d.percent
                    applied_discount_ids.append(d.id)

        total_discount_percent = max(0, min(int(total_discount_percent), 90))

        discount_amount = 0
        if total_discount_percent > 0:
            discount_amount = int(total_price * (total_discount_percent / 100))

        # ── Season reward coupon (one per purchase, no stacking) ────────────────
        coupon = None
        coupon_discount_amount = 0
        coupon_free_gb = 0
        effective_plan_info = plan_info
        if coupon_id:
            coupon = await crud.get_coupon_by_id(session, coupon_id)
            now_cp = datetime.utcnow()
            if (
                not coupon
                or coupon.user_id != user.id
                or coupon.status != "active"
                or (coupon.expires_at and coupon.expires_at < now_cp)
            ):
                return web.json_response(
                    {"ok": False, "error": "invalid_coupon", "message": "Coupon not available"},
                    status=400,
                )
            try:
                payload = json.loads(coupon.payload or "{}")
            except Exception:
                payload = {}
            ctype = coupon.coupon_type
            if ctype == "discount_percent":
                pct = int(payload.get("discount_percent") or 0)
                cap = _discount_price_cap()
                base = min(total_price, cap) if cap > 0 else total_price
                coupon_discount_amount = int(base * (pct / 100))
            elif ctype == "free_gb":
                coupon_free_gb = int(payload.get("gb") or 0)
                if coupon_free_gb > 0:
                    effective_plan_info = {**plan_info, "gb": int(plan_info.get("gb") or 0) + coupon_free_gb}
            else:
                # free_plan / free_autorenew / vip_pack / legend_pack are not yet
                # redeemable at checkout (deferred tier) — never silently consume them.
                return web.json_response(
                    {
                        "ok": False,
                        "error": "coupon_not_supported_yet",
                        "message": "This coupon type is not yet redeemable at checkout.",
                    },
                    status=400,
                )

        discount_amount += coupon_discount_amount
        if discount_amount > total_price:
            discount_amount = total_price

        price_after_discount = total_price - discount_amount

        credit_used = 0
        if use_credit and user.credit > 0:
            credit_used = min(user.credit, price_after_discount)

        final_price = price_after_discount - credit_used

        renewal_requested_at = datetime.utcnow() if auto_renewal else None

        sub = await crud.create_subscription(
            db=session,
            user_id=user.id,
            referrer_id=referrer_id,
            marzban_username=marzban_username,
            plan=plan_name,
            receipt_message_id=None,
            renewal_paid=auto_renewal,
            renewal_template=renewal_plan if auto_renewal else None,
            renewal_price=renewal_price if auto_renewal else None,
            renewal_requested_at=renewal_requested_at,
            renewal_applied=False,
            price=plan_info["price"],
            status="draft",
        )

        sub.credit_used = credit_used
        sub.applied_discount_ids = ",".join(str(i) for i in applied_discount_ids) if applied_discount_ids else None
        sub.applied_coupon_id = coupon.id if coupon else None
        await session.commit()
        await session.refresh(sub)

        if credit_used > 0:
            await crud.deduct_credit(session, user.id, credit_used)

        if applied_discount_ids:
            await crud.mark_user_discounts_used(session, applied_discount_ids)

        if coupon:
            # Consume the coupon now (parity with discounts). Restored on cancel or
            # auto-approve failure below.
            await crud.mark_coupon_used(session, coupon.id)

        if final_price <= 0:
            auto_ok = False
            try:
                marzban_info = await crud.create_subscription_on_marzban(sub, effective_plan_info)
                if marzban_info and marzban_info.get("subscription_url"):
                    await crud.activate_subscription(session, sub.id)
                    try:
                        sub.user_link_sent = True
                        await session.commit()
                    except Exception:
                        pass
                    auto_ok = True
            except Exception as e:
                logger.error(f"Auto-approve failed for order {sub.id}: {e}")
                auto_ok = False

            if auto_ok:
                try:
                    from app.core.settings import ADMIN_ID
                    from app.utils.admin_bot_helper import get_admin_bot

                    admin_bot = get_admin_bot()
                    if admin_bot:
                        plan_gb = plan_info.get("gb", 0)
                        admin_text = (
                            "✅ خرید با اعتبار (خودکار)\n\n"
                            f"👤 کاربر: {user.full_name} ({user_chat_id})\n"
                            f"📦 پلن: {plan_name} ({plan_gb} گیگابایت)\n"
                            f"🔖 نام سرویس: {sub.marzban_username}\n"
                            f"💰 اعتبار استفاده شده: {credit_used:,} تومان\n"
                            f"🆔 شماره سفارش: #{sub.id}"
                        )
                        await admin_bot.send_message(ADMIN_ID, admin_text)
                except Exception:
                    pass

                resp_data = {
                    "ok": True,
                    "auto_approved": True,
                    "order": {
                        "id": sub.id,
                        "status": "active",
                        "plan": plan_name,
                        "plan_gb": plan_info["gb"],
                        "plan_price": initial_price,
                        "service_name": marzban_username,
                        "auto_renewal": auto_renewal,
                        "renewal_plan": renewal_plan if auto_renewal else None,
                        "renewal_price": renewal_price if auto_renewal else 0,
                        "total_price": total_price,
                        "discount_percent": total_discount_percent,
                        "discount_amount": discount_amount,
                        "coupon": ({"id": coupon.id, "type": coupon.coupon_type, "free_gb": coupon_free_gb} if coupon else None),
                        "credit_used": credit_used,
                        "final_price": 0,
                    },
                }
                resp = web.json_response(resp_data)
                if new_session_token:
                    set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
                return resp

            try:
                if credit_used > 0:
                    await crud.add_credit(session, user.id, credit_used)
                if sub.applied_coupon_id:
                    await crud.restore_coupon(session, sub.applied_coupon_id)
                if sub.applied_discount_ids:
                    try:
                        id_list = [int(x) for x in sub.applied_discount_ids.split(",") if x.strip().isdigit()]
                        if id_list:
                            res = await session.execute(select(UserDiscount).filter(UserDiscount.id.in_(id_list)))
                            discounts = res.scalars().all()
                            for d in discounts:
                                d.used = False
                    except Exception:
                        pass
                await crud.delete_subscription(session, sub.id)
            except Exception:
                pass
            return web.json_response(
                {
                    "ok": False,
                    "error": "auto_approve_failed",
                    "message": "Purchase could not be completed automatically. Please try again.",
                },
                status=502,
            )

        resp_data = {
            "ok": True,
            "order": {
                "id": sub.id,
                "plan": plan_name,
                "plan_gb": plan_info["gb"],
                "plan_price": initial_price,
                "service_name": marzban_username,
                "auto_renewal": auto_renewal,
                "renewal_plan": renewal_plan if auto_renewal else None,
                "renewal_price": renewal_price if auto_renewal else 0,
                "total_price": total_price,
                "discount_percent": total_discount_percent,
                "discount_amount": discount_amount,
                "coupon": ({"id": coupon.id, "type": coupon.coupon_type, "free_gb": coupon_free_gb} if coupon else None),
                "credit_used": credit_used,
                "final_price": final_price,
            },
        }

        resp = web.json_response(resp_data)
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
