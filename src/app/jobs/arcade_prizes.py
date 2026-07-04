"""Monthly arcade leaderboard prizes (2026-07-03).

Once per calendar month, the top players of the PREVIOUS month receive prize
coupons (config: ARCADE_MONTHLY_PRIZES in settings/web_game.py — 50GB / 10GB /
5GB free-traffic for ranks 1-3, 10% discount for ranks 4-10).

Fairness guarantees (matching the hardened submit path):
- Ranking uses DailyGamePlay.best_score, which is ONLY ever written by the
  single round-token-validated rewarded run per day. Practice, replayed and
  rejected runs can never enter this ranking.
- Only users with show_on_leaderboard=True are ranked — the prize board is
  exactly the board everyone can see.
- Ties break in favor of whoever reached the score on an earlier day.
- Idempotent: a reward_history guard row per month ensures the awards are
  minted at most once, no matter how often the job runs.

The job runs on an interval and no-ops until a new month begins.
"""
import datetime
import json

from sqlalchemy import select

from app.core.settings import ARCADE_MONTHLY_PRIZES, ARCADE_PRIZE_COUPON_EXPIRY_DAYS
from app.database import crud
from app.database.models import (
    AsyncSessionLocal,
    RewardCoupon,
    RewardHistory,
    User,
)
from app.utils.logger import bot_logger

GUARD_SOURCE = "arcade_prize"


def _previous_month_bounds(today: datetime.date) -> tuple[datetime.date, datetime.date, str]:
    """(first_day, last_day, 'YYYY-MM') of the month before `today`."""
    first_of_this = today.replace(day=1)
    last_prev = first_of_this - datetime.timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev, f"{first_prev.year:04d}-{first_prev.month:02d}"


def _prize_for_rank(rank: int) -> dict | None:
    for p in ARCADE_MONTHLY_PRIZES:
        if p["min_rank"] <= rank <= p["max_rank"]:
            return p
    return None


async def award_monthly_arcade_prizes(session, month_start, month_end, month_key, bot=None) -> int:
    """Rank last month's validated scores and mint prize coupons. Returns
    number of winners awarded. Assumes the caller checked the month guard."""
    max_rank = max(p["max_rank"] for p in ARCADE_MONTHLY_PRIZES)

    # Canonical race ranking (shared with /api/arcade/race).
    ranking = await crud.get_monthly_arcade_ranking(session, month_start, month_end, limit=max_rank)

    if not ranking:
        bot_logger.info(f"Arcade prizes {month_key}: no eligible players")
        return 0

    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(days=ARCADE_PRIZE_COUPON_EXPIRY_DAYS)
    awarded = 0

    for rank, (user_id, top_score, _first_play, _name) in enumerate(ranking, start=1):
        prize = _prize_for_rank(rank)
        if not prize:
            continue
        session.add(RewardCoupon(
            user_id=user_id,
            source="arcade_leaderboard",
            coupon_type=prize["coupon_type"],
            payload=json.dumps(prize["payload"]),
            created_at=now,
            expires_at=expires,
            status="active",
        ))
        await crud.add_reward_history(
            session,
            user_id=user_id,
            reward_type=GUARD_SOURCE,
            reward_value=rank,
            source=GUARD_SOURCE,
            notes=f"{month_key} rank {rank} (score {top_score}) → {prize['name']}",
        )
        awarded += 1

        if bot is not None:
            try:
                user = (await session.execute(
                    select(User).filter(User.id == user_id)
                )).scalars().first()
                if user and user.chat_id:
                    await bot.send_message(
                        chat_id=user.chat_id,
                        text=(
                            f"🏆 <b>AstroBugz {month_key} — Rank #{rank}!</b>\n\n"
                            f"Your best score of <b>{top_score}</b> earned you:\n"
                            f"🎁 <b>{prize['name']}</b>\n\n"
                            "The coupon is in your rewards wallet — use it on your next purchase. "
                            f"It expires in {ARCADE_PRIZE_COUPON_EXPIRY_DAYS} days."
                        ),
                        parse_mode="HTML",
                    )
            except Exception as e:
                bot_logger.warning(f"Arcade prizes {month_key}: notify rank {rank} failed: {e}")

    await session.commit()
    bot_logger.info(f"Arcade prizes {month_key}: awarded {awarded} coupons")
    return awarded


async def arcade_monthly_prizes_job(bot=None):
    """Interval job: on/after the 1st of each month, award last month once."""
    today = datetime.date.today()
    month_start, month_end, month_key = _previous_month_bounds(today)

    async with AsyncSessionLocal() as session:
        # Idempotency guard: any prize row for this month means we're done.
        existing = (await session.execute(
            select(RewardHistory.id)
            .filter(
                RewardHistory.source == GUARD_SOURCE,
                RewardHistory.notes.like(f"{month_key} rank %"),
            )
            .limit(1)
        )).scalars().first()
        if existing:
            return

        await award_monthly_arcade_prizes(session, month_start, month_end, month_key, bot=bot)
