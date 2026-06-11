"""Shared charge (top-up) flow: create / cancel / receipt / approve / deny.

Replaces the duplicated implementations in ``handlers/user/charge`` +
``handlers/admin/charge/approve.py`` (bot) and ``api/routes/dashboard_charge`` +
``api/routes/admin/receipts/charge_actions`` (webapp/panel).

Money rules:
- wallet credit reserved at order creation is recorded on ``ChargeRequest.credit_used``
  and refunded on cancel/deny;
- auto-renew intent is stored on the ChargeRequest and applied to the subscription
  only at approval — never before the payment is verified;
- approval requires an active subscription and grants referral rewards (the admin
  panel previously skipped both — that was drift, not policy).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import CHARGE_PRESET_PACKAGES, PLANS
from app.database import crud, notifications_crud
from app.database.models import ChargeRequest, Subscription
from app.database.models import User as _User
from app.services.flows.errors import FlowError
from app.services.marzban import marzban_api

logger = logging.getLogger(__name__)

GB = 1024 * 1024 * 1024
TRAFFIC_GATE_GB = 5

_REFUNDABLE_STATUSES = ("draft", "pending")


@dataclass
class ChargeOrderResult:
    charge_request: ChargeRequest
    remaining_gb: float
    credit_used: int
    final_price: int


@dataclass
class ApproveChargeResult:
    charge_request: ChargeRequest
    subscription: Subscription
    user: _User
    added_gb: float
    extra_days: int | None
    carry_bytes: int
    lost_bytes: int
    is_5gb_limit_charge: bool


@dataclass
class DenyChargeResult:
    user_id: int
    credit_refunded: int
    service_name: str | None


async def start_charge_order(
    session: AsyncSession,
    user,
    *,
    subscription_id: int,
    package_name: str,
    charge_type: str = "normal",
    use_credit: bool = False,
    renewal_template: str | None = None,
    status: str = "draft",
) -> ChargeOrderResult:
    """Create a charge order for one of the preset packages.

    ``status="draft"`` is the webapp flow (receipt uploaded in a second step);
    the bot attaches its Telegram receipt immediately and passes ``status="pending"``
    via :func:`submit_charge_receipt` instead.
    """
    if package_name not in CHARGE_PRESET_PACKAGES:
        raise FlowError("invalid_package", "Selected package does not exist")
    if renewal_template is not None and renewal_template not in PLANS:
        raise FlowError("invalid_renewal_plan", "Invalid renewal plan selected")

    sub = await session.get(Subscription, subscription_id)
    if not sub:
        raise FlowError("subscription_not_found")
    if sub.user_id != user.id:
        raise FlowError("unauthorized")
    if sub.status != "active":
        raise FlowError("subscription_not_active")

    user_info = await marzban_api.get_user_info(sub.marzban_username)
    if not user_info:
        raise FlowError("failed_to_fetch_traffic", "Could not fetch subscription status from server")

    data_limit = user_info.get("data_limit", 0) or 0
    used_traffic = user_info.get("used_traffic", 0) or 0
    remaining_gb = max(data_limit - used_traffic, 0) / GB

    if remaining_gb > TRAFFIC_GATE_GB and charge_type == "normal":
        err = FlowError("traffic_above_5gb", "You have more than 5GB remaining. Please choose an option.")
        err.remaining_gb = remaining_gb
        raise err

    pkg = CHARGE_PRESET_PACKAGES[package_name]
    total_price = int(pkg.get("price", 0) or 0)
    traffic_bytes = int(pkg.get("gb", 0) or 0) * GB
    extra_days = pkg.get("days", 0) or None

    credit_used = 0
    if use_credit and (user.credit or 0) > 0:
        credit_used = min(int(user.credit or 0), total_price)

    renewal_price = int(PLANS[renewal_template].get("price") or 0) if renewal_template else None

    charge_req = await crud.create_charge_request(
        session,
        subscription_id,
        user.id,
        traffic_bytes,
        extra_days,
        total_price,
        receipt_message_id=None,
        credit_used=credit_used,
        charge_type=charge_type,
        renewal_template=renewal_template,
        renewal_price=renewal_price,
        status=status,
    )

    if credit_used > 0:
        if await crud.deduct_credit(session, user.id, credit_used) is None:
            await session.delete(charge_req)
            await session.commit()
            raise FlowError("insufficient_credit", "Not enough credit")

    return ChargeOrderResult(
        charge_request=charge_req,
        remaining_gb=remaining_gb,
        credit_used=credit_used,
        final_price=total_price - credit_used,
    )


async def start_booking_order(
    session: AsyncSession,
    user,
    *,
    subscription_id: int,
    plan_name: str,
    status: str = "draft",
) -> ChargeOrderResult:
    """Create a plan-booking order: the renewal intent is stored on the ChargeRequest
    and applied to the subscription only when an admin approves the payment.

    (Previously both surfaces set renewal_paid=True immediately — the bot without
    any payment step at all.)
    """
    if plan_name not in PLANS:
        raise FlowError("invalid_plan", "Selected plan does not exist")

    sub = await session.get(Subscription, subscription_id)
    if not sub:
        raise FlowError("subscription_not_found")
    if sub.user_id != user.id:
        raise FlowError("unauthorized")
    if sub.status != "active":
        raise FlowError("subscription_not_active")

    plan_info = PLANS[plan_name]
    price = int(plan_info.get("price") or 0)

    charge_req = await crud.create_charge_request(
        session,
        subscription_id,
        user.id,
        0,  # traffic applied later by the renewal job, not at approval
        None,
        price,
        receipt_message_id=None,
        credit_used=0,
        charge_type="booking",
        renewal_template=plan_name,
        renewal_price=price,
        status=status,
    )

    return ChargeOrderResult(charge_request=charge_req, remaining_gb=0.0, credit_used=0, final_price=price)


async def cancel_charge_order(session: AsyncSession, user, order_id: int) -> int:
    """Cancel an unreceipted charge order; returns the credit amount refunded."""
    charge_req = await session.get(ChargeRequest, order_id)
    if not charge_req:
        raise FlowError("order_not_found")
    if charge_req.user_id != user.id:
        raise FlowError("unauthorized")
    if charge_req.receipt_message_id is not None or charge_req.status not in _REFUNDABLE_STATUSES:
        raise FlowError("cannot_cancel")

    refunded = int(charge_req.credit_used or 0)
    if refunded > 0:
        await crud.add_credit(session, user.id, refunded)
    await session.delete(charge_req)
    await session.commit()
    return refunded


async def submit_charge_receipt(
    session: AsyncSession,
    user,
    order_id: int,
    *,
    receipt_message_id: int | None = None,
    receipt_image_url: str | None = None,
) -> ChargeRequest:
    """Attach a payment receipt to a charge order; rejects double submission."""
    charge_req = await session.get(ChargeRequest, order_id)
    if not charge_req:
        raise FlowError("order_not_found")
    if charge_req.user_id != user.id:
        raise FlowError("unauthorized")
    if charge_req.status not in _REFUNDABLE_STATUSES or charge_req.receipt_message_id is not None:
        raise FlowError("order_already_processed")

    charge_req.receipt_message_id = receipt_message_id if receipt_message_id is not None else -1
    if receipt_image_url:
        charge_req.receipt_image_url = receipt_image_url
    charge_req.status = "pending"
    await session.commit()
    await session.refresh(charge_req)
    return charge_req


async def deny_charge(session: AsyncSession, charge_id: int) -> DenyChargeResult:
    """Admin denial: refund reserved credit and mark the request denied."""
    charge_req = await crud.get_charge_request(session, charge_id)
    if not charge_req or charge_req.status != "pending":
        raise FlowError("not_found_or_handled")

    sub = await session.get(Subscription, charge_req.subscription_id)
    service_name = sub.marzban_username if sub else None
    user_id = charge_req.user_id
    refunded = int(charge_req.credit_used or 0)
    if refunded > 0:
        await crud.add_credit(session, user_id, refunded)
    await crud.update_charge_request_status(session, charge_id, "denied")
    return DenyChargeResult(
        user_id=user_id,
        credit_refunded=refunded,
        service_name=service_name,
    )


async def approve_charge(session: AsyncSession, charge_id: int, *, user_bot) -> ApproveChargeResult:
    """Approve a pending charge: apply the carry-over math on Marzban, persist the
    new state, apply any auto-renew intent, grant referral rewards, and notify the
    user. ``user_bot`` is the user-facing Telegram bot (DMs the customer/referrer).

    This is the single implementation of the carry-over rules previously duplicated
    between the admin bot handler and the admin panel route.
    """
    charge_req = await crud.get_charge_request(session, charge_id)
    if not charge_req or charge_req.status != "pending":
        raise FlowError("not_found_or_handled")

    await session.refresh(charge_req, attribute_names=["subscription", "user"])
    sub = charge_req.subscription
    user = charge_req.user

    if not sub or not sub.marzban_username:
        raise FlowError("sub_invalid")
    if not user:
        raise FlowError("user_missing")
    if sub.status != "active":
        raise FlowError("sub_inactive")

    if getattr(charge_req, "charge_type", "normal") == "booking":
        # A booking only records paid renewal intent — the plan itself is applied by
        # the renewal job later. No Marzban change now (traffic_bytes is 0; running
        # the carry-over math would wipe the user's data limit).
        await crud.update_charge_request_status(session, charge_id, "approved")
        await crud.update_subscription_renewal(
            session,
            sub.id,
            renewal_paid=True,
            renewal_template=charge_req.renewal_template,
            renewal_price=charge_req.renewal_price,
            renewal_requested_at=datetime.utcnow(),
        )
        result = ApproveChargeResult(
            charge_request=charge_req,
            subscription=sub,
            user=user,
            added_gb=0.0,
            extra_days=None,
            carry_bytes=0,
            lost_bytes=0,
            is_5gb_limit_charge=False,
        )
        if user_bot is not None:
            try:
                await user_bot.send_message(
                    user.chat_id,
                    f"✅ رزرو پلن «{charge_req.renewal_template}» تایید شد و در زمان تمدید اعمال می‌شود.",
                )
            except Exception as e:
                logger.error(f"Failed to DM booking approval to user {user.chat_id}: {e}")
        return result

    user_info = await marzban_api.get_user_info(sub.marzban_username)
    if not user_info:
        raise FlowError("marzban_fetch_failed")

    now_ts = datetime.utcnow().timestamp()
    expire_ts = user_info.get("expire", 0) or 0
    data_limit_current = user_info.get("data_limit", 0) or 0
    used_traffic = user_info.get("used_traffic", 0) or 0
    remaining_bytes_current = max(data_limit_current - used_traffic, 0)

    expired = bool(expire_ts and expire_ts < now_ts)
    traffic_exhausted = remaining_bytes_current == 0
    subscription_ended = expired or traffic_exhausted

    data_limit_after = data_limit_current
    reset_usage = False
    new_expire_ts = expire_ts or 0
    carry_bytes = 0
    lost_bytes = 0
    reset_at = None

    add_days_only = bool(charge_req.extra_days) and not (charge_req.traffic_bytes and charge_req.traffic_bytes > 0)
    is_5gb_limit_charge = getattr(charge_req, "charge_type", "normal") == "normal_5gb_limit"

    if add_days_only:
        base = now_ts if expired else (expire_ts or now_ts)
        new_expire_ts = int(base + charge_req.extra_days * 24 * 3600)
    elif subscription_ended:
        if charge_req.traffic_bytes and charge_req.traffic_bytes > 0:
            data_limit_after = int(charge_req.traffic_bytes)
            reset_usage = True
        if charge_req.extra_days:
            base = now_ts if expired else (expire_ts or now_ts)
            new_expire_ts = int(base + charge_req.extra_days * 24 * 3600)
    else:
        remaining = remaining_bytes_current
        if is_5gb_limit_charge:
            carry_bytes = min(remaining, TRAFFIC_GATE_GB * GB)
            lost_bytes = max(0, remaining - TRAFFIC_GATE_GB * GB)
            data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
            reset_usage = True
            if charge_req.extra_days:
                new_expire_ts = int(now_ts + charge_req.extra_days * 24 * 3600)
        elif remaining <= TRAFFIC_GATE_GB * GB:
            carry_bytes = remaining if (charge_req.traffic_bytes and charge_req.traffic_bytes > 0) else 0
            data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
            reset_usage = True
            if charge_req.extra_days:
                new_expire_ts = int((expire_ts or now_ts) + charge_req.extra_days * 24 * 3600)
        else:
            carry_bytes = min(remaining, TRAFFIC_GATE_GB * GB) if (charge_req.traffic_bytes and charge_req.traffic_bytes > 0) else 0
            lost_bytes = max(0, remaining - TRAFFIC_GATE_GB * GB)
            data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
            reset_usage = True
            if charge_req.extra_days:
                new_expire_ts = int((expire_ts or now_ts) + charge_req.extra_days * 24 * 3600)

    if reset_usage:
        ok = await marzban_api.reset_user_traffic_bytes(
            sub.marzban_username,
            new_data_limit_bytes=int(data_limit_after or 0),
            new_expire_ts=int(new_expire_ts or 0),
        )
        if not ok:
            raise FlowError("marzban_reset_failed")
    else:
        session_http = await marzban_api._get_session()
        headers = await marzban_api._get_headers()
        url = f"{marzban_api.base_url}/api/user/{sub.marzban_username}"
        patch_body = {
            "data_limit": int(data_limit_after or 0),
            "expire": int(new_expire_ts or 0),
            "status": "active",
            "data_limit_reset_strategy": "no_reset",
        }
        async with session_http.put(url, headers=headers, json=patch_body) as resp:
            if resp.status not in (200, 204):
                raise FlowError("marzban_update_failed")

    await crud.set_subscription_carry_over(session, sub.id, carry_bytes, reset_at)
    await crud.update_charge_request_status(session, charge_id, "approved")

    # Auto-renew intent becomes real only now that the payment is verified.
    if getattr(charge_req, "renewal_template", None):
        await crud.update_subscription_renewal(
            session,
            sub.id,
            renewal_paid=True,
            renewal_template=charge_req.renewal_template,
            renewal_price=charge_req.renewal_price,
            renewal_requested_at=datetime.utcnow(),
        )

    # The reward itself must not depend on a bot being available — only the DM does.
    if sub.referrer_id:
        try:
            await _grant_charge_referral_reward(session, charge_req, sub, user_bot)
        except Exception as e:
            logger.error(f"Failed to grant referral reward for charge {charge_id}: {e}")

    result = ApproveChargeResult(
        charge_request=charge_req,
        subscription=sub,
        user=user,
        added_gb=(charge_req.traffic_bytes or 0) / GB,
        extra_days=charge_req.extra_days,
        carry_bytes=carry_bytes,
        lost_bytes=lost_bytes,
        is_5gb_limit_charge=is_5gb_limit_charge,
    )

    await _notify_user_charge_approved(session, result, user_bot)
    return result


async def _grant_charge_referral_reward(session: AsyncSession, charge_req: ChargeRequest, sub: Subscription, user_bot) -> None:
    cfg = await crud.get_reward_config(session)
    result_ref = await session.execute(select(_User).filter(_User.id == sub.referrer_id))
    ref_user = result_ref.scalars().first()
    if not ref_user:
        return

    traffic_reward_bytes = None
    extra_days_reward = None
    credit_reward_amount = None

    if charge_req.traffic_bytes and charge_req.traffic_bytes > 0 and cfg.traffic_percent:
        traffic_reward_bytes = int(charge_req.traffic_bytes * cfg.traffic_percent / 100)

    if charge_req.extra_days and charge_req.extra_days > 0 and cfg.days_percent is not None:
        extra_days_calc = int(charge_req.extra_days * cfg.days_percent / 100)
        extra_days_reward = max(1, extra_days_calc) if extra_days_calc else None
    elif charge_req.traffic_bytes and charge_req.traffic_bytes > 0 and cfg.days_percent is not None:
        default_days = 30
        extra_days_calc = int(default_days * cfg.days_percent / 100)
        extra_days_reward = max(1, extra_days_calc) if extra_days_calc else None

    if cfg.credit_percent and cfg.credit_percent > 0:
        credit_reward_amount = int(charge_req.price * cfg.credit_percent / 100)

    if not (traffic_reward_bytes or extra_days_reward or credit_reward_amount):
        return

    from app.core.rewards_config import (
        MAX_STARS_PER_REFERRED_PURCHASE,
        MIN_REFERRAL_STAR_PLAN_GB,
        REFERRAL_BONUS_XP,
    )

    traffic_bytes = int(charge_req.traffic_bytes or 0)
    # Season-star option, only for qualifying (>=20GB) charges; capped at 2.
    star_increment = 0
    if traffic_bytes >= MIN_REFERRAL_STAR_PLAN_GB * GB:
        star_increment = min(traffic_bytes // (20 * GB), MAX_STARS_PER_REFERRED_PURCHASE)

    reward = await crud.create_referral_reward(
        db=session,
        subscription_id=sub.id,
        referrer_id=sub.referrer_id,
        traffic_bytes=traffic_reward_bytes,
        extra_days=extra_days_reward,
        credit_amount=credit_reward_amount,
        reward_value=star_increment or None,
        stars=star_increment or None,
    )

    # +50 XP to the referrer regardless of which reward they pick.
    try:
        await crud.add_experience_points(session, ref_user.id, REFERRAL_BONUS_XP, "referral")
    except Exception:
        pass

    from app.keyboards.inline import get_enhanced_reward_voucher_keyboard

    kb_reward = get_enhanced_reward_voucher_keyboard(
        reward.id,
        extra_gb=(traffic_reward_bytes or 0) / GB if traffic_reward_bytes else None,
        extra_days=extra_days_reward,
        credit_amount=credit_reward_amount,
        stars_progress=ref_user.stars,
        star_increment=star_increment,
        show_star=star_increment > 0,
        show_enhanced_stars=False,
    )

    desc_parts = []
    if charge_req.traffic_bytes:
        desc_parts.append(f"+{(charge_req.traffic_bytes / GB):.0f}GB")
    if charge_req.extra_days:
        desc_parts.append(f"+{charge_req.extra_days}D")
    purchase_desc = " & ".join(desc_parts) or "شارژ"

    if user_bot is None:
        logger.warning(f"Referral reward {reward.id} granted without DM (user bot unavailable)")
        return
    try:
        await user_bot.send_message(
            ref_user.chat_id,
            (
                "🎉 کاربر جدیدی که با کد شما عضو شده بود سرویس خود را شارژ کرد!\n"
                f"مقدار شارژ: {purchase_desc}\n"
                "🎁 پاداش آماده است – یکی را انتخاب کنید:"
            ),
            reply_markup=kb_reward,
        )
    except Exception as e:
        logger.error(f"Could not notify referrer {sub.referrer_id} about charge reward: {e}")


async def _notify_user_charge_approved(session: AsyncSession, result: ApproveChargeResult, user_bot) -> None:
    sub = result.subscription
    user = result.user

    if user_bot is not None:
        msg_lines = ["✅ شارژ سرویس شما تایید شد و اعمال گردید."]
        if result.added_gb:
            msg_lines.append(f"🔸 حجم افزوده‌شده: {result.added_gb:.0f} GB")
        if result.extra_days:
            msg_lines.append(f"🔸 روزهای افزوده‌شده: {result.extra_days} روز")
        if result.carry_bytes:
            msg_lines.append(f"🔹 ترافیک منتقل‌شده از دوره قبل: {result.carry_bytes / GB:.1f} GB")
        if result.lost_bytes and result.lost_bytes > 0:
            if result.is_5gb_limit_charge:
                msg_lines.append(f"⚠️ بر اساس انتخاب شما، {result.lost_bytes / GB:.1f} GB بیش از حد 5GB حذف شد.")
            else:
                msg_lines.append(f"⚠️ {result.lost_bytes / GB:.1f} GB به حد مجاز انتقال کاهش یافت.")

        try:
            from aiogram.utils.keyboard import InlineKeyboardBuilder

            kb = InlineKeyboardBuilder()
            kb.button(text="🔍 مدیریت اشتراک", callback_data=f"svc_{sub.id}")
            kb.adjust(1)
            await user_bot.send_message(user.chat_id, "\n".join(msg_lines), reply_markup=kb.as_markup())
        except Exception as e:
            logger.error(f"Failed to DM charge approval to user {user.chat_id}: {e}")

    try:
        message = (
            f"✅ Charge approved for {sub.marzban_username}.\n"
            f"Added: {result.added_gb:.0f}GB"
            + (f", +{result.extra_days} days" if result.extra_days else "")
            + (f", carried: {(result.carry_bytes / GB):.1f}GB" if result.carry_bytes else "")
        )
        await notifications_crud.create_notification(
            session,
            user_id=user.id,
            type="charge_approved",
            title="Charge approved",
            message=message,
            sent_to_webapp=True,
            sent_to_bot=False,
        )
    except Exception:
        pass
