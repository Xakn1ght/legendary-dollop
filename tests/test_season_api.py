"""Test the webapp Star Season dashboard endpoint serialization.

Drives handle_dashboard_season directly against an in-memory SQLite DB, with auth
and the session factory monkeypatched. Verifies the shape the webapp consumes:
season_stars, next_milestone, ladder (reached flags), and the coupon wallet.

Run with the project venv:
    PYTHONPATH=src .venv/bin/python tests/test_season_api.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.api.routes.dashboard.star_rewards.season as season_mod  # noqa: E402
from app.database.models import Base, User  # noqa: E402
from app.database.repos.reward import RewardRepository as RR  # noqa: E402


async def _run():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        db.add(User(id=1, chat_id=777, referral_code="x"))
        await db.commit()
        # 7 season stars → milestones 3 and 5 unlocked (next is 10).
        await RR.add_season_stars(db, 1, 7)

    # Patch auth (return our chat_id) and the handler's session factory.
    season_mod._verify_webapp_auth = lambda request: (777, None)
    season_mod.AsyncSessionLocal = Session

    resp = await season_mod.handle_dashboard_season(object())
    assert resp.status == 200, resp.status
    data = json.loads(resp.body.decode())

    assert data["ok"] is True
    assert data["season_stars"] == 7
    assert data["next_milestone"]["stars"] == 10

    ladder = {m["stars"]: m for m in data["ladder"]}
    # full ladder present
    assert sorted(ladder) == [1, 3, 5, 10, 15, 20, 25, 30, 40, 50]
    # reached flags reflect 7 stars
    assert ladder[1]["reached"] is True
    assert ladder[3]["reached"] is True
    assert ladder[5]["reached"] is True
    assert ladder[10]["reached"] is False
    # ladder carries renderable coupon metadata
    assert ladder[3]["coupon_type"] == "discount_percent"
    assert ladder[3]["payload"]["discount_percent"] == 10

    # coupon wallet has exactly the unlocked coupons (1★, 3★, 5★ at 7 stars)
    coup = sorted(data["coupons"], key=lambda c: c["milestone_stars"])
    assert [c["milestone_stars"] for c in coup] == [1, 3, 5]
    assert coup[0]["coupon_type"] == "discount_percent"
    assert coup[0]["payload"]["discount_percent"] == 5
    assert coup[0]["id"] > 0
    assert coup[0]["days_left"] is not None and coup[0]["days_left"] >= 0
    assert coup[0]["expires_at"]

    # season window metadata
    assert data["season"]["days_left"] is not None
    assert data["season"]["ends_at"]


def test_season_api():
    asyncio.run(_run())


if __name__ == "__main__":
    test_season_api()
    print("PASS test_season_api")
