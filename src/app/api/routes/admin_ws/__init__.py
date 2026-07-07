# app/api/routes/admin_ws
"""
Support WebSocket Handler
- Real-time message updates for admin AND user support chat
- Safe: If this fails, frontend falls back to polling
- Minimal: Only handles message broadcasting, nothing else
- Enhanced: Better connection health monitoring and error handling
"""

from app.api.routes.admin_ws.admin_support import handle_admin_support_ws
from app.api.routes.admin_ws.broadcasts import (
    broadcast_admin_event,
    broadcast_ticket_list_update,
    broadcast_ticket_update,
    broadcast_typing,
    broadcast_user_ticket_list_update,
)
from app.api.routes.admin_ws.presence import (
    is_user_connected_to_support,
    is_user_watching_ticket,
)
from app.api.routes.admin_ws.user_support import handle_user_support_ws

__all__ = [
    "broadcast_admin_event",
    "broadcast_ticket_list_update",
    "broadcast_ticket_update",
    "broadcast_typing",
    "broadcast_user_ticket_list_update",
    "handle_admin_support_ws",
    "handle_user_support_ws",
    "is_user_connected_to_support",
    "is_user_watching_ticket",
]
