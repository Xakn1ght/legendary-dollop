"""Purchasable themes (bubblegum, 2026-07-15) — wallet-credit money path.

- buy with enough credit: charged once, theme lands in
  dashboard_prefs.unlocked_themes, RewardHistory row written
- double-buy: idempotent no-op success, NOT charged again
- insufficient credit: FlowError(insufficient_credit) with price/credit attached
- unknown theme: FlowError(unknown_theme)

Run: PYTHONPATH=src python tests/test_theme_shop.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database.models import Base, RewardHistory, User  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from app.services.flows.theme_shop import THEME_SHOP, buy_theme, theme_shop_items  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

PRICE = THEME_SHOP["bubblegum"]["price"]


async def main():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=901, referral_code="rich", credit=PRICE + 5_000))
        db.add(User(id=2, chat_id=902, referral_code="poor", credit=PRICE - 1))
        await db.commit()

    async with Session() as db:
        rich = await db.get(User, 1)
        poor = await db.get(User, 2)

        # shop listing: not owned yet
        items = theme_shop_items(rich.dashboard_prefs)
        assert items and items[0]["key"] == "bubblegum" and items[0]["owned"] is False
        print("PASS shop listing shows bubblegum unowned")

        res = await buy_theme(db, rich, "bubblegum")
        assert res["already_owned"] is False and res["credit"] == 5_000, res
        await db.refresh(rich)
        prefs = json.loads(rich.dashboard_prefs or "{}")
        assert "bubblegum" in (prefs.get("unlocked_themes") or []), prefs
        assert rich.credit == 5_000
        hist = (await db.execute(select(RewardHistory).filter(
            RewardHistory.user_id == 1, RewardHistory.source == "theme_shop"))).scalars().all()
        assert len(hist) == 1 and hist[0].notes == "bubblegum", [(h.source, h.notes) for h in hist]
        print("PASS buy charges once, unlocks permanently, writes history")

        res2 = await buy_theme(db, rich, "bubblegum")
        assert res2["already_owned"] is True and res2["credit"] == 5_000, res2
        await db.refresh(rich)
        assert rich.credit == 5_000, "double-buy must not double-charge"
        assert theme_shop_items(rich.dashboard_prefs)[0]["owned"] is True
        print("PASS double-buy is an idempotent no-op")

        try:
            await buy_theme(db, poor, "bubblegum")
            raise AssertionError("expected insufficient_credit")
        except FlowError as e:
            assert e.code == "insufficient_credit" and e.price == PRICE and e.credit == PRICE - 1
        await db.refresh(poor)
        assert poor.credit == PRICE - 1, "failed buy must not charge"
        assert "bubblegum" not in json.loads(poor.dashboard_prefs or "{}").get("unlocked_themes", [])
        print("PASS insufficient credit rejected without charge")

        try:
            await buy_theme(db, rich, "neon-zebra")
            raise AssertionError("expected unknown_theme")
        except FlowError as e:
            assert e.code == "unknown_theme"
        print("PASS unknown theme rejected")

    print("test_theme_shop: OK")


asyncio.run(main())
