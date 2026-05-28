from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models import StarRewardTier, UserStarRewardClaim


class _TiersMixin:
    @staticmethod
    async def create_star_reward_tier(db: AsyncSession, tier_data: dict):
        new_tier = StarRewardTier(**tier_data)
        db.add(new_tier)
        await db.commit()
        await db.refresh(new_tier)
        return new_tier

    @staticmethod
    async def get_star_reward_tier(db: AsyncSession, tier_id: int):
        result = await db.execute(select(StarRewardTier).filter(StarRewardTier.id == tier_id))
        return result.scalars().first()

    @staticmethod
    async def get_all_star_reward_tiers(db: AsyncSession, active_only: bool = True):
        query = select(StarRewardTier)
        if active_only:
            query = query.filter(StarRewardTier.is_active == True)  # noqa: E712
        result = await db.execute(query.order_by(StarRewardTier.star_threshold))
        return result.scalars().all()

    @staticmethod
    async def update_star_reward_tier(db: AsyncSession, tier_id: int, tier_data: dict):
        from app.database.repos.reward import RewardRepository as _RR

        tier = await _RR.get_star_reward_tier(db, tier_id)
        if tier:
            for key, value in tier_data.items():
                setattr(tier, key, value)
            await db.commit()
            await db.refresh(tier)
        return tier

    @staticmethod
    async def delete_star_reward_tier(db: AsyncSession, tier_id: int):
        from app.database.repos.reward import RewardRepository as _RR

        tier = await _RR.get_star_reward_tier(db, tier_id)
        if tier:
            await db.delete(tier)
            await db.commit()
        return tier

    @staticmethod
    async def create_user_star_reward_claim(db: AsyncSession, user_id: int, tier_id: int):
        now = datetime.utcnow()
        expires = now + timedelta(days=3)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(UserStarRewardClaim).filter(
                UserStarRewardClaim.user_id == user_id,
                UserStarRewardClaim.tier_id == tier_id,
                UserStarRewardClaim.status == "offered",
                UserStarRewardClaim.offered_at >= start_of_month,
            )
        )
        if result.scalars().first():
            return None

        new_claim = UserStarRewardClaim(user_id=user_id, tier_id=tier_id, expires_at=expires)
        db.add(new_claim)
        await db.commit()
        await db.refresh(new_claim)
        return new_claim

    @staticmethod
    async def get_user_unclaimed_rewards(db: AsyncSession, user_id: int):
        now = datetime.utcnow()
        result = await db.execute(
            select(UserStarRewardClaim)
            .options(selectinload(UserStarRewardClaim.tier))
            .filter(
                UserStarRewardClaim.user_id == user_id,
                UserStarRewardClaim.status.in_(["offered", "pending_subscription"]),
                UserStarRewardClaim.expires_at > now,
            )
            .order_by(UserStarRewardClaim.offered_at.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def claim_user_star_reward(db: AsyncSession, claim_id: int, reward_type: str):
        result = await db.execute(
            select(UserStarRewardClaim)
            .options(selectinload(UserStarRewardClaim.tier))
            .filter(UserStarRewardClaim.id == claim_id)
        )
        claim = result.scalars().first()

        if not claim or claim.status != "offered" or claim.expires_at <= datetime.utcnow():
            return None, "Claim not found, already claimed, or expired."

        if reward_type != claim.tier.reward_type:
            return None, "Invalid reward choice."

        claim.status = "claimed"
        claim.claimed_at = datetime.utcnow()
        claim.chosen_reward_type = reward_type

        await db.commit()
        await db.refresh(claim)
        return claim, "Success"

    @staticmethod
    async def get_user_star_reward_claim_by_id(db: AsyncSession, claim_id: int):
        result = await db.execute(
            select(UserStarRewardClaim)
            .options(selectinload(UserStarRewardClaim.tier))
            .filter(UserStarRewardClaim.id == claim_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_pending_extradays_claim(db: AsyncSession, user_id: int):
        now = datetime.utcnow()
        result = await db.execute(
            select(UserStarRewardClaim)
            .options(selectinload(UserStarRewardClaim.tier))
            .join(UserStarRewardClaim.tier)
            .filter(
                UserStarRewardClaim.user_id == user_id,
                UserStarRewardClaim.status == "pending_subscription",
                StarRewardTier.reward_type == "extra_days",
                UserStarRewardClaim.expires_at > now,
            )
            .order_by(UserStarRewardClaim.offered_at.desc())
            .limit(1)
        )
        return result.scalars().first()
