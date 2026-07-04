"""Handlers for dashboard Mini App HTML entrypoints."""

from pathlib import Path

from aiohttp import web


def _no_store_headers(resp: web.FileResponse) -> web.FileResponse:
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def _redirect_to_shell(request: web.Request, page: str | None = None):
    """Redirect legacy page URLs into the React shell, preserving the query
    string (bot deep links carry one-time ?auth= tokens)."""
    loc = "/webapp/dashboard/"
    qs = request.query_string
    if qs:
        loc += "?" + qs
    if page:
        loc += "#page=" + page
    raise web.HTTPFound(loc)


def build_dashboard_web_handlers(wd: Path):
    # Legacy standalone pages (shop/tasks/profile/index.html) were removed —
    # their URLs now land on the matching tab of the React shell.
    async def handle_dashboard_shop(request: web.Request):
        return _redirect_to_shell(request, "shop")

    async def handle_dashboard_tasks(request: web.Request):
        return _redirect_to_shell(request, "tasks")

    async def handle_dashboard_index_html(request: web.Request):
        return _redirect_to_shell(request)

    async def handle_dashboard_purchase(request: web.Request):
        resp = web.FileResponse(path=str(wd / "dashboard" / "react" / "purchase.html"))
        return _no_store_headers(resp)

    async def handle_dashboard_charge(request: web.Request):
        resp = web.FileResponse(path=str(wd / "dashboard" / "react" / "charge.html"))
        return _no_store_headers(resp)

    async def handle_dashboard_support(request: web.Request):
        resp = web.FileResponse(path=str(wd / "dashboard" / "react" / "support.html"))
        return _no_store_headers(resp)

    async def handle_profile_index(request: web.Request):
        return _redirect_to_shell(request, "profile")

    return (
        handle_dashboard_shop,
        handle_dashboard_tasks,
        handle_dashboard_index_html,
        handle_dashboard_purchase,
        handle_dashboard_charge,
        handle_dashboard_support,
        handle_profile_index,
    )
