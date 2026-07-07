"""Functional test for the Star Season engine on an in-memory SQLite DB.

Run with the project venv:
    PYTHONPATH=src .venv/bin/python tests/test_season_engine.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database.models import Base, User  # noqa: E402
from app.database.repos.reward import RewardRepository as RR  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402


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
        assert total == 50 and [u["milestone"] for u in unlocked] == [10, 15, 20, 25, 40, 50]

        # dedup: crossing into no new milestone unlocks nothing
        total, unlocked = await RR.add_season_stars(db, 1, 1)  # → 51
        assert unlocked == []

        coupons = await RR.get_active_coupons(db, 1)
        # 50★ mints TWO coupons (vip_days + the extra 100GB) — one claim row.
        assert sorted(c.milestone_stars for c in coupons) == [1, 3, 5, 10, 15, 20, 25, 40, 50, 50]

        # 2026-07 simplification: 40★ = plain free 60GB plan, 50★ = vip_days
        # + 100GB, and milestone cosmetics landed in prefs at unlock time.
        import json as _json
        by_type = {c.coupon_type: c for c in coupons if c.milestone_stars == 40}
        assert by_type["free_plan"] and _json.loads(by_type["free_plan"].payload)["plan_gb"] == 60
        legend = {c.coupon_type: c for c in coupons if c.milestone_stars == 50}
        assert _json.loads(legend["vip_days"].payload)["days"] == 30
        assert _json.loads(legend["free_gb"].payload)["gb"] == 100

        from sqlalchemy import select as _select
        u = (await db.execute(_select(User).filter(User.id == 1))).scalars().first()
        prefs = _json.loads(u.dashboard_prefs or "{}")
        assert prefs.get("badge") == "Legend"  # 50★ overwrote Champion
        assert set(prefs.get("unlocked_themes") or []) == {"champion", "legend"}

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
