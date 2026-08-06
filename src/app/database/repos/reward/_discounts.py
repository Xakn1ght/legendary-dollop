from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import DailyStarCap, UserDiscount


class _DiscountsMixin:
    """User discounts and daily star caps.

    Lived in _gifts.py until 2026-07-21; the peer-to-peer gift feature around
    it was deleted (UserGift model/table kept dormant, see models/_reward.py).
    """

    @staticmethod
    async def add_user_discount(
        db: AsyncSession,
        user_id: int,
        percent: int,
        expiration: datetime,
        source: str = None,
    ):
        discount = UserDiscount(
            user_id=user_id,
            percent=percent,
            expiration=expiration,
            used=False,
            source=source,
        )
        db.add(discount)
        await db.commit()
        await db.refresh(discount)
        return discount

    @staticmethod
    async def get_active_user_discounts(db: AsyncSession, user_id: int):
        now = datetime.utcnow()
        result = await db.execute(
            select(UserDiscount).filter(
                UserDiscount.user_id == user_id,
                UserDiscount.used == False,  # noqa: E712
                UserDiscount.expiration > now,
            )
        )
        return result.scalars().all()

    @staticmethod
    async def mark_user_discounts_used(db: AsyncSession, discount_ids: list):
        if not discount_ids:
            return
        result = await db.execute(
            select(UserDiscount).filter(UserDiscount.id.in_(discount_ids))
        )
        discounts = result.scalars().all()
        for d in discounts:
            d.used = True
        await db.commit()
        return discounts

    @staticmethod
    async def get_or_create_daily_cap(
        db: AsyncSession, user_id: int, date: date = None, max_allowed: int = 10
    ):
        if date is None:
            date = datetime.utcnow().date()
        result = await db.execute(
            select(DailyStarCap).filter(
                DailyStarCap.user_id == user_id,
                DailyStarCap.date == date,
            )
        )
        cap = result.scalar_one_or_none()
        if not cap:
            cap = DailyStarCap(
                user_id=user_id,
                date=date,
                stars_earned=0,
                max_allowed=max_allowed,
            )
            db.add(cap)
            await db.commit()
            await db.refresh(cap)
        return cap

    @staticmethod
    async def get_daily_cap_status(
        db: AsyncSession, user_id: int, max_allowed: int = 10
    ) -> dict:
        from app.database.repos.reward import RewardRepository as _RR

        cap = await _RR.get_or_create_daily_cap(db, user_id, max_allowed=max_allowed)
        return {
            "stars_earned": cap.stars_earned,
            "max_allowed": cap.max_allowed,
            "remaining": max(cap.max_allowed - cap.stars_earned, 0),
            "can_earn_more": cap.stars_earned < cap.max_allowed,
        }
