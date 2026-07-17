"""Pricing parity law (2026-07-12): VIP % applies to charges like purchases.

- VIP user: preset (and @Nm-scaled) charge orders get VIP_PURCHASE_DISCOUNT_PERCENT off
- VIP user: fixed vip_only bundles stay at list price (they ARE the perk)
- non-VIP user: list price
- bookings and stored renewal templates carry the same VIP % (vip_only exempt)

Run: PYTHONPATH=src python tests/test_charge_vip_discount.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, ChargeRequest, Subscription, User  # noqa: E402
from app.services.flows import charge as charge_mod  # noqa: E402
from app.services.flows.charge import GB, start_booking_order, start_charge_order  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

VIP_CHAT = 771
REG_CHAT = 772
# Plan parity (2026-07-18): ONE catalog — top-ups resolve against PLANS.
PLANS = {
    "pkg30": {"gb": 30, "price": 120000, "days": 30},
    "plan50": {"gb": 50, "price": 200000, "days": 35},
    "vipplan": {"gb": 350, "price": 862500, "days": 35, "vip_only": True, "min_months": 2},
}


class FakePasarGuard:
    async def get_user_info(self, username):
        return {"data_limit": 10 * GB, "used_traffic": 8 * GB, "expire": 0}


async def _setup():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    charge_mod.PLANS = PLANS
    charge_mod.VIP_PURCHASE_DISCOUNT_ENABLED = True
    charge_mod.VIP_PURCHASE_DISCOUNT_PERCENT = 20
    charge_mod.pasarguard_api = FakePasarGuard()
    async with Session() as db:
        db.add(User(id=1, chat_id=VIP_CHAT, referral_code="v", credit=0, is_vip=True, vip_until=None))
        db.add(User(id=2, chat_id=REG_CHAT, referral_code="r", credit=0))
        db.add(Subscription(id=10, user_id=1, marzban_username="vsvc", plan_name="p", status="active"))
        db.add(Subscription(id=20, user_id=2, marzban_username="rsvc", plan_name="p", status="active"))
        await db.commit()
    return Session


async def main():
    Session = await _setup()

    async with Session() as db:
        vip = await crud.get_user(db, VIP_CHAT)
        reg = await crud.get_user(db, REG_CHAT)

        r = await start_charge_order(db, vip, subscription_id=10, package_name="pkg30")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 96000, cr.price  # 120000 - 20%
        print("PASS vip preset gets 20% off")

        r = await start_charge_order(db, vip, subscription_id=10, package_name="pkg30@2m")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 192000, cr.price  # 240000 - 20%
        assert cr.traffic_bytes == 60 * GB
        print("PASS vip 2-month preset gets 20% off the scaled total")

        # VIP-exclusive plan: bare name resolves to its 2-month minimum
        # (862500 x 2) and carries NO VIP % — the plan IS the perk.
        r = await start_charge_order(db, vip, subscription_id=10, package_name="vipplan")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 1725000, cr.price
        assert cr.traffic_bytes == 700 * GB, cr.traffic_bytes
        print("PASS vip-exclusive plan at list price (2-month minimum)")

        r = await start_charge_order(db, reg, subscription_id=20, package_name="pkg30")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 120000, cr.price
        print("PASS non-vip pays list price")

        r = await start_booking_order(db, vip, subscription_id=10, plan_name="plan50")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 160000 and cr.renewal_price == 160000, (cr.price, cr.renewal_price)
        print("PASS vip booking carries the VIP %")

        r = await start_booking_order(db, reg, subscription_id=20, plan_name="plan50")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 200000, cr.price
        print("PASS non-vip booking at list price")

        r = await start_booking_order(db, vip, subscription_id=10, plan_name="plan50@2m")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.price == 320000, cr.price  # 400000 scaled - 20%
        print("PASS vip 2-month booking discounted on the scaled total")

        r = await start_booking_order(db, vip, subscription_id=10, plan_name="custom:52")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.renewal_template == "custom:52" and cr.price > 0
        print("PASS custom-GB booking accepted")

        from app.services.flows.errors import FlowError
        try:
            await start_booking_order(db, reg, subscription_id=20, plan_name="vipplan@2m")
            raise AssertionError("expected vip_only_plan")
        except FlowError as e:
            assert e.code == "vip_only_plan", e.code
        print("PASS non-vip cannot book a vip-only plan")

        # Multi-month is a VIP perk (2026-07-14): non-VIP bookings and
        # renewal templates with @Nm are rejected on the money path.
        try:
            await start_booking_order(db, reg, subscription_id=20, plan_name="plan50@2m")
            raise AssertionError("expected months_vip_only")
        except FlowError as e:
            assert e.code == "months_vip_only", e.code
        try:
            await start_charge_order(db, reg, subscription_id=20, package_name="pkg30",
                                     renewal_template="plan50@2m")
            raise AssertionError("expected months_vip_only (renewal template)")
        except FlowError as e:
            assert e.code == "months_vip_only", e.code
        print("PASS non-vip multi-month booking/renewal rejected")

        r = await start_charge_order(db, vip, subscription_id=10, package_name="pkg30",
                                     renewal_template="plan50")
        cr = await db.get(ChargeRequest, r.charge_request.id)
        assert cr.renewal_price == 160000, cr.renewal_price
        print("PASS vip renewal template stored discounted")

    print("test_charge_vip_discount: OK")


asyncio.run(main())
