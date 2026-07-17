"""Charge multi-month suffix ("<preset>@Nm") tests — shop months selector.

- @2m/@3m scale price/gb/days xN on the created order (VIP buyer — multi-month
  is a VIP perk since 2026-07-14)
- bare names unchanged; @1m equals bare
- @4m (beyond MAX_PLAN_MONTHS) rejected
- VIP fixed bundles and custom top-ups reject the suffix
- unknown base with suffix rejected
- non-VIP with any months suffix >1 → months_vip_only

Run: PYTHONPATH=src python tests/test_charge_months.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database.models import Base, ChargeRequest, Subscription, User  # noqa: E402
from app.services.flows import charge as charge_mod  # noqa: E402
from app.services.flows.charge import GB, start_charge_order  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 556
# Plan parity (2026-07-18): ONE catalog — top-ups resolve against PLANS.
PLANS = {
    "pkg30": {"gb": 30, "price": 120000, "days": 30},
    "vipplan": {"gb": 350, "price": 862500, "days": 35, "vip_only": True, "min_months": 2},
}


class FakePasarGuard:
    async def get_user_info(self, username):
        # 2GB left of 10GB: under the 5GB gate, charges allowed
        return {"data_limit": 10 * GB, "used_traffic": 8 * GB, "expire": 0}


async def _setup():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    charge_mod.PLANS = PLANS
    # This test is about months scaling only — pin the VIP % off so the
    # VIP buyer's prices stay at list (discount math has its own test file).
    charge_mod.VIP_PURCHASE_DISCOUNT_ENABLED = False
    charge_mod.pasarguard_api = FakePasarGuard()
    async with Session() as db:
        # multi-month buyer must be VIP (2026-07-14 months_vip_only gate)
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=0, is_vip=True, vip_until=None))
        db.add(User(id=2, chat_id=CHAT + 1, referral_code="reg", credit=0))
        db.add(Subscription(id=10, user_id=1, marzban_username="svc", plan_name="p", status="active"))
        db.add(Subscription(id=20, user_id=2, marzban_username="rsvc", plan_name="p", status="active"))
        await db.commit()
    return Session


async def _user(db):
    from app.database import crud
    return await crud.get_user(db, CHAT)


async def _start(db, name):
    return await start_charge_order(
        db, await _user(db), subscription_id=10, package_name=name)


async def main():
    Session = await _setup()

    async with Session() as db:
        res = await _start(db, "pkg30@2m")
        cr = await db.get(ChargeRequest, res.charge_request.id)
        assert cr.price == 240000, cr.price
        assert cr.traffic_bytes == 60 * GB, cr.traffic_bytes
        assert cr.extra_days == 60, cr.extra_days
        print("PASS @2m scales price/gb/days")

        res3 = await _start(db, "pkg30@3m")
        cr3 = await db.get(ChargeRequest, res3.charge_request.id)
        assert (cr3.price, cr3.traffic_bytes, cr3.extra_days) == (360000, 90 * GB, 90)
        print("PASS @3m scales price/gb/days")

        res1 = await _start(db, "pkg30@1m")
        cr1 = await db.get(ChargeRequest, res1.charge_request.id)
        assert (cr1.price, cr1.traffic_bytes, cr1.extra_days) == (120000, 30 * GB, 30)
        base = await _start(db, "pkg30")
        crb = await db.get(ChargeRequest, base.charge_request.id)
        assert (crb.price, crb.traffic_bytes, crb.extra_days) == (120000, 30 * GB, 30)
        print("PASS @1m == bare name")

        for bad in ("pkg30@4m", "pkg30@0m", "custom:50@2m", "nope@2m"):
            try:
                await _start(db, bad)
                raise AssertionError(f"{bad} was accepted")
            except FlowError as e:
                assert e.code == "invalid_package", (bad, e.code)
        print("PASS suffix rejected for cap/custom/unknown")

        # VIP plans are min_months=2 monthly products now (parity with
        # purchase): bare name resolves to the 2-month package; @2m explicit
        # matches; @1m is below the plan's minimum.
        rv = await _start(db, "vipplan")
        crv = await db.get(ChargeRequest, rv.charge_request.id)
        assert (crv.price, crv.traffic_bytes, crv.extra_days) == (1725000, 700 * GB, 70), (
            crv.price, crv.traffic_bytes, crv.extra_days)
        rv2 = await _start(db, "vipplan@2m")
        crv2 = await db.get(ChargeRequest, rv2.charge_request.id)
        assert (crv2.price, crv2.traffic_bytes, crv2.extra_days) == (1725000, 700 * GB, 70)
        try:
            await _start(db, "vipplan@1m")
            raise AssertionError("vipplan@1m was accepted")
        except FlowError as e:
            assert e.code == "plan_min_months", e.code
        print("PASS vip plan resolves to min 2 months; @1m rejected")

        # Non-VIP: months>1 is rejected on the money path (VIP perk).
        from app.database import crud
        reg = await crud.get_user(db, CHAT + 1)
        for name, sub_id in (("pkg30@2m", 20), ("pkg30@3m", 20)):
            try:
                await start_charge_order(db, reg, subscription_id=sub_id, package_name=name)
                raise AssertionError(f"non-VIP {name} was accepted")
            except FlowError as e:
                assert e.code == "months_vip_only", (name, e.code)
        r = await start_charge_order(db, reg, subscription_id=20, package_name="pkg30")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 120000, cr.price
        print("PASS non-VIP: @Nm rejected (months_vip_only), 1-month OK")

    print("test_charge_months: OK")


asyncio.run(main())
