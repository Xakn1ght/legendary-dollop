"""Dashboard support tickets API (split from former routes/dashboard_tickets.py)."""

from app.api.routes.dashboard_tickets.detail_ops import (
    handle_dashboard_tickets_delete,
    handle_dashboard_tickets_detail,
    handle_dashboard_tickets_reply,
)
from app.api.routes.dashboard_tickets.list_create import (
    handle_dashboard_tickets_create,
    handle_dashboard_tickets_list,
)

__all__ = [
    "handle_dashboard_tickets_create",
    "handle_dashboard_tickets_delete",
    "handle_dashboard_tickets_detail",
    "handle_dashboard_tickets_list",
    "handle_dashboard_tickets_reply",
]
