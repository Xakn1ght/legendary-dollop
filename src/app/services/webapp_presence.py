"""Webapp-open presence guard (2026-07-13, Pasha).

While a user has THEIR Mini App open, their bot chat is locked: the two
surfaces share money/subscription state, and letting both drive it at once
races the FSM and the approval flows (the classic double-submit/exploit
window). The webapp heartbeats a short-TTL Redis key while it is visible;
the bot's WebappLockMiddleware refuses to run handlers while that key exists
and tells the user to close the Mini App.

Design choices:
- Redis key per chat_id, short TTL — self-heals if the close beacon is lost
  (worst case the lock lingers one TTL, ~20s, then clears itself).
- FAIL-OPEN everywhere: a Redis hiccup must never brick someone's bot. If we
  cannot read the key we treat the app as closed.
- /start and /cancel always bypass AND clear the lock — a guaranteed escape
  hatch so a user can never get permanently stuck.
"""
from app.core.redis_config import cache

# Heartbeat cadence is ~8s (frontend); TTL must outlive a couple missed beats
# but stay short so a lost close-beacon self-heals fast.
WEBAPP_LOCK_TTL = 20


def _key(chat_id: int) -> str:
    return f"webapp:open:{int(chat_id)}"


async def touch(chat_id: int, ttl: int = WEBAPP_LOCK_TTL) -> None:
    """Mark the user's Mini App as open (heartbeat). Best-effort."""
    try:
        await cache.set(_key(chat_id), 1, ttl=ttl)
    except Exception:
        pass


async def clear(chat_id: int) -> None:
    """Mark the Mini App closed (explicit close beacon or escape hatch)."""
    try:
        await cache.delete(_key(chat_id))
    except Exception:
        pass


async def is_open(chat_id: int) -> bool:
    """True only if we can positively confirm the Mini App is open.
    Fail-open: any error / missing key → False (bot stays usable)."""
    try:
        return bool(await cache.get(_key(chat_id)))
    except Exception:
        return False
