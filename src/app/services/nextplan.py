"""Native PasarGuard next-plan booking (2026-07-12, Pasha-approved design).

The panel natively supports scheduling a follow-up plan: an armed ``next_plan``
object on the user fires automatically the moment the CURRENT plan runs out
(data exhausted or expired) — even if this app is down. Product decisions:

- **carry nothing**: ``add_remaining_traffic=False``. Leftover GB is dropped;
  the panel cannot express our old 5GB cap and carry-all leaks free traffic.
- **full switch**: bookings arm the panel at payment approval; the renewal
  sweep is a reconcile watchdog (mark fired bookings, arm missed ones), not an
  early-fire engine.

Panel facts (live-probed on 5.0.3, see handoff 2026-07-12):
- Arm via ``PUT /api/user/{u}`` with ``next_plan = {user_template_id,
  data_limit, expire, add_remaining_traffic}``; ``expire`` is a DURATION in
  seconds counted from activation, not an epoch.
- Any modify PUT that omits ``next_plan`` WIPES it — every PUT in this app
  goes through ``with_next_plan_preserved`` (services/pasarguard.py).
- On fire the panel applies the plan and clears ``next_plan``; reading it back
  returns the raw seconds int, so armed objects round-trip verbatim.

State machine per booked sub (renewal_paid & !renewal_applied):
    armed_at NULL + panel armed      -> adopt (stamp armed_at)
    armed_at NULL + panel not armed  -> arm now (also the migration path)
    armed_at set  + panel armed      -> waiting, nothing to do
    armed_at set  + panel not armed  -> FIRED: mark applied, history, DM user
"""

from datetime import datetime

from app.core.settings import PLANS
from app.database import crud
from app.services.pasarguard import pasarguard_api
from app.utils.logger import bot_logger

GB = 1024 ** 3


def booked_next_plan_fields(template_name: str, plans: dict | None = None) -> dict | None:
    """The exact ``next_plan`` object to arm for a booked template, or None if
    the template no longer resolves (catalog drift). ``plans`` is test/caller
    injectable, same contract as flows.pricing.get_plan_info."""
    from app.services.flows.pricing import get_plan_info

    info = get_plan_info(template_name, plans if plans is not None else PLANS)
    if not info:
        return None
    # Catalog days already include the sales grace (plans ship days=35 for a
    # "1 month" plan; legacy renewals granted exactly that). No extra padding.
    days = int(info.get("days") or 30)
    return {
        "user_template_id": None,
        "data_limit": int(info.get("gb") or 0) * GB,
        "expire": days * 86400,  # duration in seconds from activation
        "add_remaining_traffic": False,  # carry nothing — Pasha 2026-07-12
    }


async def arm_native_next_plan(session, sub, *, plans: dict | None = None, source: str = "") -> bool:
    """Arm the panel's next_plan for a paid booking and stamp renewal_armed_at.
    Non-fatal by design: on any failure the caller proceeds and the watchdog
    sweep retries on its next pass."""
    template = getattr(sub, "renewal_template", None)
    if not (getattr(sub, "renewal_paid", False) and template):
        return False
    # Defence in depth: quote_purchase and start_charge_order both refuse to
    # book a free trial or a cross-route template, but this is the last gate
    # before the PANEL holds the booking and fires it on its own, possibly
    # months later with nobody watching.
    from app.core.products import plan_route
    from app.services.flows.pricing import get_plan_info

    booked_info = get_plan_info(template, plans if plans is not None else PLANS)
    if booked_info and booked_info.get("free"):
        bot_logger.warning(
            f"[NEXTPLAN] refusing to arm a free trial for {sub.marzban_username} ({source})"
        )
        return False
    current_info = get_plan_info(getattr(sub, "plan_name", "") or "", plans if plans is not None else PLANS)
    if booked_info and plan_route(booked_info) != plan_route(current_info):
        bot_logger.warning(
            f"[NEXTPLAN] refusing cross-route booking for {sub.marzban_username}: "
            f"{plan_route(current_info)} sub, {plan_route(booked_info)} template ({source})"
        )
        return False

    fields = booked_next_plan_fields(template, plans)
    if not fields:
        bot_logger.warning(
            f"[NEXTPLAN] cannot arm {sub.marzban_username}: template '{template}' not in catalog ({source})"
        )
        return False
    try:
        ok = await pasarguard_api.update_user(sub.marzban_username, {"next_plan": fields})
    except Exception as e:
        bot_logger.warning(f"[NEXTPLAN] arm failed for {sub.marzban_username} ({source}): {e}")
        return False
    if not ok:
        bot_logger.warning(f"[NEXTPLAN] arm rejected by panel for {sub.marzban_username} ({source})")
        return False
    sub.renewal_armed_at = datetime.utcnow()
    await session.commit()
    bot_logger.info(f"[NEXTPLAN] armed {sub.marzban_username}: '{template}' ({source})")
    return True


async def reconcile_booked_sub(session, sub, bot) -> str:
    """One watchdog step for a booked sub. Returns one of:
    'waiting' | 'adopted' | 'armed' | 'fired' | 'error'."""
    info = await pasarguard_api.get_user_info(sub.marzban_username)
    if not info:
        return "error"

    armed = info.get("next_plan")
    if isinstance(armed, dict):
        if not getattr(sub, "renewal_armed_at", None):
            # Armed on the panel but not stamped here (e.g. armed manually or a
            # pre-stamp crash) — adopt it as ours.
            sub.renewal_armed_at = datetime.utcnow()
            await session.commit()
            return "adopted"
        return "waiting"

    if not getattr(sub, "renewal_armed_at", None):
        # Paid booking that predates the native switch (or a failed arm at
        # approval): arm it now. This is also the one-time migration path.
        return "armed" if await arm_native_next_plan(session, sub, source="watchdog") else "error"

    # We armed it and the panel no longer holds it: the panel fired the plan.
    # (Manual removal in the panel UI is the only false positive; every app
    # PUT preserves armed plans via with_next_plan_preserved.)
    data_limit = int(info.get("data_limit") or 0)
    await crud.update_subscription_renewal(session, sub.id, renewal_applied=True)
    sub.renewal_armed_at = None
    await session.commit()
    await crud.create_renewal_history(
        session, sub.id, result="success",
        details=f"native next_plan fired (template {sub.renewal_template}, panel limit {data_limit // GB}GB)",
    )
    await pasarguard_api.invalidate_user_info(sub.marzban_username)
    bot_logger.info(f"[NEXTPLAN] fired for {sub.marzban_username}: '{sub.renewal_template}'")
    if bot is not None:
        # Explicit fetch — sub.user is often lazy/unloaded in job sessions.
        from app.database.models import User as _User
        chat_id = None
        if getattr(sub, "user_id", None):
            u = await session.get(_User, sub.user_id)
            chat_id = getattr(u, "chat_id", None)
        if chat_id:
            try:
                await bot.send_message(
                    chat_id,
                    "سرویس شما به‌صورت خودکار تمدید شد و پلن رزروشده فعال شد.",
                )
            except Exception as e:
                bot_logger.warning(f"[NEXTPLAN] renewal DM failed for chat {chat_id}: {e}")
    return "fired"
