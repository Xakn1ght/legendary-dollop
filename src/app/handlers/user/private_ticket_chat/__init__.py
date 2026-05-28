"""Private support ticket live chat; submodules register handlers on the shared `router`."""

# Registration order matches the legacy monolith.
from . import (
    common,  # noqa: F401
    forwarding,  # noqa: F401
    invitations,  # noqa: F401
    messages,  # noqa: F401
    session_end,  # noqa: F401
)
from .common import PrivateChatStates, router
from .forwarding import forward_message_between_chats

__all__ = ("PrivateChatStates", "forward_message_between_chats", "router")
