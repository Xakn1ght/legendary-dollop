"""Free-trial eligibility and cooldowns (app.services.flows.free_tests).

Eligibility is derived from the subscriptions table, so these tests construct
rows in each state and assert what the derivation concludes. The two rules that
matter most:

- the two trials are counted INDEPENDENTLY (a normal trial must not block a
  Pro trial), and
- a row that no longer exists (pre-provision failure rolled back) leaves the
  allowance intact, while a row that survived provisioning consumes it.

Run: PYTHONPATH=src python tests/test_free_tests.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.products import PRO_TEST_PLAN, TEST_PLAN  # noqa: E402
from app.database.models import Base, Subscription, User  # noqa: E402
from app.services.flows import free_tests as ft  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 9001


async def _setup():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me"))
        await db.commit()
    return Session


async def _add_trial(Session, tier, days_ago, status="active"):
    async with Session() as db:
        db.add(Subscription(
            user_id=1, marzban_username=f"{tier}-{days_ago}-{status}",
            plan_name=tier, status=status, price=0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=days_ago),
        ))
        await db.commit()


async def _user(Session):
    """Caller owns the session and must close it - returning one out of an
    `async with` closes it early and leaves the pool complaining at exit."""
    from app.database import crud

    db = Session()
    return db, await crud.get_user(db, CHAT)


async def test_fresh_user_is_allowed():
    Session = await _setup()
    db, user = await _user(Session)
    assert await ft.is_free_test_available(db, user, TEST_PLAN)
    assert await ft.is_free_test_available(db, user, PRO_TEST_PLAN)
    await ft.assert_test_allowed(db, user, TEST_PLAN)
    await db.close()
    print("fresh user allowed both trials OK")


async def test_recent_trial_blocks_same_tier_only():
    Session = await _setup()
    await _add_trial(Session, TEST_PLAN, days_ago=3)
    db, user = await _user(Session)
    # 3 days into a 7-day cooldown
    assert not await ft.is_free_test_available(db, user, TEST_PLAN)
    remaining = await ft.test_cooldown_remaining(db, user, TEST_PLAN)
    assert 3 * 86400 < remaining <= 4 * 86400, remaining
    # ...and the Pro trial is untouched. This is the rule the sales bot is
    # explicit about; sharing one query here would be a real product bug.
    assert await ft.is_free_test_available(db, user, PRO_TEST_PLAN)
    assert await ft.test_cooldown_remaining(db, user, PRO_TEST_PLAN) == 0
    await db.close()
    print(f"normal trial blocks itself ({ft.format_cooldown(remaining,'en')} left), not the Pro trial OK")


async def test_cooldowns_have_different_lengths():
    Session = await _setup()
    await _add_trial(Session, PRO_TEST_PLAN, days_ago=10)
    db, user = await _user(Session)
    # 10 days would clear the 7-day normal cooldown but not the 30-day Pro one.
    assert not await ft.is_free_test_available(db, user, PRO_TEST_PLAN)
    remaining = await ft.test_cooldown_remaining(db, user, PRO_TEST_PLAN)
    assert 19 * 86400 < remaining <= 20 * 86400, remaining
    await db.close()
    print(f"pro trial still blocked at 10 days ({ft.format_cooldown(remaining,'en')} left) OK")


async def test_expired_cooldown_allows_again():
    Session = await _setup()
    await _add_trial(Session, TEST_PLAN, days_ago=8)
    await _add_trial(Session, PRO_TEST_PLAN, days_ago=31)
    db, user = await _user(Session)
    assert await ft.is_free_test_available(db, user, TEST_PLAN)
    assert await ft.is_free_test_available(db, user, PRO_TEST_PLAN)
    await db.close()
    print("expired cooldowns allow again OK")


async def test_in_progress_blocks():
    Session = await _setup()
    await _add_trial(Session, TEST_PLAN, days_ago=0, status="pending")
    db, user = await _user(Session)
    assert await ft.free_test_in_progress(db, user, TEST_PLAN)
    assert not await ft.is_free_test_available(db, user, TEST_PLAN)
    try:
        await ft.assert_test_allowed(db, user, TEST_PLAN)
        raise AssertionError("expected test_in_progress")
    except FlowError as e:
        assert e.code == "test_in_progress", e.code
    await db.close()
    print("in-progress trial blocks a second one OK")


async def test_rolled_back_order_leaves_allowance_intact():
    """A pre-provision failure calls _rollback_order, which DELETES the row.
    Nothing is left to find, so the user may try again immediately - which is
    the behaviour the sales bot documents and Pasha confirmed."""
    Session = await _setup()
    await _add_trial(Session, TEST_PLAN, days_ago=0)
    db, user = await _user(Session)
    assert not await ft.is_free_test_available(db, user, TEST_PLAN)
    async with Session() as db2:
        from sqlalchemy import delete
        await db2.execute(delete(Subscription).where(Subscription.plan_name == TEST_PLAN))
        await db2.commit()
    db3, user3 = await _user(Session)
    assert await ft.is_free_test_available(db3, user3, TEST_PLAN)
    await db.close()
    await db3.close()
    print("rolled-back (deleted) order leaves the allowance intact OK")


async def test_cooldown_error_carries_the_remaining_time():
    Session = await _setup()
    await _add_trial(Session, TEST_PLAN, days_ago=1)
    db, user = await _user(Session)
    try:
        await ft.assert_test_allowed(db, user, TEST_PLAN)
        raise AssertionError("expected test_cooldown")
    except FlowError as e:
        assert e.code == "test_cooldown", e.code
        assert getattr(e, "remaining_seconds", 0) > 0
        assert "روز" in ft.format_cooldown(e.remaining_seconds, "fa")
    await db.close()
    print("cooldown error carries remaining time OK")


async def test_unknown_tier_rejected():
    Session = await _setup()
    db, user = await _user(Session)
    try:
        await ft.assert_test_allowed(db, user, "custom:50")
        raise AssertionError("expected invalid_test_tier")
    except FlowError as e:
        assert e.code == "invalid_test_tier", e.code
    await db.close()
    print("unknown tier rejected OK")


async def main():
    await test_fresh_user_is_allowed()
    await test_recent_trial_blocks_same_tier_only()
    await test_cooldowns_have_different_lengths()
    await test_expired_cooldown_allows_again()
    await test_in_progress_blocks()
    await test_rolled_back_order_leaves_allowance_intact()
    await test_cooldown_error_carries_the_remaining_time()
    await test_unknown_tier_rejected()
    print("\nAll free-trial eligibility tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
