"""Persistent session state, cookies, rate limits, and session creation."""

import logging

from app.core.settings import ADMIN_ID, ADMIN_SESSION_EXPIRY_HOURS

logger = logging.getLogger(__name__)

from .cookies import (  # noqa: E402
    _ADMIN_CSRF_COOKIE,
    _ADMIN_CSRF_HEADER,
    _ADMIN_SESSION_COOKIE,
    _admin_cookie_attrs,
    _generate_csrf_token,
)
from .password import _migrate_password_hash  # noqa: E402
from .persistence import (  # noqa: E402
    _admin_session_state,
    _admin_sessions,
    _get_last_login_ts,
    _invalidate_all_sessions_for_chat,
    _last_seen_write_ts,
    _load_admin_session_state,
    _load_admin_sessions,
    _save_admin_session_state,
    _save_admin_sessions,
    _set_last_login_ts,
)
from .rate_limit import _get_client_ip, _is_rate_limited, _record_login_attempt  # noqa: E402
from .runtime import _active_sessions, _login_attempts, _pending_2fa  # noqa: E402
from .session import _create_session  # noqa: E402
from .session_tokens import (  # noqa: E402
    _create_persistent_token,
    _generate_2fa_code,
    _generate_session_token,
    _verify_persistent_token,
)
from .user_agent import _ua_short  # noqa: E402

__all__ = [
    "ADMIN_ID",
    "ADMIN_SESSION_EXPIRY_HOURS",
    "logger",
    "_ADMIN_CSRF_COOKIE",
    "_ADMIN_CSRF_HEADER",
    "_ADMIN_SESSION_COOKIE",
    "_active_sessions",
    "_admin_session_state",
    "_admin_sessions",
    "_create_persistent_token",
    "_create_session",
    "_generate_2fa_code",
    "_generate_csrf_token",
    "_generate_session_token",
    "_get_client_ip",
    "_get_last_login_ts",
    "_invalidate_all_sessions_for_chat",
    "_is_rate_limited",
    "_last_seen_write_ts",
    "_load_admin_session_state",
    "_load_admin_sessions",
    "_login_attempts",
    "_migrate_password_hash",
    "_pending_2fa",
    "_record_login_attempt",
    "_save_admin_session_state",
    "_save_admin_sessions",
    "_set_last_login_ts",
    "_ua_short",
    "_verify_persistent_token",
]
