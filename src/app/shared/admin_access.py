from app.core.settings import ADMIN_ID, ADMIN_USERNAME

ADMIN_IDS: list[int] = [int(ADMIN_ID or 0)]


def is_admin_user(tg_user) -> bool:
    """Return True if the Telegram user matches admin id/username."""
    try:
        if getattr(tg_user, "id", None) in ADMIN_IDS:
            return True
        uname = (getattr(tg_user, "username", None) or "").lower().lstrip("@")
        if ADMIN_USERNAME and uname and uname == str(ADMIN_USERNAME).lower().lstrip("@"):
            return True
    except Exception:
        pass
    return False


def get_admin_broadcast_ids() -> list[int]:
    return ADMIN_IDS

