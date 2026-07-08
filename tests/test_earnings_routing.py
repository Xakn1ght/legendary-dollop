"""Two-stage referral earnings routing tests (app.services.flows.earnings).

Covers:
- pre-gate payouts land in store credit, ledgered, capped at 1M lifetime
- a cap-busting payout is rejected whole (voucher not burned by caller)
- crossing 20 active referrals stamps promoter_unlocked_at permanently
- post-gate payouts land in cashback_balance, store credit untouched
- unlock survives active referrals dropping later (permanent)

Run: PYTHONPATH=src python tests/test_earnings_routing.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.rewards_config import REFERRAL_STORE_CREDIT_CAP_TOMAN  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import Base, Referral, Subscription, User  # noqa: E402
from app.services.flows.earnings import (  # noqa: E402
    credit_referral_payout,
    ensure_promoter_unlock,
    referral_store_credit_earned,
)
from app.services.flows.errors import FlowError  # noqa: E402

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


async def test_unlock_is_permanent():
    Session = await _mk(active_referrals=20)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        assert await ensure_promoter_unlock(db, user) is True

        # all referees lapse — the unlock must hold
        subs = (await db.execute(
            __import__("sqlalchemy").future.select(Subscription)
        )).scalars().all()
        for s in subs:
            s.status = "expired"
        await db.commit()

        assert await ensure_promoter_unlock(db, user) is True, "unlock is one-way"
        bucket = await credit_referral_payout(db, user, 30000)
        assert bucket == "cash"
    print("PASS test_unlock_is_permanent")


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
    await test_unlock_is_permanent()
    await test_pre_gate_credit_stays_credit_after_unlock()
    print("ALL EARNINGS ROUTING TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
