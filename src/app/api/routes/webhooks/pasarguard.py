"""PasarGuard panel webhook receiver — the push layer over the polling sweeps.

The panel POSTs user lifecycle events here (limited/expired/threshold hits…).
We react instantly instead of waiting for the 60s renewal sweep / 10min notify
sweep; both sweeps keep running as the safety net and share the same redis
throttle keys, so nothing fires twice.

Payload tolerance: Marzban-family panels send either a single event object or
a list of them; fields of interest are `action`/`event` and `username` (with
an optional embedded `user` object). Unknown actions are logged and ACKed —
never bounce the panel (it retries `recurrent` times).
"""
import hmac
from datetime import datetime

from aiohttp import web
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.redis_config import cache
from app.core.settings import PASARGUARD_WEBHOOK_SECRET
from app.database import models
from app.database.models import AsyncSessionLocal
from app.services import user_alerts
from app.services.pasarguard import pasarguard_api
from app.utils.logger import bot_logger

# Actions that mean "plan ran out" → try instant auto-renew / finished DM.
_EXHAUSTED_ACTIONS = {"user_limited", "user_expired", "limited", "expired", "user_data_usage_reset"}
_USAGE_WARN_ACTIONS = {"reached_usage_percent", "usage_percent"}
_DAYS_WARN_ACTIONS = {"reached_days_left", "days_left"}


def _extract_events(payload) -> list[dict]:
    if isinstance(payload, list):
        return [e for e in payload if isinstance(e, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _event_fields(event: dict) -> tuple[str, str]:
    action = str(event.get("action") or event.get("event") or "").lower()
    username = event.get("username") or (event.get("user") or {}).get("username") or ""
    return action, str(username)


async def _sub_for_username(session, username: str):
    res = await session.execute(
        select(models.Subscription)
        .options(selectinload(models.Subscription.user))
        .filter(models.Subscription.marzban_username == username)
        .limit(1)
    )
    return res.scalars().first()


async def _instant_renew(session, sub, bot) -> bool:
    """Apply a reserved renewal right now (same lock + entrypoint as the sweep)."""
    if not (getattr(sub, "renewal_paid", False) and getattr(sub, "renewal_template", None)):
        return False
    lock_key = f"lock:renew:{sub.marzban_username}"
    try:
        if await cache.get(lock_key):
            return False  # sweep (or a previous event) is already on it
        await cache.set(lock_key, True, ttl=60)
    except Exception:
        pass
    try:
        from app.jobs.renewal import apply_renewal

        await apply_renewal(sub.id, session, bot)
        return True
    finally:
        try:
            await cache.delete(lock_key)
        except Exception:
            pass


async def handle_pasarguard_webhook(request: web.Request):
    secret = request.headers.get("x-webhook-secret") or request.headers.get("X-Webhook-Secret") or ""
    if not PASARGUARD_WEBHOOK_SECRET or not hmac.compare_digest(secret, PASARGUARD_WEBHOOK_SECRET):
        return web.json_response({"ok": False}, status=401)

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    events = _extract_events(payload)
    if not events:
        return web.json_response({"ok": True, "handled": 0})

    bot = request.app.get("bot")
    handled = 0

    for event in events:
        action, username = _event_fields(event)
        if not username:
            continue
        handled += 1
        bot_logger.info(f"[WEBHOOK] {action or 'unknown'} for {username[:3]}***")

        # Any lifecycle event → that user's cached panel info is stale.
        try:
            await pasarguard_api.invalidate_user_info(username)
        except Exception:
            pass

        if not bot:
            continue

        try:
            async with AsyncSessionLocal() as session:
                sub = await _sub_for_username(session, username)
                if not sub:
                    continue

                if action in _EXHAUSTED_ACTIONS:
                    renewed = await _instant_renew(session, sub, bot)
                    if renewed:
                        bot_logger.info(f"[WEBHOOK] instant renewal applied: {username[:3]}***")
                        continue
                    # No booking → tell the user their plan ran out.
                    if action in {"user_expired", "expired"}:
                        await user_alerts.send_expired_alert(bot, session, sub)
                    else:
                        await user_alerts.send_finished_data_alert(
                            bot, sub, auto_renew=bool(getattr(sub, "renewal_paid", False))
                        )

                elif action in _USAGE_WARN_ACTIONS:
                    # Threshold warning (panel configured at 80% used).
                    info = await pasarguard_api.get_fast_user_info(username, getattr(sub, "sub_token", None))
                    data_limit = (info or {}).get("data_limit") or 0
                    used = (info or {}).get("used_traffic") or 0
                    remaining = max(data_limit - used, 0)
                    pct = (remaining / data_limit * 100) if data_limit > 0 else 100
                    if getattr(sub, "renewal_paid", False) and getattr(sub, "renewal_template", None):
                        continue  # auto-renew handles it; the sweep-parity skip
                    await user_alerts.send_low_traffic_alert(bot, sub, remaining, pct)

                elif action in _DAYS_WARN_ACTIONS:
                    await user_alerts.send_expiry_soon_alert(bot, session, sub)

                elif action in {"user_updated", "user_created", "user_deleted", "user_enabled", "user_disabled"}:
                    pass  # cache already invalidated; nothing else to do

        except Exception as e:
            bot_logger.warning(f"[WEBHOOK] handler error for {username[:3]}***: {e}")

    return web.json_response({"ok": True, "handled": handled, "ts": datetime.utcnow().isoformat()})
