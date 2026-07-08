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
        check("tint skins carry no sprite", lo["skin_sprite"] is None)
        check("loadout flags spread, not shield",
              lo["spread_start"] is True and lo["shield_start"] is False)
        check("loadout carries extra life", lo["extra_lives"] == 1)

        # sprite skins (full redesigns) ride the same pipeline
        err, wallet = await crud.arcade_buy(db, u.id, "skin:falcon")
        check("sprite skin purchase succeeds + auto-equips",
              err is None and wallet.equipped_skin == "falcon")
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("loadout carries the redesign sprite",
              lo["skin_sprite"] == "sprites/ship_falcon.png" and lo["skin_color"] is None)

        # ECONOMY SEAL: all that shopping cannot have touched money fields
        user = (await db.execute(select(User).filter(User.id == u.id))).scalars().first()
        check("credit untouched by coin economy", (user.credit or 0) == 0)
        check("stars untouched by coin economy", (user.stars or 0) == 0)


async def test_admin_adjust():
    print("-- admin adjust (coins + difficulty, 2026-07-08) --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 5006, "adjusted")

        err, wallet = await crud.admin_arcade_adjust(db, u.id, coins_delta=100)
        check("admin grant credits coins", err is None and wallet.coins == 100)
        check("grants don't inflate lifetime-earned", wallet.coins_earned_total == 0)

        err, wallet = await crud.admin_arcade_adjust(db, u.id, coins_delta=-40)
        check("admin removal deducts", err is None and wallet.coins == 60)
        err, wallet = await crud.admin_arcade_adjust(db, u.id, coins_delta=-500)
        check("balance floors at zero", err is None and wallet.coins == 0)

        err, wallet = await crud.admin_arcade_adjust(db, u.id, difficulty="boss_rush")
        check("difficulty set", err is None and wallet.difficulty == "boss_rush")
        err, _ = await crud.admin_arcade_adjust(db, u.id, difficulty="nightmare")
        check("unknown difficulty rejected", err == "unknown_difficulty")

        # difficulty rides the loadout to the game
        wallet = await crud.get_or_create_arcade_wallet(db, u.id)
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("loadout carries the difficulty", lo["difficulty"] == "boss_rush")
        err, wallet = await crud.admin_arcade_adjust(db, u.id, difficulty="normal")
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("difficulty resets to normal", lo["difficulty"] == "normal")

        # fresh wallets default to normal
        u2 = await seed_user(db, 5007, "fresh")
        wallet2 = await crud.get_or_create_arcade_wallet(db, u2.id)
        check("fresh wallet difficulty is normal",
              crud.arcade_wallet_public(wallet2)["difficulty"] == "normal")

        # ECONOMY SEAL: admin coin grants touch nothing but the wallet
        user = (await db.execute(select(User).filter(User.id == u.id))).scalars().first()
        check("admin grants don't touch credit/stars",
              (user.credit or 0) == 0 and (user.stars or 0) == 0)


async def test_ship_classes():
    """Ship classes (2026-07-08): every skin carries a perk/ability id that
    rides the loadout; the client can only ever get the power of the skin
    the SERVER says is equipped."""
    print("-- ship classes (perks + abilities in the loadout) --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 5008, "classes")
        await crud.award_arcade_coins(db, u.id, 500)
        await db.commit()

        # catalog: every skin declares its power; premium trio is priced above
        skins = ARCADE_SHOP["skins"]
        check("all non-default skins carry a power",
              all(("perk" in v or "ability" in v) for k, v in skins.items() if k != "default"))
        check("premium trio priced 80/110/150",
              (skins["reaper"]["price"], skins["vulcan"]["price"], skins["aegis"]["price"])
              == (80, 110, 150))
        check("premium trio carries abilities, not perks",
              all("ability" in skins[k] and "perk" not in skins[k]
                  for k in ("reaper", "vulcan", "aegis")))

        # default ship: no powers
        wallet = await crud.get_or_create_arcade_wallet(db, u.id)
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("default loadout has no perk/ability",
              lo["perk"] is None and lo["ability"] is None)

        # perk skin: loadout names the perk
        await crud.arcade_buy(db, u.id, "skin:phantom")
        wallet = await crud.get_or_create_arcade_wallet(db, u.id)
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("phantom loadout carries cheat_death perk",
              lo["perk"] == "cheat_death" and lo["ability"] is None)

        # ability skin: loadout names the ability
        err, wallet = await crud.arcade_buy(db, u.id, "skin:reaper")
        check("reaper purchase works", err is None)
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("reaper loadout carries scythe ability",
              lo["ability"] == "scythe" and lo["perk"] is None)

        # equipping back to a tint swaps the power with it
        await crud.arcade_equip(db, u.id, "default")
        wallet = await crud.get_or_create_arcade_wallet(db, u.id)
        lo = build_loadout(crud.arcade_wallet_public(wallet))
        check("re-equipping default drops the power",
              lo["perk"] is None and lo["ability"] is None)


async def main():
    await test_wallet_and_awards()
    await test_buy_and_equip()
    await test_retry()
    await test_loadout_and_economy_seal()
    await test_admin_adjust()
    await test_ship_classes()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
