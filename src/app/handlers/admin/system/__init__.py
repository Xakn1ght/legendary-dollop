"""Admin system power commands (/errors, /health, /run_renewal, /renewal_preview).

The system menu and its log/backup/monitoring screens were retired 2026-07-21;
the admin panel covers them.
"""

from . import commands  # noqa: F401
from .common import router

__all__ = ["router"]
