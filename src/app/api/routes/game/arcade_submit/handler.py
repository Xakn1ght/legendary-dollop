from datetime import date, datetime

from aiohttp import web

from app.api.deps import _verify_webapp_auth
from app.api.routes.game.common import logger
from app.api.routes.game.round_start import consume_round_token
from app.api.schemas import ArcadeSubmitRequest, validate_request
from app.core.settings import GAME_REWARDS
from app.database import crud
from app.database.models import AsyncSessionLocal


async def handle_arcade_submit(request: web.Request):
    """Handle game score submission and award rewards with balanced system"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(ArcadeSubmitRequest, data)
    if error:
        return web.json_response(error, status=400)

    init_data = validated.init_data or ""
    score = validated.score
    duration = validated.duration
    is_practice = validated.practice
    display_name = validated.display_name or ""
    round_token = validated.round_token or ""

    user_chat_id, _new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        auth_from_query = request.query.get("auth", "")[:20]
        logger.warning(
            f"[ARCADE] Auth failed - query auth: {auth_from_query}... | init_data: {bool(init_data)} | cookies: {list(request.cookies.keys())}"
        )
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        # Practice runs are recorded for analytics only — they never touch
        # best_score, so they can't reach any leaderboard or prize ranking.
        if is_practice:
            await crud.save_game_play(
                session, user.id, score, duration, display_name,
                rewarded=False, count_for_leaderboard=False,
            )
            return web.json_response({"ok": True, "practice": True, "score": score, "message": "Practice mode - no rewards"})

        today = date.today()
        existing_play = await crud.check_daily_game_play(session, user.id, today)

        if existing_play and existing_play.rewarded:
            await crud.save_game_play(
                session, user.id, score, duration, display_name,
                rewarded=False, count_for_leaderboard=False,
            )
            return web.json_response(
                {
                    "ok": True,
                    "already_played": True,
                    "score": score,
                    "message": "Daily limit reached. Play again tomorrow for rewards!",
                }
            )

        # ── Anti-cheat gate ─────────────────────────────────────────────
        # 1. A valid single-use round token must exist (issued when the round
        #    started). Consuming it yields the SERVER-measured round length —
        #    the client cannot lie about duration or replay a submit.
        server_elapsed = await consume_round_token(round_token, user_chat_id)
        if server_elapsed is None:
            logger.warning(f"[ARCADE] Rejected submit without valid round token: user={user_chat_id} score={score}")
            await crud.add_arcade_flag(session, user.id, score, duration, None, "no_token")
            await crud.save_game_play(
                session, user.id, score, duration, display_name,
                rewarded=False, count_for_leaderboard=False,
            )
            return web.json_response(
                {
                    "ok": True,
                    "rejected": True,
                    "score": score,
                    "message": "Round could not be verified. Please reopen the game and try again.",
                }
            )

        # 2. Plausibility: server-side elapsed time bounds the duration, and
        #    the score is capped by a generous points-per-second ceiling.
        min_duration = GAME_REWARDS.get("min_session_seconds", 20)
        duration_slack = GAME_REWARDS.get("duration_slack_seconds", 30)
        max_rate = GAME_REWARDS.get("max_points_per_second", 500)
        max_score = GAME_REWARDS.get("max_score_absolute", 500_000)
        effective_duration = min(duration, server_elapsed + duration_slack)

        if server_elapsed < min_duration:
            await crud.save_game_play(
                session, user.id, score, duration, display_name,
                rewarded=False, count_for_leaderboard=False,
            )
            return web.json_response(
                {
                    "ok": True,
                    "too_short": True,
                    "score": score,
                    "message": f"Game too short. Play at least {min_duration} seconds for rewards!",
                }
            )

        if score > max_score or score > max_rate * max(server_elapsed, 1):
            logger.warning(
                f"[ARCADE] Rejected implausible score: user={user_chat_id} score={score} "
                f"server_elapsed={server_elapsed}s client_duration={duration}s"
            )
            await crud.add_arcade_flag(session, user.id, score, duration, server_elapsed, "implausible_score")
            await crud.save_game_play(
                session, user.id, 0, effective_duration, display_name,
                rewarded=False, count_for_leaderboard=False,
            )
            return web.json_response(
                {
                    "ok": True,
                    "rejected": True,
                    "score": score,
                    "message": "Score could not be validated.",
                }
            )

        duration = effective_duration

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

        current_month = datetime.utcnow().replace(day=1).date()
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
            notes=f"Score: {score} | {credits} Cr, {xp} XP, {star_pieces} pieces, {stars_awarded} stars",
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

        await session.commit()

        return web.json_response(
            {
                "ok": True,
                "awarded": True,
                "rewarded": True,
                "score": score,
                "streak_bonus": streak_bonus_percent,
                "message": f"Earned {xp} XP!",  # arcade is XP-only now (see web_game.py)
                "rewards": {
                    "credits": credits,
                    "xp": xp,
                    "star_pieces": star_pieces,
                    "stars_converted": stars_awarded,
                    "total_pieces": user.star_pieces,
                    "loyalty_points": loyalty_points,
                },
                "monthly_stars": {
                    "earned": user.arcade_stars_this_month,
                    "cap": monthly_cap,
                    "remaining": monthly_cap - user.arcade_stars_this_month,
                },
            }
        )
