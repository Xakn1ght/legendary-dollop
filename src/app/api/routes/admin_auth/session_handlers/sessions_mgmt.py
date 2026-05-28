"""Multi-device session list and revoke."""

from datetime import datetime

from aiohttp import web

from app.core.settings import ADMIN_ID

from .. import state as st
from ..token_verify import verify_admin_token
from .request_token import _get_token_from_request


async def handle_admin_sessions_list(request: web.Request):
    """List active admin sessions (multi-device)."""
    token = _get_token_from_request(request)
    session = verify_admin_token(token)
    if not session:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    current_sid = str(session.get("session_id") or "")
    sessions = []
    try:
        for sid, s in (st._admin_sessions.get("sessions") or {}).items():
            if not isinstance(s, dict):
                continue
            if int(s.get("chat_id") or 0) != int(ADMIN_ID):
                continue
            sessions.append(
                {
                    "session_id": sid,
                    "created_at": s.get("created_at"),
                    "last_seen_at": s.get("last_seen_at"),
                    "expires_at": s.get("expires_at"),
                    "ip": s.get("ip"),
                    "user_agent": s.get("user_agent"),
                    "revoked": bool(s.get("revoked")),
                    "revoked_at": s.get("revoked_at"),
                    "is_current": sid == current_sid,
                }
            )
    except Exception:
        sessions = []

    def _ts(v: str | None) -> float:
        try:
            return datetime.fromisoformat(str(v)).timestamp()
        except Exception:
            return 0.0

    sessions.sort(key=lambda x: _ts(x.get("last_seen_at")) or _ts(x.get("created_at")), reverse=True)
    return web.json_response({"ok": True, "sessions": sessions})


async def handle_admin_session_revoke(request: web.Request):
    """Revoke a specific session_id."""
    token = _get_token_from_request(request)
    session = verify_admin_token(token)
    if not session:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        data = {}
    sid = str((data or {}).get("session_id") or "").strip()
    if not sid:
        return web.json_response({"ok": False, "error": "missing_session_id"}, status=400)

    stored = st._admin_sessions.get("sessions", {}).get(sid)
    if not isinstance(stored, dict) or int(stored.get("chat_id") or 0) != int(ADMIN_ID):
        return web.json_response({"ok": False, "error": "not_found"}, status=404)

    if stored.get("revoked"):
        return web.json_response({"ok": True, "already": True})

    stored["revoked"] = True
    stored["revoked_at"] = datetime.utcnow().isoformat()
    st._save_admin_sessions()

    try:
        to_drop = [tok for tok, s in st._active_sessions.items() if str(s.get("session_id") or "") == sid]
        for tok in to_drop:
            st._active_sessions.pop(tok, None)
    except Exception:
        pass

    return web.json_response({"ok": True})


async def handle_admin_sessions_revoke_others(request: web.Request):
    """Revoke all sessions except the current one."""
    token = _get_token_from_request(request)
    session = verify_admin_token(token)
    if not session:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    current_sid = str(session.get("session_id") or "")
    count = 0
    try:
        for sid, s in (st._admin_sessions.get("sessions") or {}).items():
            if not isinstance(s, dict):
                continue
            if int(s.get("chat_id") or 0) != int(ADMIN_ID):
                continue
            if sid == current_sid:
                continue
            if s.get("revoked"):
                continue
            s["revoked"] = True
            s["revoked_at"] = datetime.utcnow().isoformat()
            count += 1
        st._save_admin_sessions()
    except Exception:
        pass

    try:
        to_drop = [tok for tok, s in st._active_sessions.items() if str(s.get("session_id") or "") != current_sid]
        for tok in to_drop:
            st._active_sessions.pop(tok, None)
    except Exception:
        pass

    return web.json_response({"ok": True, "revoked": count})
