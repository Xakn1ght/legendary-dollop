"""Charge flow-service tests (app.services.flows.charge) on in-memory SQLite.

Covers the divergences fixed by the shared layer:
- credit reserved at order creation is stored on the row and refunded on cancel/deny
- server-side >5GB gate
- approve is idempotent and requires an active subscription
- carry-over math cases (expired / <=5GB / >5GB with 5GB-limit / days-only)
- booking: renewal_paid is set ONLY at approval, with no Marzban call

Run: PYTHONPATH=src python tests/test_charge_service.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, Subscription, User  # noqa: E402
from app.services.flows import charge as charge_mod  # noqa: E402
from app.services.flows.charge import (  # noqa: E402
    GB,
    approve_charge,
    cancel_charge_order,
    deny_charge,
    start_booking_order,
    start_charge_order,
    submit_charge_receipt,
)
from app.services.flows.errors import FlowError  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 555
PACKAGES = {"pkg30": {"gb": 30, "price": 120000, "days": 30}}
PLANS = {"plan50": {"gb": 50, "price": 200000, "days": 35}}


class _FakeResp:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeHttp:
    def __init__(self, log):
        self.log = log

    def put(self, url, headers=None, json=None):
        self.log.append(("put", json))
        return _FakeResp()


class FakeMarzban:
    base_url = "http://fake"

    def __init__(self, info):
        self.info = info
        self.calls = []

    async def get_user_info(self, username):
        return self.info

    async def reset_user_traffic_bytes(self, username, new_data_limit_bytes, new_expire_ts):
        self.calls.append(("reset", new_data_limit_bytes, new_expire_ts))
        return True

    async def _get_session(self):
        return _FakeHttp(self.calls)

    async def _get_headers(self):
        return {}


async def _setup(marzban_info=None):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    charge_mod.CHARGE_PRESET_PACKAGES = PACKAGES
    charge_mod.PLANS = PLANS
    fake = FakeMarzban(marzban_info or {"data_limit": 10 * GB, "used_traffic": 8 * GB, "expire": 0})
    charge_mod.marzban_api = fake

    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=200000))
        db.add(Subscription(id=10, user_id=1, marzban_username="svc", plan_name="plan50", status="active"))
        await db.commit()
    return Session, fake


async def test_start_cancel_deny_credit():
    Session, fake = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)

        res = await start_charge_order(
            db, user, subscription_id=10, package_name="pkg30", use_credit=True, status="draft"
        )
        req = res.charge_request
        assert req.credit_used == 120000 and req.status == "draft", (req.credit_used, req.status)
        await db.refresh(user)
        assert user.credit == 80000

        # Cancel refunds the reserved credit.
        refunded = await cancel_charge_order(db, user, req.id)
        assert refunded == 120000
        await db.refresh(user)
        assert user.credit == 200000

        # Same again, but deny after receipt.
        res = await start_charge_order(
            db, user, subscription_id=10, package_name="pkg30", use_credit=True, status="draft"
        )
        await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=1)
        result = await deny_charge(db, res.charge_request.id)
        assert result.credit_refunded == 120000
        await db.refresh(user)
        assert user.credit == 200000
    print("PASS test_start_cancel_deny_credit")


async def test_gate_ownership_and_guards():
    Session, fake = await _setup(marzban_info={"data_limit": 20 * GB, "used_traffic": 0, "expire": 0})
    async with Session() as db:
        user = await crud.get_user(db, CHAT)

        # >5GB remaining blocks a plain 'normal' charge server-side.
        try:
            await start_charge_order(db, user, subscription_id=10, package_name="pkg30")
            raise AssertionError("expected traffic_above_5gb")
        except FlowError as e:
            assert e.code == "traffic_above_5gb" and getattr(e, "remaining_gb", 0) > 5

        # ...but the explicit 5GB-limit variant goes through.
        res = await start_charge_order(
            db, user, subscription_id=10, package_name="pkg30", charge_type="normal_5gb_limit"
        )
        assert res.charge_request.charge_type == "normal_5gb_limit"

        # Ownership.
        db.add(User(id=2, chat_id=999, referral_code="other"))
        await db.commit()
        other = await crud.get_user(db, 999)
        try:
            await start_charge_order(db, other, subscription_id=10, package_name="pkg30")
            raise AssertionError("expected unauthorized")
        except FlowError as e:
            assert e.code == "unauthorized"

        # Double receipt submit.
        await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=5)
        try:
            await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=6)
            raise AssertionError("expected order_already_processed")
        except FlowError as e:
            assert e.code == "order_already_processed"
    print("PASS test_gate_ownership_and_guards")


async def test_approve_carry_over_and_idempotency():
    # remaining = 2GB (<=5GB): carry it all, reset usage.
    Session, fake = await _setup(marzban_info={"data_limit": 10 * GB, "used_traffic": 8 * GB, "expire": 0})
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        res = await start_charge_order(db, user, subscription_id=10, package_name="pkg30")
        await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=2)

        result = await approve_charge(db, res.charge_request.id, user_bot=None)
        assert result.carry_bytes == 2 * GB and result.lost_bytes == 0
        kind, limit, _ = fake.calls[-1]
        assert kind == "reset" and limit == 2 * GB + 30 * GB, fake.calls

        # Idempotent: second approve refuses.
        try:
            await approve_charge(db, res.charge_request.id, user_bot=None)
            raise AssertionError("expected not_found_or_handled")
        except FlowError as e:
            assert e.code == "not_found_or_handled"

    # remaining = 12GB with 5GB-limit: carry 5, lose 7.
    Session, fake = await _setup(marzban_info={"data_limit": 12 * GB, "used_traffic": 0, "expire": 0})
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        res = await start_charge_order(
            db, user, subscription_id=10, package_name="pkg30", charge_type="normal_5gb_limit"
        )
        await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=3)
        result = await approve_charge(db, res.charge_request.id, user_bot=None)
        assert result.carry_bytes == 5 * GB and result.lost_bytes == 7 * GB

    # expired subscription: fresh limit, no carry.
    past = int(datetime.datetime.utcnow().timestamp()) - 1000
    Session, fake = await _setup(marzban_info={"data_limit": 12 * GB, "used_traffic": 1 * GB, "expire": past})
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        res = await start_charge_order(
            db, user, subscription_id=10, package_name="pkg30", charge_type="normal_5gb_limit"
        )
        await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=4)
        result = await approve_charge(db, res.charge_request.id, user_bot=None)
        assert result.carry_bytes == 0
        kind, limit, _ = fake.calls[-1]
        assert kind == "reset" and limit == 30 * GB

    # inactive subscription refuses approval.
    Session, fake = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        res = await start_charge_order(db, user, subscription_id=10, package_name="pkg30")
        await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=5)
        sub = await db.get(Subscription, 10)
        sub.status = "expired"
        await db.commit()
        try:
            await approve_charge(db, res.charge_request.id, user_bot=None)
            raise AssertionError("expected sub_inactive")
        except FlowError as e:
            assert e.code == "sub_inactive"
    print("PASS test_approve_carry_over_and_idempotency")


async def test_booking_renewal_only_at_approval():
    Session, fake = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)

        res = await start_booking_order(db, user, subscription_id=10, plan_name="plan50")
        req = res.charge_request
        assert req.charge_type == "booking" and req.renewal_template == "plan50" and req.price == 200000

        sub = await db.get(Subscription, 10)
        assert not sub.renewal_paid  # NOT set before payment is verified

        await submit_charge_receipt(db, user, req.id, receipt_message_id=9)
        sub = await db.get(Subscription, 10)
        assert not sub.renewal_paid  # still not set: receipt is unverified

        marzban_calls_before = list(fake.calls)
        await approve_charge(db, req.id, user_bot=None)
        assert fake.calls == marzban_calls_before  # booking approval never touches Marzban

        await db.refresh(sub)
        assert sub.renewal_paid and sub.renewal_template == "plan50" and sub.renewal_price == 200000
    print("PASS test_booking_renewal_only_at_approval")


async def test_referral_reward_granted_without_bot():
    """The referral reward must be created even when no user bot is available
    (panel approvals previously skipped rewards entirely)."""
    from sqlalchemy import select

    from app.database.models import ReferralReward

    Session, fake = await _setup()
    async with Session() as db:
        db.add(User(id=2, chat_id=999, referral_code="ref"))
        sub = await db.get(Subscription, 10)
        sub.referrer_id = 2
        await db.commit()

        user = await crud.get_user(db, CHAT)
        res = await start_charge_order(db, user, subscription_id=10, package_name="pkg30")
        await submit_charge_receipt(db, user, res.charge_request.id, receipt_message_id=7)
        await approve_charge(db, res.charge_request.id, user_bot=None)

        rewards = (await db.execute(select(ReferralReward))).scalars().all()
        assert len(rewards) == 1 and rewards[0].referrer_id == 2, rewards
    print("PASS test_referral_reward_granted_without_bot")


async def main():
    await test_start_cancel_deny_credit()
    await test_gate_ownership_and_guards()
    await test_approve_carry_over_and_idempotency()
    await test_booking_renewal_only_at_approval()
    await test_referral_reward_granted_without_bot()
    print("\nAll charge-service tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
