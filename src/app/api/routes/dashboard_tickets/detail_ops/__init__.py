from .delete import handle_dashboard_tickets_delete
from .detail import handle_dashboard_tickets_detail
from .photo import handle_dashboard_ticket_photo_get, handle_dashboard_ticket_photo_upload
from .reply import handle_dashboard_tickets_reply

__all__ = [
    "handle_dashboard_ticket_photo_get",
    "handle_dashboard_ticket_photo_upload",
    "handle_dashboard_tickets_delete",
    "handle_dashboard_tickets_detail",
    "handle_dashboard_tickets_reply",
]
