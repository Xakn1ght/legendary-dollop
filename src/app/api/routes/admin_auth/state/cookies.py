import secrets

from aiohttp import web

_ADMIN_SESSION_COOKIE = "admin_session"
_ADMIN_CSRF_COOKIE = "admin_csrf"
_ADMIN_CSRF_HEADER = "X-CSRF-Token"


def _admin_cookie_attrs(request: web.Request) -> tuple[bool, str]:
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    is_https = (forwarded_proto == "https") or (request.scheme == "https")
    samesite = "None" if is_https else "Lax"
    return is_https, samesite


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
