from __future__ import annotations

import logging
import re
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID, PLANS
from app.database import crud


async def process_approved_subscription(sub_id: int, session: AsyncSession, bot: Bot) -> bool:
    """
    Handles all logic for an approved subscription, whether by admin or auto-approved (e.g., via credit).
    Returns True on success, False on failure.

    ``bot`` must be the **user** Telegram bot (``BOT_TOKEN``): it sends DMs with subscription links.
    When approving from AstroAdmin, use ``get_user_bot()`` — not the admin bot instance.
    """
    from app.database.models import Subscription
    from app.database.models import User as _User

    async def _cleanup_admin_messages(sub: Subscription) -> None:
        # Admin chat messages (forwarded receipt + inline keyboard) live in the **admin** bot.
        from app.utils.admin_bot_helper import get_admin_bot

        admin_bot = get_admin_bot()
        if not admin_bot:
            return
        try:
            if getattr(sub, "admin_request_message_id", None):
                try:
                    await admin_bot.delete_message(ADMIN_ID, int(sub.admin_request_message_id))
                except Exception:
                    try:
                        await admin_bot.edit_message_text(
                            "✅ این درخواست در داشبورد/ربات تایید شد.",
                            chat_id=ADMIN_ID,
                            message_id=int(sub.admin_request_message_id),
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            if getattr(sub, "admin_receipt_forward_message_id", None):
                try:
                    await admin_bot.delete_message(ADMIN_ID, int(sub.admin_receipt_forward_message_id))
                except Exception:
                    pass
        except Exception:
            pass

    subscription: Subscription | None = await session.get(Subscription, sub_id)
    if not subscription:
        logging.error(f"Could not find subscription {sub_id} to process approval.")
        return False

    if subscription.status == "active" and getattr(subscription, "user_link_sent", False):
        await _cleanup_admin_messages(subscription)
        return True

    if subscription.status == "pending":
        try:
            res = await session.execute(
                update(Subscription)
                .where(Subscription.id == sub_id, Subscription.status == "pending")
                .values(status="active")
            )
            await session.commit()
            if getattr(res, "rowcount", 0) == 0:
                subscription = await session.get(Subscription, sub_id)
                if subscription and subscription.status == "active" and getattr(subscription, "user_link_sent", False):
                    await _cleanup_admin_messages(subscription)
                    return True
        except Exception:
            pass

    result = await session.execute(select(_User).filter(_User.id == subscription.user_id))
    user = result.scalar_one_or_none()
    if not user:
        logging.error(f"Could not find user for subscription {sub_id}")
        return False

    plan_info = PLANS[subscription.plan_name]

    try:
        marzban_user = await crud.create_subscription_on_marzban(subscription, plan_info)
    except Exception as e:
        logging.error(f"Failed to create Marzban user for sub {sub_id}: {e}")
        await crud.deactivate_subscription_on_failure(session, sub_id)
        try:
            await bot.send_message(
                user.chat_id,
                "متاسفانه در ساخت سرویس شما مشکلی پیش آمده. لطفاً مجدداً تلاش کنید یا به پشتیبانی پیام دهید.",
            )
        except Exception as notify_error:
            logging.error(f"Failed to notify user {user.chat_id} about marzban failure: {notify_error}")
        return False

    sub_url = marzban_user.get("subscription_url") if marzban_user else None
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

    # Rewards policy: no XP / loyalty / purchase cashback from this flow (see handlers policy).

    try:
        pending_claim = await crud.get_pending_extradays_claim(session, user.id)
        if pending_claim:
            days_to_add = int(pending_claim.tier.reward_value)
            from app.handlers.user.rewards.redemption import _patch_marzban_user

            user_info = await crud.marzban_api.get_user_info(subscription.marzban_username)
            current_expire_ts = (user_info or {}).get("expire", 0)
            new_expire_ts = current_expire_ts + (days_to_add * 24 * 60 * 60)
            patch_success = await _patch_marzban_user(subscription.marzban_username, {"expire": new_expire_ts})
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
            await bot.send_message(
                user.chat_id,
                "✅ سرویس شما با موفقیت فعال شد!\n\n"
                f"🔗 لینک اشتراک شما:\n<code>{sub_url}</code>\n\n"
                "برای مدیریت سرویس، کپی لینک، و مشاهده وضعیت، از داشبورد استفاده کنید:",
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
            subscription.user_link_sent = True
            await session.commit()
    except Exception as notify_error:
        logging.error(f"Failed to send subscription link to user {user.chat_id}: {notify_error}")
        return True

    if sub_url:
        try:
            token_match = re.search(r"/sub/([^/]+)/?", sub_url)
            if token_match:
                subscription.sub_token = token_match.group(1)
                await session.commit()
        except Exception:
            pass

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
                credit_pct = cfg.credit_percent or 0
                total_gb = plan_info["gb"]
                total_price = plan_info["price"]

                if subscription.renewal_paid and subscription.renewal_template:
                    renewal_info = PLANS.get(subscription.renewal_template)
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
                    star_line = f"\n⭐ گزینه ستاره فصلی: +{star_increment}" if star_increment > 0 else ""
                    await bot.send_message(
                        ref_user.chat_id,
                        "🎉 یک کاربر با کد شما سرویس جدید خریداری کرد!\n"
                        "🎁 پاداش شما آماده است – یکی را انتخاب کنید:"
                        f"{star_line}",
                        reply_markup=kb_reward,
                    )
                except Exception as e:
                    logging.error(f"Could not notify referrer {ref_user.id}: {e}")
    return True
