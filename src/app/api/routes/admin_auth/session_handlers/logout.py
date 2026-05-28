"""Admin logout."""

from datetime import datetime

from aiohttp import web

from .. import state as st
from ..token_verify import invalidate_session, verify_admin_token
from .request_token import _get_token_from_request


async def handle_admin_logout(request: web.Request):
    """Logout and invalidate session"""
    token = _get_token_from_request(request)
    if token:
        try:
            cookie_mode = bool(request.cookies.get(st._ADMIN_SESSION_COOKIE))
            sess = verify_admin_token(token)
            if cookie_mode and sess:
                expected = str(sess.get("csrf_token") or "")
                provided = (request.headers.get(st._ADMIN_CSRF_HEADER) or request.headers.get("X-CSRFToken") or "").strip()
                if not expected or not provided or provided != expected:
                    return web.json_response({"ok": False, "error": "csrf_failed"}, status=403)
        except Exception:
            pass

        try:
            sess = verify_admin_token(token)
            sid = str((sess or {}).get("session_id") or "")
            if sid:
                stored = st._admin_sessions.get("sessions", {}).get(sid)
                if isinstance(stored, dict) and not stored.get("revoked"):
                    stored["revoked"] = True
                    stored["revoked_at"] = datetime.utcnow().isoformat()
                    st._save_admin_sessions()
        except Exception:
            pass
        invalidate_session(token)

    response = web.json_response({"ok": True})
    response.del_cookie(st._ADMIN_SESSION_COOKIE, path="/")
    response.del_cookie(st._ADMIN_CSRF_COOKIE, path="/")
    return response
