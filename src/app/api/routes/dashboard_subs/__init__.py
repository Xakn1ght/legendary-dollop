"""Dashboard subscription API (split from former routes/dashboard_subs.py)."""

from app.api.routes.dashboard_subs.subscriptions import (
    handle_dashboard_add_sub,
    handle_dashboard_links,
    handle_dashboard_list_subs,
    handle_dashboard_overview,
    handle_dashboard_remove_local,
    handle_dashboard_revoke,
)
from app.api.routes.dashboard_subs.tools import (
    handle_dashboard_detect_country,
    handle_dashboard_flag,
    handle_dashboard_ping,
    handle_dashboard_speed_dl,
    handle_dashboard_speed_ul,
)

__all__ = [
    "handle_dashboard_add_sub",
    "handle_dashboard_detect_country",
    "handle_dashboard_flag",
    "handle_dashboard_links",
    "handle_dashboard_list_subs",
    "handle_dashboard_overview",
    "handle_dashboard_ping",
    "handle_dashboard_remove_local",
    "handle_dashboard_revoke",
    "handle_dashboard_speed_dl",
    "handle_dashboard_speed_ul",
]
