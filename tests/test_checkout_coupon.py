"""Checkout coupon-spend tests (webapp start_purchase) on an in-memory SQLite DB.

Drives handle_start_purchase directly with auth + Marzban patched, exercising the
Phase-1 coupon types (discount_percent, free_gb), the 100GB discount cap, rejection of
unsupported/invalid coupons (no consumption), and coupon restore.

Run with the project venv:
    PYTHONPATH=src .venv/bin/python tests/test_checkout_coupon.py
"""
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.api.routes.dashboard_purchase.start_purchase.handler as hmod  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import Base, RewardCoupon, User  # noqa: E402
from app.database.repos.reward import RewardRepository as RR  # noqa: E402

CHAT = 555
PLANS = {
    "plan20": {"gb": 20, "price": 90000, "days": 35},
    "plan100": {"gb": 100, "price": 400000, "days": 35},
    "big": {"gb": 300, "price": 1000000, "days": 35},
}


class _Req:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


async def _mk_coupon(db, ctype, payload, user_id=1, days_to_expiry=45, status="active"):
    now = datetime.datetime.utcnow()
    c = RewardCoupon(
        user_id=user_id,
        source="star_season",
        coupon_type=ctype,
        payload=json.dumps(payload),
        created_at=now,
        expires_at=now + datetime.timedelta(days=days_to_expiry),
        status=status,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _call(Session, body):
    return await hmod.handle_start_purchase(_Req(body))


async def _run():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    # Patch auth + the handler's session factory + plans + VIP/global discounts.
    hmod._verify_webapp_auth = lambda request: (CHAT, None)
    hmod.AsyncSessionLocal = Session
    hmod.PLANS = PLANS
    hmod.GLOBAL_PURCHASE_DISCOUNTS = []
    hmod.VIP_PURCHASE_DISCOUNT_ENABLED = False
    hmod.VIP_PURCHASE_DISCOUNT_PERCENT = 0

    # Capture Marzban provisioning instead of hitting the network.
    captured = {}

    async def _fake_marzban(sub, plan_info):
        captured["plan_info"] = plan_info
        return {"subscription_url": "https://x/sub"}

    async def _fake_activate(db, sub_id):
        return None

    crud.create_subscription_on_marzban = _fake_marzban
    crud.activate_subscription = _fake_activate

    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=0))
        db.add(User(id=2, chat_id=999, referral_code="other"))
        await db.commit()

    # 1) discount_percent on a receipt-path order (no credit) → 10% off 90k = 9k.
    async with Session() as db:
        c = await _mk_coupon(db, "discount_percent", {"discount_percent": 10})
        cid = c.id
    resp = await _call(Session, {"plan": "plan20", "use_credit": False, "coupon_id": cid})
    data = json.loads(resp.body.decode())
    assert resp.status == 200 and data["ok"] is True, data
    o = data["order"]
    assert o["discount_amount"] == 9000, o
    assert o["final_price"] == 81000, o
    assert o["coupon"]["id"] == cid and o["coupon"]["type"] == "discount_percent"
    async with Session() as db:
        assert (await crud.get_coupon_by_id(db, cid)).status == "used"

    # 2) discount cap: 10% of a 300GB/1,000,000 plan is capped to the 100GB plan price.
    async with Session() as db:
        c = await _mk_coupon(db, "discount_percent", {"discount_percent": 10})
        cid = c.id
    resp = await _call(Session, {"plan": "big", "use_credit": False, "coupon_id": cid})
    data = json.loads(resp.body.decode())
    assert data["order"]["discount_amount"] == 40000, data["order"]  # 10% of 400k cap

    # 3) free_gb on an auto-approved order (credit covers price) → +10GB provisioned.
    async with Session() as db:
        u = await crud.get_user(db, CHAT)
        u.credit = 90000
        await db.commit()
        c = await _mk_coupon(db, "free_gb", {"gb": 10})
        cid = c.id
    captured.clear()
    resp = await _call(Session, {"plan": "plan20", "use_credit": True, "coupon_id": cid})
    data = json.loads(resp.body.decode())
    assert data.get("auto_approved") is True, data
    assert captured["plan_info"]["gb"] == 30, captured  # 20 base + 10 bonus
    assert data["order"]["coupon"]["free_gb"] == 10
    async with Session() as db:
        assert (await crud.get_coupon_by_id(db, cid)).status == "used"
        u = await crud.get_user(db, CHAT)
        u.credit = 0
        await db.commit()

    # 4) expired coupon → rejected, not consumed.
    async with Session() as db:
        c = await _mk_coupon(db, "discount_percent", {"discount_percent": 50}, days_to_expiry=-1)
        cid = c.id
    resp = await _call(Session, {"plan": "plan20", "use_credit": False, "coupon_id": cid})
    data = json.loads(resp.body.decode())
    assert resp.status == 400 and data["error"] == "invalid_coupon", data
    async with Session() as db:
        assert (await crud.get_coupon_by_id(db, cid)).status == "active"

    # 5) unsupported type (free_plan) → rejected, not consumed.
    async with Session() as db:
        c = await _mk_coupon(db, "free_plan", {"plan_gb": 20, "duration_days": 35})
        cid = c.id
    resp = await _call(Session, {"plan": "plan20", "use_credit": False, "coupon_id": cid})
    data = json.loads(resp.body.decode())
    assert resp.status == 400 and data["error"] == "coupon_not_supported_yet", data
    async with Session() as db:
        assert (await crud.get_coupon_by_id(db, cid)).status == "active"

    # 6) coupon owned by another user → rejected.
    async with Session() as db:
        c = await _mk_coupon(db, "discount_percent", {"discount_percent": 10}, user_id=2)
        cid = c.id
    resp = await _call(Session, {"plan": "plan20", "use_credit": False, "coupon_id": cid})
    data = json.loads(resp.body.decode())
    assert resp.status == 400 and data["error"] == "invalid_coupon", data

    # 7) restore: a used coupon returns to active (cancel/failure parity).
    async with Session() as db:
        c = await _mk_coupon(db, "discount_percent", {"discount_percent": 10})
        cid = c.id
        assert await RR.mark_coupon_used(db, cid) is True
        assert (await crud.get_coupon_by_id(db, cid)).status == "used"
        assert await RR.restore_coupon(db, cid) is True
        assert (await crud.get_coupon_by_id(db, cid)).status == "active"


def test_checkout_coupon():
    asyncio.run(_run())


if __name__ == "__main__":
    test_checkout_coupon()
    print("PASS test_checkout_coupon")
