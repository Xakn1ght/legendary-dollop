"""Admin panel static shell handlers and legacy redirects."""

from pathlib import Path

from aiohttp import web

from .constants import LEGACY_ADMIN_PREFIXES


def build_admin_page_handlers(wd: Path):
    async def handle_admin_index(request: web.Request):
        resp = web.FileResponse(path=str(wd / "admin" / "index.html"))
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    async def handle_admin_legacy_redirect(request: web.Request):
        path = request.path
        for prefix in LEGACY_ADMIN_PREFIXES:
            if path.startswith(prefix):
                target = "/admin/" + path[len(prefix) :]
                break
        else:
            target = "/admin/"
        qs = request.query_string or ""
        if qs:
            target = target + "?" + qs
        raise web.HTTPFound(target)

    async def handle_admin_support(request: web.Request):
        resp = web.FileResponse(path=str(wd / "admin" / "support.html"))
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    async def handle_admin_support_legacy(request: web.Request):
        qs = request.query_string or ""
        target = "/admin/support"
        if qs:
            target = target + "?" + qs
        raise web.HTTPFound(target)

    return (
        handle_admin_index,
        handle_admin_legacy_redirect,
        handle_admin_support,
        handle_admin_support_legacy,
    )
