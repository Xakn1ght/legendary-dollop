"""
One-time maintenance script to cleanup abandoned / ghost web purchase orders.

Ghost definition:
- status='draft' (new flow) OR
- status='pending' AND receipt_message_id IS NULL (legacy flow before the draft-status fix)

Safety:
- Dry-run by default.
- Use --apply to actually delete and refund.
"""

import os
import sys
import argparse
import asyncio
from datetime import datetime, timedelta

# Ensure project root is on sys.path so `import app.*` works
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isdir(os.path.join(_ROOT, "src", "app")):
    _P = os.path.join(_ROOT, "src")
else:
    _P = _ROOT
if _P not in sys.path:
    sys.path.insert(0, _P)

from sqlalchemy import or_, update
from sqlalchemy import delete, text
from sqlalchemy.future import select

from app.database.models import (
    AsyncSessionLocal,
    Subscription,
    ReferralReward,
    RenewalHistory,
    ChargeRequest,
    Receipt,
    Ticket,
    PendingDeletionRequest,
)
from app.database import crud


async def run_cleanup(*, older_minutes: int, apply: bool, limit: int | None):
    cutoff = datetime.utcnow() - timedelta(minutes=older_minutes)

    async with AsyncSessionLocal() as session:
        q = (
            select(Subscription)
            .filter(
                Subscription.created_at < cutoff,
                or_(
                    Subscription.status == "draft",
                    (Subscription.status == "pending") & (Subscription.receipt_message_id == None),  # noqa: E711
                ),
            )
            .order_by(Subscription.created_at.asc())
        )
        if limit and limit > 0:
            q = q.limit(limit)

        res = await session.execute(q)
        rows = res.scalars().all()

        print(f"Found {len(rows)} abandoned orders older than {older_minutes} minutes.")
        if not rows:
            return

        # Show a short preview (no secrets)
        preview = rows[: min(20, len(rows))]
        for s in preview:
            print(
                f"- id={s.id} status={s.status} username={s.marzban_username} "
                f"receipt_message_id={s.receipt_message_id} created_at={s.created_at}"
            )
        if len(rows) > len(preview):
            print(f"... and {len(rows) - len(preview)} more")

        if not apply:
            print("Dry-run mode. Re-run with --apply to actually refund + delete.")
            return

        # Import here to avoid circular imports at module import time
        try:
            from app.database.models import UserDiscount
        except Exception:
            UserDiscount = None

        async def _delete_dependents(subscription_id: int) -> None:
            """
            Delete rows that reference subscriptions.id so Postgres doesn't block deletion.
            Keep this conservative: only tables that should not contain meaningful data
            for abandoned orders.
            """
            # Safe to delete for abandoned orders
            await session.execute(delete(ReferralReward).where(ReferralReward.subscription_id == subscription_id))
            await session.execute(delete(RenewalHistory).where(RenewalHistory.subscription_id == subscription_id))
            await session.execute(delete(ChargeRequest).where(ChargeRequest.subscription_id == subscription_id))
            await session.execute(delete(Receipt).where(Receipt.subscription_id == subscription_id))
            # Tickets should be preserved; just detach them from the deleted subscription
            await session.execute(
                update(Ticket)
                .where(Ticket.subscription_id == subscription_id)
                .values(subscription_id=None)
            )
            # Deletion requests referencing this subscription become invalid once we delete it
            await session.execute(
                delete(PendingDeletionRequest).where(PendingDeletionRequest.subscription_id == subscription_id)
            )
            # Raw link table (not a mapped model)
            await session.execute(
                text("DELETE FROM subscription_links WHERE subscription_id = :sid"),
                {"sid": subscription_id},
            )

        deleted = 0
        for sub in rows:
            # Refund credit
            if getattr(sub, "credit_used", 0) and sub.user_id:
                await crud.add_credit(session, sub.user_id, int(sub.credit_used))

            # Restore discounts
            if UserDiscount and getattr(sub, "applied_discount_ids", None):
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

            # Remove FK dependents first
            await _delete_dependents(int(sub.id))

            await session.delete(sub)
            deleted += 1

        await session.commit()
        print(f"Applied. Deleted {deleted} abandoned orders and refunded/restore where needed.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--older-minutes", type=int, default=45)
    p.add_argument("--apply", action="store_true", default=False)
    p.add_argument("--limit", type=int, default=0, help="Optional limit (0 = no limit)")
    args = p.parse_args()

    asyncio.run(
        run_cleanup(
            older_minutes=max(1, int(args.older_minutes)),
            apply=bool(args.apply),
            limit=(None if not args.limit else int(args.limit)),
        )
    )


if __name__ == "__main__":
    main()


