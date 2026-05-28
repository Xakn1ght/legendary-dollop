from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.level_config import get_level_from_xp, get_level_rewards
from app.database.models import RewardConfig as _RewardConfig
from app.database.models import RewardHistory, User


class _PointsMixin:
    @staticmethod
    async def add_reward_history(
        db: AsyncSession,
        user_id: int,
        reward_type: str,
        reward_value: int,
        source: str,
        source_id: int = None,
        notes: str = None,
    ):
        entry = RewardHistory(
            user_id=user_id,
            reward_type=reward_type,
            reward_value=reward_value,
            source=source,
            source_id=source_id,
            notes=notes,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def get_user_reward_history(db: AsyncSession, user_id: int, limit: int = 50):
        result = await db.execute(
            select(RewardHistory)
            .filter(RewardHistory.user_id == user_id)
            .order_by(RewardHistory.earned_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def add_experience_points(
        db: AsyncSession, user_id: int, points: int, source: str = "general"
    ):
        if points <= 0:
            return None, False

        from app.database.repos.reward import RewardRepository as _RR

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None, False

        old_level = user.level
        user.experience_points += points
        new_level = get_level_from_xp(user.experience_points)
        user.level = new_level

        await _RR.add_reward_history(db, user_id, "xp", points, source)
        await db.commit()
        await db.refresh(user)

        leveled_up = new_level > old_level
        if leveled_up:
            rewards = get_level_rewards(new_level)
            if rewards.get("loyalty_points"):
                user.loyalty_points += rewards["loyalty_points"]
                await _RR.add_reward_history(db, user_id, "loyalty_points", rewards["loyalty_points"], "level_up", new_level)
            if rewards.get("credit"):
                user.credit += rewards["credit"]
                await _RR.add_reward_history(db, user_id, "credit", rewards["credit"], "level_up", new_level)
            await db.commit()
            await db.refresh(user)

        return user, leveled_up

    @staticmethod
    async def add_loyalty_points(
        db: AsyncSession,
        user_id: int,
        points: int,
        source: str = "general",
        description: str | None = None,
    ):
        if points <= 0:
            return None

        from app.database.repos.reward import RewardRepository as _RR

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if user:
            user.loyalty_points += points
            await _RR.add_reward_history(db, user_id, "loyalty_points", points, source, notes=description)
            await db.commit()
            await db.refresh(user)
        return user

    @staticmethod
    async def deduct_loyalty_points(
        db: AsyncSession,
        user_id: int,
        points: int,
        reason: str | None = None,
    ):
        if points <= 0:
            return None

        from app.database.repos.reward import RewardRepository as _RR

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user or user.loyalty_points < points:
            return None

        user.loyalty_points -= points
        await _RR.add_reward_history(db, user_id, "loyalty_points", -points, "deduction", notes=reason)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_reward_config(db: AsyncSession):
        result = await db.execute(select(_RewardConfig).limit(1))
        cfg = result.scalars().first()
        if cfg is None:
            cfg = _RewardConfig(traffic_percent=10.0, days_percent=10.0, credit_percent=10.0)
            db.add(cfg)
            await db.commit()
            await db.refresh(cfg)
        return cfg

    @staticmethod
    async def update_reward_config(db: AsyncSession, **kwargs):
        from app.database.repos.reward import RewardRepository as _RR

        cfg = await _RR.get_reward_config(db)
        allowed = {"traffic_percent", "days_percent", "credit_percent"}
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                setattr(cfg, k, v)
        await db.commit()
        await db.refresh(cfg)
        return cfg

    @staticmethod
    async def check_level_up(db: AsyncSession, user_id: int):
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None, False

        old_level = user.level
        new_level = get_level_from_xp(user.experience_points)

        if new_level > old_level:
            user.level = new_level
            await db.commit()
            await db.refresh(user)
            return user, True

        return user, False

    @staticmethod
    async def calculate_and_award_cashback(db: AsyncSession, user_id: int, milestone: int) -> int:
        from app.database.repos.reward import RewardRepository as _RR
        from app.database.repos.subscription import SubscriptionRepository

        subs = await SubscriptionRepository.get_user_subscriptions(db, user_id)
        if len(subs) < milestone:
            return 0

        last_subs = subs[-milestone:]
        total_cashback = 0
        for sub in last_subs:
            if not sub.price:
                continue
            plan_name = sub.plan_name or ""
            if "20" in plan_name or sub.price <= 70000:
                rate = 0.03
            elif "40" in plan_name or sub.price <= 140000:
                rate = 0.04
            elif "60" in plan_name or sub.price <= 200000:
                rate = 0.05
            else:
                rate = 0.06
            total_cashback += int(sub.price * rate)

        if total_cashback > 0:
            from app.database.repos.user import UserRepository

            await UserRepository.add_credit(db, user_id, total_cashback)
            await _RR.add_reward_history(
                db,
                user_id,
                "credit",
                total_cashback,
                "purchase_cashback",
                notes=f"Cashback for {milestone} purchases",
            )

        return total_cashback
