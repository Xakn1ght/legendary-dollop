"""Compose HTTP route registration (order matches historical monolithic registration)."""

from pathlib import Path

from aiohttp import web

from app.api.route_registry.admin_api import register_admin_api_routes
from app.api.route_registry.admin_pages import register_admin_pages
from app.api.route_registry.dashboard_api import register_dashboard_api_routes
from app.api.route_registry.dashboard_web import register_dashboard_web_routes
from app.api.route_registry.game import register_game_routes
from app.api.route_registry.health import register_health_routes


def register_all_routes(app: web.Application, wd: Path) -> None:
    register_health_routes(app)
    register_game_routes(app, wd)
    register_dashboard_web_routes(app, wd)
    register_admin_pages(app, wd)
    register_dashboard_api_routes(app)
    register_admin_api_routes(app)
