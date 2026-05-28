# app/api/routes/admin_auth
"""
Highly Secure Admin Authentication System

Security Features:
1. Password hashing with Argon2 (automatically migrates from SHA-256)
2. Rate limiting (5 attempts per 15 minutes)
3. Secure session tokens with expiration
4. Admin ID verification (must match ADMIN_ID)
5. Optional 2FA via Telegram bot
6. IP logging for security auditing
7. Automatic lockout after failed attempts
8. Backwards compatible with SHA-256 hashes (auto-upgrades to Argon2)
"""

from app.api.routes.admin_auth.login_handlers import (
    handle_admin_login,
    handle_admin_verify_2fa,
)
from app.api.routes.admin_auth.session_handlers import (
    _get_token_from_request,
    handle_admin_logout,
    handle_admin_session_revoke,
    handle_admin_sessions_list,
    handle_admin_sessions_revoke_others,
    handle_admin_verify_session,
    setup_admin_password,
)
from app.api.routes.admin_auth.token_verify import invalidate_session, verify_admin_token

__all__ = [
    "_get_token_from_request",
    "handle_admin_login",
    "handle_admin_logout",
    "handle_admin_session_revoke",
    "handle_admin_sessions_list",
    "handle_admin_sessions_revoke_others",
    "handle_admin_verify_2fa",
    "handle_admin_verify_session",
    "invalidate_session",
    "setup_admin_password",
    "verify_admin_token",
]
