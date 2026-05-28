"""Register dashboard Mini App static routes."""

from pathlib import Path

from aiohttp import web

from app.api.routes.dashboard import handle_dashboard_index

from .constants import DASHBOARD_WEB_BASE, PROFILE_WEB_BASE, SHARED_STATIC_PREFIX
from .handlers import build_dashboard_web_handlers


def register_dashboard_web_routes(app: web.Application, wd: Path) -> None:
    (
        handle_dashboard_shop,
        handle_dashboard_purchase,
        handle_dashboard_charge,
        handle_dashboard_support,
        handle_profile_index,
    ) = build_dashboard_web_handlers(wd)

    app.router.add_get(DASHBOARD_WEB_BASE, handle_dashboard_index)
    app.router.add_get(DASHBOARD_WEB_BASE + "/", handle_dashboard_index)

    app.router.add_get(DASHBOARD_WEB_BASE + "/shop.html", handle_dashboard_shop)
    app.router.add_get(DASHBOARD_WEB_BASE + "/shop", handle_dashboard_shop)

    app.router.add_get(DASHBOARD_WEB_BASE + "/purchase.html", handle_dashboard_purchase)
    app.router.add_get(DASHBOARD_WEB_BASE + "/purchase", handle_dashboard_purchase)

    app.router.add_get(DASHBOARD_WEB_BASE + "/charge.html", handle_dashboard_charge)
    app.router.add_get(DASHBOARD_WEB_BASE + "/charge", handle_dashboard_charge)

    app.router.add_get(DASHBOARD_WEB_BASE + "/support.html", handle_dashboard_support)
    app.router.add_get(DASHBOARD_WEB_BASE + "/support", handle_dashboard_support)

    app.router.add_static(DASHBOARD_WEB_BASE + "/", path=str(wd / "dashboard"), name="dashboard_static")

    app.router.add_get(PROFILE_WEB_BASE, handle_profile_index)
    app.router.add_static(PROFILE_WEB_BASE + "/", path=str(wd / "profile"), name="profile_static")
    app.router.add_static(SHARED_STATIC_PREFIX, path=str(wd / "static"), name="web_static")
