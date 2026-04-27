# SPDX-License-Identifier: AGPL-3.0-or-later
"""OMId health check."""
import logging

log = logging.getLogger("omid")


def health() -> dict:
    try:
        from services.omid.service import get_omi_service
        service = get_omi_service()
        return {
            "status": "ok",
            "omi_connected": service.is_connected() if hasattr(service, 'is_connected') else False,
        }
    except Exception as e:
        log.warning(f"OMId health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
