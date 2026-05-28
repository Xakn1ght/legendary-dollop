"""Admin financial dashboard and reports (split from former ``financial.py``).

``app.admin_bot.handlers.financial`` re-exports :attr:`router` from here.
"""

# menu first (entry text handlers); remainder order is non-critical after revenue filter fix.
from . import (
    analysis,  # noqa: F401
    cashout,  # noqa: F401
    menu,  # noqa: F401
    revenue,  # noqa: F401
    transactions,  # noqa: F401
)
from .common import router

__all__ = ["router"]
