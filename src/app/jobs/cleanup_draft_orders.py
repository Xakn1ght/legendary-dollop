import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, text, update
from sqlalchemy.future import select

from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription

logger = logging.getLogger(__name__)


async def cleanup_draft_orders_job(bot=None):
    """
    Cleanup abandoned web purchase orders (draft + legacy ghost rows).

    Why:
    - Web purchase creates a subscription row early to reserve the username and compute pricing.
    - If the user closes the webapp without cancelling/submitting receipt, those rows accumulate and
      can also permanently reserve usernames and hold credit/discounts.

    Policy:
    - Delete draft orders older than DRAFT_TTL_MINUTES.
    - Also delete *legacy ghost* orders created before the draft-status fix:
      status='pending' with receipt_message_id IS NULL (no receipt ever submitted).
    - Refund held credit and restore discounts before deletion.
    """
    DRAFT_TTL_MINUTES = 45
    cutoff = datetime.utcnow() - timedelta(minutes=DRAFT_TTL_MINUTES)

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Subscription).filter(
                Subscription.created_at < cutoff,
                or_(
                    Subscription.status == "draft",
                    # Legacy ghost: pending + no receipt submitted
                    (Subscription.status == "pending") & (Subscription.receipt_message_id == None),  # noqa: E711
                ),
            )
        )
        abandoned = res.scalars().all()
        if not abandoned:
            return

        # Local import to avoid circular import at module load time
        try:
            from app.database.models import (
                ChargeRequest,
                PendingDeletionRequest,
                Receipt,
                ReferralReward,
                RenewalHistory,
                Ticket,
                UserDiscount,
            )
        except Exception:
            UserDiscount = None
            ReferralReward = None
            RenewalHistory = None
            ChargeRequest = None
            Receipt = None
            Ticket = None
            PendingDeletionRequest = None

        async def _delete_dependents(subscription_id: int) -> None:
            # Best-effort cleanup of FK-referencing rows
            try:
                if ReferralReward:
                    await session.execute(delete(ReferralReward).where(ReferralReward.subscription_id == subscription_id))
                if RenewalHistory:
                    await session.execute(delete(RenewalHistory).where(RenewalHistory.subscription_id == subscription_id))
                if ChargeRequest:
                    await session.execute(delete(ChargeRequest).where(ChargeRequest.subscription_id == subscription_id))
                if Receipt:
                    await session.execute(delete(Receipt).where(Receipt.subscription_id == subscription_id))
                if Ticket:
                    await session.execute(
                        update(Ticket)
                        .where(Ticket.subscription_id == subscription_id)
                        .values(subscription_id=None)
                    )
                if PendingDeletionRequest:
                    await session.execute(
                        delete(PendingDeletionRequest).where(PendingDeletionRequest.subscription_id == subscription_id)
                    )
                await session.execute(
                    text("DELETE FROM subscription_links WHERE subscription_id = :sid"),
                    {"sid": subscription_id},
                )
            except Exception as e:
                logger.warning("Failed deleting dependents for order %s: %s", subscription_id, e)

        deleted = 0
        for sub in abandoned:
            try:
                # Refund credit
                if getattr(sub, "credit_used", 0) and sub.user_id:
                    await crud.add_credit(session, sub.user_id, int(sub.credit_used))

                # Restore discounts
                if UserDiscount and getattr(sub, "applied_discount_ids", None):
                    try:
                        id_list = [
                            int(x)
                            for x in str(sub.applied_discount_ids).split(",")
                            if x.strip().isdigit()
                        ]
                        if id_list:
                            r2 = await session.execute(select(UserDiscount).filter(UserDiscount.id.in_(id_list)))
                            discounts = r2.scalars().all()
                            for d in discounts:
                                d.used = False
                    except Exception as e:
                        logger.warning("Failed to restore discounts for draft order %s: %s", sub.id, e)

                await _delete_dependents(int(sub.id))

                # Delete draft subscription row
                await session.delete(sub)
                deleted += 1
            except Exception as e:
                logger.warning("Failed to cleanup abandoned order %s: %s", getattr(sub, "id", None), e)

        try:
            await session.commit()
        except Exception as e:
            logger.error("Failed to commit draft order cleanup: %s", e)
            try:
                await session.rollback()
            except Exception:
                pass
            return

        logger.debug("Cleaned up %s abandoned web orders (older than %s minutes)", deleted, DRAFT_TTL_MINUTES)


