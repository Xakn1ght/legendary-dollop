"""Admin support ticket handlers (package split of the former ``support.py`` monolith).

``app.admin_bot.handlers.support`` re-exports :attr:`router` and :class:`AdminSupportStates`
from here so the isolated admin bot and this tree share one implementation.
"""

from . import (
    canned,  # noqa: F401
    extras,  # noqa: F401
    lists,  # noqa: F401
    menu,  # noqa: F401
    reply,  # noqa: F401
    ticket_detail,  # noqa: F401
)
from .common import AdminSupportStates, router

__all__ = ["router", "AdminSupportStates"]
