"""Handlers for dashboard Mini App HTML entrypoints."""

from pathlib import Path

from aiohttp import web


def _no_store_headers(resp: web.FileResponse) -> web.FileResponse:
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def build_dashboard_web_handlers(wd: Path):
    async def handle_dashboard_shop(request: web.Request):
        return web.FileResponse(path=str(wd / "dashboard" / "shop.html"))

    async def handle_dashboard_purchase(request: web.Request):
        resp = web.FileResponse(path=str(wd / "dashboard" / "purchase.html"))
        return _no_store_headers(resp)

    async def handle_dashboard_charge(request: web.Request):
        resp = web.FileResponse(path=str(wd / "dashboard" / "charge.html"))
        return _no_store_headers(resp)

    async def handle_dashboard_support(request: web.Request):
        resp = web.FileResponse(path=str(wd / "dashboard" / "support.html"))
        return _no_store_headers(resp)

    async def handle_profile_index(request: web.Request):
        raise web.HTTPFound("/webapp/dashboard/profile.html")

    return (
        handle_dashboard_shop,
        handle_dashboard_purchase,
        handle_dashboard_charge,
        handle_dashboard_support,
        handle_profile_index,
    )
