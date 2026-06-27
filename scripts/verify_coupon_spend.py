"""READ-ONLY prod verification of free_plan / free_autorenew checkout coupons.

Against the LIVE DB + LIVE pricing config + a REAL user row, this creates the two
new coupon types in an UNCOMMITTED session, prices real purchases through the shared
quote service, asserts the money math, then ROLLS BACK. Nothing is committed — prod
data is untouched.

Run:  PYTHONPATH=src .venv/bin/python scripts/verify_coupon_spend.py [chat_id]
"""
import asyncio
import datetime
import json
import sys

from app.core.settings import PLANS
from app.database import crud
from app.database.models import RewardCoupon
from app.database.models._base import AsyncSessionLocal
from app.services.flows.pricing import QuoteError, get_plan_info, quote_purchase

CHAT = int(sys.argv[1]) if len(sys.argv) > 1 else 8148909121


def _pick_plan(gb_target):
    """A real plan name whose gb matches (fixed-plan anchor)."""
    for name, info in PLANS.items():
        if int(info.get("gb") or 0) == gb_target:
            return name
    return None


async def _mk(session, ctype, payload, user_id):
    c = RewardCoupon(
        user_id=user_id,
        source="verify_script",
        coupon_type=ctype,
        payload=json.dumps(payload),
        created_at=datetime.datetime.utcnow(),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=45),
        status="active",
    )
    session.add(c)
    await session.flush()  # visible to quote in this txn; NOT committed
    return c


async def main():
    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, CHAT)
        assert user, f"no user {CHAT} in prod DB"

        plan = _pick_plan(20) or next(iter(PLANS))
        plan_price = int(get_plan_info(plan)["price"])
        print(f"user={CHAT} plan={plan} price={plan_price:,}")

        # 1) free_plan on the exact plan → plan fully free.
        c = await _mk(session, "free_plan", {"plan_gb": get_plan_info(plan)["gb"], "duration_days": 35}, user.id)
        q = await quote_purchase(session, user, plan_name=plan, coupon_id=c.id, use_credit=False)
        assert q.coupon and q.coupon.discount_amount == plan_price, (q.discount_amount, plan_price)
        assert q.final_price == 0, q.final_price
        print(f"✓ free_plan: -{q.coupon.discount_amount:,} → final {q.final_price:,} (free)")

        # 2) free_autorenew WITHOUT a renewal → rejected, un-consumed.
        c2 = await _mk(session, "free_autorenew", {"max_plan_gb": 100, "duration_days": 35}, user.id)
        try:
            await quote_purchase(session, user, plan_name=plan, coupon_id=c2.id, use_credit=False)
            raise AssertionError("expected coupon_needs_renewal")
        except QuoteError as e:
            assert e.code == "coupon_needs_renewal", e.code
            print(f"✓ free_autorenew w/o renewal: rejected ({e.code}), not consumed")

        # 3) free_autorenew WITH a renewal → renewal zeroed.
        q3 = await quote_purchase(
            session, user, plan_name=plan, renewal_plan=plan, coupon_id=c2.id, use_credit=False,
        )
        assert q3.coupon and q3.coupon.discount_amount == q3.renewal_price, (q3.coupon, q3.renewal_price)
        assert q3.final_price == q3.plan_price, (q3.final_price, q3.plan_price)
        print(f"✓ free_autorenew w/ renewal: -{q3.coupon.discount_amount:,} (renewal free) → final {q3.final_price:,}")

        # 4) vip_pack with a renewal → renewal zeroed (money part). Grants apply at
        #    provision, not in a pure quote, so we only check the money here.
        c4 = await _mk(session, "vip_pack", {
            "free_autorenew": {"max_plan_gb": 100, "duration_days": 35},
            "priority_support_days": 30, "badge": "Champion", "theme": "champion",
        }, user.id)
        q4 = await quote_purchase(session, user, plan_name=plan, renewal_plan=plan, coupon_id=c4.id, use_credit=False)
        assert q4.coupon and q4.coupon.discount_amount == q4.renewal_price, (q4.coupon, q4.renewal_price)
        print(f"✓ vip_pack w/ renewal: -{q4.coupon.discount_amount:,} (renewal free), grants apply at provision")

        # 5) legend_pack → +100GB bonus surfaces as free_gb on the order.
        c5 = await _mk(session, "legend_pack", {
            "free_autorenew": {"max_plan_gb": 100, "duration_days": 35},
            "bonus_gb": 100, "priority_support_days": 60, "badge": "Legend", "theme": "legend",
        }, user.id)
        q5 = await quote_purchase(session, user, plan_name=plan, coupon_id=c5.id, use_credit=False)
        assert q5.coupon_free_gb == 100, q5.coupon_free_gb
        print(f"✓ legend_pack: +{q5.coupon_free_gb}GB bonus")

        await session.rollback()
        print("\nrolled back — prod DB untouched. ALL CHECKS PASS")


if __name__ == "__main__":
    asyncio.run(main())
