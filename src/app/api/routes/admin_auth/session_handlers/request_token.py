"""Resolve admin session token from cookie or Authorization header."""

from aiohttp import web

from .. import state as st


def _get_token_from_request(request: web.Request) -> str:
    """Get admin session token from cookie (preferred) or Authorization header (fallback)"""
    token = request.cookies.get(st._ADMIN_SESSION_COOKIE, "")
    if token:
        return token
    return request.headers.get("Authorization", "").replace("Bearer ", "")
