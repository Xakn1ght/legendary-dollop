"""Marzban API connectivity probe."""

import asyncio
import time
from typing import Any, Dict

import aiohttp

from app.services.marzban import marzban_api


async def check_marzban_health() -> Dict[str, Any]:
    """Check Marzban API connectivity."""
    start_time = time.time()
    try:
        session = await marzban_api._get_session()
        headers = await marzban_api._get_headers()

        url = f"{marzban_api.base_url}/api/system"

        timeout = aiohttp.ClientTimeout(total=5)

        async with session.get(url, headers=headers, timeout=timeout) as response:
            latency_ms = round((time.time() - start_time) * 1000, 2)

            if response.status == 200:
                return {
                    "status": "ok",
                    "latency_ms": latency_ms,
                }
            if response.status == 401:
                await marzban_api._login()
                headers = await marzban_api._get_headers()

                async with session.get(url, headers=headers, timeout=timeout) as retry_response:
                    total_latency = round((time.time() - start_time) * 1000, 2)

                    if retry_response.status == 200:
                        return {
                            "status": "ok",
                            "latency_ms": total_latency,
                            "note": "re-authenticated",
                        }
                    return {
                        "status": "degraded",
                        "latency_ms": total_latency,
                        "error": f"Status {retry_response.status} after retry",
                    }
            return {
                "status": "degraded",
                "latency_ms": latency_ms,
                "error": f"Status {response.status}",
            }

    except asyncio.TimeoutError:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "timeout",
            "latency_ms": latency_ms,
            "error": "Connection timeout",
        }
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": str(e),
        }
