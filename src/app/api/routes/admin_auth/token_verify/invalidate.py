"""Remove token from in-memory session cache."""

from ..state import _active_sessions


def invalidate_session(token: str):
    """Invalidate/logout a session"""
    if token in _active_sessions:
        del _active_sessions[token]
