"""Arcade leaderboard aggregation tests (2026-07-19 fix) on in-memory SQLite.

The old query returned raw DailyGamePlay rows: one user could occupy several
weekly/all_time slots (one per day played) and unrewarded/practice rows were
ranked. The fixed query aggregates one row per user (daily = that day's best,
weekly/all_time = SUM of daily bests, matching the monthly race), counts only
rewarded runs with best_score > 0, and keeps the show_on_leaderboard opt-in.

Run: PYTHONPATH=src python tests/test_arcade_leaderboard.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, DailyGamePlay, User  # noqa: E402
from app.utils.tehran_time import tehran_now  # noqa: E402
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


def week_days(n):
    """First n dates of the current IRAN week (guaranteed inside the week)."""
    now = tehran_now()
    week_start = (now - datetime.timedelta(days=now.weekday())).date()
    today = now.date()
    days = [week_start + datetime.timedelta(days=i) for i in range(7)]
    days = [d for d in days if d <= today]
    # Late in the week there are always >= 1 days; wrap by reusing today
    while len(days) < n:
        days.append(today)
    return days[:n]


async def test_weekly_aggregates_per_user():
    print("-- weekly: one row per user, scores summed --")
    maker = await make_session()
    async with maker() as db:
        grinder = await seed_user(db, 5001, "grinder")
        rival = await seed_user(db, 5002, "rival")

        days = week_days(3)
        unique_days = sorted(set(days))
        # grinder: several validated daily runs this week
        per_day = {}
        for d in days:
            per_day[d] = per_day.get(d, 0)
        scores = [1000, 2000, 3000]
        for d, s in zip(unique_days, scores):
            db.add(DailyGamePlay(user_id=grinder.id, play_date=d, best_score=s,
                                 rewarded=True, duration_seconds=60))
        expected_sum = sum(scores[: len(unique_days)])
        # rival: one big single day, but less than grinder's sum
        db.add(DailyGamePlay(user_id=rival.id, play_date=unique_days[0],
                             best_score=expected_sum - 500, rewarded=True, duration_seconds=60))
        await db.commit()

        board = await crud.get_game_leaderboard(db, period="weekly", limit=10)
        rows_for_grinder = [r for r in board if r["user_id"] == grinder.id]
        check("grinder appears exactly once", len(rows_for_grinder) == 1)
        check("grinder's weekly score is the SUM of daily bests",
              rows_for_grinder and rows_for_grinder[0]["score"] == expected_sum)
        check("summed grinder outranks single-day rival",
              board and board[0]["user_id"] == grinder.id)
        check("ranks are sequential", [r["rank"] for r in board] == list(range(1, len(board) + 1)))

        # all_time behaves the same way (sum, one row per user)
        board_all = await crud.get_game_leaderboard(db, period="all_time", limit=10)
        rows_for_grinder = [r for r in board_all if r["user_id"] == grinder.id]
        check("all_time: grinder appears exactly once", len(rows_for_grinder) == 1)
        check("all_time: score is summed",
              rows_for_grinder and rows_for_grinder[0]["score"] == expected_sum)


async def test_unrewarded_and_optout_excluded():
    print("-- unrewarded rows and opted-out users never rank --")
    maker = await make_session()
    async with maker() as db:
        honest = await seed_user(db, 6001, "honest")
        cheat = await seed_user(db, 6002, "cheat")
        ghost = await seed_user(db, 6003, "ghost", show=False)
        today = tehran_now().date()

        db.add(DailyGamePlay(user_id=honest.id, play_date=today, best_score=800,
                             rewarded=True, duration_seconds=60))
        # practice-era / rejected rows: rewarded=False
        db.add(DailyGamePlay(user_id=cheat.id, play_date=today, best_score=99999,
                             rewarded=False, duration_seconds=60))
        # opted-out user with a valid run
        db.add(DailyGamePlay(user_id=ghost.id, play_date=today, best_score=7777,
                             rewarded=True, duration_seconds=60))
        await db.commit()

        for period in ("daily", "weekly", "all_time"):
            board = await crud.get_game_leaderboard(db, period=period, limit=10)
            ids = [r["user_id"] for r in board]
            check(f"{period}: unrewarded row excluded", cheat.id not in ids)
            check(f"{period}: opted-out user hidden", ghost.id not in ids)
            check(f"{period}: honest player ranked", honest.id in ids)

        # zero-score rewarded row (retry-reset state) must not rank either
        zero = await seed_user(db, 6004, "zero")
        db.add(DailyGamePlay(user_id=zero.id, play_date=today, best_score=0,
                             rewarded=True, duration_seconds=60))
        await db.commit()
        board = await crud.get_game_leaderboard(db, period="daily", limit=10)
        check("zero-score row not ranked", zero.id not in [r["user_id"] for r in board])


async def test_daily_shows_days_best():
    print("-- daily period: that day's best_score, today only --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 7001, "daily-player")
        today = tehran_now().date()
        yesterday = today - datetime.timedelta(days=1)
        db.add(DailyGamePlay(user_id=u.id, play_date=yesterday, best_score=5000,
                             rewarded=True, duration_seconds=60))
        db.add(DailyGamePlay(user_id=u.id, play_date=today, best_score=1200,
                             rewarded=True, duration_seconds=60))
        await db.commit()

        board = await crud.get_game_leaderboard(db, period="daily", limit=10)
        mine = [r for r in board if r["user_id"] == u.id]
        check("daily board has exactly one row for the user", len(mine) == 1)
        check("daily score is today's best (not yesterday's, not a sum)",
              mine and mine[0]["score"] == 1200)


async def main():
    await test_weekly_aggregates_per_user()
    await test_unrewarded_and_optout_excluded()
    await test_daily_shows_days_best()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
