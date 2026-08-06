"""The single reward-granting core for a validated arcade run.

Extracted from arcade_submit/handler.py (2026-07-19) so the same math runs
for both a real client submit and a server-side finalization of an abandoned
round (round_lifecycle.py). Anything that mints must live here exactly once.

Iron rule: the arcade pays XP only (thresholds in settings/web_game.py keep
credits/star_pieces at 0), plus sealed ArcadeWallet coins (capped per run).
"""

from app.core.settings import ARCADE_COINS, GAME_REWARDS
from app.database import crud
from app.utils.tehran_time import tehran_today


async def grant_validated_run(
    session,
    user,
    *,
    score: int,
    duration: int,
    display_name: str = "",
    coins_reported: int = 0,
    finalized: bool = False,
) -> dict:
    """Apply rewards for THE validated daily run and persist the play row.

    Caller must have verified: not practice, not already rewarded today, the
    round token was consumed, and the score passed the anti-cheat gates.
    Commits the session. Returns the response payload dict (same shape the
    submit endpoint always returned).
    """
    thresholds = GAME_REWARDS.get("thresholds", [])
    credits = 0
    xp = 0
    star_pieces = 0

    for threshold in thresholds:
        if score >= threshold.get("min_score", 0):
            credits = threshold.get("credits", 0)
            xp = threshold.get("xp", 0)
            star_pieces = threshold.get("star_pieces", 0)
            break

    streak = user.login_streak or 0
    streak_bonus_per_day = GAME_REWARDS.get("streak_bonus_percent_per_day", 5)
    streak_bonus_max = GAME_REWARDS.get("streak_bonus_max_percent", 25)
    streak_bonus_percent = min(streak * streak_bonus_per_day, streak_bonus_max)
    multiplier = 1.0 + (streak_bonus_percent / 100.0)

    credits = int(credits * multiplier)
    xp = int(xp * multiplier)

    stars_awarded = 0
    pieces_per_star = GAME_REWARDS.get("pieces_per_star", 10)
    monthly_cap = GAME_REWARDS.get("monthly_star_cap", 6)

    current_month = tehran_today().replace(day=1)
    if user.arcade_stars_month_reset is None or user.arcade_stars_month_reset < current_month:
        user.arcade_stars_this_month = 0
        user.arcade_stars_month_reset = current_month

    if star_pieces > 0:
        user.star_pieces += star_pieces

        if user.star_pieces >= pieces_per_star:
            potential_stars = user.star_pieces // pieces_per_star
            remaining_pieces = user.star_pieces % pieces_per_star

            stars_can_award = min(potential_stars, monthly_cap - user.arcade_stars_this_month)

            if stars_can_award > 0:
                user.star_pieces = remaining_pieces + ((potential_stars - stars_can_award) * pieces_per_star)
                user.arcade_stars_this_month += stars_can_award
                stars_awarded = stars_can_award

                await crud.StarManager.add_stars(
                    session,
                    user.id,
                    count=stars_can_award,
                    reason="arcade_game",
                    notes=f"Converted {stars_can_award * pieces_per_star} pieces to {stars_can_award} stars",
                )

    # Arcade coins: only the validated run mints them, hard-capped per
    # run server-side. Coins are arcade-only — never money-adjacent.
    coins_award = min(max(int(coins_reported or 0), 0), int(ARCADE_COINS.get("max_per_run", 3)))
    coin_balance = await crud.award_arcade_coins(session, user.id, coins_award)

    user.credit += credits
    user.experience_points += xp

    loyalty_rate = GAME_REWARDS.get("loyalty_points_per_1000_credits", 1)
    loyalty_points = (credits // 1000) * loyalty_rate
    if loyalty_points > 0:
        user.loyalty_points += loyalty_points

    await crud.add_reward_history(
        session,
        user_id=user.id,
        reward_type="arcade_game",
        reward_value=credits,
        source="arcade",
        notes=f"Score: {score} | {credits} Cr, {xp} XP, {star_pieces} pieces, {stars_awarded} stars"
              + (" | finalized-abandoned" if finalized else ""),
    )

    # The single validated daily run is the ONLY thing that sets
    # best_score — leaderboards and monthly prizes rank exactly this.
    await crud.save_game_play(
        session,
        user.id,
        score,
        duration,
        display_name,
        rewarded=True,
        reward_credit=credits,
        reward_stars=stars_awarded,
        reward_xp=xp,
        count_for_leaderboard=True,
    )

    # Challenge progress: the validated daily run advances daily_game /
    # weekly_game_score challenges (XP-only payout, idempotent grant).
    try:
        await crud.record_challenge_event(session, user.id, kind="daily_game", amount=1, score=score)
    except Exception:
        # Challenges must never block the run reward itself.
        pass

    await session.commit()

    return {
        "ok": True,
        "awarded": True,
        "rewarded": True,
        "score": score,
        "streak_bonus": streak_bonus_percent,
        "message": f"Earned {xp} XP!",  # arcade is XP-only now (see web_game.py)
        "finalized": finalized,
        "rewards": {
            "credits": credits,
            "xp": xp,
            "star_pieces": star_pieces,
            "stars_converted": stars_awarded,
            "total_pieces": user.star_pieces,
            "loyalty_points": loyalty_points,
            "coins": coins_award,
            "coin_balance": coin_balance,
        },
        "monthly_stars": {
            "earned": user.arcade_stars_this_month,
            "cap": monthly_cap,
            "remaining": monthly_cap - user.arcade_stars_this_month,
        },
    }
