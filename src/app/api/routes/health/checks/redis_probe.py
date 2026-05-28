"""Redis connectivity probe."""

import time
from typing import Any, Dict

from app.core.redis_config import get_redis_client


async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity."""
    start_time = time.time()
    try:
        redis_client = await get_redis_client()

        if redis_client is None:
            return {
                "status": "unavailable",
                "latency_ms": 0,
                "note": "Redis client not initialized",
            }

        await redis_client.ping()
        latency_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "status": "ok",
            "latency_ms": latency_ms,
        }

    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "unavailable",
            "latency_ms": latency_ms,
            "error": str(e),
        }
