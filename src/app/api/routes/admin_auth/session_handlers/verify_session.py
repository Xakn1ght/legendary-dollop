"""Session validity and CSRF cookie refresh."""

from aiohttp import web

from app.core.settings import ADMIN_SESSION_EXPIRY_HOURS

from .. import state as st
from ..token_verify import verify_admin_token
from .request_token import _get_token_from_request


async def handle_admin_verify_session(request: web.Request):
    """Verify if current session is valid"""
    token = _get_token_from_request(request)
    session = verify_admin_token(token)

    if session:
        response = web.json_response(
            {
                "ok": True,
                "valid": True,
                "expires_at": session["expires_at"],
                "session_id": session.get("session_id"),
                "csrf_token": session.get("csrf_token"),
            }
        )
        try:
            is_https, samesite = st._admin_cookie_attrs(request)
            response.set_cookie(
                st._ADMIN_CSRF_COOKIE,
                str(session.get("csrf_token") or ""),
                httponly=False,
                secure=is_https,
                samesite=samesite,
                max_age=ADMIN_SESSION_EXPIRY_HOURS * 60 * 60,
                path="/",
            )
        except Exception:
            pass
        return response
    return web.json_response({"ok": True, "valid": False})
