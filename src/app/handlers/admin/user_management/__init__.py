"""Admin Telegram user management (search, credits, subscriptions, moderation, etc.).

The admin bot loads this via a thin re-export:
``app.admin_bot.handlers.user_management`` → same ``router`` instance as here.
"""

# Registration order matters: aiogram consumes an update at the first matching
# handler. admin_debug holds two catch-all `from_user.id in ADMIN_IDS` message
# handlers — they MUST register LAST or they swallow every admin text message
# (user search, credit/traffic edits, category flows, broadcast text, /endchat,
# chat relays all die). The old comment claimed "placed at the end"; it wasn't.
from . import (  # isort: skip  — order matters, see below
    categories,  # noqa: F401
    credit_lists,  # noqa: F401
    menu_search,  # noqa: F401
    moderation,  # noqa: F401
    subscriptions,  # noqa: F401
    user_detail,  # noqa: F401
)
from . import admin_debug  # noqa: F401,E402  — MUST be last: catch-all handlers
from .common import IsUserInAdminChat, UserManagementStates, router

__all__ = ["router", "UserManagementStates", "IsUserInAdminChat"]
