"""HTTP middleware shared by the aiohttp Application (security headers, admin auth, audit)."""

import logging
import time
import urllib.parse

from aiohttp import web

from app.api.routes.admin_auth import _get_token_from_request, verify_admin_token
from app.utils.admin_ip_whitelist import get_client_ip, is_ip_allowed

logger = logging.getLogger(__name__)


@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    """
    Add baseline security headers that are safe for Telegram WebApps.

    Notes:
    - DO NOT set X-Frame-Options / restrictive CSP here, because Telegram WebApps can be embedded
      (e.g., web.telegram.org) and overly strict headers can break the Mini App.
    """
    resp = await handler(request)

    # If handler returned None or doesn't have headers, return early
    if resp is None or not hasattr(resp, "headers"):
        return resp

    # Basic hardening (safe everywhere)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )

    # Minimal CSP that keeps the current UI working (inline scripts/styles + Telegram + Google Fonts).
    # Note: We use CSP frame-ancestors (instead of X-Frame-Options) because Telegram WebApps can be embedded.
    csp = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://t.me; "
        "script-src 'self' 'unsafe-inline' https://telegram.org; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:; "
        "img-src 'self' data: blob: https://flagcdn.com https://*.flagcdn.com https://t.me https://*.t.me https://telegram.org https://*.telegram.org https://*.telegram-cdn.org; "
        "connect-src 'self' https: http: wss: ws:; "
        "form-action 'self'"
    )
    resp.headers.setdefault("Content-Security-Policy", csp)

    # HSTS only when we know the request is HTTPS (direct or via proxy)
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").lower()
    is_https = bool(getattr(request, "secure", False)) or forwarded_proto == "https"
    if is_https:
        # 6 months; includeSubDomains is usually correct when you serve everything over https
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains")

    # Force no-cache for all webapp assets so design changes are picked up immediately.
    # Telegram Desktop and Telegram Web can cache mini-app resources aggressively.
    # Exception: Vite build output under react/assets/ has content-hashed filenames,
    # so it can never go stale — cache it hard (big win on slow connections; the
    # no-store HTML entry points always reference the current hashes).
    path = request.path
    if path.startswith("/webapp/dashboard/react/assets/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/webapp/static/fonts/"):
        # Self-hosted fonts effectively never change; cache for 30 days.
        resp.headers["Cache-Control"] = "public, max-age=2592000"
    elif path.startswith("/webapp/") and path.endswith((".css", ".js", ".html")):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"

    return resp


@web.middleware
async def admin_auth_middleware(request: web.Request, handler):
    """
    Protect /api/admin endpoints with the admin_session token.

    Telegram Web embeds Mini Apps cross-site; sessions are carried by HttpOnly cookies
    (or Authorization header fallback). The frontend already checks /verify-session;
    this ensures the backend also enforces auth consistently.
    """
    path = request.path
    if path.startswith("/api/admin") or path.startswith("/admin"):
        ip = get_client_ip(request)
        if not is_ip_allowed(ip):
            if path.startswith("/api/admin"):
                return web.json_response({"ok": False, "error": "ip_not_allowed"}, status=403)
            raise web.HTTPForbidden(text="Forbidden")
    if path.startswith("/api/admin"):
        # Public admin auth endpoints
        if path in {
            "/api/admin/login",
            "/api/admin/verify-2fa",
            "/api/admin/verify-session",
            "/api/admin/logout",
        }:
            return await handler(request)

        token = _get_token_from_request(request)
        session = verify_admin_token(token)
        if not session:
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
        # Make session available for later middlewares/handlers (audit logs, etc.)
        try:
            request["admin_session"] = session
        except Exception:
            pass

        # CSRF protection for cookie-based admin sessions
        safe_methods = {"GET", "HEAD", "OPTIONS"}
        if request.method.upper() not in safe_methods:
            # Only enforce CSRF when auth is carried by cookies (classic CSRF threat model).
            cookie_mode = bool(request.cookies.get("admin_session"))
            if cookie_mode:
                expected = str((session or {}).get("csrf_token") or "").strip()
                provided = (
                    request.headers.get("X-CSRF-Token") or request.headers.get("X-CSRFToken") or ""
                ).strip()
                if not expected or not provided or provided != expected:
                    return web.json_response({"ok": False, "error": "csrf_failed"}, status=403)

    # Protect admin HTML pages too:
    # - Anyone can load /admin/ (login shell)
    # - Assets (css/js/images) are public so the login shell can render
    # - Any other /admin/* page requires a valid session (prevents "type the link" access)
    if path.startswith("/admin"):
        public_admin_pages = {
            "/admin",
            "/admin/",
            "/admin/index.html",
        }
        if path in public_admin_pages:
            return await handler(request)

        # Protect uploads (receipt images) - do NOT allow these anonymously.
        # (Everything else can be a public SPA shell; sensitive data stays behind /api/admin/*.)
        if path.startswith("/admin/uploads/"):
            token = _get_token_from_request(request)
            session = verify_admin_token(token)
            if not session:
                next_path = request.path_qs or request.path
                raise web.HTTPFound("/admin/" + "?next=" + urllib.parse.quote(next_path, safe=""))
            return await handler(request)

        # Allow static assets under /admin/ so the login page isn't broken
        asset_exts = (".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".map")
        if path.endswith(asset_exts):
            return await handler(request)

        # Legacy routes (v1/v2/v3) - allow handler to do redirect
        if path.startswith("/admin/v1/") or path.startswith("/admin/v2/") or path.startswith("/admin/v3/"):
            return await handler(request)

        # Default (/admin/*) is also an SPA shell (v3 live). Allow direct navigation/refresh.
        # Sensitive ops are still protected under /api/admin/* and uploads are protected above.
        if path.startswith("/admin/"):
            return await handler(request)

        token = _get_token_from_request(request)
        session = verify_admin_token(token)
        if not session:
            # For browser navigations, a redirect is nicer than JSON 401.
            # Preserve the requested URL so after login we can send the admin back.
            next_path = request.path_qs or request.path
            raise web.HTTPFound("/admin/?next=" + urllib.parse.quote(next_path, safe=""))

    return await handler(request)


@web.middleware
async def admin_audit_log_middleware(request: web.Request, handler):
    """
    Log state-changing admin API calls for audit/debugging.

    IMPORTANT: Never log request bodies (passwords / PII).
    """
    path = request.path
    method = request.method.upper()
    is_admin_api = path.startswith("/api/admin")
    is_state_changing = method in {"POST", "PUT", "PATCH", "DELETE"}

    if not is_admin_api or not is_state_changing:
        return await handler(request)

    # Avoid noisy/sensitive auth endpoints
    if path in {"/api/admin/login", "/api/admin/verify-2fa"}:
        return await handler(request)

    start = time.time()
    status = 0
    try:
        resp = await handler(request)
        status = int(getattr(resp, "status", 200) or 200)
        return resp
    except Exception:
        status = 500
        raise
    finally:
        try:
            dur_ms = int((time.time() - start) * 1000)
            sess = {}
            try:
                s = request.get("admin_session")  # type: ignore[attr-defined]
                if isinstance(s, dict):
                    sess = s
            except Exception:
                sess = {}
            chat_id = sess.get("chat_id")
            sid = sess.get("session_id")
            ip = (
                (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
                or (request.headers.get("X-Real-IP") or "").strip()
                or "unknown"
            )
            ua = (request.headers.get("User-Agent") or "").strip()
            ua = ua[:180] if ua else "Unknown"
            logger.info(
                "[ADMIN AUDIT] %s %s status=%s ms=%s ip=%s chat_id=%s session_id=%s ua=%s",
                method,
                path,
                status,
                dur_ms,
                ip,
                chat_id,
                sid,
                ua,
            )
        except Exception:
            pass
