"""Iran-local (Asia/Tehran, UTC+3:30) day boundaries for the arcade.

The player base is Iranian, so the daily mission and the monthly race reset
at IRAN midnight, not server/UTC midnight. Iran abolished DST in 2022, so a
fixed offset is correct (and avoids a tzdata dependency).
"""
from datetime import date, datetime, timedelta, timezone

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def tehran_now() -> datetime:
    """Current Tehran wall-clock time as a naive datetime (matches the
    naive-datetime convention used across the codebase)."""
    return datetime.now(TEHRAN_TZ).replace(tzinfo=None)


def tehran_today() -> date:
    return datetime.now(TEHRAN_TZ).date()
