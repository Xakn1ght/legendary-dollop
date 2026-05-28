from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models import DailyStarCap, UserDiscount, UserGift


class _GiftsMixin:
    @staticmethod
    async def create_user_gift(
        db: AsyncSession,
        sender_id: int,
        receiver_id: int,
        gift_type: str,
        gift_value: int,
        message: str = None,
        plan_name: str | None = None,
    ):
        gift = UserGift(
            sender_id=sender_id,
            receiver_id=receiver_id,
            gift_type=gift_type,
            gift_value=gift_value,
            plan_name=plan_name,
            message=message,
        )
        db.add(gift)
        await db.commit()
        await db.refresh(gift)
        return gift

    @staticmethod
    async def get_user_gifts(db: AsyncSession, user_id: int, gift_type: str = "received"):
        if gift_type == "received":
            result = await db.execute(
                select(UserGift)
                .options(selectinload(UserGift.sender))
                .filter(UserGift.receiver_id == user_id)
            )
        else:
            result = await db.execute(
                select(UserGift)
                .options(selectinload(UserGift.receiver))
                .filter(UserGift.sender_id == user_id)
            )
        return result.scalars().all()

    @staticmethod
    async def accept_user_gift(db: AsyncSession, gift_id: int):
        result = await db.execute(
            select(UserGift).filter(
                UserGift.id == gift_id,
                UserGift.accepted == False,  # noqa: E712
            )
        )
        gift = result.scalars().first()
        if not gift:
            return None

        if gift.gift_type == "credit":
            from app.database.repos.user import UserRepository

            await UserRepository.add_credit(db, gift.receiver_id, gift.gift_value)
        elif gift.gift_type == "loyalty_points":
            from app.database.repos.reward import RewardRepository as _RR

            await _RR.add_loyalty_points(db, gift.receiver_id, gift.gift_value, "gift")

        gift.accepted = True
        gift.accepted_at = datetime.utcnow()
        await db.commit()
        await db.refresh(gift)
        return gift

    @staticmethod
    async def set_gift_payment_status(
        db: AsyncSession,
        gift_id: int,
        status: str,
        receipt_message_id: int | None = None,
    ):
        result = await db.execute(select(UserGift).filter(UserGift.id == gift_id))
        gift = result.scalars().first()
        if not gift:
            return None
        gift.payment_status = status
        if receipt_message_id is not None:
            gift.payment_receipt_message_id = receipt_message_id
        await db.commit()
        await db.refresh(gift)
        return gift

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
