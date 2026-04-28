# SPDX-License-Identifier: AGPL-3.0-or-later
"""Jarvisd health check."""
import logging

log = logging.getLogger("jarvisd")


def health() -> dict:
    try:
        from services.jarvisd.service import get_service
        service = get_service()
        # Check if service is initialized
        config = service.get_config() if hasattr(service, 'get_config') else {}
        return {
            "status": "ok",
            "voice_enabled": config.get("voice_enabled", False),
            "gateway_connected": config.get("gateway_connected", False),
        }
    except Exception as e:
        log.warning(f"Jarvisd health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
