from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import StarHistory, User
from app.utils.logger import bot_logger


class _StarsMixin:
    @staticmethod
    async def add_stars(
        db: AsyncSession,
        user_id: int,
        count: int,
        reason: str = "general",
        source_id: int = None,
        notes: str = None,
    ) -> tuple:
        if count == 0:
            raise ValueError("count must be non-zero")

        from app.database.repos.reward import RewardRepository as _RR

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return user, False, []

        original_stars = user.stars
        if count < 0 and (user.stars + count) < 0:
            return user, False, []
        user.stars += count

        await _RR.log_star_change(db, user_id, count, reason, source_id, notes)

        bot_logger.info(
            f"[STAR_MANAGER] Added {count} stars to user {user_id} for '{reason}'. "
            f"Original: {original_stars}, New: {user.stars}"
        )

        newly_unlocked_tiers = []
        if count > 0:
            all_tiers = await _RR.get_all_star_reward_tiers(db)
            for tier in all_tiers:
                if original_stars < tier.star_threshold <= user.stars:
                    claim = await _RR.create_user_star_reward_claim(db, user_id, tier.id)
                    if claim:
                        newly_unlocked_tiers.append(tier)

        threshold_reached = user.stars >= 5
        await db.commit()
        await db.refresh(user)
        return user, threshold_reached, newly_unlocked_tiers

    @staticmethod
    async def reset_stars(
        db: AsyncSession,
        user_id: int,
        reason: str = "reset",
        source_id: int = None,
        notes: str = None,
    ) -> User:
        from app.database.repos.reward import RewardRepository as _RR

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if user and user.stars > 0:
            await _RR.log_star_change(db, user_id, -user.stars, reason, source_id, notes)
            user.stars = 0
            await db.commit()
            await db.refresh(user)
        return user

    @staticmethod
    async def get_star_balance(db: AsyncSession, user_id: int) -> int:
        result = await db.execute(select(User.stars).filter(User.id == user_id))
        return result.scalar() or 0

    @staticmethod
    async def transfer_stars(
        db: AsyncSession,
        from_user_id: int,
        to_user_id: int,
        count: int,
        reason: str = "transfer",
        notes: str = None,
    ) -> tuple:
        if count <= 0:
            return False, "Transfer amount must be positive"

        from app.database.repos.reward import RewardRepository as _RR

        sender_stars = await _RR.get_star_balance(db, from_user_id)
        if sender_stars < count:
            return False, f"Insufficient stars. Have {sender_stars}, need {count}"

        await _RR.add_stars(db, from_user_id, -count, f"{reason}_out", None, notes)
        await _RR.add_stars(db, to_user_id, count, f"{reason}_in", None, notes)
        return True, f"Successfully transferred {count} stars"

    @staticmethod
    async def log_star_change(
        db: AsyncSession,
        user_id: int,
        delta: int,
        reason: str,
        source_id: int = None,
        notes: str = None,
    ):
        star_entry = StarHistory(
            user_id=user_id,
            delta=delta,
            reason=reason,
            source_id=source_id,
            notes=notes,
        )
        db.add(star_entry)
        await db.commit()
        await db.refresh(star_entry)
        return star_entry

    @staticmethod
    async def get_star_history(db: AsyncSession, user_id: int, limit: int = 50):
        result = await db.execute(
            select(StarHistory)
            .filter(StarHistory.user_id == user_id)
            .order_by(StarHistory.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
