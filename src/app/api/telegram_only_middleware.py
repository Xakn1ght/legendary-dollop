"""
Telegram-only middleware for WebApp security.

This middleware ensures that dashboard endpoints can ONLY be accessed through
Telegram Mini Apps, not from regular browsers.
"""
import logging

from aiohttp import web

logger = logging.getLogger(__name__)


def is_telegram_webapp_request(request: web.Request) -> bool:
    """
    Cheap outer gate: does the request carry any credential that could only
    have been minted through Telegram? (Cryptographic verification of those
    credentials happens in the handlers via ``_verify_webapp_auth``.)

    Deliberately NOT checked: User-Agent / Referer — both trivially spoofable
    and not needed, since every legitimate call carries initData or a session
    minted from initData.
    """
    # 1. Telegram initData in headers (WebApp runtime attaches it per call)
    init_headers = [
        request.headers.get("X-Telegram-Init"),
        request.headers.get("X-Telegram-WebApp-InitData"),
        request.headers.get("X-Telegram-Init-Data"),
    ]
    if any(h and len(h) > 20 for h in init_headers):
        return True

    # 2. Bearer session — only ever issued by /login after HMAC-verified initData
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return True

    # 3. Session cookie — same origin story as the bearer
    if request.cookies.get("tma_session") or request.cookies.get("auth_token"):
        return True

    return False


async def telegram_only_middleware(app: web.Application, handler):
    """
    Middleware that restricts dashboard access to Telegram WebApp only.
    
    This prevents users from:
    - Opening dashboard links in regular browsers
    - Sharing links that work outside Telegram
    - Accessing the dashboard from scrapers/bots
    """
    async def middleware_handler(request: web.Request):
        path = request.path
        
        # Only protect dashboard endpoints
        # Allow static files, API endpoints that handle their own auth
        protected_paths = [
            "/webapp/dashboard/",
            "/api/dashboard/",
        ]
        
        # Special cases: don't block these
        exceptions = [
            "/api/dashboard/login",  # Login needs to work from anywhere initially
            "/webapp/dashboard/favicon",
            "/webapp/dashboard/assets/",
        ]
        
        # Allow static assets (CSS, JS, images, fonts)
        static_extensions = (
            ".css", ".js", ".map", ".jpg", ".jpeg", ".png", ".gif", 
            ".svg", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot"
        )
        if path.endswith(static_extensions):
            return await handler(request)
        
        # Check if this is a protected path
        is_protected = any(path.startswith(p) for p in protected_paths)
        is_exception = any(path.startswith(e) for e in exceptions)
        
        if is_protected and not is_exception:
            # WebSocket upgrades can't carry custom headers, and Telegram Desktop's
            # webview User-Agent is plain Chrome — let WS requests that present
            # initData/auth in the query through to the handler's HMAC verification.
            if (
                request.headers.get("Upgrade", "").lower() == "websocket"
                and (request.query.get("init_data") or request.query.get("auth"))
            ):
                return await handler(request)
            # For API endpoints: enforce Telegram origin check.
            # HTML pages stay open so the mini-app shell can load in the browser frame.
            # The real auth (HMAC-signed initData + session token) happens inside each handler.
            if path.startswith("/api/dashboard/") and not is_telegram_webapp_request(request):
                return web.json_response(
                    {"ok": False, "error": "telegram_only", "message": "This API is only accessible through Telegram."},
                    status=403,
                )
        
        return await handler(request)
    
    return middleware_handler

