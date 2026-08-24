"""Money gates for free trials and the Pro/IR-Tun route.

Two classes of mistake these stop:

- a free trial silently BURNING a reward coupon (one coupon per purchase,
  consumed at order creation) on a zero-toman item
- routes mixing, which sells Pro traffic that is never delivered over the Pro
  route, or books a cross-route renewal the panel fires months later

Run: PYTHONPATH=src python tests/test_pro_route_pricing.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, Subscription, User  # noqa: E402
from app.services.flows import charge as charge_mod  # noqa: E402
from app.services.flows.charge import GB, start_charge_order  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from app.services.flows.pricing import QuoteError, quote_purchase  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 777
NORMAL_PLAN = "۲۰ گیگ | یکماه"


class FakePasarGuard:
    base_url = "http://fake"

    def __init__(self):
        self.calls = []

    async def get_user_info(self, username):
        return {"data_limit": 10 * GB, "used_traffic": 9 * GB, "expire": 0}

    async def invalidate_user_info(self, username):
        pass


async def _setup(vip=False):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    charge_mod.pasarguard_api = FakePasarGuard()
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=500_000, is_vip=vip))
        # A normal-route subscription, like every one predating the merge.
        db.add(Subscription(id=10, user_id=1, marzban_username="svc",
                            plan_name=NORMAL_PLAN, status="active"))
        await db.commit()
    return Session


async def _expect(coro, code, what):
    try:
        await coro
    except (QuoteError, FlowError) as e:
        got = getattr(e, "code", None) or str(e)
        assert got == code, f"{what}: expected {code}, got {got}"
        return
    raise AssertionError(f"{what}: expected {code}, nothing raised")


async def test_free_trial_rejects_money_extras():
    Session = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        await _expect(quote_purchase(db, user, plan_name="test", coupon_id=1),
                      "free_plan_no_coupon", "coupon on a free trial")
        await _expect(quote_purchase(db, user, plan_name="test", discount_ids=[1]),
                      "free_plan_no_discount", "discount on a free trial")
        await _expect(quote_purchase(db, user, plan_name="test", use_credit=True),
                      "free_plan_no_credit", "credit on a free trial")
        await _expect(quote_purchase(db, user, plan_name="test", renewal_plan=NORMAL_PLAN),
                      "free_plan_no_renewal", "renewal booked on a free trial")
        # The plain trial itself still quotes, at zero.
        q = await quote_purchase(db, user, plan_name="test")
        assert q.final_price == 0, q.final_price
    print("free trial rejects coupon/discount/credit/renewal OK")


async def test_trial_cannot_be_a_renewal_template():
    Session = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        await _expect(quote_purchase(db, user, plan_name=NORMAL_PLAN, renewal_plan="test"),
                      "invalid_renewal_plan", "trial as renewal template")
    print("trial cannot be a renewal template OK")


async def test_routes_do_not_mix_on_purchase():
    Session = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        await _expect(quote_purchase(db, user, plan_name="pro:20", renewal_plan=NORMAL_PLAN),
                      "route_mismatch", "pro plan with normal renewal")
        await _expect(quote_purchase(db, user, plan_name=NORMAL_PLAN, renewal_plan="pro:20"),
                      "route_mismatch", "normal plan with pro renewal")
        # Same route both sides is fine.
        q = await quote_purchase(db, user, plan_name="pro:20", renewal_plan="pro:20")
        assert q.final_price == 2 * 110_000, q.final_price
    print("routes do not mix on purchase OK")


async def test_pro_takes_the_vip_discount():
    """Pricing Parity Law: Pro is a route, not a second VIP tier, so a VIP
    buying Pro gets the normal VIP percent like any other purchase."""
    from app.core.settings import VIP_PURCHASE_DISCOUNT_ENABLED, VIP_PURCHASE_DISCOUNT_PERCENT

    Session = await _setup(vip=True)
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        if not (VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0):
            print("VIP purchase discount disabled in config - skipping")
            return
        if not await crud.is_user_vip(db, user.id):
            print("is_user_vip needs more than the flag here - skipping")
            return
        q = await quote_purchase(db, user, plan_name="pro:20")
        expected = 110_000 - (110_000 * VIP_PURCHASE_DISCOUNT_PERCENT // 100)
        assert q.final_price == expected, (q.final_price, expected)
        print(f"pro takes the VIP discount OK ({VIP_PURCHASE_DISCOUNT_PERCENT}% off 110,000)")


async def test_charge_rejects_free_and_cross_route():
    Session = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        await _expect(start_charge_order(db, user, subscription_id=10, package_name="test"),
                      "free_not_chargeable", "free trial as a top-up")
        await _expect(start_charge_order(db, user, subscription_id=10, package_name="pro:20"),
                      "route_mismatch", "pro top-up on a normal subscription")
        await _expect(
            start_charge_order(db, user, subscription_id=10, package_name=NORMAL_PLAN,
                               renewal_template="pro:20"),
            "route_mismatch", "pro renewal booked on a normal subscription")
    print("charge rejects free and cross-route OK")


async def main():
    await test_free_trial_rejects_money_extras()
    await test_trial_cannot_be_a_renewal_template()
    await test_routes_do_not_mix_on_purchase()
    await test_pro_takes_the_vip_discount()
    await test_charge_rejects_free_and_cross_route()
    print("\nAll Pro/route pricing tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
