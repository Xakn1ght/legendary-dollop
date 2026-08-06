"""Stale arcade-round sweep (2026-07-19).

Every 10 minutes, finalize open rounds whose last checkpoint is older than
GAME_REWARDS["round_stale_finalize_seconds"] (default 30 min — generous,
because the game pauses when hidden and checkpoints stop; anything younger
could still be a paused-and-resumed run). Finalization is idempotent and
race-safe against a concurrent real submit: the atomic round-token
consumption decides the winner, and the done-tombstone keeps the loser on a
friendly "already recorded" response. No-op when Redis is unavailable
(legacy behavior everywhere).
"""

from app.api.routes.game.round_lifecycle import sweep_stale_rounds
from app.utils.logger import bot_logger


async def arcade_round_sweep_job(bot=None):
    settled = await sweep_stale_rounds()
    if settled:
        bot_logger.info(f"[ARCADE] round sweep finalized {settled} stale round(s)")
