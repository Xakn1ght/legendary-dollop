"""Star Season engine: active season, season-star progress, milestone → coupon unlock.

Stars are referral-only and seasonal (reset every STAR_SEASON_LENGTH_DAYS). Reaching
a milestone auto-creates a coupon in the wallet, exactly once per season (deduped by
claim_key). See core/rewards_config.py for the ladder and rules.
"""
import datetime
import json

from sqlalchemy import select

from app.core.rewards_config import (
    COUPON_EXPIRY_DAYS,
    STAR_SEASON_LENGTH_DAYS,
    STAR_SEASON_MILESTONES,
)
from app.database.models import (
    RewardCoupon,
    StarMilestoneClaim,
    StarSeason,
    UserStarProgress,
)


class _SeasonMixin:
    @staticmethod
    async def get_or_create_active_season(db) -> StarSeason:
        """Return the current active season, creating one if none is active/in-window."""
        now = datetime.datetime.utcnow()
        season = (await db.execute(
            select(StarSeason)
            .filter(StarSeason.is_active == True)  # noqa: E712
            .order_by(StarSeason.starts_at.desc())
        )).scalars().first()
        if season and season.starts_at <= now <= season.ends_at:
            return season
        # No valid active season → rotate: deactivate any stale one, open a fresh window.
        if season and now > season.ends_at:
            season.is_active = False
        new_season = StarSeason(
            name=f"Season {now:%Y-%m}",
            starts_at=now,
            ends_at=now + datetime.timedelta(days=STAR_SEASON_LENGTH_DAYS),
            is_active=True,
        )
        db.add(new_season)
        await db.commit()
        await db.refresh(new_season)
        return new_season

    @staticmethod
    async def _get_or_create_progress(db, user_id: int, season_id: int) -> UserStarProgress:
        prog = (await db.execute(
            select(UserStarProgress).filter(
                UserStarProgress.user_id == user_id,
                UserStarProgress.season_id == season_id,
            )
        )).scalars().first()
        if prog is None:
            prog = UserStarProgress(user_id=user_id, season_id=season_id, season_stars=0)
            db.add(prog)
            await db.commit()
            await db.refresh(prog)
        return prog

    @staticmethod
    async def add_season_stars(db, user_id: int, count: int):
        """Add season stars to the user's active-season progress and unlock any newly
        reached milestones. Returns (new_total, [unlocked_coupon_info, ...])."""
        if count <= 0:
            return 0, []
        from app.database.repos.reward import RewardRepository as _RR

        season = await _RR.get_or_create_active_season(db)
        prog = await _RR._get_or_create_progress(db, user_id, season.id)
        prog.season_stars += count
        await db.commit()
        await db.refresh(prog)

        unlocked = await _RR._unlock_milestones(db, user_id, season.id, prog.season_stars)
        return prog.season_stars, unlocked

    @staticmethod
    async def _unlock_milestones(db, user_id: int, season_id: int, total_stars: int):
        """Create a coupon for every milestone <= total_stars not yet claimed this season."""
        unlocked = []
        for milestone in sorted(STAR_SEASON_MILESTONES):
            if milestone > total_stars:
                break
            claim_key = f"star_season:{season_id}:milestone:{milestone}:user:{user_id}"
            exists = (await db.execute(
                select(StarMilestoneClaim).filter(StarMilestoneClaim.claim_key == claim_key)
            )).scalars().first()
            if exists:
                continue
            info = STAR_SEASON_MILESTONES[milestone]
            now = datetime.datetime.utcnow()
            coupon = RewardCoupon(
                user_id=user_id,
                source="star_season",
                season_id=season_id,
                milestone_stars=milestone,
                coupon_type=info["coupon_type"],
                payload=json.dumps(info.get("payload", {})),
                created_at=now,
                expires_at=now + datetime.timedelta(days=COUPON_EXPIRY_DAYS),
                status="active",
            )
            db.add(coupon)
            db.add(StarMilestoneClaim(
                user_id=user_id, season_id=season_id,
                milestone_stars=milestone, claim_key=claim_key, created_at=now,
            ))
            await db.commit()
            await db.refresh(coupon)
            unlocked.append({
                "coupon_id": coupon.id, "milestone": milestone,
                "name": info["name"], "coupon_type": info["coupon_type"],
            })
        return unlocked

    @staticmethod
    async def get_active_coupons(db, user_id: int):
        """Active, non-expired coupons in the user's wallet (also lazily expires stale ones)."""
        now = datetime.datetime.utcnow()
        coupons = (await db.execute(
            select(RewardCoupon).filter(
                RewardCoupon.user_id == user_id,
                RewardCoupon.status == "active",
            ).order_by(RewardCoupon.created_at.desc())
        )).scalars().all()
        live = []
        changed = False
        for c in coupons:
            if c.expires_at and c.expires_at < now:
                c.status = "expired"
                changed = True
            else:
                live.append(c)
        if changed:
            await db.commit()
        return live

    @staticmethod
    async def end_active_season(db):
        """Deactivate the current season (used by the reset job). The next call to
        get_or_create_active_season opens a fresh window with everyone at 0 stars."""
        season = (await db.execute(
            select(StarSeason).filter(StarSeason.is_active == True)  # noqa: E712
        )).scalars().first()
        if season:
            season.is_active = False
            await db.commit()
        return season
