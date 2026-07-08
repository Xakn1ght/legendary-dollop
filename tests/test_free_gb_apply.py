"""free_gb coupon apply + traffic-voucher redemption: every failure mode.

Covers the 2026-07-09 unlimited-sub guard end to end on both endpoints that
push GB onto a panel account:

  POST /api/dashboard/coupons/{id}/apply-gb      (free_gb_apply.py)
  POST /api/dashboard/referral-rewards/{id}/redeem (redeem_reward.py, traffic)

Situations: happy path, unlimited sub (rejected BEFORE consuming), foreign
sub, foreign/wrong-type/expired/zero-GB coupon, missing sub id, panel user
missing, panel write failure (coupon restored), double apply, days-option on
unlimited (allowed), traffic voucher on unlimited (voucher kept).

Run: PYTHONPATH=src python tests/test_free_gb_apply.py
"""
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.api.routes.dashboard.referrals import redeem_reward as rr_mod  # noqa: E402
from app.api.routes.dashboard.star_rewards import free_gb_apply as fga_mod  # noqa: E402
from app.database.models import (  # noqa: E402
    Base,
    ReferralReward,
    RewardCoupon,
    Subscription,
    User,
)
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 777
GB = 1024 ** 3


class FakeRequest:
    def __init__(self, match_info=None, body=None):
        self.match_info = match_info or {}
        self._body = body or {}

    async def json(self):
        return self._body


class FakeMarzban:
    """data_limit map per username; None entry = panel user missing."""

    def __init__(self):
        self.accounts = {
            "limited1": {"data_limit": 20 * GB, "expire": 1_900_000_000},
            "limited2": {"data_limit": 5 * GB, "expire": 1_900_000_000},
            "unlim": {"data_limit": 0, "expire": 1_900_000_000},
            "unlim_null": {"data_limit": None, "expire": 1_900_000_000},
        }
        self.updates = []
        self.fail_update = False

    async def get_user_info(self, username):
        return self.accounts.get(username)

    async def update_user(self, username, patch):
        if self.fail_update:
            return False
        self.updates.append((username, patch))
        acct = self.accounts.get(username)
        if acct:
            acct.update(patch)
        return True


def _auth_ok(_request):
    return CHAT, None


def _auth_other(_request):
    return CHAT + 1, None


async def _setup():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
        await c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS subscription_links ("
                "user_id INTEGER NOT NULL, subscription_id INTEGER NOT NULL, added_at TIMESTAMP, "
                "PRIMARY KEY (user_id, subscription_id))"
            )
        )
    Session = async_sessionmaker(eng, expire_on_commit=False)

    fake = FakeMarzban()
    future = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    past = datetime.datetime.utcnow() - datetime.timedelta(days=1)

    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me"))
        db.add(User(id=2, chat_id=CHAT + 1, referral_code="other"))
        db.add(Subscription(id=10, user_id=1, marzban_username="limited1", status="active"))
        db.add(Subscription(id=11, user_id=1, marzban_username="unlim", status="active"))
        db.add(Subscription(id=12, user_id=1, marzban_username="unlim_null", status="active"))
        db.add(Subscription(id=13, user_id=2, marzban_username="limited2", status="active"))
        db.add(Subscription(id=14, user_id=1, marzban_username=None, status="active"))
        db.add(Subscription(id=15, user_id=1, marzban_username="ghost", status="active"))
        # coupons (user 1 unless noted)
        db.add(RewardCoupon(id=100, user_id=1, coupon_type="free_gb", payload='{"gb": 1}', expires_at=future))
        db.add(RewardCoupon(id=101, user_id=1, coupon_type="free_gb", payload='{"gb": 2}', expires_at=future))
        db.add(RewardCoupon(id=102, user_id=2, coupon_type="free_gb", payload='{"gb": 1}', expires_at=future))
        db.add(RewardCoupon(id=103, user_id=1, coupon_type="discount_percent", payload='{"percent": 5}', expires_at=future))
        db.add(RewardCoupon(id=104, user_id=1, coupon_type="free_gb", payload='{"gb": 1}', expires_at=past))
        db.add(RewardCoupon(id=105, user_id=1, coupon_type="free_gb", payload='{"gb": 0}', expires_at=future))
        db.add(RewardCoupon(id=106, user_id=1, coupon_type="free_gb", payload='{"gb": 3}', expires_at=future))
        db.add(RewardCoupon(id=107, user_id=1, coupon_type="free_gb", payload='{"gb": 3}', expires_at=future))
        # star vouchers: traffic-only, days-only, traffic-or-days
        db.add(ReferralReward(id=200, subscription_id=10, referrer_id=1, traffic_bytes=2 * GB, extra_days=0, credit_amount=0, stars=0))
        db.add(ReferralReward(id=201, subscription_id=10, referrer_id=1, traffic_bytes=0, extra_days=7, credit_amount=0, stars=0))
        db.add(ReferralReward(id=202, subscription_id=10, referrer_id=1, traffic_bytes=2 * GB, extra_days=0, credit_amount=0, stars=0))
        await db.commit()

    for mod in (fga_mod, rr_mod):
        mod.AsyncSessionLocal = Session
        mod.marzban_api = fake
        mod._verify_webapp_auth = _auth_ok
    return Session, fake


def _body(resp):
    return json.loads(resp.body.decode())


async def _coupon_status(Session, cid):
    async with Session() as db:
        c = await db.get(RewardCoupon, cid)
        return c.status


async def _reward_spent(Session, rid):
    async with Session() as db:
        r = await db.get(ReferralReward, rid)
        return r.spent


async def apply_gb(coupon_id, sub_id):
    return await fga_mod.handle_dashboard_coupon_apply_gb(
        FakeRequest({"coupon_id": str(coupon_id)}, {"subscription_id": sub_id})
    )


async def redeem(reward_id, body):
    return await rr_mod.handle_dashboard_redeem_referral_reward(
        FakeRequest({"reward_id": str(reward_id)}, body)
    )


async def main():
    Session, fake = await _setup()
    checks = 0

    def ok(cond, label):
        nonlocal checks
        assert cond, label
        checks += 1
        print(f"  PASS {label}")

    # ── apply-gb ────────────────────────────────────────────────────
    # 1. happy path: +1GB onto limited1 (20GB)
    r = await apply_gb(100, 10)
    b = _body(r)
    ok(r.status == 200 and b["ok"] and b["gb_added"] == 1, "happy path applies 1GB")
    ok(fake.accounts["limited1"]["data_limit"] == 21 * GB, "panel limit 20->21GB")
    ok(await _coupon_status(Session, 100) == "used", "coupon consumed")

    # 2. double apply of the same coupon → coupon_not_found is NOT the code;
    #    it fails on type/owner check pass but status gate
    r = await apply_gb(100, 10)
    ok(r.status == 400 and _body(r)["error"] == "coupon_not_active", "double apply blocked")
    ok(fake.accounts["limited1"]["data_limit"] == 21 * GB, "no second grant")

    # 3. unlimited sub (data_limit 0) → rejected, coupon untouched
    r = await apply_gb(101, 11)
    ok(r.status == 400 and _body(r)["error"] == "sub_unlimited", "unlimited(0) rejected")
    ok(await _coupon_status(Session, 101) == "active", "coupon NOT consumed on unlimited")

    # 4. unlimited sub (data_limit null) → same
    r = await apply_gb(101, 12)
    ok(r.status == 400 and _body(r)["error"] == "sub_unlimited", "unlimited(null) rejected")

    # 5. someone else's subscription → not found
    r = await apply_gb(101, 13)
    ok(r.status == 404 and _body(r)["error"] == "subscription_not_found", "foreign sub rejected")

    # 6. someone else's coupon → not found
    r = await apply_gb(102, 10)
    ok(r.status == 404 and _body(r)["error"] == "coupon_not_found", "foreign coupon rejected")

    # 7. wrong coupon type → not found
    r = await apply_gb(103, 10)
    ok(r.status == 404 and _body(r)["error"] == "coupon_not_found", "non-free_gb type rejected")

    # 8. expired coupon
    r = await apply_gb(104, 10)
    ok(r.status == 400 and _body(r)["error"] == "coupon_expired", "expired coupon rejected")

    # 9. zero-GB payload
    r = await apply_gb(105, 10)
    ok(r.status == 400 and _body(r)["error"] == "invalid_coupon", "gb=0 payload rejected")

    # 10. missing subscription_id
    r = await fga_mod.handle_dashboard_coupon_apply_gb(FakeRequest({"coupon_id": "101"}, {}))
    ok(r.status == 400 and _body(r)["error"] == "subscription_required", "missing sub id rejected")

    # 11. sub row without a panel username
    r = await apply_gb(101, 14)
    ok(r.status == 404 and _body(r)["error"] == "subscription_not_found", "sub without panel name rejected")

    # 12. panel user gone → 502, coupon untouched
    r = await apply_gb(106, 15)
    ok(r.status == 502 and _body(r)["error"] == "panel_user_not_found", "panel user missing -> 502")
    ok(await _coupon_status(Session, 106) == "active", "coupon kept when panel user missing")

    # 13. panel write failure → coupon restored
    fake.fail_update = True
    r = await apply_gb(106, 10)
    ok(r.status == 502 and _body(r)["error"] == "panel_update_failed", "panel write failure -> 502")
    ok(await _coupon_status(Session, 106) == "active", "coupon restored after panel failure")
    fake.fail_update = False

    # 14. bad coupon id in path
    r = await fga_mod.handle_dashboard_coupon_apply_gb(FakeRequest({"coupon_id": "abc"}, {"subscription_id": 10}))
    ok(r.status == 400 and _body(r)["error"] == "invalid_coupon_id", "non-numeric coupon id rejected")

    # 15. unauthorized
    fga_mod._verify_webapp_auth = lambda req: (None, None)
    r = await apply_gb(107, 10)
    ok(r.status == 403 and _body(r)["error"] == "unauthorized", "unauthenticated rejected")
    fga_mod._verify_webapp_auth = _auth_ok

    # 16. auth as the OTHER user: their coupon + my sub → sub not theirs
    fga_mod._verify_webapp_auth = _auth_other
    r = await apply_gb(102, 10)
    ok(r.status == 404 and _body(r)["error"] == "subscription_not_found", "cross-user sub rejected")
    fga_mod._verify_webapp_auth = _auth_ok

    # ── referral-reward redeem (traffic guard) ──────────────────────
    # 17. traffic voucher onto unlimited sub → rejected, voucher kept
    r = await redeem(200, {"reward_type": "traffic", "subscription_id": 11})
    ok(r.status == 400 and _body(r)["error"] == "sub_unlimited", "traffic voucher on unlimited rejected")
    ok(not await _reward_spent(Session, 200), "voucher NOT spent on unlimited")

    # 18. same voucher onto limited sub → applied + spent
    before = fake.accounts["limited1"]["data_limit"]
    r = await redeem(200, {"reward_type": "traffic", "subscription_id": 10})
    ok(r.status == 200 and _body(r)["ok"], "traffic voucher on limited sub ok")
    ok(fake.accounts["limited1"]["data_limit"] == before + 2 * GB, "voucher GB landed")
    ok(await _reward_spent(Session, 200), "voucher spent")

    # 19. days voucher onto UNLIMITED sub → allowed (expiry still real)
    before_exp = fake.accounts["unlim"]["expire"]
    r = await redeem(201, {"reward_type": "days", "subscription_id": 11})
    ok(r.status == 200 and _body(r)["ok"], "days voucher on unlimited allowed")
    ok(fake.accounts["unlim"]["expire"] == before_exp + 7 * 86400, "expiry +7d")

    # 20. traffic voucher, no sub id → falls back to first ACTIVE sub; make
    #     every fallback candidate unlimited-only by pointing at user 2's world
    #     is complex — instead verify fallback lands on an eligible (limited)
    #     sub and still applies (first active sub for user 1 is limited1).
    before = fake.accounts["limited1"]["data_limit"]
    r = await redeem(202, {"reward_type": "traffic"})
    b = _body(r)
    ok(r.status == 200 and b["ok"] and b["applied"]["subscription_id"] == 10, "no-sub-id fallback applies to first active")
    ok(fake.accounts["limited1"]["data_limit"] == before + 2 * GB, "fallback GB landed")

    print(f"\nALL {checks} CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
