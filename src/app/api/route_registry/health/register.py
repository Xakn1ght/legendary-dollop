"""Register health check HTTP routes."""

from aiohttp import web

from .constants import HEALTH_PATHS
from .handlers import handle_health_check


def register_health_routes(app: web.Application) -> None:
    for path in HEALTH_PATHS:
        app.router.add_get(path, handle_health_check)
