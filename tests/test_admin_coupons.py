"""Admin coupon ops tests (api/routes/admin/ops/coupons.py) + one cross-end
round trip through the user checkout, on in-memory SQLite.

Covers BOTH ENDS of the coupon lifecycle:
- admin create: per-user targeting (chat id + @username), unknown user,
  payload/type validation, active_subs vs all broadcast targeting
- admin list: status filter, q search, campaign filter, counts, total
- admin revoke: single (active only — used stays used), campaign bulk
- CROSS-END: admin-issued marketing coupon redeemed at user checkout
  (discount applied, status flips to used, admin list reflects it);
  a revoked coupon is rejected at checkout and stays revoked

Run: PYTHONPATH=src .venv/bin/python tests/test_admin_coupons.py
"""
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import app.api.routes.admin.ops.coupons as cmod  # noqa: E402
import app.api.routes.dashboard_purchase.start_purchase.handler as hmod  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import Base, RewardCoupon, Subscription, User  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 555
PLANS = {"plan20": {"gb": 20, "price": 90000, "days": 35}}


class _Req:
    """Stub for both the admin handlers (query/json/app) and checkout."""

    def __init__(self, body=None, query=None):
        self._body = body or {}
        self.query = query or {}
        self.app = {}
        self.headers = {}
        self.remote = "127.0.0.1"

    async def json(self):
        return self._body


def _j(resp):
    return json.loads(resp.body.decode())


async def _noop_audit(*a, **k):
    return None


async def _run():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    # ── patch the admin module ────────────────────────────────────────
    cmod.AsyncSessionLocal = Session
    cmod.record_audit = _noop_audit
    cmod.resolve_user_bot = lambda *_: None  # no DMs in tests

    # ── seed users: buyer (active sub), lurker (expired sub), ghost ───
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, username="buyer", full_name="Buyer", referral_code="a", credit=0))
        db.add(User(id=2, chat_id=666, username="lurker", full_name="Lurker", referral_code="b"))
        db.add(User(id=3, chat_id=777, username="ghost", full_name="Ghost", referral_code="c"))
        db.add(Subscription(user_id=1, marzban_username="buyer1", status="active", price=90000))
        db.add(Subscription(user_id=2, marzban_username="lurker1", status="expired", price=90000))
        await db.commit()

    # 1) create → one user by chat id
    resp = await cmod.handle_admin_coupon_create(_Req({
        "coupon_type": "discount_percent", "payload": {"discount_percent": 25},
        "expires_days": 10, "campaign": "spring-fling", "notify": False,
        "target": {"mode": "user", "chat_id": str(CHAT)},
    }))
    data = _j(resp)
    assert resp.status == 200 and data["ok"] and data["issued"] == 1, data
    print("PASS create per-user (chat id)")

    # 2) create → by @username; campaign tagged into payload
    resp = await cmod.handle_admin_coupon_create(_Req({
        "coupon_type": "free_gb", "payload": {"gb": 7},
        "expires_days": 5, "campaign": "gb-drop", "notify": False,
        "target": {"mode": "user", "chat_id": "@lurker"},
    }))
    assert _j(resp)["issued"] == 1
    async with Session() as db:
        rows = (await db.execute(
            __import__("sqlalchemy").future.select(RewardCoupon).where(RewardCoupon.user_id == 2)
        )).scalars().all()
        assert len(rows) == 1 and json.loads(rows[0].payload)["campaign"] == "gb-drop"
        assert rows[0].source == "marketing"
    print("PASS create per-user (@username), campaign in payload, source=marketing")

    # 3) unknown user → 404; bad type / bad payloads → 400, nothing issued
    resp = await cmod.handle_admin_coupon_create(_Req({
        "coupon_type": "discount_percent", "payload": {"discount_percent": 10},
        "target": {"mode": "user", "chat_id": "@nobody"},
    }))
    assert resp.status == 404 and _j(resp)["error"] == "user_not_found"
    for bad in (
        {"coupon_type": "vip_days", "payload": {"days": 30}, "target": {"mode": "all"}},
        {"coupon_type": "discount_percent", "payload": {"discount_percent": 0}, "target": {"mode": "all"}},
        {"coupon_type": "discount_percent", "payload": {"discount_percent": 101}, "target": {"mode": "all"}},
        {"coupon_type": "free_gb", "payload": {"gb": 0}, "target": {"mode": "all"}},
        {"coupon_type": "free_plan", "payload": {"plan_gb": 0}, "target": {"mode": "all"}},
    ):
        resp = await cmod.handle_admin_coupon_create(_Req(bad))
        assert resp.status == 400, (bad, _j(resp))
    async with Session() as db:
        total = len((await db.execute(__import__("sqlalchemy").future.select(RewardCoupon))).scalars().all())
        assert total == 2, f"rejections must not issue anything (got {total})"
    print("PASS validation rejections (unknown user, bad type, out-of-range payloads)")

    # 4) broadcast targeting: active_subs hits ONLY the active-sub holder
    resp = await cmod.handle_admin_coupon_create(_Req({
        "coupon_type": "free_plan", "payload": {"plan_gb": 30, "duration_days": 30},
        "expires_days": 3, "campaign": "winback", "notify": False,
        "target": {"mode": "active_subs"},
    }))
    assert _j(resp)["issued"] == 1, _j(resp)
    resp = await cmod.handle_admin_coupon_create(_Req({
        "coupon_type": "discount_percent", "payload": {"discount_percent": 5},
        "expires_days": 3, "campaign": "blast", "notify": False,
        "target": {"mode": "all"},
    }))
    assert _j(resp)["issued"] == 3, _j(resp)
    print("PASS broadcast targeting (active_subs=1, all=3)")

    # 5) list: counts, status filter, q search, campaign filter
    resp = await cmod.handle_admin_coupons_list(_Req(query={}))
    data = _j(resp)
    assert data["ok"] and data["total"] == 6 and data["counts"].get("active") == 6, data
    resp = await cmod.handle_admin_coupons_list(_Req(query={"q": "lurker"}))
    assert _j(resp)["total"] == 2  # gb-drop + blast
    resp = await cmod.handle_admin_coupons_list(_Req(query={"campaign": "winback"}))
    data = _j(resp)
    assert data["total"] == 1 and data["coupons"][0]["coupon_type"] == "free_plan", data
    resp = await cmod.handle_admin_coupons_list(_Req(query={"limit": "2", "page": "2"}))
    data = _j(resp)
    assert data["total"] == 6 and len(data["coupons"]) == 2 and data["page"] == 2
    print("PASS list filters (counts, q, campaign, pagination)")

    # 6) revoke: single active → revoked; campaign bulk only touches actives
    async with Session() as db:
        sel = __import__("sqlalchemy").future.select(RewardCoupon)
        first = (await db.execute(sel.where(RewardCoupon.user_id == 1))).scalars().first()
        first_id = first.id
    resp = await cmod.handle_admin_coupon_revoke(_Req({"coupon_id": first_id}))
    assert _j(resp)["revoked"] == 1
    resp = await cmod.handle_admin_coupon_revoke(_Req({"coupon_id": first_id}))
    assert _j(resp)["revoked"] == 0, "already-revoked must not double-revoke"
    resp = await cmod.handle_admin_coupon_revoke(_Req({"campaign": "blast"}))
    assert _j(resp)["revoked"] == 3
    resp = await cmod.handle_admin_coupons_list(_Req(query={"status": "revoked"}))
    assert _j(resp)["total"] == 4
    print("PASS revoke (single, idempotent, campaign bulk)")

    # ── CROSS-END: admin-issued coupon → user checkout ───────────────
    from app.services.flows import pricing as pricing_mod
    from app.services.flows import purchase as purchase_mod

    hmod._verify_webapp_auth = lambda request: (CHAT, None)
    hmod.AsyncSessionLocal = Session
    hmod.PLANS = PLANS
    pricing_mod.PLANS = PLANS
    pricing_mod.GLOBAL_PURCHASE_DISCOUNTS = []
    pricing_mod.VIP_PURCHASE_DISCOUNT_ENABLED = False
    pricing_mod.VIP_PURCHASE_DISCOUNT_PERCENT = 0

    async def _name_taken(db, username):
        return bool(await crud.get_subscription_by_username(db, username))
    purchase_mod.is_service_name_taken = _name_taken

    import app.utils.admin_bot_helper as abh
    abh.get_user_bot = lambda: None
    abh.get_admin_bot = lambda: None

    async def _fake_marzban(sub, plan_info):
        return {"subscription_url": "https://x/sub"}

    async def _fake_activate(db, sub_id):
        return None
    crud.create_subscription_on_marzban = _fake_marzban
    crud.activate_subscription = _fake_activate

    # 7) fresh 30% marketing coupon for the buyer → checkout applies it
    resp = await cmod.handle_admin_coupon_create(_Req({
        "coupon_type": "discount_percent", "payload": {"discount_percent": 30},
        "expires_days": 10, "campaign": "cross-end", "notify": False,
        "target": {"mode": "user", "chat_id": str(CHAT)},
    }))
    assert _j(resp)["ok"]
    async with Session() as db:
        sel = __import__("sqlalchemy").future.select(RewardCoupon)
        fresh = (await db.execute(
            sel.where(RewardCoupon.user_id == 1, RewardCoupon.status == "active",
                      RewardCoupon.payload.ilike('%cross-end%'))
        )).scalars().all()
        assert len(fresh) == 1, [c.payload for c in fresh]
        cid = fresh[0].id

    resp = await hmod.handle_start_purchase(_Req({"plan": "plan20", "use_credit": False, "coupon_id": cid}))
    data = _j(resp)
    assert resp.status == 200 and data["ok"], data
    assert data["order"]["discount_amount"] == 27000 and data["order"]["final_price"] == 63000, data["order"]
    async with Session() as db:
        assert (await crud.get_coupon_by_id(db, cid)).status == "used"
    resp = await cmod.handle_admin_coupons_list(_Req(query={"campaign": "cross-end"}))
    assert _j(resp)["coupons"][0]["status"] == "used", "admin list must reflect redemption"
    print("PASS cross-end: admin marketing coupon redeemed at checkout, list shows used")

    # 8) a REVOKED coupon is rejected at checkout and stays revoked
    async with Session() as db:
        revoked = (await db.execute(
            __import__("sqlalchemy").future.select(RewardCoupon).where(
                RewardCoupon.user_id == 1, RewardCoupon.status == "revoked",
            )
        )).scalars().first()
        rid = revoked.id
    resp = await hmod.handle_start_purchase(_Req({"plan": "plan20", "use_credit": False, "coupon_id": rid, "service_name": "second"}))
    data = _j(resp)
    assert resp.status == 400 and data["error"] == "invalid_coupon", data
    async with Session() as db:
        assert (await crud.get_coupon_by_id(db, rid)).status == "revoked"
    print("PASS cross-end: revoked coupon rejected at checkout, stays revoked")

    # 9) someone ELSE's coupon must not be spendable by this user
    async with Session() as db:
        other = RewardCoupon(
            user_id=2, source="marketing", coupon_type="discount_percent",
            payload=json.dumps({"discount_percent": 50}),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=5),
            status="active",
        )
        db.add(other)
        await db.commit()
        await db.refresh(other)
        oid = other.id
    resp = await hmod.handle_start_purchase(_Req({"plan": "plan20", "use_credit": False, "coupon_id": oid, "service_name": "third"}))
    data = _j(resp)
    assert resp.status == 400 and data["error"] == "invalid_coupon", data
    async with Session() as db:
        assert (await crud.get_coupon_by_id(db, oid)).status == "active", "foreign coupon must not be consumed"
    print("PASS cross-end: another user's coupon rejected and not consumed")

    print("ALL ADMIN COUPON TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(_run())
