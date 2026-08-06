"""Admin financial handlers — cash-out approvals only.

The financial menus (revenue/analysis/transactions) were retired 2026-07-21;
the admin panel's ops/analytics pages replaced them. Cash-out payout cards and
the receipt-photo handler stay on the bot.
"""

from . import cashout  # noqa: F401
from .common import router

__all__ = ["router"]
