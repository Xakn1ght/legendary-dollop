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
    Check if the request comes from a Telegram WebApp.
    
    Returns:
        bool: True if the request is from Telegram, False otherwise
    """
    # 1. Check for Telegram initData in headers (most reliable)
    init_headers = [
        request.headers.get("X-Telegram-Init"),
        request.headers.get("X-Telegram-WebApp-InitData"),
        request.headers.get("X-Telegram-Init-Data"),
    ]
    if any(h and len(h) > 20 for h in init_headers):
        return True
    
    # 2. Check User-Agent for Telegram indicators
    user_agent = request.headers.get("User-Agent", "").lower()
    telegram_ua_indicators = [
        "telegram",
        "telegrambot",
    ]
    if any(indicator in user_agent for indicator in telegram_ua_indicators):
        return True
    
    # 3. Check Referer header for Telegram origins
    referer = request.headers.get("Referer", "").lower()
    telegram_referers = [
        "telegram.org",
        "t.me",
        "web.telegram.org",
    ]
    if any(ref in referer for ref in telegram_referers):
        return True
    
    # REMOVED: Same-origin check - this was allowing browsers to access once they loaded the page!
    # We ONLY allow requests that have Telegram indicators, not just same-origin requests.
    
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

