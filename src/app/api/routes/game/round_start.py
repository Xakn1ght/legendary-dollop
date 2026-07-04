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


async def consume_round_token(token: str, user_id: int) -> int | None:
    """Atomically consume the token. Returns server-side elapsed seconds for
    this round, or None if the token is missing/expired/foreign/reused."""
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
        if int(owner_id) != int(user_id):
            logger.warning(f"[ARCADE] Round token user mismatch: owner={owner_id} claimer={user_id}")
            return None
        elapsed = int(time.time()) - int(issued_ts)
        return max(0, elapsed)
    except Exception:
        return None


async def handle_arcade_round_start(request: web.Request):
    """Issue a round token for the authenticated user."""
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    token = await issue_round_token(user_chat_id)
    return web.json_response({"ok": True, "round_token": token})
