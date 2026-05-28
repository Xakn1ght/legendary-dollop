"""Database connectivity probe."""

import time
from typing import Any, Dict

import sqlalchemy

from app.database.models import AsyncSessionLocal


async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and latency."""
    start_time = time.time()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(sqlalchemy.text("SELECT 1"))
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "ok",
                "latency_ms": latency_ms,
            }
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": str(e),
        }
