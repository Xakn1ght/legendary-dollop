import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import parse_qsl


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> bool:
    """Verify Telegram WebApp initData following the official spec.

    Args:
        init_data: The exact string from `Telegram.WebApp.initData`
        bot_token: Your bot token
        max_age_seconds: Reject initData older than this (replay protection).
            Note: Some Telegram clients reuse initData for a while, so this should not be too small.
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.pop("hash", None)
        if not received_hash:
            return False

        # Replay protection: auth_date must be recent
        # Telegram includes `auth_date` (unix seconds) in initData.
        if max_age_seconds is not None:
            try:
                auth_date = int(params.get("auth_date", "0") or 0)
                now = int(time.time())
                if auth_date <= 0:
                    return False
                if now - auth_date > int(max_age_seconds):
                    return False
            except Exception:
                return False

        # Build data_check_string: keys alphabetically sorted, joined by \n
        data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(params.items())])

        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(received_hash, calculated_hash)
    except Exception:
        return False



# -----------------------------
# Lightweight session token for WebApp
# -----------------------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_session_token(user_id: int, secret: str, ttl_seconds: int = 86400, jti: str | None = None) -> str:
    """Create an HMAC signed session token for the WebApp.

    Format: base64url(json_payload).hex_hmac_sha256_signature
    Where payload = {"uid": user_id, "iat": now, "exp": now+ttl}
    """
    now = int(time.time())
    payload = {"uid": int(user_id), "iat": now, "exp": now + int(ttl_seconds)}
    if jti:
        payload["jti"] = str(jti)
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    payload_b64 = _b64url(payload_bytes)
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str, secret: str) -> int:
    """Verify the session token and return user_id if valid, else 0."""
    try:
        payload_b64, sig_hex = token.split(".", 1)
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig_hex):
            return 0
        payload = json.loads(_b64url_decode(payload_b64))
        exp = int(payload.get("exp", 0))
        if int(time.time()) > exp:
            return 0
        uid = int(payload.get("uid", 0) or 0)
        return uid
    except Exception:
        return 0


# -----------------------------
# One-time query tokens (short-lived with small reuse grace)
# -----------------------------

_USED_ONE_TIME: dict[str, tuple[int, int]] = {}  # jti -> (first_seen_ts, exp_ts)
_ONE_TIME_GRACE_SECONDS = 60


def create_one_time_token(user_id: int, secret: str, ttl_seconds: int = 900) -> str:
    """Create a short-lived one-time token for URL auth."""
    jti = secrets.token_urlsafe(16)
    return create_session_token(user_id, secret, ttl_seconds=ttl_seconds, jti=jti)


def _cleanup_one_time(now: int) -> None:
    to_delete = []
    for jti, (first_seen, exp) in _USED_ONE_TIME.items():
        if now > exp or (now - first_seen) > _ONE_TIME_GRACE_SECONDS:
            to_delete.append(jti)
    for jti in to_delete:
        _USED_ONE_TIME.pop(jti, None)


def verify_one_time_token(token: str, secret: str) -> int:
    """Verify a one-time token with a small reuse grace window."""
    try:
        payload_b64, sig_hex = token.split(".", 1)
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig_hex):
            return 0
        payload = json.loads(_b64url_decode(payload_b64))
        exp = int(payload.get("exp", 0))
        if int(time.time()) > exp:
            return 0
        uid = int(payload.get("uid", 0) or 0)
        jti = str(payload.get("jti") or "").strip()
        if not uid or not jti:
            return 0

        now = int(time.time())
        _cleanup_one_time(now)
        if jti in _USED_ONE_TIME:
            first_seen, _exp = _USED_ONE_TIME[jti]
            if (now - first_seen) > _ONE_TIME_GRACE_SECONDS:
                return 0
        else:
            _USED_ONE_TIME[jti] = (now, exp)
        return uid
    except Exception:
        return 0
