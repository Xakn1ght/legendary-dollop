"""Arcade anti-cheat + monthly prize tests on in-memory SQLite.

Covers the 2026-07-03 hardening:
- save_game_play: best_score is only written by the validated rewarded run
  (practice / already-played / rejected runs can never reach a leaderboard)
- round tokens: single-use, owner-bound, expiry via server clock (memory path)
- monthly prize job: ranks last month's validated scores, mints the right
  coupons (50GB / 10GB / 5GB / 10% x7), respects show_on_leaderboard,
  tie-breaks by earlier day, and is idempotent across repeated runs

Run: PYTHONPATH=src python tests/test_arcade_prizes.py
"""
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, DailyGamePlay, RewardCoupon, User  # noqa: E402
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


async def seed_user(db, chat_id, name, show=True):
    u = User(chat_id=chat_id, full_name=name, show_on_leaderboard=show)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def test_best_score_gating():
    print("-- best_score gating --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 1001, "gater")

        # practice-style save must not create a leaderboard score
        # (arcade days roll over at IRAN midnight — match save_game_play)
        await crud.save_game_play(db, u.id, 99999, 60, "x", rewarded=False, count_for_leaderboard=False)
        play = await crud.check_daily_game_play(db, u.id, tehran_today())
        check("practice run leaves best_score at 0", play.best_score == 0)

        # the validated rewarded run sets it
        await crud.save_game_play(db, u.id, 4321, 60, "x", rewarded=True, reward_xp=50, count_for_leaderboard=True)
        play = await crud.check_daily_game_play(db, u.id, tehran_today())
        check("rewarded run sets best_score", play.best_score == 4321)
        check("rewarded flag set", play.rewarded is True)

        # a later unvalidated run cannot raise it
        await crud.save_game_play(db, u.id, 88888, 60, "x", rewarded=False, count_for_leaderboard=False)
        play = await crud.check_daily_game_play(db, u.id, tehran_today())
        check("later practice cannot raise best_score", play.best_score == 4321)


async def test_round_tokens():
    print("-- round tokens (memory fallback) --")
    from app.api.routes.game import round_start as rs

    async def _no_redis():
        return None

    rs.get_redis_client = _no_redis  # force the in-memory path

    tok = await rs.issue_round_token(42)
    check("token issued", bool(tok))

    elapsed = await rs.consume_round_token(tok, 42)
    check("consume by owner returns elapsed >= 0", elapsed is not None and elapsed >= 0)

    reuse = await rs.consume_round_token(tok, 42)
    check("token is single-use", reuse is None)

    tok2 = await rs.issue_round_token(42)
    stolen = await rs.consume_round_token(tok2, 43)
    check("foreign user cannot consume token", stolen is None)

    missing = await rs.consume_round_token("no-such-token", 42)
    check("unknown token rejected", missing is None)


async def test_monthly_prizes():
    print("-- monthly prize job --")
    import app.jobs.arcade_prizes as prizes_mod
    from app.jobs.arcade_prizes import (
        _previous_month_bounds,
        arcade_monthly_prizes_job,
        award_monthly_arcade_prizes,
    )

    maker = await make_session()
    prizes_mod.AsyncSessionLocal = maker  # point job at the test DB

    today = tehran_today()  # the job ranks by IRAN-time months
    m_start, m_end, m_key = _previous_month_bounds(today)
    check("month bounds sane", m_start.day == 1 and m_start <= m_end < today)

    async with maker() as db:
        users = []
        # 12 visible players with distinct scores 1200..100 (rank order u0..u11)
        for i in range(12):
            u = await seed_user(db, 2000 + i, f"p{i}")
            users.append(u)
            db.add(DailyGamePlay(
                user_id=u.id, play_date=m_start + datetime.timedelta(days=i),
                best_score=1200 - i * 100, rewarded=True, duration_seconds=60,
            ))
        # a hidden user with the top score — must NOT win
        ghost = await seed_user(db, 3001, "ghost", show=False)
        db.add(DailyGamePlay(user_id=ghost.id, play_date=m_start, best_score=99999,
                             rewarded=True, duration_seconds=60))
        # an unrewarded (practice-era) high score — must NOT count
        cheat = await seed_user(db, 3002, "cheat")
        db.add(DailyGamePlay(user_id=cheat.id, play_date=m_start, best_score=88888,
                             rewarded=False, duration_seconds=60))
        # tie with rank 1: same score, later day → loses the tie-break
        late = await seed_user(db, 3003, "late")
        db.add(DailyGamePlay(user_id=late.id, play_date=m_start + datetime.timedelta(days=20),
                             best_score=1200, rewarded=True, duration_seconds=60))
        await db.commit()

        n = await award_monthly_arcade_prizes(db, m_start, m_end, m_key, bot=None)
        check("awarded exactly 4 winners", n == 4)

        coupons = (await db.execute(select(RewardCoupon))).scalars().all()
        check("4 coupons minted", len(coupons) == 4)

        by_user = {c.user_id: c for c in coupons}
        c1 = by_user.get(users[0].id)
        check("rank 1 gets 50GB free_gb", c1 is not None and c1.coupon_type == "free_gb"
              and json.loads(c1.payload)["gb"] == 50)
        c2 = by_user.get(late.id)
        check("tie goes to earlier day (late player is rank 2 → 25GB)",
              c2 is not None and json.loads(c2.payload).get("gb") == 25)
        c3 = by_user.get(users[1].id)
        check("rank 3 gets 10GB", c3 is not None and json.loads(c3.payload).get("gb") == 10)
        c4 = by_user.get(users[2].id)
        check("rank 4 gets 10% discount", c4 is not None and c4.coupon_type == "discount_percent"
              and json.loads(c4.payload)["discount_percent"] == 10)
        check("ghost (hidden) got nothing", ghost.id not in by_user)
        check("unrewarded score got nothing", cheat.id not in by_user)
        check("rank 5+ got nothing", users[3].id not in by_user and users[10].id not in by_user)

    # idempotency: running the JOB now must mint nothing new
    await arcade_monthly_prizes_job(bot=None)
    async with maker() as db:
        coupons = (await db.execute(select(RewardCoupon))).scalars().all()
        check("job is idempotent (still 4 coupons)", len(coupons) == 4)


async def test_ranking_and_flags():
    print("-- ranking helper + cheat flags --")
    from app.database.models import ArcadeFlag

    maker = await make_session()
    async with maker() as db:
        u1 = await seed_user(db, 4001, "alpha")
        u2 = await seed_user(db, 4002, "beta")
        today = tehran_today()
        start = today.replace(day=1)
        db.add(DailyGamePlay(user_id=u1.id, play_date=start, best_score=500,
                             rewarded=True, duration_seconds=60))
        db.add(DailyGamePlay(user_id=u2.id, play_date=start, best_score=900,
                             rewarded=True, duration_seconds=60))
        await db.commit()

        rows = await crud.get_monthly_arcade_ranking(db, start, today)
        check("ranking ordered by score", [r.user_id for r in rows] == [u2.id, u1.id])
        check("ranking carries display names", rows[0].display_name == "beta")

        # monthly score ACCUMULATES across days (sum, not max) — a second
        # validated day lifts alpha (500+600=1100) over beta's single 900
        if (today - start).days >= 1:
            db.add(DailyGamePlay(user_id=u1.id, play_date=start + datetime.timedelta(days=1),
                                 best_score=600, rewarded=True, duration_seconds=60))
            await db.commit()
            rows = await crud.get_monthly_arcade_ranking(db, start, today)
            check("daily scores add up across the month",
                  rows[0].user_id == u1.id and int(rows[0].top_score) == 1100)

        await crud.add_arcade_flag(db, u1.id, 999999, 600, None, "no_token")
        await crud.add_arcade_flag(db, u1.id, 777777, 30, 25, "implausible_score")
        flags = (await db.execute(select(ArcadeFlag))).scalars().all()
        check("flags persisted", len(flags) == 2)
        check("flag reasons stored", sorted(f.reason for f in flags) ==
              ["implausible_score", "no_token"])


async def main():
    await test_best_score_gating()
    await test_round_tokens()
    await test_monthly_prizes()
    await test_ranking_and_flags()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
