import asyncio
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.redis_config import cache
from app.core.settings import RENEWAL_TIME_SKIP_DAYS, RENEWAL_TRAFFIC_SKIP_PERCENT
from app.database import crud, models
from app.database.crud import create_renewal_history
from app.database.models import AsyncSessionLocal
from app.services.marzban import marzban_api
from app.utils.logger import bot_logger, log_error


# --- Renewal decision thresholds (robust defaults) ---
def _safe_percent(value, default=30.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)

def _safe_days(value, default=7) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except Exception:
        return int(default)

# If the subscription still has more than threshold% traffic AND more than threshold days
# left to expiry, we do NOT renew. Renew otherwise. Values can be tuned in settings.
SKIP_RENEW_TRAFFIC_THRESHOLD_PERCENT = _safe_percent(RENEWAL_TRAFFIC_SKIP_PERCENT, 30.0)
SKIP_RENEW_TIME_THRESHOLD = timedelta(days=_safe_days(RENEWAL_TIME_SKIP_DAYS, 7))

# We still allow rollover of up to 5 GB when a renewal does happen.
ROLLOVER_THRESHOLD_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB in bytes

async def charge_add(user_info, template_info):
    """Return (data_limit, expire_ts) for patched Marzban user.

    • If the leftover traffic is < 5 GB we roll it over and add to the template limit.
    • Otherwise we reset to the template limit (no rollover).
    Expiry is always reset to 35 days from now as per requirement.
    """
    used_traffic = user_info.get('used_traffic', 0) or 0
    current_limit = user_info.get('data_limit', 0) or 0
    remaining = max(current_limit - used_traffic, 0)

    if 0 < remaining < ROLLOVER_THRESHOLD_BYTES:
        new_limit = template_info['data_limit'] + remaining
    else:
        new_limit = template_info['data_limit']

    new_expire = int((datetime.utcnow() + timedelta(days=35)).timestamp())
    return new_limit, new_expire

async def apply_renewal(subscription_id, session, bot: Bot):
    # Re-query the subscription and user in a fresh context
    result = await session.execute(
        select(models.Subscription).options(selectinload(models.Subscription.user)).filter(models.Subscription.id == subscription_id)
    )
    subscription = result.scalars().first()
    if not subscription:
        bot_logger.warning("[RENEWAL] Subscription not found", subscription_id=subscription_id)
        return
    user = subscription.user  # Eagerly load user while session is open
    chat_id = getattr(user, 'chat_id', None)
    bot_logger.debug("[RENEWAL] Attempting", subscription_id=subscription.id, username=subscription.marzban_username)
    user_info = await marzban_api.get_user_info(subscription.marzban_username)
    if not user_info:
        bot_logger.warning("[RENEWAL] User info not found", username=subscription.marzban_username)
        await create_renewal_history(session, subscription.id, result="failure", details="User info not found")
        if chat_id:
            await bot.send_message(chat_id, "❌ تمدید سرویس شما با خطا مواجه شد. لطفا با پشتیبانی تماس بگیرید.")
        return
    # Fetch template info (simulate, replace with real template fetch if needed)
    template_name = subscription.renewal_template
    from app.handlers.user.purchase import PLANS
    raw_plan = PLANS.get(template_name)
    if not raw_plan:
        bot_logger.error("[RENEWAL] Plan not found for template", subscription_id=subscription_id, template=template_name)
        await create_renewal_history(session, subscription.id, result="failure", details=f"Plan '{template_name}' not found in PLANS")
        if chat_id:
            await bot.send_message(chat_id, "❌ تمدید سرویس شما با خطا مواجه شد. لطفا با پشتیبانی تماس بگیرید.")
        return
    template_info = {
        'data_limit': int(raw_plan['gb'] * 1024 * 1024 * 1024),
        'expire_duration': 35 * 24 * 60 * 60  # 35 days in seconds
    }
    new_limit, new_expire = await charge_add(user_info, template_info)
    session_http = await marzban_api._get_session()
    url = f"{marzban_api.base_url}/api/user/{subscription.marzban_username}"
    headers = await marzban_api._get_headers()
    patch_data = {
        "data_limit": new_limit,
        "expire": new_expire,
        "status": "active",
        "data_limit_reset_strategy": "no_reset",
    }
    bot_logger.debug("[RENEWAL] PATCH", url=url, payload=str(patch_data))
    async with session_http.put(url, headers=headers, json=patch_data) as response:
        if response.status not in (200, 204):
            bot_logger.error("[RENEWAL] Update failed", username=subscription.marzban_username, status=response.status)
            await create_renewal_history(session, subscription.id, result="failure", details=f"Update failed: HTTP status {response.status}")
            if chat_id:
                await bot.send_message(chat_id, "❌ تمدید سرویس شما با خطا مواجه شد. لطفا با پشتیبانی تماس بگیرید.")
            return

    # Reset traffic usage with separate call
    reset_url = f"{marzban_api.base_url}/api/user/{subscription.marzban_username}/reset"
    bot_logger.debug("[RENEWAL] POST reset", url=reset_url)
    async with session_http.post(reset_url, headers=headers) as reset_resp:
        if reset_resp.status not in (200, 204):
            bot_logger.error("[RENEWAL] Reset failed", username=subscription.marzban_username, status=reset_resp.status)
            await create_renewal_history(session, subscription.id, result="failure", details=f"Reset failed: HTTP status {reset_resp.status}")
            if chat_id:
                await bot.send_message(chat_id, "❌ تمدید سرویس شما با خطا مواجه شد. لطفا با پشتیبانی تماس بگیرید.")
            return

    bot_logger.info("[RENEWAL] Success", username=subscription.marzban_username, template=template_name)
    await crud.update_subscription_renewal(session, subscription.id, renewal_applied=True)
    await create_renewal_history(session, subscription.id, result="success", details=f"Renewed with template {template_name}")
    if chat_id:
        await bot.send_message(chat_id, "✅ سرویس شما با موفقیت تمدید شد!")

async def renewal_job(bot: Bot):
    bot_logger.debug("[RENEWAL JOB] Running")
    async with AsyncSessionLocal() as session:
        subs = await crud.get_subscriptions_for_renewal(session)
        bot_logger.debug("[RENEWAL JOB] Eligible count", count=len(subs))
        now = datetime.utcnow()
        for sub in subs:
            sub_id = sub.id
            marzban_username = sub.marzban_username
            bot_logger.debug("[RENEWAL JOB] Checking", subscription_id=sub_id, username=marzban_username)

            # Acquire short-lived lock for idempotency
            lock_key = f"lock:renew:{marzban_username}"
            try:
                if await cache.get(lock_key):
                    bot_logger.warning("[RENEWAL JOB] Skip due to lock", username=marzban_username)
                    continue
                await cache.set(lock_key, True, ttl=60)
            except Exception as e:
                log_error(e, {"operation": "renewal_lock", "username": marzban_username})

            try:
                # Prefer fast read via share-link when available
                sub_token = getattr(sub, 'sub_token', None)
                user_info = await marzban_api.get_fast_user_info(marzban_username, sub_token)
                if not user_info:
                    bot_logger.warning("[RENEWAL JOB] No user info", username=marzban_username)
                    continue

                expire_ts = user_info.get('expire')
                if not expire_ts:
                    bot_logger.warning("[RENEWAL JOB] No expire timestamp", username=marzban_username)
                    continue

                expire_dt = datetime.utcfromtimestamp(expire_ts)
                time_remaining = expire_dt - now

                data_limit = user_info.get('data_limit', 0) or 0
                used_traffic = user_info.get('used_traffic', 0) or 0
                remaining_bytes = max(data_limit - used_traffic, 0)
                remaining_gb = remaining_bytes / (1024 ** 3)

                # Calculate percentage of remaining traffic (treat unlimited as 100%)
                remaining_percent = (remaining_bytes / data_limit * 100) if data_limit > 0 else 100

                bot_logger.debug("[RENEWAL JOB] Decision", username=marzban_username, time_left=str(time_remaining), remaining_gb=f"{remaining_gb:.2f}", pct=f"{remaining_percent:.1f}%")

                # Percent-based low-traffic trigger: if a booking exists and remaining ≤ threshold%, renew immediately
                has_booking = bool(getattr(sub, 'renewal_paid', False) and getattr(sub, 'renewal_template', None))
                if has_booking and remaining_percent <= SKIP_RENEW_TRAFFIC_THRESHOLD_PERCENT:
                    bot_logger.info("[RENEWAL JOB] Trigger: low traffic percent with booking", username=marzban_username, remaining_percent=f"{remaining_percent:.1f}")
                    await apply_renewal(sub_id, session, bot)
                    continue

                # Decision: Renew when either condition is critical
                # - Remaining percent <= threshold OR
                # - Time remaining <= threshold
                should_renew = (
                    remaining_percent <= SKIP_RENEW_TRAFFIC_THRESHOLD_PERCENT or
                    time_remaining <= SKIP_RENEW_TIME_THRESHOLD
                ) and has_booking

                if should_renew:
                    bot_logger.info("[RENEWAL JOB] Triggered by threshold(s)", username=marzban_username, remaining_percent=f"{remaining_percent:.1f}", time_left=str(time_remaining))
                    await apply_renewal(sub_id, session, bot)
                else:
                    bot_logger.debug("[RENEWAL JOB] Skipped", username=marzban_username)
            finally:
                try:
                    await cache.delete(lock_key)
                except Exception:
                    pass

if __name__ == "__main__":
    asyncio.run(renewal_job()) 