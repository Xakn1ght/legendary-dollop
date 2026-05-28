"""In-memory login/sessions maps (ephemeral)."""

from collections import defaultdict

_login_attempts = defaultdict(list)
_active_sessions: dict = {}
_pending_2fa: dict = {}
