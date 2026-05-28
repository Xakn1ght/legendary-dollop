"""Admin session token verification."""

import time
from datetime import datetime

from ..state import (
    ADMIN_SESSION_EXPIRY_HOURS,
    _active_sessions,
    _admin_sessions,
    _generate_csrf_token,
    _last_seen_write_ts,
    _save_admin_sessions,
    _verify_persistent_token,
    logger,
)


def verify_admin_token(token: str) -> dict | None:
    """Verify an admin session token. Returns session data or None"""
    if not token:
        return None

    def _ensure_csrf(stored_session: dict | None) -> str | None:
        """Ensure a stored session has a csrf_token; persist if we need to add one."""
        if not isinstance(stored_session, dict):
            return None
        if stored_session.get("csrf_token"):
            return str(stored_session.get("csrf_token"))
        try:
            stored_session["csrf_token"] = _generate_csrf_token()
            _save_admin_sessions()
            return str(stored_session.get("csrf_token"))
        except Exception:
            return None

    session = _active_sessions.get(token)
    if session:
        try:
            sid = session.get("session_id")
            if sid:
                stored = _admin_sessions.get("sessions", {}).get(str(sid))
                if stored and stored.get("revoked"):
                    _active_sessions.pop(token, None)
                    return None
        except Exception:
            pass
        expires = datetime.fromisoformat(session["expires_at"])
        if datetime.utcnow() > expires:
            del _active_sessions[token]
            return None
        try:
            sid = str(session.get("session_id") or "")
            stored = _admin_sessions.get("sessions", {}).get(sid) if sid else None
            csrf = _ensure_csrf(stored)
            if csrf:
                session["csrf_token"] = csrf
        except Exception:
            pass
        try:
            sid = str(session.get("session_id") or "")
            if sid:
                now = int(time.time())
                last_write = int(_last_seen_write_ts.get(sid, 0))
                if now - last_write >= 30:
                    _last_seen_write_ts[sid] = now
                    stored = _admin_sessions.get("sessions", {}).get(sid)
                    if isinstance(stored, dict) and not stored.get("revoked"):
                        stored["last_seen_at"] = datetime.utcnow().isoformat()
                        _save_admin_sessions()
        except Exception:
            pass
        return session

    verified = _verify_persistent_token(token, max_age_hours=ADMIN_SESSION_EXPIRY_HOURS)
    if verified:
        chat_id, issued_ts, session_id = verified
        stored = _admin_sessions.get("sessions", {}).get(str(session_id))
        if not isinstance(stored, dict):
            return None
        if stored.get("revoked"):
            return None
        if int(stored.get("chat_id") or 0) != int(chat_id):
            return None
        try:
            expires = datetime.fromisoformat(str(stored.get("expires_at")))
            if datetime.utcnow() > expires:
                return None
        except Exception:
            return None

        logger.info(f"[ADMIN AUTH] Restored session from persistent token for chat_id {chat_id}")
        try:
            _ensure_csrf(stored)
        except Exception:
            pass
        session_data = dict(stored)
        session_data["issued_ts"] = int(issued_ts)
        session_data["token"] = token
        _active_sessions[token] = session_data
        try:
            now = int(time.time())
            last_write = int(_last_seen_write_ts.get(str(session_id), 0))
            if now - last_write >= 30:
                _last_seen_write_ts[str(session_id)] = now
                stored["last_seen_at"] = datetime.utcnow().isoformat()
                _save_admin_sessions()
        except Exception:
            pass
        return session_data

    return None
