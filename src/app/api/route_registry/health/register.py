"""Register health check HTTP routes."""

from aiohttp import web

from app.api.routes.client_log import handle_client_log

from .constants import HEALTH_PATHS
from .handlers import handle_health_check


def register_health_routes(app: web.Application) -> None:
    for path in HEALTH_PATHS:
        app.router.add_get(path, handle_health_check)
    # Client-side JS error intake (see routes/client_log.py).
    app.router.add_post("/api/client-log", handle_client_log)
