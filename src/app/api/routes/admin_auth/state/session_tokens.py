import base64
import hashlib
import secrets
import time

from app.core.settings import ADMIN_ID, ADMIN_PANEL_SECRET_KEY


def _create_persistent_token(chat_id: int, session_id: str, timestamp: int | None = None) -> tuple[str, int]:
    ts = int(timestamp or time.time())
    data = f"{chat_id}:{ts}:{session_id}"
    signature = hashlib.sha256((data + ADMIN_PANEL_SECRET_KEY).encode()).hexdigest()[:32]
    token_data = f"{chat_id}:{ts}:{session_id}:{signature}"
    return base64.urlsafe_b64encode(token_data.encode()).decode(), ts


def _verify_persistent_token(token: str, max_age_hours: int = 24) -> tuple[int, int, str] | None:
    try:
        token_data = base64.urlsafe_b64decode(token.encode()).decode()
        parts = token_data.split(":")
        if len(parts) != 4:
            return None

        chat_id = int(parts[0])
        timestamp = int(parts[1])
        session_id = str(parts[2])
        signature = parts[3]

        data = f"{chat_id}:{timestamp}:{session_id}"
        expected_sig = hashlib.sha256((data + ADMIN_PANEL_SECRET_KEY).encode()).hexdigest()[:32]
        if signature != expected_sig:
            return None

        age_seconds = time.time() - timestamp
        if age_seconds > max_age_hours * 3600:
            return None

        if chat_id != ADMIN_ID:
            return None

        return chat_id, timestamp, session_id
    except Exception:
        return None


def _generate_session_token() -> str:
    return secrets.token_urlsafe(64)


def _generate_2fa_code() -> str:
    return str(secrets.randbelow(900000) + 100000)
