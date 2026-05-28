from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import CashoutRequest, Subscription, User


class CashoutRepository:
    @staticmethod
    async def has_active_paid_subscription(db: AsyncSession, user_id: int) -> bool:
        """True if user has at least one active *paid* subscription.

        For older rows where `price` may be NULL, we treat it as paid.
        """
        cnt = await db.scalar(
            select(func.count(Subscription.id)).where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == "active",
                    or_(Subscription.price.is_(None), Subscription.price > 0),
                )
            )
        )
        return bool((cnt or 0) > 0)

    @staticmethod
    async def create_cashout_request(
        db: AsyncSession,
        user_id: int,
        amount: int,
        destination: str | None = None,
    ) -> CashoutRequest | None:
        if amount <= 0:
            return None

        user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
        if not user:
            return None

        if not await CashoutRepository.has_active_paid_subscription(db, user_id):
            return None

        amount = int(amount)
        if user.credit < amount:
            return None

        # Reserve funds by deducting immediately.
        user.credit -= amount

        req = CashoutRequest(
            user_id=user_id,
            amount=amount,
            destination=(destination or None),
            status="pending",
            requested_at=datetime.utcnow(),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    @staticmethod
    async def get_cashout_request(db: AsyncSession, request_id: int) -> CashoutRequest | None:
        return (await db.execute(select(CashoutRequest).where(CashoutRequest.id == request_id))).scalars().first()

    @staticmethod
    async def list_cashout_requests(
        db: AsyncSession,
        status: str | None = None,
        limit: int = 50,
    ) -> list[CashoutRequest]:
        q = select(CashoutRequest).order_by(CashoutRequest.requested_at.desc()).limit(limit)
        if status:
            q = q.where(CashoutRequest.status == status)
        rows = await db.execute(q)
        return rows.scalars().all()

    @staticmethod
    async def deny_cashout_request(
        db: AsyncSession,
        request_id: int,
        admin_user_id: int | None = None,
        admin_note: str | None = None,
    ) -> CashoutRequest | None:
        req = await CashoutRepository.get_cashout_request(db, request_id)
        if not req or req.status != "pending":
            return None

        user = (await db.execute(select(User).where(User.id == req.user_id))).scalars().first()
        if user:
            user.credit += int(req.amount or 0)

        req.status = "denied"
        req.processed_at = datetime.utcnow()
        req.processed_by = admin_user_id
        req.admin_note = admin_note

        await db.commit()
        await db.refresh(req)
        return req

    @staticmethod
    async def mark_cashout_paid(
        db: AsyncSession,
        request_id: int,
        admin_user_id: int | None = None,
        receipt_file_id: str | None = None,
        receipt_message_id: int | None = None,
        admin_note: str | None = None,
    ) -> CashoutRequest | None:
        req = await CashoutRepository.get_cashout_request(db, request_id)
        if not req or req.status != "pending":
            return None

        req.status = "paid"
        req.processed_at = datetime.utcnow()
        req.processed_by = admin_user_id
        req.admin_note = admin_note
        req.receipt_file_id = receipt_file_id
        req.receipt_message_id = receipt_message_id

        await db.commit()
        await db.refresh(req)
        return req

