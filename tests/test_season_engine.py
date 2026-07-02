"""Functional test for the Star Season engine on an in-memory SQLite DB.

Run with the project venv:
    PYTHONPATH=src .venv/bin/python tests/test_season_engine.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.database.models import Base, User  # noqa: E402
from app.database.repos.reward import RewardRepository as RR  # noqa: E402


async def _run():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=111, referral_code="x"))
        await db.commit()

        total, unlocked = await RR.add_season_stars(db, 1, 3)
        assert total == 3 and [u["milestone"] for u in unlocked] == [1, 3]

        total, unlocked = await RR.add_season_stars(db, 1, 2)  # → 5
        assert total == 5 and [u["milestone"] for u in unlocked] == [5]

        total, unlocked = await RR.add_season_stars(db, 1, 45)  # → 50
        assert total == 50 and [u["milestone"] for u in unlocked] == [10, 15, 20, 25, 30, 40, 50]

        # dedup: crossing into no new milestone unlocks nothing
        total, unlocked = await RR.add_season_stars(db, 1, 1)  # → 51
        assert unlocked == []

        coupons = await RR.get_active_coupons(db, 1)
        assert sorted(c.milestone_stars for c in coupons) == [1, 3, 5, 10, 15, 20, 25, 30, 40, 50]

        # season reset → fresh season starts at 0
        await RR.end_active_season(db)
        await RR.get_or_create_active_season(db)
        total, _ = await RR.add_season_stars(db, 1, 1)
        assert total == 1


def test_season_engine():
    asyncio.run(_run())


if __name__ == "__main__":
    test_season_engine()
    print("PASS test_season_engine")
