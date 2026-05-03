# SPDX-License-Identifier: AGPL-3.0-or-later
"""Health check for reminderd."""
import asyncio
import time

import httpx

from clawos_core.constants import PORT_REMINDERD


async def check_health(timeout: float = 5.0) -> dict:
    """Check reminderd health."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"http://127.0.0.1:{PORT_REMINDERD}/health")
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy" if data.get("status") == "healthy" else "unhealthy",
                    "service": "reminderd",
                    "port": PORT_REMINDERD,
                    "response_time_ms": 0,
                }
            return {
                "status": "unhealthy",
                "service": "reminderd",
                "error": f"HTTP {response.status_code}",
            }
    except (httpx.HTTPError, OSError, ConnectionError, TimeoutError) as e:
        return {
            "status": "unhealthy",
            "service": "reminderd",
            "error": str(e),
        }


def check_health_sync(timeout: float = 5.0) -> dict:
    """Synchronous health check."""
    return asyncio.run(check_health(timeout))
