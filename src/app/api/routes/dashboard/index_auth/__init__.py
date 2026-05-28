from .index_page import handle_dashboard_index
from .referral_signup import handle_dashboard_submit_referral
from .webapp_login import handle_dashboard_login

__all__ = [
    "handle_dashboard_index",
    "handle_dashboard_login",
    "handle_dashboard_submit_referral",
]
