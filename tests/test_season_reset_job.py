"""Functional test for the season reset job (expire coupons + rotate season).

Run: PYTHONPATH=src .venv/bin/python tests/test_season_reset_job.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.jobs.season_reset as sr  # noqa: E402
from app.database.models import Base, RewardCoupon, StarSeason, User  # noqa: E402


async def _run():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    sr.AsyncSessionLocal = async_sessionmaker(eng, expire_on_commit=False)  # monkeypatch

    now = datetime.datetime.utcnow()
    async with sr.AsyncSessionLocal() as db:
        db.add(User(id=1, chat_id=1, referral_code="a"))
        db.add(RewardCoupon(
            user_id=1, coupon_type="discount_percent", payload="{}",
            created_at=now - datetime.timedelta(days=50),
            expires_at=now - datetime.timedelta(days=5), status="active",
        ))
        db.add(StarSeason(
            name="old", starts_at=now - datetime.timedelta(days=100),
            ends_at=now - datetime.timedelta(days=10), is_active=True,
        ))
        await db.commit()

    await sr.season_reset_job(bot=None)

    async with sr.AsyncSessionLocal() as db:
        coupon = (await db.execute(select(RewardCoupon))).scalars().first()
        active = [s for s in (await db.execute(select(StarSeason))).scalars().all() if s.is_active]
        assert coupon.status == "expired"
        assert len(active) == 1 and active[0].ends_at > datetime.datetime.utcnow()


def test_season_reset_job():
    asyncio.run(_run())


if __name__ == "__main__":
    test_season_reset_job()
    print("PASS test_season_reset_job")
