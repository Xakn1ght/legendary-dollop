"""Two-stage referral earnings routing tests (app.services.flows.earnings).

Covers (LIVE-gate semantics, 2026-07-09):
- below-gate payouts land in store credit, ledgered, capped at 1M lifetime
- a cap-busting payout is rejected whole (voucher not burned by caller)
- >=20 active referrals routes to cashback_balance, store credit untouched
- the gate is LIVE: dropping under 20 re-routes new payouts to store credit
  (already-earned cash stays) — the old permanent unlock is gone
- "active referral" = referee BOUGHT within the trailing 30 days
  (provisioned sub or approved charge; purchase recency, not sub status)

Run: PYTHONPATH=src python tests/test_earnings_routing.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.rewards_config import REFERRAL_STORE_CREDIT_CAP_TOMAN  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import Base, ChargeRequest, Referral, Subscription, User  # noqa: E402
from app.services.flows.cashout import count_active_referrals  # noqa: E402
from app.services.flows.earnings import (  # noqa: E402
    credit_referral_payout,
    ensure_promoter_unlock,
    referral_store_credit_earned,
)
from app.services.flows.errors import FlowError  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 555


async def _mk(active_referrals: int):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me"))
        for i in range(active_referrals):
            uid = 100 + i
            db.add(User(id=uid, chat_id=9000 + i, referral_code=f"r{i}"))
            db.add(Referral(referrer_id=1, referee_id=uid))
            # created_at defaults to now → a recent purchase → active referee
            db.add(Subscription(user_id=uid, marzban_username=f"ref{i}", status="active", price=90000))
        await db.commit()
    return Session


async def test_pre_gate_credit_and_cap():
    Session = await _mk(active_referrals=3)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)

        bucket = await credit_referral_payout(db, user, 40000, source_id=None)
        assert bucket == "credit"
        await db.refresh(user)
        assert user.credit == 40000 and user.cashback_balance == 0
        assert await referral_store_credit_earned(db, 1) == 40000

        # fill almost to the cap, then bust it
        bucket = await credit_referral_payout(db, user, REFERRAL_STORE_CREDIT_CAP_TOMAN - 40000)
        assert bucket == "credit"
        assert await referral_store_credit_earned(db, 1) == REFERRAL_STORE_CREDIT_CAP_TOMAN
        try:
            await credit_referral_payout(db, user, 1000)
            raise AssertionError("expected credit_cap_reached")
        except FlowError as e:
            assert e.code == "credit_cap_reached"
        await db.refresh(user)
        assert user.credit == REFERRAL_STORE_CREDIT_CAP_TOMAN, "cap bust must grant nothing"
    print("PASS test_pre_gate_credit_and_cap")


async def test_unlock_routes_to_cash():
    Session = await _mk(active_referrals=20)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        assert user.promoter_unlocked_at is None

        bucket = await credit_referral_payout(db, user, 55000)
        assert bucket == "cash"
        await db.refresh(user)
        assert user.promoter_unlocked_at is not None, "gate crossing must stamp the unlock"
        assert user.cashback_balance == 55000
        assert user.credit == 0, "post-gate cuts never touch store credit"
    print("PASS test_unlock_routes_to_cash")


async def test_gate_is_live_and_recloses():
    Session = await _mk(active_referrals=20)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        assert await ensure_promoter_unlock(db, user) is True
        bucket = await credit_referral_payout(db, user, 30000)
        assert bucket == "cash"

        # Referees stop BUYING: age all their purchases past the 30-day
        # window (status stays 'active' — recency is what counts).
        subs = (await db.execute(
            __import__("sqlalchemy").future.select(Subscription)
        )).scalars().all()
        old = datetime.datetime.utcnow() - datetime.timedelta(days=45)
        for s in subs:
            s.created_at = old
        await db.commit()

        assert await count_active_referrals(db, 1) == 0
        assert await ensure_promoter_unlock(db, user) is False, "gate must re-close under 20"
        bucket = await credit_referral_payout(db, user, 20000)
        assert bucket == "credit", "below the live gate new payouts return to store credit"
        await db.refresh(user)
        assert user.cashback_balance == 30000, "already-earned cash stays"
        assert user.credit == 20000

        # One referee buys again (fresh charge approval) — 1 active, still under.
        db.add(ChargeRequest(user_id=100, subscription_id=1, traffic_bytes=0, price=50000, status="approved"))
        await db.commit()
        assert await count_active_referrals(db, 1) == 1
    print("PASS test_gate_is_live_and_recloses")


async def test_active_definition_recent_buyers_only():
    """Expired-but-recent purchase counts; old still-active sub does not."""
    Session = await _mk(active_referrals=0)
    async with Session() as db:
        now = datetime.datetime.utcnow()
        # referee A: bought 10 days ago, sub already expired → ACTIVE referee
        db.add(User(id=201, chat_id=9201, referral_code="ra"))
        db.add(Referral(referrer_id=1, referee_id=201))
        db.add(Subscription(user_id=201, marzban_username="ra1", status="expired", price=90000,
                            created_at=now - datetime.timedelta(days=10)))
        # referee B: bought 60 days ago, sub STILL active → not active anymore
        db.add(User(id=202, chat_id=9202, referral_code="rb"))
        db.add(Referral(referrer_id=1, referee_id=202))
        db.add(Subscription(user_id=202, marzban_username="rb1", status="active", price=90000,
                            created_at=now - datetime.timedelta(days=60)))
        # referee C: only a pending (never approved) order 5 days ago → not active
        db.add(User(id=203, chat_id=9203, referral_code="rc"))
        db.add(Referral(referrer_id=1, referee_id=203))
        db.add(Subscription(user_id=203, marzban_username="rc1", status="pending", price=90000,
                            created_at=now - datetime.timedelta(days=5)))
        await db.commit()
        assert await count_active_referrals(db, 1) == 1
    print("PASS test_active_definition_recent_buyers_only")


async def test_pre_gate_credit_stays_credit_after_unlock():
    Session = await _mk(active_referrals=19)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        await credit_referral_payout(db, user, 200000)  # store credit
        # 20th active referral arrives
        db.add(User(id=990, chat_id=9990, referral_code="r99"))
        db.add(Referral(referrer_id=1, referee_id=990))
        db.add(Subscription(user_id=990, marzban_username="ref99", status="active", price=90000))
        await db.commit()

        bucket = await credit_referral_payout(db, user, 100000)
        assert bucket == "cash"
        await db.refresh(user)
        assert user.credit == 200000, "old store credit must not convert to cash"
        assert user.cashback_balance == 100000
    print("PASS test_pre_gate_credit_stays_credit_after_unlock")


async def main():
    await test_pre_gate_credit_and_cap()
    await test_unlock_routes_to_cash()
    await test_gate_is_live_and_recloses()
    await test_active_definition_recent_buyers_only()
    await test_pre_gate_credit_stays_credit_after_unlock()
    print("ALL EARNINGS ROUTING TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
