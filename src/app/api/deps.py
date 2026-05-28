import json
import logging
import time
from urllib.parse import parse_qsl

from aiohttp import web

from app.core.settings import BOT_TOKEN, WEBAPP_SESSION_SECRET
from app.utils.webapp_verify import create_session_token, verify_init_data, verify_session_token

logger = logging.getLogger(__name__)

def _is_https_request(request: web.Request) -> bool:
    """
    Best-effort HTTPS detection (direct or behind a proxy).

    Important for cookie settings (SameSite=None requires Secure=True).
    """
    try:
        forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").lower().strip()
        if forwarded_proto:
            return forwarded_proto == "https"
    except Exception:
        pass
    try:
        if getattr(request, "secure", False):
            return True
    except Exception:
        pass
    try:
        return (request.scheme or "").lower() == "https"
    except Exception:
        return False


def dashboard_cookie_attrs(request: web.Request) -> tuple[bool, str]:
    """
    Cookie attributes for Telegram Mini Apps.

    - Telegram Web (web.telegram.org) often embeds Mini Apps cross-site (iframe).
      Cookies need SameSite=None; Secure on HTTPS to be sent reliably.
    - For local dev over HTTP, browsers reject SameSite=None cookies, so fall back to Lax.
    """
    is_https = _is_https_request(request)
    samesite = "None" if is_https else "Lax"
    secure = True if is_https else False
    return secure, samesite


def set_tma_session_cookie(
    resp: web.StreamResponse,
    request: web.Request,
    token: str,
    *,
    max_age: int = 86400,
) -> None:
    secure, samesite = dashboard_cookie_attrs(request)
    resp.set_cookie(
        "tma_session",
        token,
        max_age=int(max_age),
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def _get_token_age_seconds(token: str) -> int | None:
    """Best-effort decode to enforce short-lived query auth tokens."""
    try:
        payload_b64 = token.split(".", 1)[0]
        pad = '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        iat = int(payload.get("iat", 0) or 0)
        if iat <= 0:
            return None
        return int(time.time()) - iat
    except Exception:
        return None


def _token_has_jti(token: str) -> bool:
    """Detect one-time/query tokens (they include a `jti`)."""
    try:
        payload_b64 = token.split(".", 1)[0]
        pad = '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        jti = str(payload.get("jti") or "").strip()
        return bool(jti)
    except Exception:
        return False

def _verify_webapp_auth(request: web.Request):
    """
    Verify WebApp authentication via header token or query init_data.
    Returns: (user_chat_id, new_session_token)
    """
    session_secret = WEBAPP_SESSION_SECRET or BOT_TOKEN
    if not session_secret:
        logger.error("WebApp session secret is not configured")
        return None, None

    # Track the chosen method for debugging (safe: no token contents)
    try:
        request["auth_method"] = ""
    except Exception:
        pass

    # 0. Preferred: Telegram initData sent via header (WebApp runtime provides this each open)
    init_header = (
        request.headers.get("X-Telegram-Init", "")
        or request.headers.get("X-Telegram-WebApp-InitData", "")
        or request.headers.get("X-Telegram-Init-Data", "")
    )
    init_header_ok = False
    if init_header:
        init_header_ok = verify_init_data(init_header, BOT_TOKEN)
    if init_header and init_header_ok:
        user_id = _extract_user_id_from_init(init_header)
        if user_id:
            new_token = create_session_token(user_id, session_secret, ttl_seconds=86400)
            return user_id, new_token

    # 1. Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        # Do not accept one-time/query tokens as Bearer; they are more likely to leak via URLs.
        if _token_has_jti(token):
            return None, None
        user_id = verify_session_token(token, session_secret)
        if user_id:
            # Rotate into a fresh cookie-friendly token to reduce reuse of long-lived URL/header tokens.
            new_token = create_session_token(user_id, session_secret, ttl_seconds=86400)
            return user_id, new_token

    # 2. Check query param (legacy/fallback)
    auth_query = request.query.get("auth", "")
    if auth_query:
        user_id = verify_session_token(auth_query, session_secret)
        if user_id:
            new_token = create_session_token(user_id, session_secret, ttl_seconds=86400)
            try:
                request["auth_method"] = "query_auth"
            except Exception:
                pass
            return user_id, new_token

    # 3. Check cookies (check both auth_token and tma_session for compatibility)
    auth_cookie = request.cookies.get("tma_session", "") or request.cookies.get("auth_token", "")
    if auth_cookie:
        user_id = verify_session_token(auth_cookie, session_secret)
        if user_id:
            # Optionally rotate; keeps session alive and allows future secret rotation strategies.
            new_token = create_session_token(user_id, session_secret, ttl_seconds=86400)
            try:
                request["auth_method"] = "cookie"
            except Exception:
                pass
            return user_id, new_token

    # 4. Check init_data (initial handshake)
    init_data = request.query.get("init_data", "")
    if init_data and verify_init_data(init_data, BOT_TOKEN):
        user_id = _extract_user_id_from_init(init_data)
        if user_id:
            # Optionally rotate; keeps session alive and allows future secret rotation strategies.
            new_token = create_session_token(user_id, session_secret, ttl_seconds=86400)
            try:
                request["auth_method"] = "init_data"
            except Exception:
                pass
            return user_id, new_token

    # Don't log tokens/init_data. Just log the high-level auth attempt shape for debugging.
    had_any = bool(init_header or auth_header or auth_query or auth_cookie or init_data)
    if had_any:
        init_age = None
        if init_header:
            try:
                params = dict(parse_qsl(init_header, keep_blank_values=True))
                auth_date = int(params.get("auth_date", "0") or 0)
                if auth_date > 0:
                    init_age = int(time.time()) - auth_date
            except Exception:
                init_age = None
        logger.info(
            "WebApp auth failed (init_header=%s init_header_ok=%s init_age_s=%s bearer=%s query_auth=%s cookie=%s query_init=%s)",
            bool(init_header),
            bool(init_header_ok),
            init_age,
            bool(auth_header),
            bool(auth_query),
            bool(auth_cookie),
            bool(init_data),
        )
    return None, None

def _extract_user_id_from_init(init_data: str) -> int:
    try:
        payload = dict(parse_qsl(init_data, keep_blank_values=True))
        user_json = payload.get("user", "{}")
        user_data = json.loads(user_json)
        return int(user_data.get("id", 0))
    except Exception:
        return 0
