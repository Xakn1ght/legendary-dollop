"""Free-trial eligibility, cooldowns and instant provisioning.

Ported from the live sales bot during the merge (``MERGE_PLAN.md``). Two
trials, counted INDEPENDENTLY - a normal trial must never block a Pro trial or
the other way round:

- ``test``      one per account per 7 days, normal route
- ``pro_test``  one per account per 30 days, Pro / IR-Tun route

Eligibility is DERIVED from the ``subscriptions`` table rather than stored in a
column, because the existing order lifecycle already produces exactly the rule
the sales bot documents:

- a failure BEFORE provisioning calls ``_rollback_order``, which ends in
  ``delete_subscription`` - the row is gone, so the allowance is intact;
- a failure AFTER provisioning (e.g. the delivery DM bounces) leaves the row
  active - the allowance is consumed, which is correct, because handing out a
  second panel user would be worse.

A stored column could not express that without careful write ordering, and
would need its own backfill when the sales bot's 4,593 historical orders are
imported at cutover. Derived, that history enforces the cooldown for free.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.products import (
    FREE_TEST_PLANS,
    PRO_TEST_PLAN,
    TEST_PLAN,
    test_cooldown_days,
)
from app.database.models import Subscription
from app.services.flows.errors import FlowError

# An order in one of these has consumed nothing yet but is on its way, so a
# second tap must not start another one.
IN_PROGRESS_STATUSES = ("draft", "pending", "processing")

# How long the "one tap at a time" lock is held. Long enough to cover
# provisioning, short enough that a crash cannot wedge a user out of their
# trial for meaningfully longer than the flow itself.
CLAIM_LOCK_TTL_SEC = 90


def _is_admin(user) -> bool:
    """Admins are exempt, mirroring the live sales bot - they need to be able
    to re-test the flow without waiting a week."""
    from app.shared.admin_access import ADMIN_IDS

    return int(getattr(user, "chat_id", 0) or 0) in ADMIN_IDS


async def _latest_trial(session: AsyncSession, user_id: int, tier: str) -> Subscription | None:
    """Most recent trial row of this tier. Only this tier - the two allowances
    are independent."""
    res = await session.execute(
        select(Subscription)
        .filter(Subscription.user_id == user_id, Subscription.plan_name == tier)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    return res.scalars().first()


async def test_cooldown_remaining(session: AsyncSession, user, tier: str) -> int:
    """Seconds until ``user`` may take ``tier`` again. 0 means allowed now."""
    if tier not in FREE_TEST_PLANS:
        return 0
    if _is_admin(user):
        return 0
    latest = await _latest_trial(session, user.id, tier)
    if latest is None or not latest.created_at:
        return 0
    due = latest.created_at + timedelta(days=test_cooldown_days(tier))
    remaining = (due - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


async def free_test_in_progress(session: AsyncSession, user, tier: str) -> bool:
    latest = await _latest_trial(session, user.id, tier)
    return bool(latest is not None and latest.status in IN_PROGRESS_STATUSES)


async def is_free_test_available(session: AsyncSession, user, tier: str) -> bool:
    """Used to decide whether the button is shown at all - Pasha's call was to
    hide it entirely on cooldown rather than relabel it."""
    if await free_test_in_progress(session, user, tier):
        return False
    return await test_cooldown_remaining(session, user, tier) <= 0


def format_cooldown(seconds: int, lang: str = "fa") -> str:
    """Round UP, so "1 day" never means "in 30 seconds it becomes 0 days"."""
    if seconds >= 86400:
        days = (seconds + 86399) // 86400
        if lang == "fa":
            return f"{days} روز".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        return f"{days} day" + ("s" if days != 1 else "")
    hours = max(1, (seconds + 3599) // 3600)
    if lang == "fa":
        return f"{hours} ساعت".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    return f"{hours} hour" + ("s" if hours != 1 else "")


async def assert_test_allowed(session: AsyncSession, user, tier: str) -> None:
    """Raise unless ``user`` may take ``tier`` right now.

    Codes: ``invalid_test_tier``, ``test_in_progress``, ``test_cooldown``
    (carries ``.remaining_seconds`` for the message).
    """
    if tier not in FREE_TEST_PLANS:
        raise FlowError("invalid_test_tier", "Unknown trial")
    if await free_test_in_progress(session, user, tier):
        raise FlowError("test_in_progress", "Your trial is already being created")
    remaining = await test_cooldown_remaining(session, user, tier)
    if remaining > 0:
        err = FlowError("test_cooldown", "You have used this trial recently")
        err.remaining_seconds = remaining
        raise err


async def claim_free_test(user, tier: str) -> bool:
    """Short Redis lock closing the double-tap window between the eligibility
    check and the order row existing. Returns False if a tap is already in
    flight. Fails OPEN when Redis is unavailable - the in-progress status check
    is the backstop, and a dead cache must not block every trial in the system.
    """
    try:
        from app.core.redis_config import cache

        key = f"freetest:{user.id}:{tier}"
        if await cache.get(key):
            return False
        await cache.set(key, True, ttl=CLAIM_LOCK_TTL_SEC)
        return True
    except Exception:
        return True


async def release_free_test_claim(user, tier: str) -> None:
    try:
        from app.core.redis_config import cache

        await cache.delete(f"freetest:{user.id}:{tier}")
    except Exception:
        pass


async def start_free_test(session: AsyncSession, user, tier: str, bot=None):
    """Provision a free trial immediately. No name prompt, no receipt step.

    That is the whole point of the flow Pasha approved on the live bot: tap the
    button, the subscription arrives. It works here without a special path
    because the order simply prices to zero - ``start_purchase_order`` sends any
    fully-covered order straight down ``_auto_approve``, so the FSM never enters
    the name or receipt states.

    ``service_name=None`` makes ``resolve_service_name`` generate a random
    8-character name, already sanitised for the panel and already carrying
    TEST_PANEL_PREFIX when test mode is on. That is exactly the live bot's
    random_sub_name; do not reimplement it.

    Raises FlowError: invalid_test_tier, test_in_progress, test_cooldown,
    auto_approve_failed.
    """
    from app.services.flows.pricing import quote_purchase
    from app.services.flows.purchase import start_purchase_order

    if tier not in FREE_TEST_PLANS:
        raise FlowError("invalid_test_tier", "Unknown trial")

    if not await claim_free_test(user, tier):
        raise FlowError("test_in_progress", "Your trial is already being created")

    try:
        # Checked again inside the lock: the tap that lost the race must not
        # get through on a stale read taken before the winner's row existed.
        await assert_test_allowed(session, user, tier)
        quote = await quote_purchase(session, user, plan_name=tier)
        label = "سیستم (تست رایگان)" if tier == TEST_PLAN else "سیستم (تست پرو رایگان)"
        result = await start_purchase_order(
            session, user, quote=quote, service_name=None,
            auto_renewal=False, bot=bot, approved_by=label,
        )
    except Exception:
        # A pre-provision failure rolls the row away, so the allowance is
        # intact - release the lock too or the user waits 90s for nothing.
        await release_free_test_claim(user, tier)
        raise
    # Released on success as well: the order row now exists, so the in-progress
    # and cooldown checks are the real gate and the lock has nothing left to
    # protect. Holding it would just be 90 seconds of a worse error message.
    await release_free_test_claim(user, tier)
    return result


__all__ = [
    "PRO_TEST_PLAN",
    "TEST_PLAN",
    "assert_test_allowed",
    "claim_free_test",
    "format_cooldown",
    "free_test_in_progress",
    "is_free_test_available",
    "release_free_test_claim",
    "start_free_test",
    "test_cooldown_remaining",
]
