"""Instant free-trial provisioning end to end (services/flows/free_tests).

The behaviour Pasha approved on the live bot: tap the button, the subscription
arrives. No name prompt, no receipt step. Asserted here at the service layer,
where it actually holds - the order prices to zero, so start_purchase_order
sends it straight down _auto_approve and the FSM never enters the name or
receipt states.

Run: PYTHONPATH=src python tests/test_free_test_order.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.products import PRO_TEST_PLAN, TEST_PLAN  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import Base, Subscription, User  # noqa: E402
from app.services.flows import free_tests as ft  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 4242


class FakePanel:
    """Provisions successfully unless told to fail."""

    def __init__(self, fail=False):
        self.fail = fail
        self.created = []

    async def add_user(self, username, gb, days, on_hold_days=None, group_ids=None):
        self.created.append({"username": username, "gb": gb, "days": days, "group_ids": group_ids})
        if self.fail:
            return None
        return {"username": username, "subscription_url": f"/sub/{username}"}

    async def get_user_info(self, username):
        return None

    async def invalidate_user_info(self, username):
        pass


async def _setup(fail=False):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    panel = FakePanel(fail=fail)
    import app.database.repos.subscription as sub_repo
    import app.services.flows.purchase as purchase_mod
    from app.services import pasarguard as pg_mod
    pg_mod.pasarguard_api = panel
    sub_repo.pasarguard_api = panel
    purchase_mod.__dict__.setdefault("_", None)

    # The double-tap lock lives in REAL Redis and these tests always use
    # user id 1, so a lock left by an earlier test (or an earlier failed run -
    # its TTL is 90s) would leak across cases. Clear it per setup.
    try:
        from app.core.redis_config import cache
        for tier in (TEST_PLAN, PRO_TEST_PLAN):
            await cache.delete(f"freetest:1:{tier}")
    except Exception:
        pass

    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=0))
        await db.commit()
    return Session, panel


async def test_trial_provisions_with_no_name_and_no_receipt():
    Session, panel = await _setup()
    db = Session()
    user = await crud.get_user(db, CHAT)

    res = await ft.start_free_test(db, user, TEST_PLAN, bot=None)
    sub = res.subscription

    assert res.auto_approved is True, "a zero-price trial must auto-approve"
    assert sub.receipt_message_id is None, "a trial must never ask for a receipt"
    assert sub.marzban_username and len(sub.marzban_username) >= 8, sub.marzban_username
    assert sub.price == 0 and sub.paid_amount == 0, (sub.price, sub.paid_amount)
    assert sub.renewal_paid is False, "a trial must not book a renewal"
    assert sub.plan_name == TEST_PLAN
    assert panel.created and panel.created[0]["gb"] == 0.25, panel.created
    await db.close()
    print(f"trial provisioned as {panel.created[0]['username']} with no name/receipt step OK")


async def test_second_trial_is_refused():
    Session, panel = await _setup()
    db = Session()
    user = await crud.get_user(db, CHAT)
    await ft.start_free_test(db, user, TEST_PLAN, bot=None)
    try:
        await ft.start_free_test(db, user, TEST_PLAN, bot=None)
        raise AssertionError("expected the cooldown to refuse a second trial")
    except FlowError as e:
        assert e.code in ("test_cooldown", "test_in_progress"), e.code
        code = e.code
    await db.close()
    print(f"second trial refused ({code}) OK")


async def test_pro_trial_is_independent_and_routed():
    Session, panel = await _setup()
    db = Session()
    user = await crud.get_user(db, CHAT)
    await ft.start_free_test(db, user, TEST_PLAN, bot=None)
    # The normal trial must not have consumed the Pro allowance.
    res = await ft.start_free_test(db, user, PRO_TEST_PLAN, bot=None)
    assert res.auto_approved is True
    pro_call = panel.created[-1]
    from app.core.settings import PASARGUARD_IR_TUN_GROUP_ID
    assert pro_call["group_ids"] == [PASARGUARD_IR_TUN_GROUP_ID], pro_call
    await db.close()
    print(f"pro trial independent, routed to group {pro_call['group_ids']} OK")


async def test_failed_provision_leaves_no_row_and_no_cooldown():
    """The allowance must survive a panel failure - the user got nothing."""
    Session, panel = await _setup(fail=True)
    db = Session()
    user = await crud.get_user(db, CHAT)
    try:
        await ft.start_free_test(db, user, TEST_PLAN, bot=None)
    except FlowError:
        pass
    rows = (await db.execute(select(Subscription).filter(Subscription.plan_name == TEST_PLAN))).scalars().all()
    assert not rows, f"failed provision left {len(rows)} row(s) behind"
    await ft.release_free_test_claim(user, TEST_PLAN)
    assert await ft.is_free_test_available(db, user, TEST_PLAN), "allowance was consumed by a failure"
    await db.close()
    print("failed provision leaves no row and no cooldown OK")


async def test_free_trial_never_pays_a_referral_reward():
    """Free trials plus referral rewards would be a farm: refer yourself a
    trial a week and the GB/days percentages pay out every time."""
    Session, panel = await _setup()
    db = Session()
    db.add(User(id=2, chat_id=CHAT + 1, referral_code="ref"))
    await db.commit()
    user = await crud.get_user(db, CHAT)
    res = await ft.start_free_test(db, user, TEST_PLAN, bot=None)
    res.subscription.referrer_id = 2
    await db.commit()

    from app.database.models import ReferralReward
    rewards = (await db.execute(select(ReferralReward))).scalars().all()
    assert not rewards, f"a free trial minted {len(rewards)} referral reward(s)"
    await db.close()
    print("free trial pays no referral reward OK")


async def main():
    await test_trial_provisions_with_no_name_and_no_receipt()
    await test_second_trial_is_refused()
    await test_pro_trial_is_independent_and_routed()
    await test_failed_provision_leaves_no_row_and_no_cooldown()
    await test_free_trial_never_pays_a_referral_reward()
    print("\nAll instant free-trial tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
