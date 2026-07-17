"""Mission achievements — server-evaluated conditions + one-time 1GB claims.

Definitions live HERE in code (no admin CRUD): each achievement key maps to an
async evaluator that reads real DB state and returns (progress, target). The
claim endpoint re-evaluates server-side and mints a ``free_gb`` RewardCoupon
into the wallet through the same rail checkout already consumes — no new money
path. Claims are one-time (unique constraint) and, by the paying-customer
rule, only unlock for users with at least one approved PAID purchase.

Spec: docs/design-specs/specs/2026-07-08-achievements-redesign-design.md
"""
from __future__ import annotations

import datetime
import json

from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.rewards_config import COUPON_EXPIRY_DAYS
from app.database.models import (
    AchievementClaim,
    ChargeRequest,
    DailyGamePlay,
    RewardCoupon,
    Subscription,
    User,
)
from app.database.repos.user import UserRepository
from app.services.flows.cashout import count_active_referrals
from app.services.flows.errors import FlowError

REWARD_GB = 1
IN_ORBIT_DAYS = 90
# deepSpace: 1 TB of LIFETIME traffic on a single subscription. The panel's
# lifetime_used_traffic survives renewal resets (image-15: "Total: 3.53 TB"),
# so heavy long-term users hit this across many 100GB refills.
DEEP_SPACE_GB = 1024

# Subscription rows that reached payment: draft/pending never got approved and
# denied/cancelled rows are deleted, so anything else was a real purchase.
# price>0 keeps reward-minted free plans from counting as "paying customer"
# (NULL price predates the column and is treated as paid, matching the repo).
_PAID_SUB = and_(
    Subscription.status.notin_(("draft", "pending")),
    or_(Subscription.price.is_(None), Subscription.price > 0),
)


async def _paid_purchases(session: AsyncSession, user: User) -> int:
    return await session.scalar(
        select(func.count(Subscription.id)).where(Subscription.user_id == user.id, _PAID_SUB)
    ) or 0


async def _approved_charges(session: AsyncSession, user: User) -> int:
    return await session.scalar(
        select(func.count(ChargeRequest.id)).where(
            ChargeRequest.user_id == user.id, ChargeRequest.status == "approved"
        )
    ) or 0


async def _season_stars(session: AsyncSession, user: User) -> int:
    from app.database.repos.reward import RewardRepository

    _season, stars = await RewardRepository.get_season_progress(session, user.id)
    return int(stars or 0)


async def _arcade_runs(session: AsyncSession, user: User) -> int:
    return await session.scalar(
        select(func.count(DailyGamePlay.id)).where(
            DailyGamePlay.user_id == user.id, DailyGamePlay.rewarded.is_(True)
        )
    ) or 0


async def _account_days(session: AsyncSession, user: User) -> int:
    if not user.created_at:
        return 0
    return max(0, (datetime.datetime.utcnow() - user.created_at).days)


async def _lifetime_traffic_gb(session: AsyncSession, user: User) -> int:
    """Best (max) LIFETIME panel traffic in GB across the user's services.

    Uses the admin user object's ``lifetime_used_traffic`` (survives renewal
    resets — the "Total" column in the panel). max() with the current-period
    ``used_traffic`` guards panels that only roll lifetime up at reset time.
    Panel-shield: one burst per user per hour via a dedicated Redis key; a
    total read failure is NOT cached so the next view retries.
    """
    from app.core.redis_config import cache

    cache_key = f"ach:lifetime_gb:{user.id}"
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return int(cached)
    except Exception:
        pass

    usernames = (await session.execute(
        select(Subscription.marzban_username).where(
            Subscription.user_id == user.id,
            Subscription.marzban_username.isnot(None),
        )
    )).scalars().all()

    from app.services.pasarguard import pasarguard_api

    best_bytes = 0
    any_read = False
    for uname in usernames[:5]:  # hard cap on panel calls per snapshot
        try:
            info = await pasarguard_api.get_user_info(uname)
        except Exception:
            info = None
        if not info:
            continue
        any_read = True
        lifetime = int(info.get("lifetime_used_traffic") or 0)
        used = int(info.get("used_traffic") or 0)
        best_bytes = max(best_bytes, lifetime, used)

    gb = best_bytes // (1024 ** 3)
    if any_read or not usernames:
        try:
            await cache.set(cache_key, gb, ttl=3600)
        except Exception:
            pass
    return gb


async def _evaluate(session: AsyncSession, user: User, key: str) -> tuple[int, int]:
    """Return (progress, target) for one achievement, capped at target."""
    if key == "launch":
        return min(1, await _paid_purchases(session, user)), 1
    if key == "refuel":
        return min(1, await _approved_charges(session, user)), 1
    if key == "starHunter":
        return min(1, await _season_stars(session, user)), 1
    if key == "orbiter":
        return min(5, await _season_stars(session, user)), 5
    if key == "supernova":
        return min(20, await _season_stars(session, user)), 20
    if key == "envoy":
        return min(5, await count_active_referrals(session, user.id)), 5
    if key == "fleetCommander":
        return min(20, await count_active_referrals(session, user.id)), 20
    if key == "crew":
        return (1 if await UserRepository.is_user_vip(session, user.id) else 0), 1
    if key == "arcadePilot":
        return min(1, await _arcade_runs(session, user)), 1
    if key == "deepSpace":
        return min(DEEP_SPACE_GB, await _lifetime_traffic_gb(session, user)), DEEP_SPACE_GB
    if key == "inOrbit":
        days = min(IN_ORBIT_DAYS, await _account_days(session, user))
        # both legs required: the day counter only "completes" for buyers
        if days >= IN_ORBIT_DAYS and await _paid_purchases(session, user) < 1:
            days = IN_ORBIT_DAYS - 1
        return days, IN_ORBIT_DAYS
    raise FlowError("unknown_achievement")


# Order = display order on the profile page.
ACHIEVEMENT_KEYS = (
    "launch", "refuel", "starHunter", "orbiter", "supernova",
    "envoy", "fleetCommander", "crew", "arcadePilot", "deepSpace", "inOrbit",
)

# envoy/fleetCommander and star tiers share underlying counters — evaluate the
# expensive ones once per snapshot instead of once per key.


async def snapshot(session: AsyncSession, user: User) -> dict:
    """Everything the profile section renders, one payload."""
    stars = await _season_stars(session, user)
    active_refs = await count_active_referrals(session, user.id)
    purchases = await _paid_purchases(session, user)
    charges = await _approved_charges(session, user)
    arcade = await _arcade_runs(session, user)
    days = await _account_days(session, user)
    is_vip = await UserRepository.is_user_vip(session, user.id)
    lifetime_gb = await _lifetime_traffic_gb(session, user)

    progress = {
        "launch": (min(1, purchases), 1),
        "refuel": (min(1, charges), 1),
        "starHunter": (min(1, stars), 1),
        "orbiter": (min(5, stars), 5),
        "supernova": (min(20, stars), 20),
        "envoy": (min(5, active_refs), 5),
        "fleetCommander": (min(20, active_refs), 20),
        "crew": ((1 if is_vip else 0), 1),
        "arcadePilot": (min(1, arcade), 1),
        "deepSpace": (min(DEEP_SPACE_GB, lifetime_gb), DEEP_SPACE_GB),
        "inOrbit": (
            min(IN_ORBIT_DAYS, days) if (days < IN_ORBIT_DAYS or purchases >= 1) else IN_ORBIT_DAYS - 1,
            IN_ORBIT_DAYS,
        ),
    }

    claimed_keys = set(
        (await session.execute(
            select(AchievementClaim.achievement_key).where(AchievementClaim.user_id == user.id)
        )).scalars().all()
    )

    paying = purchases >= 1
    items = []
    for key in ACHIEVEMENT_KEYS:
        p, target = progress[key]
        done = p >= target
        claimed = key in claimed_keys
        items.append({
            "key": key,
            "progress": p,
            "target": target,
            "done": done,
            "claimed": claimed,
            "claimable": done and not claimed and paying,
            "reward_gb": REWARD_GB,
        })
    return {"paying_customer": paying, "achievements": items}


async def claim(session: AsyncSession, user: User, key: str) -> RewardCoupon:
    """Validate + mint the 1GB coupon. Raises FlowError:
    unknown_achievement, requires_purchase, not_completed, already_claimed."""
    if key not in ACHIEVEMENT_KEYS:
        raise FlowError("unknown_achievement")

    if await _paid_purchases(session, user) < 1:
        raise FlowError("requires_purchase")

    progress, target = await _evaluate(session, user, key)
    if progress < target:
        raise FlowError("not_completed")

    existing = await session.scalar(
        select(func.count(AchievementClaim.id)).where(
            AchievementClaim.user_id == user.id, AchievementClaim.achievement_key == key
        )
    )
    if existing:
        raise FlowError("already_claimed")

    now = datetime.datetime.utcnow()
    coupon = RewardCoupon(
        user_id=user.id,
        source="achievement",
        coupon_type="free_gb",
        payload=json.dumps({"gb": REWARD_GB, "achievement": key}),
        created_at=now,
        expires_at=now + datetime.timedelta(days=COUPON_EXPIRY_DAYS),
        status="active",
    )
    session.add(coupon)
    await session.flush()

    session.add(AchievementClaim(
        user_id=user.id,
        achievement_key=key,
        coupon_id=coupon.id,
        claimed_at=now,
    ))
    try:
        await session.commit()
    except Exception:
        # unique-constraint race: another claim slipped in between check and insert
        await session.rollback()
        raise FlowError("already_claimed")
    return coupon
