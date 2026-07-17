from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID
from app.database import crud


async def extend_vip_window(session: AsyncSession, user, days: int) -> None:
    """Extend the user's VIP window by ``days`` (activating VIP if needed).
    Shared by admin VIP approval side-paths and the vip_days coupon redemption."""
    if not user or days <= 0:
        return
    now = datetime.utcnow()
    base = user.vip_until if (user.vip_until and user.vip_until > now) else now
    user.is_vip = True
    user.vip_until = base + timedelta(days=days)  # extend, don't overwrite
    await session.commit()


async def process_approved_subscription(sub_id: int, session: AsyncSession, bot: Bot, approved_by: str | None = None) -> bool:
    """
    Handles all logic for an approved subscription, whether by admin or auto-approved (e.g., via credit).
    Returns True on success, False on failure.

    ``bot`` must be the **user** Telegram bot (``BOT_TOKEN``): it sends DMs with subscription links.
    When approving from AstroAdmin, use ``get_user_bot()`` — not the admin bot instance.
    ``approved_by`` names who approved (admin display name / "سیستم …") for the
    verified stamp edited onto the admin receipt card.
    """
    from app.database.models import Subscription
    from app.database.models import User as _User

    async def _cleanup_admin_messages(sub: Subscription) -> None:
        """Approved receipts stay in the admin chat as an audit trail
        (2026-07-13, Pasha: "after accepting ... doesnt delete it, only edit
        its caption as verified by admin"): rebuild the structured caption
        from DB state, append the verified stamp, drop the buttons."""
        from app.core.settings import PLANS
        from app.utils.admin_bot_helper import get_admin_bot
        from app.utils.receipt_captions import purchase_receipt_caption, verified_stamp

        admin_bot = get_admin_bot()
        if not admin_bot:
            return

        try:
            receipt_user = await session.get(_User, sub.user_id)
            caption = purchase_receipt_caption(sub, receipt_user, source="bot", plans=PLANS)
            caption = f"{caption}\n\n{verified_stamp(approved_by)}"
        except Exception:
            caption = f"رسید خرید — سفارش #{sub.id}\n\n{verified_stamp(approved_by)}"

        # Both columns usually point at the SAME combined photo+buttons message.
        msg_ids = []
        for attr in ("admin_request_message_id", "admin_receipt_forward_message_id"):
            mid = getattr(sub, attr, None)
            if mid and int(mid) not in msg_ids:
                msg_ids.append(int(mid))
        for mid in msg_ids:
            try:
                await admin_bot.edit_message_caption(
                    chat_id=ADMIN_ID, message_id=mid, caption=caption, reply_markup=None,
                )
            except Exception:
                try:
                    await admin_bot.edit_message_text(
                        caption, chat_id=ADMIN_ID, message_id=mid, reply_markup=None,
                    )
                except Exception:
                    pass

    subscription: Subscription | None = await session.get(Subscription, sub_id)
    if not subscription:
        logging.error(f"Could not find subscription {sub_id} to process approval.")
        return False

    if subscription.status == "active" and getattr(subscription, "user_link_sent", False):
        await _cleanup_admin_messages(subscription)
        return True

    # Only a row we ATOMICALLY move pending→active here may be provisioned. This
    # guard closes the approve-vs-deny race: if a concurrent deny already claimed
    # the row (status 'processing'/'denied' or the row is gone), we must NOT fall
    # through to PasarGuard provisioning — otherwise we'd build a service for an
    # order that deny is simultaneously refunding and deleting.
    if subscription.status != "pending":
        logging.warning(f"Sub {sub_id} not pending (status={subscription.status}); refusing to provision.")
        return False
    try:
        res = await session.execute(
            update(Subscription)
            .where(Subscription.id == sub_id, Subscription.status == "pending")
            .values(status="active")
        )
        await session.commit()
        if getattr(res, "rowcount", 0) == 0:
            # lost the claim — only a no-op success if it's already fully provisioned
            subscription = await session.get(Subscription, sub_id)
            if subscription and subscription.status == "active" and getattr(subscription, "user_link_sent", False):
                await _cleanup_admin_messages(subscription)
                return True
            return False
    except Exception:
        logging.exception(f"Sub {sub_id}: failed to claim pending→active")
        return False

    result = await session.execute(select(_User).filter(_User.id == subscription.user_id))
    user = result.scalar_one_or_none()
    if not user:
        logging.error(f"Could not find user for subscription {sub_id}")
        return False

    from app.services.flows.pricing import get_plan_info
    plan_info = get_plan_info(subscription.plan_name)
    if not plan_info:
        logging.error(f"Unknown plan {subscription.plan_name} for subscription {sub_id}")
        return False

    # Apply a free_gb season coupon's bonus GB at provisioning so receipt/admin-approved
    # orders get the same bonus the webapp auto-approve path applies.
    try:
        bonus_gb = await crud.free_gb_bonus_for_coupon(session, getattr(subscription, "applied_coupon_id", None))
        if bonus_gb > 0:
            plan_info = {**plan_info, "gb": int(plan_info.get("gb") or 0) + int(bonus_gb)}
    except Exception:
        pass

    # Reward free-plan orders (fully coupon-paid, zero toman moved) provision
    # as on_hold — the plan's days start at the user's FIRST CONNECT, so an
    # unused gift never quietly burns down. Paid orders are never on_hold.
    try:
        coupon = await crud.get_coupon_by_id(session, getattr(subscription, "applied_coupon_id", None))
        fully_free = int(getattr(subscription, "paid_amount", None) or getattr(subscription, "price", 0) or 0) == 0
        if coupon and coupon.coupon_type == "free_plan" and fully_free:
            plan_info = {**plan_info, "on_hold": True}
    except Exception:
        pass

    try:
        pasarguard_user = await crud.create_subscription_on_pasarguard(subscription, plan_info)
    except Exception as e:
        logging.error(f"Failed to create PasarGuard user for sub {sub_id}: {e}")
        await crud.deactivate_subscription_on_failure(session, sub_id)
        try:
            await bot.send_message(
                user.chat_id,
                "متاسفانه در ساخت سرویس شما مشکلی پیش آمده. لطفاً مجدداً تلاش کنید یا به پشتیبانی پیام دهید.",
            )
        except Exception as notify_error:
            logging.error(f"Failed to notify user {user.chat_id} about panel failure: {notify_error}")
        return False

    sub_url = pasarguard_user.get("subscription_url") if pasarguard_user else None
    if not sub_url:
        await crud.deactivate_subscription_on_failure(session, sub_id)
        try:
            await bot.send_message(
                user.chat_id,
                "متاسفانه در دریافت لینک اشتراک شما مشکلی پیش آمده. لطفاً به پشتیبانی پیام دهید.",
            )
        except Exception as notify_error:
            logging.error(f"Failed to notify user {user.chat_id} about URL failure: {notify_error}")
        return False

    # Persist the share-link token NOW (it used to happen after the DM block,
    # whose failure path returns early — losing the token and forcing the next
    # read back onto the admin API). Creation already returned the link; no
    # extra panel call ever needed for it again.
    try:
        token_match = re.search(r"/sub/([^/]+)/?", sub_url)
        if token_match and not getattr(subscription, "sub_token", None):
            subscription.sub_token = token_match.group(1)
            await session.commit()
    except Exception:
        pass

    # A purchase with auto-renewal reserved arms the panel's native next_plan
    # right at provisioning; it fires panel-side when the plan runs out. Failure
    # is non-fatal — the renewal watchdog re-arms on its next sweep.
    if getattr(subscription, "renewal_paid", False) and getattr(subscription, "renewal_template", None):
        try:
            from app.services.nextplan import arm_native_next_plan
            await arm_native_next_plan(session, subscription, source="purchase_provision")
        except Exception as e:
            logging.warning(f"Native next_plan arming failed for sub {sub_id} (watchdog will retry): {e}")

    # Rewards policy: no XP / loyalty / purchase cashback from this flow (see handlers policy).
    # (Pack grants retired 2026-07: badge/theme now unlock at the star milestone,
    # VIP time comes from the wallet-redeemed vip_days coupon.)

    try:
        pending_claim = await crud.get_pending_extradays_claim(session, user.id)
        if pending_claim:
            days_to_add = int(pending_claim.tier.reward_value)
            from app.handlers.user.rewards.redemption import _patch_panel_user

            user_info = await crud.pasarguard_api.get_user_info(subscription.marzban_username)
            # `or 0`: PasarGuard returns expire=null for never-expires users
            current_expire_ts = (user_info or {}).get("expire", 0) or 0
            new_expire_ts = current_expire_ts + (days_to_add * 24 * 60 * 60)
            patch_success = await _patch_panel_user(subscription.marzban_username, {"expire": new_expire_ts})
            if patch_success:
                pending_claim.status = "claimed"
                pending_claim.claimed_at = datetime.utcnow()
                await session.commit()
                await crud.add_reward_history(
                    session,
                    user.id,
                    "extra_days",
                    days_to_add,
                    "star_tier",
                    pending_claim.tier_id,
                    notes=f"Auto-applied to new sub {subscription.marzban_username}",
                )
                await bot.send_message(
                    user.chat_id,
                    f"🎁 جایزه {days_to_add} روز اعتبار هدیه شما با موفقیت به اشتراک جدیدتان اضافه شد!",
                )
            else:
                logging.error(f"Failed to auto-apply {days_to_add} days to sub {subscription.id} for user {user.id}")
    except Exception as e:
        logging.error(f"Error checking/applying pending extra_days reward for user {user.id}: {e}")

    try:
        if not getattr(subscription, "user_link_sent", False):
            from aiogram.types import WebAppInfo
            from aiogram.utils.keyboard import InlineKeyboardBuilder

            from app.core.settings import (
                BOT_TOKEN,
                DASHBOARD_PUBLIC_BASE_URL,
                DASHBOARD_WEBAPP_BASE_PATH,
                WEBAPP_SESSION_SECRET,
            )
            from app.utils.webapp_verify import create_one_time_token

            session_secret = WEBAPP_SESSION_SECRET or BOT_TOKEN
            auth_token = create_one_time_token(user.id, session_secret, ttl_seconds=15 * 60)  # 15 minutes
            dashboard_url = f"{DASHBOARD_PUBLIC_BASE_URL}{DASHBOARD_WEBAPP_BASE_PATH}?auth={auth_token}"
            kb = InlineKeyboardBuilder()
            kb.button(text="🌐 باز کردن داشبورد", web_app=WebAppInfo(url=dashboard_url))
            kb.adjust(1)
            # Never DM the panel's relative "/sub/<token>" path — host the
            # token on the public SUBLINK domain (utils/sub_links.py).
            from app.utils.sub_links import public_sub_url
            public_link = public_sub_url(sub_url, token=getattr(subscription, "sub_token", None)) or sub_url
            await bot.send_message(
                user.chat_id,
                "سرویس شما فعال شد.\n\n"
                f"لینک اتصال شما — با یک لمس کپی می‌شود:\n<code>{public_link}</code>\n\n"
                "برای مدیریت سرویس، کپی لینک و مشاهده وضعیت، از داشبورد استفاده کنید:",
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
            subscription.user_link_sent = True
            await session.commit()
    except Exception as notify_error:
        logging.error(f"Failed to send subscription link to user {user.chat_id}: {notify_error}")
        return True

    await _cleanup_admin_messages(subscription)

    if subscription.referrer_id:
        from app.database.models import ReferralReward as _ReferralReward

        existing_reward_q = await session.execute(
            select(_ReferralReward.id).filter(_ReferralReward.subscription_id == subscription.id).limit(1)
        )
        if existing_reward_q.scalar_one_or_none() is None:
            cfg = await crud.get_reward_config(session)
            result_ref = await session.execute(select(_User).filter(_User.id == subscription.referrer_id))
            ref_user = result_ref.scalars().first()
            if ref_user:
                traffic_pct = cfg.traffic_percent or 0
                days_pct = cfg.days_percent or 0
                # Tiered promoter cut: a referrer with more active referrals earns a
                # higher store-credit % (5/10/12/15%). Admin keeps the on/off switch via
                # credit_percent==0. ponytail: per-purchase O(referrals) count — fine at
                # this scale; cache on the user row if referral volume ever spikes.
                credit_pct = cfg.credit_percent or 0
                if credit_pct > 0:
                    from app.services.flows.cashout import count_active_referrals, promoter_credit_percent
                    active_refs = await count_active_referrals(session, ref_user.id)
                    credit_pct = promoter_credit_percent(active_refs)
                total_gb = plan_info["gb"]
                total_price = plan_info["price"]

                if subscription.renewal_paid and subscription.renewal_template:
                    renewal_info = get_plan_info(subscription.renewal_template)
                    if renewal_info:
                        total_gb += renewal_info["gb"]
                        total_price += renewal_info["price"]

                extra_gb = total_gb * traffic_pct / 100 if traffic_pct else None
                total_days = 30
                if subscription.renewal_paid and subscription.renewal_template:
                    total_days += 30

                extra_days = None
                if days_pct > 0:
                    calc_days = int(total_days * days_pct / 100)
                    extra_days = max(1, calc_days)
                credit_amount = int(total_price * credit_pct / 100) if credit_pct else None

                # Season-star option — one of the 4 referral choices (not auto-granted).
                # Qualifying purchase = >=20GB; +1 normally, +2 if a renewal was reserved.
                from app.core.rewards_config import (
                    MAX_STARS_PER_REFERRED_PURCHASE,
                    MIN_REFERRAL_STAR_PLAN_GB,
                    NORMAL_REFERRAL_STARS,
                    REFERRAL_BONUS_XP,
                    RESERVED_AUTORENEW_REFERRAL_STARS,
                )
                star_increment = 0
                if total_gb >= MIN_REFERRAL_STAR_PLAN_GB:
                    star_increment = min(
                        RESERVED_AUTORENEW_REFERRAL_STARS if subscription.renewal_paid
                        else NORMAL_REFERRAL_STARS,
                        MAX_STARS_PER_REFERRED_PURCHASE,
                    )

                reward = await crud.create_referral_reward(
                    db=session,
                    subscription_id=subscription.id,
                    referrer_id=subscription.referrer_id,
                    traffic_bytes=int(extra_gb * 1024 * 1024 * 1024) if extra_gb else None,
                    extra_days=extra_days,
                    credit_amount=credit_amount,
                    reward_value=star_increment or None,
                    stars=star_increment or None,
                )

                # +50 XP to the referrer for every referral, regardless of choice.
                try:
                    await crud.add_experience_points(session, ref_user.id, REFERRAL_BONUS_XP, "referral")
                except Exception:
                    pass

                from app.keyboards.inline import get_enhanced_reward_voucher_keyboard

                kb_reward = get_enhanced_reward_voucher_keyboard(
                    reward.id,
                    extra_gb=extra_gb,
                    extra_days=extra_days,
                    credit_amount=credit_amount,
                    stars_progress=ref_user.stars,
                    star_increment=star_increment,
                    show_star=star_increment > 0,
                    show_enhanced_stars=False,
                )
                try:
                    await bot.send_message(
                        ref_user.chat_id,
                        "🎉 یک کاربر با کد شما سرویس جدید خریداری کرد!\n"
                        "🎁 پاداش شما آماده است – یکی را انتخاب کنید:",
                        reply_markup=kb_reward,
                    )
                except Exception as e:
                    logging.error(f"Could not notify referrer {ref_user.id}: {e}")
    return True
