# SPDX-License-Identifier: AGPL-3.0-or-later
"""Wake trigger service health check."""
import httpx

from clawos_core.constants import PORT_WAKETRD


async def check_health(timeout: float = 5.0) -> dict:
    """Check waketrd health."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"http://127.0.0.1:{PORT_WAKETRD}/health")
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy" if data.get("status") == "healthy" else "unhealthy",
                    "service": "waketrd",
                    "port": PORT_WAKETRD,
                }
            return {
                "status": "unhealthy",
                "service": "waketrd",
                "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "waketrd",
            "error": str(e),
        }
