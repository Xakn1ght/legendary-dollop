"""Aggregated health check HTTP response."""

import asyncio
import time
from datetime import datetime

from aiohttp import web

from .checks import (
    check_bot_health,
    check_database_health,
    check_pasarguard_health,
    check_redis_health,
    check_scheduler_health,
)


async def handle_health_check(request: web.Request) -> web.Response:
    """
    Main health check endpoint handler.

    Returns comprehensive system health information.
    """
    start_time = time.time()

    # Run all health checks concurrently
    database_check, pasarguard_check, redis_check, bot_check, scheduler_check = await asyncio.gather(
        check_database_health(),
        check_pasarguard_health(),
        check_redis_health(),
        check_bot_health(request),
        check_scheduler_health(request),
        return_exceptions=True
    )

    # Handle any exceptions from gather
    def process_check(check_result, default_status="error"):
        if isinstance(check_result, Exception):
            return {
                "status": default_status,
                "error": str(check_result)
            }
        return check_result

    database_check = process_check(database_check)
    pasarguard_check = process_check(pasarguard_check)
    redis_check = process_check(redis_check, "unavailable")
    bot_check = process_check(bot_check)
    scheduler_check = process_check(scheduler_check)

    # Determine overall system status
    critical_services = [database_check, pasarguard_check, bot_check]
    optional_services = [redis_check, scheduler_check]

    overall_status = "healthy"

    # Check critical services
    for service in critical_services:
        if service.get("status") in ["error", "unavailable", "timeout"]:
            overall_status = "unhealthy"
            break
        elif service.get("status") in ["degraded", "stopped"]:
            overall_status = "degraded"

    # Check optional services (only degrade, don't mark as unhealthy)
    if overall_status == "healthy":
        for service in optional_services:
            if service.get("status") in ["error", "unavailable", "stopped"]:
                overall_status = "degraded"
                break

    # Build response
    response_data = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {
            "database": database_check,
            "pasarguard": pasarguard_check,
            "redis": redis_check,
            "bot": bot_check,
            "scheduler": scheduler_check
        },
        "version": "1.0.0",
        "response_time_ms": round((time.time() - start_time) * 1000, 2)
    }

    # Set HTTP status code based on health
    http_status = 200 if overall_status == "healthy" else 503 if overall_status == "unhealthy" else 200

    return web.json_response(response_data, status=http_status)
