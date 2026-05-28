"""User-facing support / ticketing; submodules register on the shared `router`."""

# Order matches the legacy monolithic module.
from . import (
    common,  # noqa: F401
    entry,  # noqa: F401
    flow,  # noqa: F401
    legacy_editing,  # noqa: F401
    routing,  # noqa: F401
    tickets,  # noqa: F401
)
from .common import SupportStates, router

__all__ = ("SupportStates", "router")
