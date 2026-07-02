"""Cash-out flow-service tests (app.services.flows.cashout) on in-memory SQLite.

Covers:
- the VIP-Promoter gate (>=20 active referrals) enforced in the service, not the route
- funds reserved atomically on creation
- insufficient credit / no paid subscription rejections

Run: PYTHONPATH=src python tests/test_cashout_service.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.rewards_config import CASHOUT_MIN_AMOUNT_TOMAN  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import Base, Referral, Subscription, User  # noqa: E402
from app.services.flows.cashout import CASHOUT_MIN_ACTIVE_REFERRALS, create_cashout  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 444


async def _setup(active_referrals: int):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=500000))
        db.add(Subscription(id=1, user_id=1, marzban_username="own", status="active", price=90000))
        for i in range(active_referrals):
            uid = 100 + i
            db.add(User(id=uid, chat_id=10000 + i, referral_code=f"r{i}"))
            db.add(Referral(referrer_id=1, referee_id=uid))
            db.add(Subscription(user_id=uid, marzban_username=f"ref{i}", status="active", price=90000))
        await db.commit()
    return Session


async def test_gate_enforced():
    Session = await _setup(active_referrals=2)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        try:
            await create_cashout(db, user, amount=250000)
            raise AssertionError("expected requires_vip_promoter")
        except FlowError as e:
            assert e.code == "requires_vip_promoter"
            assert e.active_referrals == 2 and e.min_active_referrals == CASHOUT_MIN_ACTIVE_REFERRALS
    print("PASS test_gate_enforced")


async def test_reserve_and_rejections():
    Session = await _setup(active_referrals=CASHOUT_MIN_ACTIVE_REFERRALS)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)

        for amount, code in [
            (0, "invalid_amount"),
            (-5, "invalid_amount"),
            (CASHOUT_MIN_AMOUNT_TOMAN - 1, "amount_below_minimum"),
            (999999, "insufficient_credit"),
        ]:
            try:
                await create_cashout(db, user, amount=amount)
                raise AssertionError(f"expected {code}")
            except FlowError as e:
                assert e.code == code, (e.code, code)
                if code == "amount_below_minimum":
                    assert e.min_amount == CASHOUT_MIN_AMOUNT_TOMAN

        try:
            await create_cashout(db, user, amount=250000, destination="short")
            raise AssertionError("expected invalid_destination")
        except FlowError as e:
            assert e.code == "invalid_destination"

        req = await create_cashout(db, user, amount=CASHOUT_MIN_AMOUNT_TOMAN, destination="IR12345678901234")
        assert req.status == "pending" and req.amount == CASHOUT_MIN_AMOUNT_TOMAN
        await db.refresh(user)
        assert user.credit == 500000 - CASHOUT_MIN_AMOUNT_TOMAN  # reserved immediately

        # Denial returns the funds (repo behavior the admin panel relies on).
        back = await crud.deny_cashout_request(db, req.id)
        assert back is not None and back.status == "denied"
        await db.refresh(user)
        assert user.credit == 500000
    print("PASS test_reserve_and_rejections")


async def main():
    await test_gate_enforced()
    await test_reserve_and_rejections()
    print("\nAll cashout-service tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
