import secrets
from datetime import datetime, timedelta

from app.core.settings import ADMIN_SESSION_EXPIRY_HOURS

from .cookies import _generate_csrf_token
from .persistence import _admin_sessions, _save_admin_sessions
from .runtime import _active_sessions
from .session_tokens import _create_persistent_token
from .user_agent import _ua_short


def _create_session(chat_id: int, ip: str, user_agent: str) -> dict:
    """Create a new admin session (multi-session)."""
    session_id = secrets.token_urlsafe(18)
    token, issued_ts = _create_persistent_token(chat_id, session_id)
    expires = datetime.utcnow() + timedelta(hours=ADMIN_SESSION_EXPIRY_HOURS)
    now_iso = datetime.utcnow().isoformat()

    sess = {
        "session_id": session_id,
        "chat_id": chat_id,
        "ip": ip,
        "user_agent": _ua_short(user_agent),
        "issued_ts": int(issued_ts),
        "created_at": now_iso,
        "last_seen_at": now_iso,
        "expires_at": expires.isoformat(),
        "csrf_token": _generate_csrf_token(),
        "revoked": False,
        "revoked_at": None,
    }

    _admin_sessions.setdefault("sessions", {})[session_id] = sess
    _save_admin_sessions()

    session_data = dict(sess)
    session_data["token"] = token
    _active_sessions[token] = session_data
    return session_data
