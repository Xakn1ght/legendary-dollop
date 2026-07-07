"""Arcade coin wallet + shop tests on in-memory SQLite (2026-07-07).

Covers:
- wallet auto-creation + coin awarding (and that awards accumulate)
- buy: skins / powers / extra life; auto-equip on skin purchase;
  insufficient coins; double-buy rejected; unknown items rejected
- equip: owned-only, unknown skins rejected, default always equippable
- retry: requires a rewarded run today, spends coins, zeroes best_score,
  reopens the daily gate; can't retry twice without playing again
- loadout derivation from the wallet
- economy seal: the wallet cannot touch user credit/stars

Run: PYTHONPATH=src python tests/test_arcade_shop.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.api.routes.game.shop import build_loadout  # noqa: E402
from app.core.settings import ARCADE_SHOP  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import Base, User  # noqa: E402
from app.utils.tehran_time import tehran_today  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}")


async def make_session():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def seed_user(db, chat_id, name):
    u = User(chat_id=chat_id, full_name=name)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def test_wallet_and_awards():
    print("-- wallet + coin awards --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 5001, "wallet-guy")

        wallet = await crud.get_or_create_arcade_wallet(db, u.id)
        check("wallet auto-created with 0 coins", wallet.coins == 0)
        pub = crud.arcade_wallet_public(wallet)
        check("default skin owned + equipped from the start",
              pub["equipped_skin"] == "default" and "default" in pub["owned_skins"])

        bal = await crud.award_arcade_coins(db, u.id, 3)
        await db.commit()
        check("award credits coins", bal == 3)
        bal = await crud.award_arcade_coins(db, u.id, 2)
        await db.commit()
        check("awards accumulate", bal == 5)

        wallet = await crud.get_or_create_arcade_wallet(db, u.id)
        check("lifetime counter tracks", wallet.coins_earned_total == 5)

        bal = await crud.award_arcade_coins(db, u.id, 0)
        check("zero award is a no-op", bal == 5)


async def test_buy_and_equip():
    print("-- buy + equip --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 5002, "shopper")
        await crud.award_arcade_coins(db, u.id, 200)
        await db.commit()

        crimson_price = ARCADE_SHOP["skins"]["crimson"]["price"]
        err, wallet = await crud.arcade_buy(db, u.id, "skin:crimson")
        pub = crud.arcade_wallet_public(wallet)
        check("skin purchase succeeds", err is None and "crimson" in pub["owned_skins"])
        check("bought skin auto-equips", pub["equipped_skin"] == "crimson")
        check("price deducted", pub["coins"] == 200 - crimson_price)

        err, _ = await crud.arcade_buy(db, u.id, "skin:crimson")
        check("double-buy rejected", err == "already_owned")
        err, _ = await crud.arcade_buy(db, u.id, "skin:default")
        check("default skin can't be bought", err == "already_owned")
        err, _ = await crud.arcade_buy(db, u.id, "skin:nonexistent")
        check("unknown skin rejected", err == "unknown_item")
        err, _ = await crud.arcade_buy(db, u.id, "banana")
        check("garbage item rejected", err == "unknown_item")

        err, wallet = await crud.arcade_buy(db, u.id, "power:shield_start")
        pub = crud.arcade_wallet_public(wallet)
        check("power purchase succeeds", err is None and "shield_start" in pub["owned_powers"])
        err, _ = await crud.arcade_buy(db, u.id, "power:shield_start")
        check("power double-buy rejected", err == "already_owned")

        err, wallet = await crud.arcade_buy(db, u.id, "extra_life")
        check("extra life purchase succeeds", err is None and wallet.extra_lives == 1)
        err, _ = await crud.arcade_buy(db, u.id, "extra_life")
        check("second extra life rejected", err == "already_owned")

        err, wallet = await crud.arcade_equip(db, u.id, "default")
        check("equip back to default works", err is None and wallet.equipped_skin == "default")
        err, _ = await crud.arcade_equip(db, u.id, "gold")
        check("equipping unowned skin rejected", err == "not_owned")
        err, _ = await crud.arcade_equip(db, u.id, "nope")
        check("equipping unknown skin rejected", err == "unknown_skin")

        # a broke user can't buy anything
        poor = await seed_user(db, 5003, "broke")
        err, _ = await crud.arcade_buy(db, poor.id, "skin:ice")
        check("insufficient coins rejected", err == "not_enough_coins")


async def test_retry():
    print("-- daily retry --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 5004, "retrier")
        retry_price = ARCADE_SHOP["retry"]["price"]

        # no run today → nothing to retry
        err, _ = await crud.arcade_retry(db, u.id)
        check("retry without a run rejected", err == "nothing_to_retry")

        # play the validated daily run
        await crud.save_game_play(db, u.id, 4200, 60, "x", rewarded=True,
                                  reward_xp=50, count_for_leaderboard=True)
        play = await crud.check_daily_game_play(db, u.id, tehran_today())
        check("run banked", play.rewarded and play.best_score == 4200)

        # broke → rejected
        err, _ = await crud.arcade_retry(db, u.id)
        check("retry without coins rejected", err == "not_enough_coins")

        await crud.award_arcade_coins(db, u.id, retry_price + 5)
        await db.commit()

        err, coins = await crud.arcade_retry(db, u.id)
        check("retry succeeds with coins", err is None)
        check("retry price deducted", coins == 5)
        play = await crud.check_daily_game_play(db, u.id, tehran_today())
        check("today's score wiped + gate reopened",
              play.best_score == 0 and play.rewarded is False)

        # gate reopened → can_play says yes again
        st = await crud.can_play_daily_game(db, u.id)
        check("daily gate open after retry", st["allowed"] is True)

        # can't retry twice without playing again
        err, _ = await crud.arcade_retry(db, u.id)
        check("second retry without a new run rejected", err == "nothing_to_retry")

        # the new run replaces the old score (even lower)
        await crud.save_game_play(db, u.id, 900, 60, "x", rewarded=True,
                                  count_for_leaderboard=True)
        play = await crud.check_daily_game_play(db, u.id, tehran_today())
        check("new run replaces the wiped score", play.best_score == 900)


async def test_loadout_and_economy_seal():
    print("-- loadout + economy seal --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 5005, "loadout")
        await crud.award_arcade_coins(db, u.id, 500)
        await db.commit()

        await crud.arcade_buy(db, u.id, "skin:gold")
        await crud.arcade_buy(db, u.id, "power:spread_start")
        await crud.arcade_buy(db, u.id, "extra_life")

        wallet = await crud.get_or_create_arcade_wallet(db, u.id)
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("loadout carries the equipped skin + its color",
              lo["skin"] == "gold" and lo["skin_color"] == ARCADE_SHOP["skins"]["gold"]["color"])
        check("loadout flags spread, not shield",
              lo["spread_start"] is True and lo["shield_start"] is False)
        check("loadout carries extra life", lo["extra_lives"] == 1)

        # ECONOMY SEAL: all that shopping cannot have touched money fields
        user = (await db.execute(select(User).filter(User.id == u.id))).scalars().first()
        check("credit untouched by coin economy", (user.credit or 0) == 0)
        check("stars untouched by coin economy", (user.stars or 0) == 0)


async def main():
    await test_wallet_and_awards()
    await test_buy_and_equip()
    await test_retry()
    await test_loadout_and_economy_seal()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
