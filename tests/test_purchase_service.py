"""Purchase flow-service tests (app.services.flows.pricing + purchase) on in-memory SQLite.

Covers the divergences fixed by the shared layer:
- quote math: VIP toggle, global discounts, 90% cap, coupon cap, credit capping
- service-name regex enforced server-side
- orders start as draft; receipt flips to pending; double-submit rejected
- cancel refunds credit to the INTERNAL user id and restores coupon + discounts
- auto-approve rollback when the panel provisioning fails
- deny restores the consumed coupon (previously lost on both surfaces)

Run: PYTHONPATH=src python tests/test_purchase_service.py
"""
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, RewardCoupon, User, UserDiscount  # noqa: E402
from app.services.flows import pricing as pricing_mod  # noqa: E402
from app.services.flows import purchase as purchase_mod  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from app.services.flows.pricing import quote_purchase  # noqa: E402
from app.services.flows.purchase import (  # noqa: E402
    cancel_purchase_order,
    deny_purchase_order,
    start_purchase_order,
    submit_purchase_receipt,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 777
PLANS = {
    "plan20": {"gb": 20, "price": 90000, "days": 35},
    "plan100": {"gb": 100, "price": 400000, "days": 35},
}


def _patch_settings():
    pricing_mod.PLANS = PLANS
    pricing_mod.GLOBAL_PURCHASE_DISCOUNTS = []
    pricing_mod.VIP_PURCHASE_DISCOUNT_ENABLED = True
    pricing_mod.VIP_PURCHASE_DISCOUNT_PERCENT = 20

    async def _name_taken(db, username):
        return bool(await crud.get_subscription_by_username(db, username))

    purchase_mod.is_service_name_taken = _name_taken


async def _setup():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    _patch_settings()
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=0))
        await db.commit()
    return Session


async def _user(db):
    return await crud.get_user(db, CHAT)


def _mk_coupon(db, ctype, payload):
    now = datetime.datetime.utcnow()
    c = RewardCoupon(
        user_id=1,
        source="star_season",
        coupon_type=ctype,
        payload=json.dumps(payload),
        created_at=now,
        expires_at=now + datetime.timedelta(days=30),
        status="active",
    )
    db.add(c)
    return c


async def test_quote_math():
    Session = await _setup()
    async with Session() as db:
        user = await _user(db)

        # No VIP, no discounts: plain price.
        pricing_mod.VIP_PURCHASE_DISCOUNT_ENABLED = False
        q = await quote_purchase(db, user, plan_name="plan20")
        assert q.base_total == 90000 and q.final_price == 90000 and q.discount_percent == 0, q

        # VIP toggle ON → 20% off everywhere the quote is used.
        pricing_mod.VIP_PURCHASE_DISCOUNT_ENABLED = True
        user.is_vip = True
        await db.commit()
        q = await quote_purchase(db, user, plan_name="plan20")
        assert q.discount_percent == 20 and q.final_price == 72000, q

        # Global discounts stack; the combined percent is capped at 90.
        pricing_mod.GLOBAL_PURCHASE_DISCOUNTS = [{"percent": 50}, {"percent": 40}]
        q = await quote_purchase(db, user, plan_name="plan20")
        assert q.discount_percent == 90, q
        assert q.final_price == 9000, q

        pricing_mod.GLOBAL_PURCHASE_DISCOUNTS = []
        user.is_vip = False

        # Credit is capped to the amount due.
        user.credit = 1_000_000
        await db.commit()
        q = await quote_purchase(db, user, plan_name="plan20", use_credit=True)
        assert q.credit_used == 90000 and q.final_price == 0, q
        user.credit = 0
        await db.commit()
    print("PASS test_quote_math")


async def test_invalid_inputs():
    Session = await _setup()
    async with Session() as db:
        user = await _user(db)
        for kwargs, code in [
            (dict(plan_name="nope"), "invalid_plan"),
            (dict(plan_name="plan20", renewal_plan="nope"), "invalid_renewal_plan"),
            (dict(plan_name="plan20", coupon_id=12345), "invalid_coupon"),
        ]:
            try:
                await quote_purchase(db, user, **kwargs)
                raise AssertionError(f"expected {code}")
            except FlowError as e:
                assert e.code == code, (e.code, code)

        # Bad service names rejected server-side.
        q = await quote_purchase(db, user, plan_name="plan20")
        for bad in ("ab", "x" * 21, "has space", "نام"):
            try:
                await start_purchase_order(db, user, quote=q, service_name=bad)
                raise AssertionError("expected invalid_service_name")
            except FlowError as e:
                assert e.code == "invalid_service_name", e.code
    print("PASS test_invalid_inputs")


async def test_draft_receipt_and_double_submit():
    Session = await _setup()
    async with Session() as db:
        user = await _user(db)
        q = await quote_purchase(db, user, plan_name="plan20")
        res = await start_purchase_order(db, user, quote=q, service_name="svcone")
        sub = res.subscription
        assert sub.status == "draft" and not res.auto_approved

        sub = await submit_purchase_receipt(db, user, sub.id, receipt_message_id=42)
        assert sub.status == "pending" and sub.receipt_message_id == 42

        try:
            await submit_purchase_receipt(db, user, sub.id, receipt_message_id=43)
            raise AssertionError("expected order_already_processed")
        except FlowError as e:
            assert e.code == "order_already_processed", e.code

        # Ownership: another user can't touch the order.
        db.add(User(id=2, chat_id=888, referral_code="other"))
        await db.commit()
        other = await crud.get_user(db, 888)
        for fn in (submit_purchase_receipt, cancel_purchase_order):
            try:
                await fn(db, other, sub.id)
                raise AssertionError("expected unauthorized")
            except FlowError as e:
                assert e.code in ("unauthorized", "order_already_processed"), e.code
    print("PASS test_draft_receipt_and_double_submit")


async def test_cancel_restores_everything():
    Session = await _setup()
    async with Session() as db:
        user = await _user(db)
        user.credit = 50000
        d = UserDiscount(
            user_id=1,
            percent=10,
            source="test",
            used=False,
            expiration=datetime.datetime.utcnow() + datetime.timedelta(days=30),
        )
        db.add(d)
        c = _mk_coupon(db, "discount_percent", {"discount_percent": 10})
        await db.commit()

        q = await quote_purchase(
            db, user, plan_name="plan20", discount_ids=[d.id], coupon_id=c.id, use_credit=True
        )
        res = await start_purchase_order(db, user, quote=q, service_name="svccancel")

        await db.refresh(user)
        await db.refresh(d)
        await db.refresh(c)
        assert user.credit == 0 and d.used and c.status == "used"

        await cancel_purchase_order(db, user, res.subscription.id)

        await db.refresh(user)
        await db.refresh(d)
        await db.refresh(c)
        # Credit comes back to the internal user id (the old bot path refunded to the
        # Telegram chat id, which silently no-opped).
        assert user.credit == 50000, user.credit
        assert d.used is False and c.status == "active"
    print("PASS test_cancel_restores_everything")


async def test_auto_approve_rollback():
    Session = await _setup()
    async with Session() as db:
        user = await _user(db)
        user.credit = 90000
        c = _mk_coupon(db, "free_gb", {"gb": 10})
        await db.commit()

        async def _fail_marzban(sub, plan_info):
            raise RuntimeError("panel down")

        crud.create_subscription_on_pasarguard = _fail_marzban

        q = await quote_purchase(db, user, plan_name="plan20", coupon_id=c.id, use_credit=True)
        assert q.final_price == 0
        try:
            await start_purchase_order(db, user, quote=q, service_name="svcfail", bot=None)
            raise AssertionError("expected auto_approve_failed")
        except FlowError as e:
            assert e.code == "auto_approve_failed", e.code

        await db.refresh(user)
        await db.refresh(c)
        assert user.credit == 90000 and c.status == "active"
        assert await crud.get_subscription_by_username(db, "svcfail") is None
    print("PASS test_auto_approve_rollback")


async def test_auto_approve_success_free_gb():
    Session = await _setup()
    async with Session() as db:
        user = await _user(db)
        user.credit = 90000
        c = _mk_coupon(db, "free_gb", {"gb": 10})
        await db.commit()

        captured = {}

        async def _ok_marzban(sub, plan_info):
            captured["plan_info"] = plan_info
            return {"subscription_url": "https://x/sub/tok"}

        crud.create_subscription_on_pasarguard = _ok_marzban

        q = await quote_purchase(db, user, plan_name="plan20", coupon_id=c.id, use_credit=True)
        res = await start_purchase_order(db, user, quote=q, service_name="svcfree", bot=None)
        assert res.auto_approved
        # The coupon's bonus GB is applied at provisioning via applied_coupon_id.
        assert captured["plan_info"]["gb"] == 30, captured
        await db.refresh(res.subscription)
        assert res.subscription.status == "active"
    print("PASS test_auto_approve_success_free_gb")


async def test_deny_restores_coupon():
    Session = await _setup()
    async with Session() as db:
        user = await _user(db)
        user.credit = 10000
        c = _mk_coupon(db, "discount_percent", {"discount_percent": 5})
        await db.commit()

        q = await quote_purchase(db, user, plan_name="plan20", coupon_id=c.id, use_credit=True)
        res = await start_purchase_order(db, user, quote=q, service_name="svcdeny")
        await submit_purchase_receipt(db, user, res.subscription.id, receipt_message_id=7)

        result = await deny_purchase_order(db, res.subscription.id)
        assert result.credit_refunded == 10000 and result.coupon_restored

        await db.refresh(user)
        await db.refresh(c)
        assert user.credit == 10000 and c.status == "active"

        # Idempotent: the row is gone, a second deny reports not_found.
        try:
            await deny_purchase_order(db, res.subscription.id)
            raise AssertionError("expected not_found")
        except FlowError as e:
            assert e.code == "not_found", e.code
    print("PASS test_deny_restores_coupon")


async def main():
    await test_quote_math()
    await test_invalid_inputs()
    await test_draft_receipt_and_double_submit()
    await test_cancel_restores_everything()
    await test_auto_approve_rollback()
    await test_auto_approve_success_free_gb()
    await test_deny_restores_coupon()
    print("\nAll purchase-service tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
