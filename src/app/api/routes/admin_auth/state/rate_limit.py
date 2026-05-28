import time

from aiohttp import web

from app.core.settings import (
    ADMIN_LOGIN_LOCKOUT_MINUTES,
    ADMIN_LOGIN_MAX_ATTEMPTS,
    TRUST_PROXY_HEADERS,
)

from .runtime import _login_attempts


def _get_client_ip(request: web.Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
    peername = request.transport.get_extra_info("peername")
    if peername:
        return peername[0]
    return "unknown"


def _is_rate_limited(ip: str) -> tuple[bool, int]:
    now = time.time()
    cutoff = now - (ADMIN_LOGIN_LOCKOUT_MINUTES * 60)

    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]

    if len(_login_attempts[ip]) >= ADMIN_LOGIN_MAX_ATTEMPTS:
        oldest = min(_login_attempts[ip])
        remaining = int((oldest + ADMIN_LOGIN_LOCKOUT_MINUTES * 60) - now)
        return True, max(0, remaining)

    return False, 0


def _record_login_attempt(ip: str):
    _login_attempts[ip].append(time.time())
