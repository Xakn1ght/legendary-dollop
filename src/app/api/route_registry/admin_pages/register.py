"""Register admin panel static routes."""

from pathlib import Path

from aiohttp import web

from .constants import ADMIN_LEGACY_SUBPAGES, ADMIN_SPA_GET_PATHS, LEGACY_VERSIONS
from .handlers import build_admin_page_handlers


def register_admin_pages(app: web.Application, wd: Path) -> None:
    handle_admin_index, handle_admin_legacy_redirect, handle_admin_support, handle_admin_support_legacy = (
        build_admin_page_handlers(wd)
    )

    app.router.add_get("/admin", handle_admin_index)
    app.router.add_get("/admin/", handle_admin_index)
    app.router.add_get("/admin/index.html", handle_admin_index)
    for path in ADMIN_SPA_GET_PATHS:
        app.router.add_get(path, handle_admin_index)

    for ver in LEGACY_VERSIONS:
        app.router.add_get(f"/admin/{ver}", handle_admin_legacy_redirect)
        app.router.add_get(f"/admin/{ver}/", handle_admin_legacy_redirect)
        app.router.add_get(f"/admin/index_{ver}.html", handle_admin_legacy_redirect)
        for page in ADMIN_LEGACY_SUBPAGES:
            app.router.add_get(f"/admin/{ver}/{page}", handle_admin_legacy_redirect)
        app.router.add_get(f"/admin/{ver}/support", handle_admin_support_legacy)
        app.router.add_get(f"/admin/{ver}/support.html", handle_admin_support_legacy)
    app.router.add_get("/admin/support.html", handle_admin_support)
    app.router.add_get("/admin/support", handle_admin_support)
    app.router.add_static("/admin/", path=str(wd / "admin"), name="admin_static")
