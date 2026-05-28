import json
import os

from app.core.paths import data_path

from .runtime import _active_sessions

_ADMIN_SESSION_STATE_PATH = data_path("admin_session_state.json")
_admin_session_state: dict = {"last_login_ts_by_chat_id": {}}

_ADMIN_SESSIONS_PATH = data_path("admin_sessions.json")
_admin_sessions: dict = {"sessions": {}}
_last_seen_write_ts: dict[str, int] = {}


def _load_admin_session_state() -> None:
    try:
        if not os.path.exists(_ADMIN_SESSION_STATE_PATH):
            return
        with open(_ADMIN_SESSION_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            ll = data.get("last_login_ts_by_chat_id")
            if isinstance(ll, dict):
                _admin_session_state["last_login_ts_by_chat_id"] = ll
    except Exception:
        return


def _save_admin_session_state() -> None:
    try:
        os.makedirs(os.path.dirname(_ADMIN_SESSION_STATE_PATH), exist_ok=True)
        with open(_ADMIN_SESSION_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(_admin_session_state, f)
    except Exception:
        return


def _load_admin_sessions() -> None:
    try:
        if not os.path.exists(_ADMIN_SESSIONS_PATH):
            return
        with open(_ADMIN_SESSIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict) and isinstance(data.get("sessions"), dict):
            _admin_sessions["sessions"] = data["sessions"]
    except Exception:
        return


def _save_admin_sessions() -> None:
    try:
        os.makedirs(os.path.dirname(_ADMIN_SESSIONS_PATH), exist_ok=True)
        with open(_ADMIN_SESSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(_admin_sessions, f)
    except Exception:
        return


def _get_last_login_ts(chat_id: int) -> int:
    try:
        v = _admin_session_state.get("last_login_ts_by_chat_id", {}).get(str(chat_id), 0)
        return int(v) if v else 0
    except Exception:
        return 0


def _set_last_login_ts(chat_id: int, ts: int) -> None:
    try:
        _admin_session_state.setdefault("last_login_ts_by_chat_id", {})[str(chat_id)] = int(ts)
        _save_admin_session_state()
    except Exception:
        return


def _invalidate_all_sessions_for_chat(chat_id: int) -> None:
    try:
        to_delete = [tok for tok, s in _active_sessions.items() if s.get("chat_id") == chat_id]
        for tok in to_delete:
            _active_sessions.pop(tok, None)
    except Exception:
        return


_load_admin_session_state()
_load_admin_sessions()
