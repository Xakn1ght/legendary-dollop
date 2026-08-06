"""Challenge system tests (2026-07-19 rebuild) on in-memory SQLite.

Covers the event-driven challenge pipeline:
- ensure-on-access creation (daily game + weekly referral/score challenges)
- progress from a validated arcade run through the REAL reward core
  (api/routes/game/reward_core.grant_validated_run)
- completion pays XP exactly once (double-completion safe via the
  RewardHistory guard row)
- ECONOMY IRON RULE: legacy monetary reward definitions (credit /
  loyalty_points) map to XP at grant time and never touch credit/stars
- referral events advance the weekly referral challenge

Run: PYTHONPATH=src python tests/test_challenges_flow.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, Challenge, RewardHistory, User, UserChallenge  # noqa: E402
from app.database.repos.reward._challenges import challenge_xp_value  # noqa: E402
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


def test_xp_mapping():
    print("-- monetary reward definitions map to XP --")
    check("xp passes through", challenge_xp_value("xp", 20) == 20)
    check("500 credit -> 50 XP", challenge_xp_value("credit", 500) == 50)
    check("100 loyalty -> 50 XP", challenge_xp_value("loyalty_points", 100) == 50)
    check("150 loyalty -> 75 XP", challenge_xp_value("loyalty_points", 150) == 75)
    check("credit clamps at 200 XP", challenge_xp_value("credit", 1_000_000) == 200)
    check("credit clamps at 10 XP minimum", challenge_xp_value("credit", 10) == 10)
    check("stars fall back to 50 XP", challenge_xp_value("stars", 3) == 50)
    check("garbage value is safe", challenge_xp_value("credit", "abc") == 10)


async def test_ensure_creation():
    print("-- ensure-on-access creation --")
    maker = await make_session()
    async with maker() as db:
        daily = await crud.ensure_today_daily_challenge(db)
        check("daily challenge created", daily is not None and daily.challenge_type == "daily")
        check("daily challenge pays XP", daily.reward_type == "xp")

        weekly = await crud.ensure_current_weekly_challenges(db)
        types = {(c.requirement_type or "").lower() for c in weekly}
        check("weekly referral challenge created", "referrals" in types)
        check("weekly game-score challenge created",
              bool(types.intersection({"weekly_game_score", "game_score"})))
        check("all weekly challenges pay XP", all(c.reward_type == "xp" for c in weekly))

        # calling again creates nothing new
        await crud.ensure_today_daily_challenge(db)
        await crud.ensure_current_weekly_challenges(db)
        count = len((await db.execute(select(Challenge))).scalars().all())
        check("ensure is idempotent (3 challenges total)", count == 3)


async def test_arcade_submit_progress_and_single_payout():
    print("-- validated arcade run drives challenge progress, pays XP once --")
    from app.api.routes.game.reward_core import grant_validated_run

    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 8001, "runner")

        payload = await grant_validated_run(
            db, u, score=12000, duration=300, display_name="runner", coins_reported=2,
        )
        check("run itself rewarded XP", payload["rewards"]["xp"] > 0)
        check("run pays no credit", payload["rewards"]["credits"] == 0)

        # daily challenge exists and is completed
        daily = await crud.ensure_today_daily_challenge(db)
        rows = await crud.get_user_challenge_progress(db, u.id, daily.id)
        check("daily challenge completed by the run", rows and rows[0].completed)

        guard = (await db.execute(
            select(RewardHistory).filter(
                RewardHistory.user_id == u.id,
                RewardHistory.source == "challenge",
                RewardHistory.source_id == daily.id,
            )
        )).scalars().all()
        check("exactly one challenge payout row", len(guard) == 1)
        check("payout is XP-typed", guard[0].reward_type == "xp")
        xp_paid = guard[0].reward_value
        check("daily challenge paid its configured XP",
              xp_paid == challenge_xp_value(daily.reward_type, daily.reward_value))

        # double-fire the same event: progress moves, payout must NOT repeat
        await crud.record_challenge_event(db, u.id, kind="daily_game", amount=1, score=500)
        guard2 = (await db.execute(
            select(RewardHistory).filter(
                RewardHistory.user_id == u.id,
                RewardHistory.source == "challenge",
                RewardHistory.source_id == daily.id,
            )
        )).scalars().all()
        check("double completion pays exactly once", len(guard2) == 1)

        # weekly game-score challenge got the score added
        weekly = await crud.ensure_current_weekly_challenges(db)
        score_ch = next(c for c in weekly
                        if (c.requirement_type or "").lower() in ("weekly_game_score", "game_score"))
        rows = await crud.get_user_challenge_progress(db, u.id, score_ch.id)
        check("weekly score challenge accumulated the run score",
              rows and rows[0].progress == 12000 + 500)


async def test_monetary_challenge_maps_to_xp_never_money():
    print("-- legacy monetary challenge rows grant XP, never money --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 8002, "legacy")
        now = datetime.utcnow()
        # a legacy row exactly like the old seeds: weekly referrals for loyalty
        legacy = Challenge(
            title="چالش قدیمی", description="legacy", challenge_type="weekly",
            requirement_type="referrals", requirement_value=1,
            reward_type="loyalty_points", reward_value=100,
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=5), active=True,
        )
        # and one carrying credit
        legacy_credit = Challenge(
            title="چالش اعتباری", description="legacy credit", challenge_type="weekly",
            requirement_type="referrals", requirement_value=2,
            reward_type="credit", reward_value=500,
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=5), active=True,
        )
        db.add_all([legacy, legacy_credit])
        await db.commit()

        credit_before = u.credit or 0
        stars_before = u.stars or 0
        loyalty_before = u.loyalty_points or 0

        completed = await crud.record_challenge_event(db, u.id, kind="referral")
        check("legacy loyalty challenge completed", any(c.id == legacy.id for c in completed))

        await crud.record_challenge_event(db, u.id, kind="referral")

        user = (await db.execute(select(User).filter(User.id == u.id))).scalars().first()
        check("credit untouched", (user.credit or 0) == credit_before)
        check("stars untouched", (user.stars or 0) == stars_before)
        check("loyalty untouched", (user.loyalty_points or 0) == loyalty_before)
        check("XP was granted instead", (user.experience_points or 0) > 0)

        payouts = (await db.execute(
            select(RewardHistory).filter(
                RewardHistory.user_id == u.id,
                RewardHistory.source == "challenge",
            )
        )).scalars().all()
        check("every challenge payout row is XP", all(p.reward_type == "xp" for p in payouts))
        by_source = {p.source_id: p.reward_value for p in payouts}
        check("100 loyalty row paid 50 XP", by_source.get(legacy.id) == 50)
        check("500 credit row paid 50 XP", by_source.get(legacy_credit.id) == 50)

        # no money-typed reward history rows appeared at all
        money_rows = (await db.execute(
            select(RewardHistory).filter(
                RewardHistory.user_id == u.id,
                RewardHistory.reward_type.in_(["credit", "stars", "loyalty_points"]),
            )
        )).scalars().all()
        check("no money-typed history rows", len(money_rows) == 0)


async def test_referral_event_progress():
    print("-- referral events advance the weekly referral challenge --")
    maker = await make_session()
    async with maker() as db:
        u = await seed_user(db, 8003, "promoter")

        await crud.record_challenge_event(db, u.id, kind="referral")
        weekly = await crud.ensure_current_weekly_challenges(db)
        ref_ch = next(c for c in weekly if (c.requirement_type or "").lower() == "referrals")
        rows = await crud.get_user_challenge_progress(db, u.id, ref_ch.id)
        check("first referral counted", rows and rows[0].progress == 1)
        check("not completed yet", not rows[0].completed)

        await crud.record_challenge_event(db, u.id, kind="referral")
        completed = await crud.record_challenge_event(db, u.id, kind="referral")
        check("third referral completes the challenge",
              any(c.id == ref_ch.id for c in completed))

        rows = await crud.get_user_challenge_progress(db, u.id, ref_ch.id)
        check("progress reached the requirement", rows[0].progress >= ref_ch.requirement_value)

        guard = (await db.execute(
            select(RewardHistory).filter(
                RewardHistory.user_id == u.id,
                RewardHistory.source == "challenge",
                RewardHistory.source_id == ref_ch.id,
            )
        )).scalars().all()
        check("weekly referral payout exactly once", len(guard) == 1)

        # user_challenges table holds one row per user+challenge
        ucs = (await db.execute(
            select(UserChallenge).filter(UserChallenge.user_id == u.id,
                                         UserChallenge.challenge_id == ref_ch.id)
        )).scalars().all()
        check("single progress row per user+challenge", len(ucs) == 1)


async def main():
    test_xp_mapping()
    await test_ensure_creation()
    await test_arcade_submit_progress_and_single_payout()
    await test_monetary_challenge_maps_to_xp_never_money()
    await test_referral_event_progress()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
