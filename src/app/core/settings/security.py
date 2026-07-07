"""Admin panel auth, session secrets, password hashing, and startup validation helpers."""

import hashlib
import os
import secrets

from passlib.hash import argon2

from app.core.paths import data_path
from app.core.settings.bootstrap import logger
from app.core.settings.bots import ADMIN_BOT_TOKEN, BOT_TOKEN
from app.core.settings.external import MARZBAN_PASSWORD
from app.core.settings.persistence import DATABASE_URL

# ===========================================
# ADMIN PANEL SECURITY SETTINGS
# ===========================================
# Set your admin password in .env file as ADMIN_PANEL_PASSWORD
# The password will be hashed and verified securely
ADMIN_PANEL_PASSWORD_HASH = os.environ.get("ADMIN_PANEL_PASSWORD_HASH", None)
ADMIN_PANEL_SECRET_KEY = os.environ.get("ADMIN_PANEL_SECRET_KEY", secrets.token_hex(32))

# ===========================================
# WEBAPP SESSION SETTINGS
# ===========================================
# Security note:
# - Telegram WebApp `init_data` MUST be verified using BOT_TOKEN (per Telegram spec).
# - Our own session cookies/tokens SHOULD be signed with a dedicated secret, not the bot token.
# Set WEBAPP_SESSION_SECRET in .env for stable sessions across restarts.
_WEBAPP_SESSION_SECRET_RAW = os.environ.get("WEBAPP_SESSION_SECRET", "") or ""
WEBAPP_SESSION_SECRET_EXPLICIT = bool(_WEBAPP_SESSION_SECRET_RAW.strip())
WEBAPP_SESSION_SECRET = _WEBAPP_SESSION_SECRET_RAW if WEBAPP_SESSION_SECRET_EXPLICIT else ADMIN_PANEL_SECRET_KEY

# Rate limiting for login attempts
ADMIN_LOGIN_MAX_ATTEMPTS = 5
ADMIN_LOGIN_LOCKOUT_MINUTES = 15

# Session settings
ADMIN_SESSION_EXPIRY_HOURS = 24

# 2FA via Telegram (optional but recommended)
ADMIN_2FA_ENABLED = os.environ.get("ADMIN_2FA_ENABLED", "true").lower() == "true"

# Trust proxy headers like X-Forwarded-For (set to true only behind a trusted proxy)
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true"

# Admin IP whitelist storage (used by admin-only access control)
ADMIN_IP_WHITELIST_PATH = data_path("admin_ip_whitelist.json")

# ===========================================
# ADMIN SURFACE HOST GATE
# ===========================================
# The whole aiohttp process serves every vhost (arcade game1.*, dashboard dash.*).
# Without a gate, /admin and /api/admin answer on ALL of them — so a user who
# knows the public game domain can find the admin login there. We restrict the
# admin surface to a dedicated host; everywhere else it 404s as if it never
# existed. Derives its default from the dashboard URL's host so a normal deploy
# needs no extra config; override with a comma list via ADMIN_ALLOWED_HOSTS.
def _default_admin_hosts() -> str:
    try:
        from urllib.parse import urlparse

        from app.core.settings.web_game import DASHBOARD_PUBLIC_BASE_URL

        host = urlparse(DASHBOARD_PUBLIC_BASE_URL).hostname or ""
    except Exception:
        host = ""
    return host or "dash.astrobytech.com"


_admin_hosts_raw = os.environ.get("ADMIN_ALLOWED_HOSTS", "") or _default_admin_hosts()
# Loopback always allowed so internal health probes / local tooling keep working.
ADMIN_ALLOWED_HOSTS = {
    h.strip().lower()
    for h in (_admin_hosts_raw.split(",") + ["127.0.0.1", "localhost"])
    if h.strip()
}


def is_admin_host_allowed(host_header: str) -> bool:
    """True if the request's Host may reach the admin surface. Host-only match
    (port stripped); loopback with any port is allowed for internal access."""
    if not ADMIN_ALLOWED_HOSTS:
        return True  # unset → don't lock anyone out (fail-open on misconfig)
    host = (host_header or "").split(":")[0].strip().lower()
    if not host:
        return False
    if host in ADMIN_ALLOWED_HOSTS:
        return True
    return host in {"127.0.0.1", "localhost", "::1"}


def is_sha256_hash(hash_string: str) -> bool:
    """Check if a hash is SHA-256 format (64 hex characters)"""
    return len(hash_string) == 64 and all(c in "0123456789abcdef" for c in hash_string.lower())


def is_argon2_hash(hash_string: str) -> bool:
    """Check if a hash is Argon2 format"""
    return hash_string.startswith("$argon2")


def hash_admin_password_sha256(password: str) -> str:
    """Legacy SHA-256 hash function for backwards compatibility"""
    salt = ADMIN_PANEL_SECRET_KEY[:16]
    return hashlib.sha256((salt + password + salt).encode()).hexdigest()


def hash_admin_password(password: str) -> str:
    """Hash password with Argon2 for storage (modern secure method)"""
    return argon2.hash(password)


def verify_admin_password(password: str, stored_hash: str) -> bool:
    """
    Verify password against stored hash.
    Supports both Argon2 (new) and SHA-256 (legacy) hashes for backwards compatibility.
    """
    if not stored_hash:
        return False

    # Check if it's an Argon2 hash (starts with $argon2)
    if is_argon2_hash(stored_hash):
        try:
            return argon2.verify(password, stored_hash)
        except Exception:
            return False

    # Check if it's a SHA-256 hash (64 hex characters) - legacy support
    if is_sha256_hash(stored_hash):
        legacy_hash = hash_admin_password_sha256(password)
        return legacy_hash == stored_hash

    return False


def needs_password_migration(stored_hash: str) -> bool:
    """Check if a password hash needs migration from SHA-256 to Argon2"""
    return bool(stored_hash and is_sha256_hash(stored_hash))


def generate_password_hash(password: str) -> str:
    """Generate hash for a new password - use this to create ADMIN_PANEL_PASSWORD_HASH"""
    return hash_admin_password(password)


def get_missing_critical_settings(
    *,
    require_user_bot_token: bool = True,
    require_admin_bot_token: bool = False,
    require_webapp_secrets: bool = True,
) -> list[str]:
    """
    Return a list of missing/misconfigured *critical* settings.

    IMPORTANT:
    - Never include secret values in these messages.
    - Keep checks strict but practical for production.
    """
    missing: list[str] = []

    if require_user_bot_token and not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if require_admin_bot_token and not ADMIN_BOT_TOKEN:
        missing.append("ADMIN_BOT_TOKEN")

    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    else:
        # Project requirement: Postgres-only (no SQLite in prod).
        if not str(DATABASE_URL).startswith("postgresql+asyncpg://"):
            missing.append("DATABASE_URL (must start with postgresql+asyncpg://)")

    if require_webapp_secrets:
        # Admin panel must be protected by a real password hash
        if not ADMIN_PANEL_PASSWORD_HASH:
            missing.append("ADMIN_PANEL_PASSWORD_HASH")

        # Dashboard/WebApp sessions must be signed with a dedicated secret (not BOT_TOKEN).
        if not WEBAPP_SESSION_SECRET_EXPLICIT:
            missing.append("WEBAPP_SESSION_SECRET")

    return missing


def security_sanity_warnings() -> None:
    """
    Log high-signal warnings for missing critical secrets/config.
    (Never log the secret values.)
    """
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not set. The bot cannot start.")
    if BOT_TOKEN and not ADMIN_BOT_TOKEN:
        logger.info(
            "ADMIN_BOT_TOKEN is not set. Admin panel bot is disabled "
            "(recommended to run separately for max security)."
        )
    if not DATABASE_URL:
        logger.critical("DATABASE_URL is not set. Database access will fail.")
    if not MARZBAN_PASSWORD:
        logger.warning("MARZBAN_PASSWORD is not set. Marzban API calls will fail.")
    if not WEBAPP_SESSION_SECRET_EXPLICIT:
        logger.warning(
            "WEBAPP_SESSION_SECRET is not explicitly set. Set it in .env for stable WebApp sessions."
        )
