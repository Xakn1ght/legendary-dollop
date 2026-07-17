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
from app.services.pasarguard import pasarguard_api
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
    """Return (data_limit, expire_ts) for patched PasarGuard user.

    • Leftover traffic rolls over into the new plan, capped at 5 GB — the same
      rule as manual charge approval (flows.charge) so renewals never lose more
      than the cap.
    Expiry is always reset to 35 days from now as per requirement.
    """
    used_traffic = user_info.get('used_traffic', 0) or 0
    current_limit = user_info.get('data_limit', 0) or 0
    remaining = max(current_limit - used_traffic, 0)

    new_limit = template_info['data_limit'] + min(remaining, ROLLOVER_THRESHOLD_BYTES)

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
    user_info = await pasarguard_api.get_user_info(subscription.marzban_username)
    if not user_info:
        bot_logger.warning("[RENEWAL] User info not found", username=subscription.marzban_username)
        await create_renewal_history(session, subscription.id, result="failure", details="User info not found")
        if chat_id:
            await bot.send_message(chat_id, "❌ تمدید سرویس شما با خطا مواجه شد. لطفا با پشتیبانی تماس بگیرید.")
        return
    # Fetch template info (simulate, replace with real template fetch if needed)
    template_name = subscription.renewal_template
    from app.services.flows.pricing import get_plan_info
    raw_plan = get_plan_info(template_name)
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
    await pasarguard_api.invalidate_user_info(subscription.marzban_username)
    session_http = await pasarguard_api._get_session()
    url = f"{pasarguard_api.base_url}/api/user/{subscription.marzban_username}"
    headers = await pasarguard_api._get_headers()
    patch_data = await pasarguard_api.with_next_plan_preserved(subscription.marzban_username, {
        "data_limit": new_limit,
        "expire": new_expire,
        "status": "active",
        "data_limit_reset_strategy": "no_reset",
    })
    bot_logger.debug("[RENEWAL] PATCH", url=url, payload=str(patch_data))
    async with session_http.put(url, headers=headers, json=patch_data) as response:
        if response.status not in (200, 204):
            bot_logger.error("[RENEWAL] Update failed", username=subscription.marzban_username, status=response.status)
            await create_renewal_history(session, subscription.id, result="failure", details=f"Update failed: HTTP status {response.status}")
            if chat_id:
                await bot.send_message(chat_id, "❌ تمدید سرویس شما با خطا مواجه شد. لطفا با پشتیبانی تماس بگیرید.")
            return

    # Reset traffic usage with separate call
    reset_url = f"{pasarguard_api.base_url}/api/user/{subscription.marzban_username}/reset"
    bot_logger.debug("[RENEWAL] POST reset", url=reset_url)
    async with session_http.post(reset_url, headers=headers) as reset_resp:
        if reset_resp.status not in (200, 204):
            bot_logger.error("[RENEWAL] Reset failed", username=subscription.marzban_username, status=reset_resp.status)
            await create_renewal_history(session, subscription.id, result="failure", details=f"Reset failed: HTTP status {reset_resp.status}")
            if chat_id:
                await bot.send_message(chat_id, "❌ تمدید سرویس شما با خطا مواجه شد. لطفا با پشتیبانی تماس بگیرید.")
            return

    bot_logger.info("[RENEWAL] Success", username=subscription.marzban_username, template=template_name)
    # Renewal just rewrote limit/expire and reset usage — drop the cached panel
    # info immediately so the user's next dashboard poll shows the new plan.
    await pasarguard_api.invalidate_user_info(subscription.marzban_username)
    await crud.update_subscription_renewal(session, subscription.id, renewal_applied=True)
    await create_renewal_history(session, subscription.id, result="success", details=f"Renewed with template {template_name}")
    if chat_id:
        await bot.send_message(chat_id, "✅ سرویس شما با موفقیت تمدید شد!")

async def renewal_job(bot: Bot):
    """Native next-plan WATCHDOG (full switch, 2026-07-12 — Pasha).

    Bookings are armed as PasarGuard ``next_plan`` at payment approval and the
    PANEL fires them the moment the current plan runs out (data or expiry) —
    no early app-side firing anymore. This sweep only reconciles state:

    - booking armed on panel        -> waiting (nothing to do)
    - armed_at stamped, panel empty -> the panel fired it: mark applied,
                                       write history, DM the user
    - never armed (pre-switch rows,
      or a failed arm at approval)  -> arm it now (the migration path)

    ``apply_renewal`` above stays as the manual/emergency app-side applier
    (admin tooling), but no automatic path calls it anymore.
    """
    bot_logger.debug("[RENEWAL JOB] Watchdog running")
    async with AsyncSessionLocal() as session:
        subs = await crud.get_subscriptions_for_renewal(session)
        bot_logger.debug("[RENEWAL JOB] Booked subs", count=len(subs))
        counts = {}
        for sub in subs:
            marzban_username = sub.marzban_username

            # Short-lived lock — shared with the webhook reconcile path.
            lock_key = f"lock:renew:{marzban_username}"
            try:
                if await cache.get(lock_key):
                    bot_logger.warning("[RENEWAL JOB] Skip due to lock", username=marzban_username)
                    continue
                await cache.set(lock_key, True, ttl=60)
            except Exception as e:
                log_error(e, {"operation": "renewal_lock", "username": marzban_username})

            try:
                from app.services.nextplan import reconcile_booked_sub
                outcome = await reconcile_booked_sub(session, sub, bot)
                counts[outcome] = counts.get(outcome, 0) + 1
                if outcome in ("armed", "adopted"):
                    bot_logger.warning(
                        "[RENEWAL JOB] Booking was not armed on panel — reconciled",
                        username=marzban_username, outcome=outcome,
                    )
            except Exception as e:
                log_error(e, {"operation": "renewal_watchdog", "username": marzban_username})
            finally:
                try:
                    await cache.delete(lock_key)
                except Exception:
                    pass
        if counts:
            bot_logger.info("[RENEWAL JOB] Watchdog summary", **{k: str(v) for k, v in counts.items()})

if __name__ == "__main__":
    asyncio.run(renewal_job()) 