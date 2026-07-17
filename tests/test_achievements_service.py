"""Mission-achievements service tests (app.services.achievements) on in-memory SQLite.

Covers:
- snapshot progress math for purchases/charges/stars/referrals/VIP/arcade/age
- the paying-customer rule (no claims without >=1 paid purchase)
- claim mints exactly one free_gb coupon; double-claim rejected
- inOrbit needs BOTH 90 days and a purchase

Run: PYTHONPATH=src python tests/test_achievements_service.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import (  # noqa: E402
    Base,
    ChargeRequest,
    DailyGamePlay,
    Referral,
    RewardCoupon,
    Subscription,
    User,
)
from app.services import achievements as ach  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.future import select  # noqa: E402

CHAT = 777


async def _mk(days_old=10, vip=False):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(
            id=1, chat_id=CHAT, referral_code="me",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=days_old),
            is_vip=vip,
        ))
        await db.commit()
    return Session


async def test_fresh_user_nothing_claimable():
    Session = await _mk()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        snap = await ach.snapshot(db, user)
        assert snap["paying_customer"] is False
        assert all(not a["claimable"] for a in snap["achievements"])
        launch = next(a for a in snap["achievements"] if a["key"] == "launch")
        assert launch["progress"] == 0 and launch["done"] is False
        try:
            await ach.claim(db, user, "launch")
            raise AssertionError("expected requires_purchase")
        except FlowError as e:
            assert e.code == "requires_purchase"
    print("PASS test_fresh_user_nothing_claimable")


async def test_purchase_unlocks_launch_and_claim_mints_once():
    Session = await _mk()
    async with Session() as db:
        db.add(Subscription(user_id=1, marzban_username="s1", status="active", price=90000))
        await db.commit()
        user = await crud.get_user(db, CHAT)

        snap = await ach.snapshot(db, user)
        assert snap["paying_customer"] is True
        launch = next(a for a in snap["achievements"] if a["key"] == "launch")
        assert launch["done"] and launch["claimable"]

        coupon = await ach.claim(db, user, "launch")
        assert coupon.coupon_type == "free_gb" and coupon.source == "achievement"

        coupons = (await db.execute(select(RewardCoupon))).scalars().all()
        assert len(coupons) == 1 and coupons[0].status == "active"

        try:
            await ach.claim(db, user, "launch")
            raise AssertionError("expected already_claimed")
        except FlowError as e:
            assert e.code == "already_claimed"
        coupons = (await db.execute(select(RewardCoupon))).scalars().all()
        assert len(coupons) == 1, "double claim must not mint a second coupon"

        snap2 = await ach.snapshot(db, user)
        launch2 = next(a for a in snap2["achievements"] if a["key"] == "launch")
        assert launch2["claimed"] and not launch2["claimable"]
    print("PASS test_purchase_unlocks_launch_and_claim_mints_once")


async def test_not_completed_rejected():
    Session = await _mk()
    async with Session() as db:
        db.add(Subscription(user_id=1, marzban_username="s1", status="active", price=90000))
        await db.commit()
        user = await crud.get_user(db, CHAT)
        try:
            await ach.claim(db, user, "refuel")  # no approved charge yet
            raise AssertionError("expected not_completed")
        except FlowError as e:
            assert e.code == "not_completed"
        try:
            await ach.claim(db, user, "nonsense")
            raise AssertionError("expected unknown_achievement")
        except FlowError as e:
            assert e.code == "unknown_achievement"
    print("PASS test_not_completed_rejected")


async def test_counters_move_progress():
    Session = await _mk(days_old=100, vip=True)
    async with Session() as db:
        db.add(Subscription(id=1, user_id=1, marzban_username="s1", status="active", price=90000))
        db.add(ChargeRequest(
            user_id=1, subscription_id=1, traffic_bytes=10 * 1024 ** 3, price=50000, status="approved",
        ))
        db.add(DailyGamePlay(
            user_id=1, play_date=datetime.date.today(), best_score=1000, rewarded=True,
        ))
        for i in range(6):
            uid = 100 + i
            db.add(User(id=uid, chat_id=9000 + i, referral_code=f"r{i}"))
            db.add(Referral(referrer_id=1, referee_id=uid))
            db.add(Subscription(user_id=uid, marzban_username=f"ref{i}", status="active", price=90000))
        await db.commit()
        user = await crud.get_user(db, CHAT)

        snap = await ach.snapshot(db, user)
        by = {a["key"]: a for a in snap["achievements"]}
        assert by["refuel"]["done"]
        assert by["arcadePilot"]["done"]
        assert by["crew"]["done"]
        assert by["envoy"]["done"] and by["envoy"]["progress"] == 5
        assert by["fleetCommander"]["progress"] == 6 and not by["fleetCommander"]["done"]
        assert by["inOrbit"]["done"], "90+ days AND a purchase → done"

        for key in ("refuel", "arcadePilot", "crew", "envoy", "inOrbit"):
            await ach.claim(db, user, key)
        coupons = (await db.execute(select(RewardCoupon))).scalars().all()
        assert len(coupons) == 5
    print("PASS test_counters_move_progress")


async def test_in_orbit_requires_purchase_leg():
    Session = await _mk(days_old=120)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        snap = await ach.snapshot(db, user)
        orbit = next(a for a in snap["achievements"] if a["key"] == "inOrbit")
        assert not orbit["done"], "old account without a purchase must NOT complete inOrbit"
    print("PASS test_in_orbit_requires_purchase_leg")


async def test_deep_space_lifetime_traffic():
    """deepSpace reads the panel's lifetime counter; max(lifetime, used)
    guards panels that only roll lifetime up at reset time."""
    import app.services.pasarguard as pg
    GB = 1024 ** 3
    old_api = pg.pasarguard_api
    pg.pasarguard_api = _StubPanel({
        "s1": {"lifetime_used_traffic": 300 * GB, "used_traffic": 10 * GB},
        "s2": {"lifetime_used_traffic": 0, "used_traffic": 1500 * GB},
    })
    try:
        Session = await _mk()
        async with Session() as db:
            db.add(Subscription(user_id=1, marzban_username="s1", status="active", price=90000))
            db.add(Subscription(user_id=1, marzban_username="s2", status="active", price=90000))
            await db.commit()
            user = await crud.get_user(db, CHAT)
            snap = await ach.snapshot(db, user)
            ds = next(a for a in snap["achievements"] if a["key"] == "deepSpace")
            assert ds["target"] == 1024
            assert ds["progress"] == 1024 and ds["done"], ds  # s2's 1500GB used, capped
            assert ds["claimable"]
            coupon = await ach.claim(db, user, "deepSpace")
            assert coupon.coupon_type == "free_gb"
    finally:
        pg.pasarguard_api = old_api
    print("PASS test_deep_space_lifetime_traffic")


class _StubPanel:
    def __init__(self, info_by_user):
        self.info = info_by_user

    async def get_user_info(self, username):
        return self.info.get(username)


class _NullCache:
    async def get(self, key):
        return None

    async def set(self, key, value, ttl=None):
        return None


async def main():
    # Hermetic run: no live Redis (prod key collisions) and no live panel —
    # snapshot() now reads panel lifetime traffic for deepSpace.
    import app.core.redis_config as rc
    import app.services.pasarguard as pg
    old_cache, old_api = rc.cache, pg.pasarguard_api
    rc.cache = _NullCache()
    pg.pasarguard_api = _StubPanel({})
    try:
        await test_fresh_user_nothing_claimable()
        await test_purchase_unlocks_launch_and_claim_mints_once()
        await test_not_completed_rejected()
        await test_counters_move_progress()
        await test_in_orbit_requires_purchase_leg()
        await test_deep_space_lifetime_traffic()
    finally:
        rc.cache, pg.pasarguard_api = old_cache, old_api
    print("ALL ACHIEVEMENTS TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
