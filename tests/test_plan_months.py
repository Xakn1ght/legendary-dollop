"""Multi-month plan variants + VIP-exclusive rules (flows/pricing, 2026-07-09).

- "@<n>m" suffix scales price/gb/days linearly, months 1-3
- vip_only plans carry min_months=2: bare name resolves to the 2-month
  package, "@1m" is rejected with the plan_min_months quote error
- custom plans never take a months suffix
- quote_purchase: the VIP percent does NOT apply to vip_only orders
  (offer removed), still applies to regular plans for VIP users

Run: PYTHONPATH=src python tests/test_plan_months.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database.models import Base, User  # noqa: E402
from app.services.flows import pricing as pricing_mod  # noqa: E402
from app.services.flows.pricing import (  # noqa: E402
    QuoteError,
    get_plan_info,
    parse_plan_months,
    plan_display_name,
    quote_purchase,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CATALOG = {
    "۲۰ گیگ | یکماه": {"price": 90_000, "gb": 20, "days": 35, "name_en": "20 GB | 30 D"},
    "۳۵۰ گیگ VIP": {"price": 862_500, "gb": 350, "days": 35, "vip_only": True, "min_months": 2, "name_en": "350 GB VIP"},
}


def test_parse():
    assert parse_plan_months("۲۰ گیگ | یکماه") == ("۲۰ گیگ | یکماه", None)
    assert parse_plan_months("۲۰ گیگ | یکماه@2m") == ("۲۰ گیگ | یکماه", 2)
    assert parse_plan_months("x@12m") == ("x", 12)
    assert parse_plan_months("x@m") == ("x@m", None)


def test_scaling():
    one = get_plan_info("۲۰ گیگ | یکماه", CATALOG)
    assert (one["price"], one["gb"], one["days"], one["months"]) == (90_000, 20, 35, 1)
    two = get_plan_info("۲۰ گیگ | یکماه@2m", CATALOG)
    assert (two["price"], two["gb"], two["days"], two["months"]) == (180_000, 40, 70, 2)
    three = get_plan_info("۲۰ گیگ | یکماه@3m", CATALOG)
    assert (three["price"], three["gb"], three["days"], three["months"]) == (270_000, 60, 105, 3)
    # catalog dict must not be mutated by scaling
    assert CATALOG["۲۰ گیگ | یکماه"]["price"] == 90_000
    assert "months" not in CATALOG["۲۰ گیگ | یکماه"]


def test_bounds():
    assert get_plan_info("۲۰ گیگ | یکماه@4m", CATALOG) is None
    assert get_plan_info("۲۰ گیگ | یکماه@0m", CATALOG) is None
    assert get_plan_info("nope@2m", CATALOG) is None


def test_vip_min_months():
    bare = get_plan_info("۳۵۰ گیگ VIP", CATALOG)
    assert (bare["months"], bare["price"], bare["gb"], bare["days"]) == (2, 1_725_000, 700, 70)
    assert get_plan_info("۳۵۰ گیگ VIP@1m", CATALOG) is None
    three = get_plan_info("۳۵۰ گیگ VIP@3m", CATALOG)
    assert (three["months"], three["price"]) == (3, 2_587_500)


def test_custom_rejects_months():
    assert get_plan_info("custom:50@2m", CATALOG) is None
    assert get_plan_info("custom:50", CATALOG) is not None


def test_display_names():
    assert plan_display_name("۲۰ گیگ | یکماه") == "۲۰ گیگ | یکماه"
    fa2 = plan_display_name("۲۰ گیگ | یکماه@2m")
    assert "ماهه" in fa2 and "یکماه" not in fa2, fa2
    en3 = plan_display_name("۳۵۰ گیگ VIP@3m", "en")
    assert en3.endswith("| 3 Months"), en3


async def _quote_env(is_vip):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=42, referral_code="me", credit=0))
        await db.commit()
        user = await db.get(User, 1)

    # pin the live catalog + VIP knobs for deterministic quoting
    pricing_mod.PLANS.clear()
    pricing_mod.PLANS.update(CATALOG)
    pricing_mod.VIP_PURCHASE_DISCOUNT_ENABLED = True
    pricing_mod.VIP_PURCHASE_DISCOUNT_PERCENT = 20

    async def fake_is_vip(session, uid):
        return is_vip
    pricing_mod.crud.is_user_vip = fake_is_vip

    async def no_discounts(session, uid):
        return []
    pricing_mod.crud.get_active_user_discounts = no_discounts
    return Session, user


def test_quotes():
    async def run():
        Session, user = await _quote_env(is_vip=True)
        async with Session() as db:
            # regular plan: VIP % still applies
            q = await quote_purchase(db, user, plan_name="۲۰ گیگ | یکماه")
            assert (q.plan_price, q.discount_percent, q.final_price) == (90_000, 20, 72_000), vars(q)
            # regular plan, 3 months: scaled then discounted
            q = await quote_purchase(db, user, plan_name="۲۰ گیگ | یکماه@3m")
            assert (q.plan_price, q.final_price) == (270_000, 216_000), vars(q)
            # VIP-exclusive: NO vip percent, bare = 2-month package
            q = await quote_purchase(db, user, plan_name="۳۵۰ گیگ VIP")
            assert (q.plan_price, q.discount_percent, q.final_price) == (1_725_000, 0, 1_725_000), vars(q)
            q = await quote_purchase(db, user, plan_name="۳۵۰ گیگ VIP@3m")
            assert (q.plan_price, q.final_price) == (2_587_500, 2_587_500), vars(q)
            # 1-month VIP attempt → specific error
            try:
                await quote_purchase(db, user, plan_name="۳۵۰ گیگ VIP@1m")
                assert False, "1-month VIP must be rejected"
            except QuoteError as e:
                assert e.code == "plan_min_months", e.code
            # mixed order (regular plan + VIP renewal): vip % exempted wholesale
            q = await quote_purchase(db, user, plan_name="۲۰ گیگ | یکماه", renewal_plan="۳۵۰ گیگ VIP")
            assert q.discount_percent == 0 and q.base_total == 90_000 + 1_725_000, vars(q)

        # non-VIP: vip-exclusive rejected outright
        Session2, user2 = await _quote_env(is_vip=False)
        async with Session2() as db:
            q = await quote_purchase(db, user2, plan_name="۲۰ گیگ | یکماه@2m")
            assert (q.plan_price, q.discount_percent) == (180_000, 0), vars(q)
            try:
                await quote_purchase(db, user2, plan_name="۳۵۰ گیگ VIP@2m")
                assert False, "non-VIP must be rejected"
            except QuoteError as e:
                assert e.code == "vip_only_plan", e.code
    asyncio.run(run())


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} plan-months tests passed.")
