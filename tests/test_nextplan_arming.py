"""Native next-plan lifecycle (services/nextplan.py) on in-memory SQLite.

Booked subs are armed as a PasarGuard ``next_plan`` and the PANEL fires them;
the renewal watchdog only reconciles. Covered here:
- booked_next_plan_fields: carry-none object, plan days + 5 grace, months scale
- reconcile: fired (armed_at set, panel empty) -> applied + history + DM
- reconcile: never-armed booking gets armed (the migration path)
- reconcile: panel armed but unstamped -> adopted
- reconcile: armed and waiting -> no-op

Run: PYTHONPATH=src python tests/test_nextplan_arming.py
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database.models import Base, Subscription, User  # noqa: E402
from app.services import nextplan as np  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

GB = 1024 ** 3
PLANS = {"plan50": {"gb": 50, "price": 200000, "days": 30}}


class FakePanel:
    def __init__(self, info):
        self.info = info
        self.updates = []
        self.invalidated = []

    async def get_user_info(self, username):
        return self.info

    async def update_user(self, username, update_data):
        self.updates.append((username, update_data))
        return True

    async def invalidate_user_info(self, username):
        self.invalidated.append(username)


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


async def _setup(*, armed_at=None):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=777, referral_code="x"))
        db.add(Subscription(
            id=10, user_id=1, marzban_username="svc", plan_name="plan50",
            status="active", renewal_paid=True, renewal_template="plan50",
            renewal_applied=False, renewal_armed_at=armed_at,
        ))
        await db.commit()
    return Session


def test_fields():
    f = np.booked_next_plan_fields("plan50", PLANS)
    assert f == {
        "user_template_id": None,
        "data_limit": 50 * GB,
        "expire": 30 * 86400,  # catalog days verbatim (catalog bakes grace in)
        "add_remaining_traffic": False,
    }, f
    # Multi-month variants scale gb and days through get_plan_info.
    f2 = np.booked_next_plan_fields("plan50@2m", PLANS)
    assert f2["data_limit"] == 100 * GB and f2["expire"] == 60 * 86400, f2
    assert np.booked_next_plan_fields("ghost-plan", PLANS) is None
    print("PASS fields carry-none + catalog days + months")


async def test_fired():
    Session = await _setup(armed_at=datetime.utcnow())
    fake = FakePanel({"data_limit": 50 * GB, "used_traffic": 0, "next_plan": None})
    np.pasarguard_api = fake
    bot = FakeBot()
    async with Session() as db:
        sub = await db.get(Subscription, 10)
        out = await np.reconcile_booked_sub(db, sub, bot)
        assert out == "fired", out
        await db.refresh(sub)
        assert sub.renewal_applied is True and sub.renewal_armed_at is None
        assert bot.sent and bot.sent[0][0] == 777
        from app.database.models import RenewalHistory
        from sqlalchemy import select
        rows = (await db.execute(select(RenewalHistory))).scalars().all()
        assert rows and rows[0].result == "success" and "native next_plan" in rows[0].details
    print("PASS reconcile fired -> applied + history + DM")


async def test_arm_missing():
    Session = await _setup(armed_at=None)
    fake = FakePanel({"data_limit": 10 * GB, "used_traffic": 1 * GB, "next_plan": None})
    np.pasarguard_api = fake
    real_plans = np.PLANS
    np.PLANS = PLANS
    try:
        async with Session() as db:
            sub = await db.get(Subscription, 10)
            out = await np.reconcile_booked_sub(db, sub, FakeBot())
            assert out == "armed", out
            assert fake.updates and fake.updates[0][1]["next_plan"]["data_limit"] == 50 * GB
            await db.refresh(sub)
            assert sub.renewal_armed_at is not None and sub.renewal_applied is False
    finally:
        np.PLANS = real_plans
    print("PASS reconcile arms never-armed booking (migration path)")


async def test_adopt():
    Session = await _setup(armed_at=None)
    armed_obj = {"user_template_id": None, "data_limit": 50 * GB, "expire": 35 * 86400, "add_remaining_traffic": False}
    fake = FakePanel({"data_limit": 10 * GB, "next_plan": armed_obj})
    np.pasarguard_api = fake
    async with Session() as db:
        sub = await db.get(Subscription, 10)
        out = await np.reconcile_booked_sub(db, sub, FakeBot())
        assert out == "adopted", out
        await db.refresh(sub)
        assert sub.renewal_armed_at is not None and sub.renewal_applied is False
        assert not fake.updates  # nothing re-written
    print("PASS reconcile adopts panel-armed booking")


async def test_waiting():
    Session = await _setup(armed_at=datetime.utcnow())
    armed_obj = {"user_template_id": None, "data_limit": 50 * GB, "expire": 35 * 86400, "add_remaining_traffic": False}
    fake = FakePanel({"data_limit": 10 * GB, "next_plan": armed_obj})
    np.pasarguard_api = fake
    bot = FakeBot()
    async with Session() as db:
        sub = await db.get(Subscription, 10)
        out = await np.reconcile_booked_sub(db, sub, bot)
        assert out == "waiting", out
        await db.refresh(sub)
        assert sub.renewal_applied is False and not fake.updates and not bot.sent
    print("PASS reconcile waiting is a no-op")


async def main():
    test_fields()
    await test_fired()
    await test_arm_missing()
    await test_adopt()
    await test_waiting()
    print("\ntest_nextplan_arming: OK")


if __name__ == "__main__":
    asyncio.run(main())
