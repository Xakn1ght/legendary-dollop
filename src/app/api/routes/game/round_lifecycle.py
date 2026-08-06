"""Arcade round checkpoints + abandoned-round finalization (2026-07-19).

Design goals (launch hardening):
- An honest player who gets interrupted (call, Telegram killed, crash) keeps
  the score they had earned: the client checkpoints score every ~10s and the
  server finalizes the round from the last checkpoint.
- Closing mid-run can NOT be used to retry-grind: once a round has >= the
  minimum session length of checkpointed play, starting a new round (or the
  10-min sweep) finalizes it server-side — consuming the daily attempt.
- A round with no checkpoints (or under the minimum) dies silently, exactly
  like today: closing before anything happened costs nothing.
- Per-window rate checks replace the blunt 500 pts/s session average for
  checkpoint-aware clients; bursts (bomb wipes, megaboss 8000) fit in the
  burst allowance.
- Cached v27 clients send no checkpoints — every legacy behavior is kept
  bit-for-bit (no meta -> legacy gates in the submit handler).
- Redis down -> degrade to exactly today's behavior (no checkpoints, no
  finalize; round tokens fall back to process memory as before).

Redis keys (all TTL-bound, no schema changes):
  arcade:round:<token>       -> "<user_id>:<issued_ts>"   (round_start.py)
  arcade:round:meta:<token>  -> JSON rolling checkpoint state
  arcade:round:open:<uid>    -> most recent open round token for the user
  arcade:round:done:<token>  -> "1" tombstone; a late submit for a finalized
                                round gets a friendly "already recorded"
                                instead of a cheat flag
"""

import json
import time

from aiohttp import web

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth
from app.api.routes.game.common import logger
from app.api.routes.game.round_start import consume_round_token_any, peek_round_token
from app.core.redis_config import get_redis_client
from app.core.settings import BOT_TOKEN, GAME_REWARDS
from app.utils.webapp_verify import verify_init_data

META_PREFIX = "arcade:round:meta:"
OPEN_PREFIX = "arcade:round:open:"
DONE_PREFIX = "arcade:round:done:"
DONE_TTL = 6 * 60 * 60  # tombstones outlive the 2h token TTL comfortably


def _ttl() -> int:
    return int(GAME_REWARDS.get("round_token_ttl_seconds", 7200))


def _max_rate() -> int:
    return int(GAME_REWARDS.get("max_points_per_second", 500))


def _burst() -> int:
    return int(GAME_REWARDS.get("checkpoint_burst_allowance", 8000))


def _max_anomalies() -> int:
    return int(GAME_REWARDS.get("checkpoint_max_anomalies", 1))


# ---------------------------------------------------------------------------
# Redis helpers (every call degrades to None/no-op when Redis is down)
# ---------------------------------------------------------------------------

async def _redis():
    try:
        return await get_redis_client()
    except Exception:
        return None


async def get_round_meta(token: str) -> dict | None:
    redis = await _redis()
    if redis is None or not token:
        return None
    try:
        raw = await redis.get(META_PREFIX + token)
    except Exception as e:
        logger.warning(f"[ARCADE] meta read failed: {e}")
        return None
    if not raw:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode()
        meta = json.loads(raw)
        return meta if isinstance(meta, dict) else None
    except Exception:
        return None


async def _set_round_meta(token: str, meta: dict) -> None:
    redis = await _redis()
    if redis is None:
        return
    try:
        await redis.set(META_PREFIX + token, json.dumps(meta), ex=_ttl())
    except Exception as e:
        logger.warning(f"[ARCADE] meta write failed: {e}")


async def pop_round_meta(token: str) -> dict | None:
    """Read-and-delete the checkpoint meta (used at submit/finalize)."""
    redis = await _redis()
    if redis is None or not token:
        return None
    try:
        if hasattr(redis, "getdel"):
            raw = await redis.getdel(META_PREFIX + token)
        else:
            pipe = redis.pipeline()
            pipe.get(META_PREFIX + token)
            pipe.delete(META_PREFIX + token)
            raw = (await pipe.execute())[0]
    except Exception as e:
        logger.warning(f"[ARCADE] meta pop failed: {e}")
        return None
    if not raw:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode()
        meta = json.loads(raw)
        return meta if isinstance(meta, dict) else None
    except Exception:
        return None


async def mark_round_done(token: str) -> None:
    """Tombstone a consumed round so a late duplicate submit gets a friendly
    'already recorded' instead of a no_token cheat flag."""
    redis = await _redis()
    if redis is None or not token:
        return
    try:
        await redis.set(DONE_PREFIX + token, "1", ex=DONE_TTL)
    except Exception:
        pass


async def is_round_done(token: str) -> bool:
    redis = await _redis()
    if redis is None or not token:
        return False
    try:
        return bool(await redis.exists(DONE_PREFIX + token))
    except Exception:
        return False


async def set_open_round(user_id: int, token: str) -> str | None:
    """Remember the user's newest open round; returns the PREVIOUS open token
    (if any) so the caller can finalize it."""
    redis = await _redis()
    if redis is None:
        return None
    key = OPEN_PREFIX + str(int(user_id))
    prev = None
    try:
        if hasattr(redis, "getset"):
            prev = await redis.getset(key, token)
        else:
            prev = await redis.get(key)
            await redis.set(key, token)
        await redis.expire(key, _ttl())
    except Exception as e:
        logger.warning(f"[ARCADE] open-round bookkeeping failed: {e}")
        return None
    if isinstance(prev, bytes):
        prev = prev.decode()
    if prev and prev != token:
        return prev
    return None


async def clear_open_round(user_id: int, token: str) -> None:
    """Best-effort: forget the open round after it was consumed by a submit."""
    redis = await _redis()
    if redis is None:
        return
    key = OPEN_PREFIX + str(int(user_id))
    try:
        current = await redis.get(key)
        if isinstance(current, bytes):
            current = current.decode()
        if current == token:
            await redis.delete(key)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Checkpoint endpoint
# ---------------------------------------------------------------------------

def _auth_user(request: web.Request) -> int | None:
    """Same auth ladder the other arcade endpoints use: session/header first,
    then Telegram init_data from the query string."""
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    return user_chat_id or None


async def handle_arcade_checkpoint(request: web.Request):
    """Fire-and-forget mid-run score checkpoint. NEVER fails the game: every
    outcome (bad token, Redis down, over-rate window) is a 200 so the client
    can stay dumb. The token is validated for ownership but NOT consumed."""
    user_chat_id = _auth_user(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    token = str(data.get("round_token") or "")[:64]
    try:
        score = max(0, int(data.get("score") or 0))
        coins = max(0, int(data.get("coins") or 0))
        level = max(0, int(data.get("level") or 0))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)
    score = min(score, 1_000_000_000)

    if not token:
        return web.json_response({"ok": True, "stored": False})

    if await is_round_done(token):
        # round already finalized/submitted — tell the client to stop
        return web.json_response({"ok": True, "stored": False, "done": True})

    owner = await peek_round_token(token)
    if owner is None:
        return web.json_response({"ok": True, "stored": False})
    owner_id, issued_ts = owner
    if int(owner_id) != int(user_chat_id):
        logger.warning(f"[ARCADE] checkpoint token owner mismatch: owner={owner_id} claimer={user_chat_id}")
        return web.json_response({"ok": True, "stored": False})

    redis = await _redis()
    if redis is None:
        # Redis down: degrade to legacy behavior (no checkpoint state at all)
        return web.json_response({"ok": True, "stored": False})

    now = int(time.time())
    meta = await get_round_meta(token)
    if meta is None:
        meta = {
            "user_id": int(user_chat_id),
            "first_ts": now,
            "issued_ts": int(issued_ts),
            "last_ts": int(issued_ts),
            "last_score": 0,
            "last_coins": 0,
            "level": 0,
            "count": 0,
            "anomalies": 0,
            "max_window_rate": 0.0,
        }

    window = max(1, now - int(meta.get("last_ts") or issued_ts))
    prev_score = int(meta.get("last_score") or 0)
    delta = score - prev_score
    allowed = _max_rate() * window + _burst()

    if delta < 0:
        # monotonic violation: keep the max, count the anomaly
        meta["anomalies"] = int(meta.get("anomalies") or 0) + 1
        score = prev_score
    elif delta > allowed:
        meta["anomalies"] = int(meta.get("anomalies") or 0) + 1
        rate = delta / window
        meta["max_window_rate"] = max(float(meta.get("max_window_rate") or 0.0), round(rate, 1))
        logger.warning(
            f"[ARCADE] checkpoint over-rate: user={user_chat_id} +{delta} in {window}s "
            f"(allowed {allowed}) anomalies={meta['anomalies']}"
        )

    meta["last_ts"] = now
    meta["last_score"] = max(prev_score, score)
    meta["last_coins"] = max(int(meta.get("last_coins") or 0), coins)
    meta["level"] = max(int(meta.get("level") or 0), level)
    meta["count"] = int(meta.get("count") or 0) + 1
    await _set_round_meta(token, meta)

    return web.json_response({"ok": True, "stored": True})


# ---------------------------------------------------------------------------
# Server-side finalization of abandoned rounds
# ---------------------------------------------------------------------------

def meta_played_seconds(meta: dict) -> int:
    """Seconds of checkpointed play recorded in the meta."""
    try:
        return max(0, int(meta.get("last_ts") or 0) - int(meta.get("issued_ts") or meta.get("first_ts") or 0))
    except Exception:
        return 0


async def finalize_round(token: str, *, reason: str) -> bool:
    """Consume an abandoned round and settle it server-side.

    - No/short checkpoint timeline (< min_session_seconds): the round is
      silently invalidated — no daily attempt consumed (matches today's
      semantics for closing before anything happened).
    - Enough timeline: the last checkpoint score goes through the SAME
      reward/save path as a real submit (idempotent per Iran day via the
      existing rewarded guard), consuming the daily attempt. Anomalous
      checkpoint curves are flagged instead of paid.
    Race-safe: the atomic token consumption decides between this and a
    concurrent real submit; the tombstone keeps the loser friendly.
    Returns True if the round was settled (either way).
    """
    consumed = await consume_round_token_any(token)
    if consumed is None:
        # someone else (real submit / another sweep) won the race
        await pop_round_meta(token)
        return False
    owner_id, issued_ts = consumed
    meta = await pop_round_meta(token)
    await mark_round_done(token)

    min_duration = int(GAME_REWARDS.get("min_session_seconds", 20))
    if not meta or meta_played_seconds(meta) < min_duration or int(meta.get("last_score") or 0) <= 0:
        # nothing meaningful played — free abandon, exactly like today
        logger.info(f"[ARCADE] round {reason}: silently invalidated (no/short checkpoints) user={owner_id}")
        return True

    score = int(meta.get("last_score") or 0)
    duration = meta_played_seconds(meta)
    coins = int(meta.get("last_coins") or 0)
    anomalies = int(meta.get("anomalies") or 0)

    from app.database import crud
    from app.database.models import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, owner_id)
        if not user:
            return True

        from app.utils.tehran_time import tehran_today
        today = tehran_today()
        existing_play = await crud.check_daily_game_play(session, user.id, today)
        if existing_play and existing_play.rewarded:
            # daily already settled by another run — record analytics only
            await crud.save_game_play(
                session, user.id, score, duration, "",
                rewarded=False, count_for_leaderboard=False,
            )
            return True

        max_score = int(GAME_REWARDS.get("max_score_absolute", 500_000))
        if score > max_score or anomalies > _max_anomalies():
            logger.warning(
                f"[ARCADE] finalize rejected: user={owner_id} score={score} "
                f"anomalies={anomalies} played={duration}s"
            )
            await crud.add_arcade_flag(session, user.id, score, duration, duration, "checkpoint_curve")
            await crud.save_game_play(
                session, user.id, 0, duration, "",
                rewarded=False, count_for_leaderboard=False,
            )
            return True

        from app.api.routes.game.reward_core import grant_validated_run
        await grant_validated_run(
            session, user,
            score=score, duration=duration, display_name="",
            coins_reported=coins, finalized=True,
        )
        logger.info(
            f"[ARCADE] round {reason}: finalized user={owner_id} score={score} "
            f"played={duration}s coins={coins}"
        )
        return True


async def finalize_previous_round_of(user_id: int, new_token: str) -> None:
    """Round-start hook: settle the user's previous open round (if any)
    before the new one begins — this is what kills abandon-grinding."""
    prev = await set_open_round(user_id, new_token)
    if prev:
        try:
            await finalize_round(prev, reason="superseded")
        except Exception as e:
            logger.warning(f"[ARCADE] finalize of superseded round failed: {e}")


async def sweep_stale_rounds() -> int:
    """Finalize open rounds whose last checkpoint is old (default 30 min —
    generous: the game pauses when hidden and checkpoints stop, so anything
    younger could still be a paused-and-resumed run). Returns settled count."""
    redis = await _redis()
    if redis is None:
        return 0
    stale_after = int(GAME_REWARDS.get("round_stale_finalize_seconds", 1800))
    now = int(time.time())
    settled = 0
    try:
        cursor = 0
        keys = []
        while True:
            cursor, batch = await redis.scan(cursor=cursor, match=OPEN_PREFIX + "*", count=200)
            keys.extend(batch)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning(f"[ARCADE] stale-round scan failed: {e}")
        return 0

    for key in keys:
        try:
            token = await redis.get(key)
            if isinstance(token, bytes):
                token = token.decode()
            if not token:
                await redis.delete(key)
                continue
            alive = await peek_round_token(token)
            if alive is None:
                # token consumed or expired — nothing left to finalize
                await redis.delete(key)
                continue
            meta = await get_round_meta(token)
            if meta is None:
                # no checkpoints yet: only reap once the token itself is near
                # death (legacy clients never checkpoint — leave them alone,
                # their token simply expires like today)
                continue
            if now - int(meta.get("last_ts") or 0) < stale_after:
                continue
            if await finalize_round(token, reason="stale"):
                settled += 1
            await redis.delete(key)
        except Exception as e:
            logger.warning(f"[ARCADE] stale-round sweep entry failed: {e}")
    return settled
