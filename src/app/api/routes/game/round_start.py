"""Single-use arcade round tokens (anti-cheat).

The game client calls /api/arcade/round-start the moment a round actually
begins. The server hands back a random token and remembers when it was
issued. On submit, the token is consumed atomically and the SERVER-measured
elapsed time (token age) becomes the authoritative round duration — the
client can no longer invent a duration, replay a submit, or post a score
without having started a round.

Tokens live in Redis (arcade:round:<token> → "<user_id>:<issued_ts>").
If Redis is unavailable we fall back to an in-process dict — fine for the
single-process aiohttp server.
"""

import secrets
import time

from aiohttp import web

from app.api.deps import _verify_webapp_auth
from app.api.routes.game.common import logger
from app.core.redis_config import get_redis_client
from app.core.settings import GAME_REWARDS

_KEY_PREFIX = "arcade:round:"
_memory_tokens: dict[str, str] = {}   # fallback when Redis is down


def _ttl() -> int:
    return int(GAME_REWARDS.get("round_token_ttl_seconds", 7200))


async def issue_round_token(user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    value = f"{user_id}:{int(time.time())}"
    redis = await get_redis_client()
    if redis is not None:
        try:
            await redis.set(_KEY_PREFIX + token, value, ex=_ttl())
            return token
        except Exception as e:
            logger.warning(f"[ARCADE] Redis round-token store failed, using memory: {e}")
    # memory fallback (also opportunistically prune expired entries)
    now = time.time()
    for k in [k for k, v in _memory_tokens.items() if now - int(v.split(":")[1]) > _ttl()]:
        _memory_tokens.pop(k, None)
    _memory_tokens[token] = value
    return token


async def consume_round_token_any(token: str) -> tuple[int, int] | None:
    """Atomically consume the token regardless of claimer. Returns
    (owner_user_id, issued_ts) or None if missing/expired/reused. Used by the
    submit path (which then checks ownership) and by server-side finalization
    of abandoned rounds (which acts on behalf of the owner)."""
    if not token or len(token) > 64:
        return None
    value = None
    redis = await get_redis_client()
    if redis is not None:
        try:
            if hasattr(redis, "getdel"):
                value = await redis.getdel(_KEY_PREFIX + token)
            else:  # older redis-py: emulate atomically enough via pipeline
                pipe = redis.pipeline()
                pipe.get(_KEY_PREFIX + token)
                pipe.delete(_KEY_PREFIX + token)
                value = (await pipe.execute())[0]
        except Exception as e:
            logger.warning(f"[ARCADE] Redis round-token consume failed: {e}")
    if value is None:
        value = _memory_tokens.pop(token, None)
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    try:
        owner_id, issued_ts = value.split(":")
        return int(owner_id), int(issued_ts)
    except Exception:
        return None


async def peek_round_token(token: str) -> tuple[int, int] | None:
    """Read a round token WITHOUT consuming it. Returns (owner_user_id,
    issued_ts) or None. Used by the checkpoint endpoint."""
    if not token or len(token) > 64:
        return None
    value = None
    redis = await get_redis_client()
    if redis is not None:
        try:
            value = await redis.get(_KEY_PREFIX + token)
        except Exception as e:
            logger.warning(f"[ARCADE] Redis round-token peek failed: {e}")
    if value is None:
        value = _memory_tokens.get(token)
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    try:
        owner_id, issued_ts = value.split(":")
        return int(owner_id), int(issued_ts)
    except Exception:
        return None


async def consume_round_token(token: str, user_id: int) -> int | None:
    """Atomically consume the token. Returns server-side elapsed seconds for
    this round, or None if the token is missing/expired/foreign/reused."""
    consumed = await consume_round_token_any(token)
    if consumed is None:
        return None
    owner_id, issued_ts = consumed
    if int(owner_id) != int(user_id):
        logger.warning(f"[ARCADE] Round token user mismatch: owner={owner_id} claimer={user_id}")
        return None
    elapsed = int(time.time()) - issued_ts
    return max(0, elapsed)


async def handle_arcade_round_start(request: web.Request):
    """Issue a round token for the authenticated user. Also returns the
    player's shop loadout (skin/powers/extra lives) so the run can apply
    it even when the page skipped the status call."""
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    token = await issue_round_token(user_chat_id)

    # Anti-abandon (2026-07-19): settle the user's previous open round before
    # this one starts. With >= min_session_seconds of checkpoints it consumes
    # the daily attempt at the last checkpointed score; with none it dies
    # silently (free, same as today). Never blocks round issuance.
    try:
        from app.api.routes.game.round_lifecycle import finalize_previous_round_of
        await finalize_previous_round_of(user_chat_id, token)
    except Exception as e:
        logger.warning(f"[ARCADE] previous-round finalize failed: {e}")

    loadout = None
    try:
        from app.api.routes.game.shop import build_loadout
        from app.database import crud
        from app.database.models import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if user:
                wallet = await crud.get_or_create_arcade_wallet(session, user.id)
                loadout = build_loadout(crud.arcade_wallet_public(wallet))
    except Exception as e:
        logger.warning(f"[ARCADE] loadout fetch failed on round-start: {e}")

    return web.json_response({"ok": True, "round_token": token, "loadout": loadout})
