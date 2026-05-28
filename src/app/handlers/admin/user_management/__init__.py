"""Admin Telegram user management (search, credits, subscriptions, moderation, etc.).

The admin bot loads this via a thin re-export:
``app.admin_bot.handlers.user_management`` → same ``router`` instance as here.
"""

# Registration order matches the former monolith (overlapping filters depend on it).
from . import (
    admin_debug,  # noqa: F401
    categories,  # noqa: F401
    credit_lists,  # noqa: F401
    menu_search,  # noqa: F401
    moderation,  # noqa: F401
    subscriptions,  # noqa: F401
    user_detail,  # noqa: F401
)
from .common import IsUserInAdminChat, UserManagementStates, router

__all__ = ["router", "UserManagementStates", "IsUserInAdminChat"]
