"""Support UX, jobs, renewal thresholds, plans ordering; loads optional JSON from ``app/core/``."""

import json

from app.core.settings.bootstrap import CORE_DIR

# -----------------------------
# Renewal Settings (Thresholds)
# -----------------------------
RENEWAL_TIME_SKIP_DAYS = 3
RENEWAL_TRAFFIC_SKIP_PERCENT = 15
RENEWAL_ADDED_DAYS = 30
RENEWAL_MIN_ROLLOVER_GB = 0.1
RENEWAL_MAX_ROLLOVER_GB = 5.0

# -----------------------------
# Support System Settings
# -----------------------------
SUPPORT_CATEGORIES = {
    "support_quick_connection": "مشکل اتصال 🔌",
    "support_quick_money": "مشکل مالی 💰",
    "support_quick_other": "سوال عمومی ❓",
}

ISPS = [
    "MCI (همراه اول)",
    "Irancell (ایرانسل)",
    "Rightel (رایتل)",
    "ADSL/VDSL (اینترنت خانگی)",
    "TD-LTE",
    "Other (سایر)",
]

TROUBLESHOOTER_STEPS = [
    "آیا نرم‌افزار شما به آخرین نسخه آپدیت شده است؟",
    "آیا از لینک اشتراک جدید استفاده می‌کنید؟",
    "آیا ساعت گوشی شما تنظیم است؟",
    "آیا با اینترنت دیگری تست کرده‌اید؟",
]

SUPPORT_AVG_HANDLE_MINUTES = 15
SUPPORT_TICKET_REMINDER_HOURS = 24
SUPPORT_TICKET_AUTOCLOSE_DAYS = 3

MAX_TICKET_TEXTS = 5
MAX_TICKET_IMAGES = 3

# Job Schedules (overrideable)
JOB_SCHEDULES = {
    # Low-data warnings are throttled to once/day per sub anyway — sweeping every 15s
    # only hammered the Marzban panel (one API call per active sub per tick). 10 min
    # is still far more responsive than a daily notification needs.
    "check_low_data_job": {"type": "interval", "minutes": 10},
    # Auto-renew should feel "instant"; 60s + the 90s marzban info cache keeps worst-case
    # renewal lag ~2-3 min while cutting panel sweeps 4x. Override via job_schedules.json.
    "renewal_job": {"type": "interval", "seconds": 60, "max_instances": 1, "coalesce": True},
    "update_user_analytics_job": {"type": "interval", "hours": 1},
    "expire_claims_job": {"type": "interval", "minutes": 15},
    "reminder_unclaimed_star_rewards_job": {"type": "interval", "hours": 12},
    "cleanup_draft_orders_job": {"type": "interval", "minutes": 10},
    "season_reset_job": {"type": "interval", "hours": 12},  # rotate season + expire coupons
}

_job_schedules_path = str(CORE_DIR / "job_schedules.json")
if CORE_DIR.joinpath("job_schedules.json").exists():
    try:
        with open(_job_schedules_path, "r", encoding="utf-8") as _f:
            _loaded = json.load(_f)
            if isinstance(_loaded, dict):
                JOB_SCHEDULES.update(_loaded)
    except Exception:
        pass


def save_job_schedules():
    try:
        with open(_job_schedules_path, "w", encoding="utf-8") as f:
            json.dump(JOB_SCHEDULES, f, indent=2)
    except Exception:
        pass


# Plans Order
PLANS_ORDER_FILE = str(CORE_DIR / "plans_order.json")


def get_plans_order():
    if CORE_DIR.joinpath("plans_order.json").exists():
        try:
            with open(PLANS_ORDER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_plans_order(order_list):
    try:
        with open(PLANS_ORDER_FILE, "w", encoding="utf-8") as f:
            json.dump(order_list, f)
    except Exception:
        pass


# Support Settings Override
SUPPORT_SETTINGS_FILE = str(CORE_DIR / "support_settings.json")


def load_support_settings():
    global SUPPORT_CATEGORIES, ISPS, TROUBLESHOOTER_STEPS
    global SUPPORT_TICKET_REMINDER_HOURS, SUPPORT_TICKET_AUTOCLOSE_DAYS, SUPPORT_AVG_HANDLE_MINUTES
    if CORE_DIR.joinpath("support_settings.json").exists():
        try:
            with open(SUPPORT_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "categories" in data:
                    SUPPORT_CATEGORIES = data["categories"]
                if "isps" in data:
                    ISPS = data["isps"]
                if "troubleshooter_steps" in data:
                    TROUBLESHOOTER_STEPS = data["troubleshooter_steps"]
                if "ticket_reminder_hours" in data:
                    SUPPORT_TICKET_REMINDER_HOURS = int(data["ticket_reminder_hours"])
                if "ticket_autoclose_days" in data:
                    SUPPORT_TICKET_AUTOCLOSE_DAYS = int(data["ticket_autoclose_days"])
                if "ticket_avg_handle_minutes" in data:
                    SUPPORT_AVG_HANDLE_MINUTES = int(data["ticket_avg_handle_minutes"])
        except Exception:
            pass


def save_support_settings(
    *,
    reminder_hours: int | None = None,
    autoclose_days: int | None = None,
    avg_handle_minutes: int | None = None,
):
    global SUPPORT_TICKET_REMINDER_HOURS, SUPPORT_TICKET_AUTOCLOSE_DAYS, SUPPORT_AVG_HANDLE_MINUTES
    if reminder_hours is not None:
        SUPPORT_TICKET_REMINDER_HOURS = reminder_hours
    if autoclose_days is not None:
        SUPPORT_TICKET_AUTOCLOSE_DAYS = autoclose_days
    if avg_handle_minutes is not None:
        SUPPORT_AVG_HANDLE_MINUTES = avg_handle_minutes

    data = {
        "categories": SUPPORT_CATEGORIES,
        "isps": ISPS,
        "troubleshooter_steps": TROUBLESHOOTER_STEPS,
        "ticket_reminder_hours": SUPPORT_TICKET_REMINDER_HOURS,
        "ticket_autoclose_days": SUPPORT_TICKET_AUTOCLOSE_DAYS,
        "ticket_avg_handle_minutes": SUPPORT_AVG_HANDLE_MINUTES,
    }
    try:
        with open(SUPPORT_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


load_support_settings()
