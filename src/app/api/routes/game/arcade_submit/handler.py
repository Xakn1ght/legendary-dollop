from aiohttp import web

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth
from app.api.routes.game.common import logger
from app.api.routes.game.reward_core import grant_validated_run
from app.api.routes.game.round_lifecycle import (
    clear_open_round,
    is_round_done,
    mark_round_done,
    pop_round_meta,
)
from app.api.routes.game.round_start import consume_round_token
from app.api.schemas import ArcadeSubmitRequest, validate_request
from app.core.settings import BOT_TOKEN, GAME_REWARDS
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.utils.tehran_time import tehran_today
from app.utils.webapp_verify import verify_init_data


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
    coins_reported = validated.coins or 0

    user_chat_id, _new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        # sendBeacon retries (final-submit safety net) cannot set headers or
        # rely on cookies — fall back to the HMAC-verified initData that the
        # payload already carries (same trust level as the header path).
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data) or None
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

        today = tehran_today()  # arcade days roll over at IRAN midnight
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
            # Friendly path (2026-07-19): the round was already settled — the
            # server finalized it (abandon/sweep) or a duplicate submit
            # (sendBeacon retry) landed after the real one. Not cheating.
            if round_token and await is_round_done(round_token):
                return web.json_response(
                    {
                        "ok": True,
                        "already_recorded": True,
                        "score": score,
                        "message": "Run already recorded.",
                    }
                )
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

        # The token is consumed: tombstone it so late duplicates stay friendly,
        # collect checkpoint meta (v28+ clients), release the open-round marker.
        meta = await pop_round_meta(round_token)
        await mark_round_done(round_token)
        await clear_open_round(user_chat_id, round_token)

        # 2. Plausibility: server-side elapsed time bounds the duration, and
        #    the score is capped. Checkpoint-aware clients are judged on their
        #    per-window history; legacy (no-checkpoint) clients keep the exact
        #    old session-average gate.
        min_duration = GAME_REWARDS.get("min_session_seconds", 20)
        duration_slack = GAME_REWARDS.get("duration_slack_seconds", 30)
        max_rate = GAME_REWARDS.get("max_points_per_second", 500)
        max_score = GAME_REWARDS.get("max_score_absolute", 500_000)
        burst = GAME_REWARDS.get("checkpoint_burst_allowance", 8000)
        max_anomalies = GAME_REWARDS.get("checkpoint_max_anomalies", 1)
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

        implausible = False
        flag_reason = "implausible_score"
        if score > max_score:
            implausible = True
        elif meta:
            # v28+ checkpoint curve: the final score may only exceed the last
            # checkpoint by what the remaining window allows, and the recorded
            # per-window history must be (nearly) clean.
            import time as _time
            last_score = int(meta.get("last_score") or 0)
            last_ts = int(meta.get("last_ts") or 0)
            tail_window = max(1, int(_time.time()) - last_ts)
            anomalies = int(meta.get("anomalies") or 0)
            if score > last_score + max_rate * tail_window + burst:
                implausible = True
                flag_reason = "checkpoint_curve"
            elif anomalies > max_anomalies:
                implausible = True
                flag_reason = "checkpoint_curve"
        else:
            # legacy client (no checkpoints): exact old gate, unchanged
            if score > max_rate * max(server_elapsed, 1):
                implausible = True

        if implausible:
            logger.warning(
                f"[ARCADE] Rejected implausible score: user={user_chat_id} score={score} "
                f"server_elapsed={server_elapsed}s client_duration={duration}s reason={flag_reason}"
            )
            await crud.add_arcade_flag(session, user.id, score, duration, server_elapsed, flag_reason)
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

        payload = await grant_validated_run(
            session,
            user,
            score=score,
            duration=effective_duration,
            display_name=display_name,
            coins_reported=coins_reported,
        )
        return web.json_response(payload)
