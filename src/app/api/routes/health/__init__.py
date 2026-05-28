"""
Health check endpoint for system monitoring and status checks.

This endpoint provides comprehensive health information about:
- Database connectivity
- Marzban API connectivity
- Redis cache availability
- Bot status
- Scheduler status
"""

from .handler import handle_health_check

__all__ = ["handle_health_check"]
