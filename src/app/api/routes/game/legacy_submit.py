from aiohttp import web

from app.api.routes.game.common import logger


async def handle_submit(request: web.Request):
    """Legacy game submit endpoint — permanently disabled (anti-cheat 2026-07-03).

    No shipped client calls this anymore (both arcade builds use
    /api/arcade/submit). It used to award full daily rewards and write
    leaderboard scores WITHOUT the round-token validation, which made it a
    straight bypass around the hardened submit path. It now refuses everything.
    """
    logger.warning(
        f"[ARCADE] Blocked legacy /api/game/submit call from {request.remote} "
        f"(ua={request.headers.get('User-Agent', '')[:60]})"
    )
    return web.json_response(
        {"ok": False, "error": "endpoint_retired", "use": "/api/arcade/submit"},
        status=410,
    )
