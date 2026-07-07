"""vip_days coupon (50★ Season Legend): wallet redemption rules.

- reaching 50★ mints a vip_days coupon
- redemption extends the VIP window by payload days (stacks if already VIP)
- the coupon is consumed exactly once (double-redeem blocked)
- checkout pricing REJECTS vip_days (wallet-only redemption)

Run: PYTHONPATH=src .venv/bin/python tests/test_vip_days_coupon.py
"""
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.database.models import Base, User  # noqa: E402
from app.database.repos.reward import RewardRepository as RR  # noqa: E402
from app.services.subscription_processing import extend_vip_window  # noqa: E402


async def _run():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=111, referral_code="x"))
        await db.commit()

        # 50★ mints the vip_days coupon
        _total, unlocked = await RR.add_season_stars(db, 1, 50)
        vip_unlock = [u for u in unlocked if u["coupon_type"] == "vip_days"]
        assert len(vip_unlock) == 1 and vip_unlock[0]["milestone"] == 50

        coupons = await RR.get_active_coupons(db, 1)
        coupon = next(c for c in coupons if c.coupon_type == "vip_days")
        days = json.loads(coupon.payload)["days"]
        assert days == 30

        # redeem: consume-first, then extend the VIP window
        user = (await db.get(User, 1))
        assert not user.is_vip
        assert await RR.mark_coupon_used(db, coupon.id)
        await extend_vip_window(db, user, days)
        assert user.is_vip
        first_until = user.vip_until
        assert first_until and first_until > datetime.datetime.utcnow() + datetime.timedelta(days=29)

        # double-redeem blocked (coupon no longer active)
        assert not await RR.mark_coupon_used(db, coupon.id)

        # stacking: another grant extends from the current expiry, not from now
        await extend_vip_window(db, user, 30)
        assert user.vip_until > first_until + datetime.timedelta(days=29)

        # checkout must reject vip_days
        from app.services.flows.pricing import SUPPORTED_COUPON_TYPES
        assert "vip_days" not in SUPPORTED_COUPON_TYPES
        assert "vip_pack" not in SUPPORTED_COUPON_TYPES
        assert "legend_pack" not in SUPPORTED_COUPON_TYPES


def test_vip_days_coupon():
    asyncio.run(_run())


if __name__ == "__main__":
    test_vip_days_coupon()
    print("PASS test_vip_days_coupon")
