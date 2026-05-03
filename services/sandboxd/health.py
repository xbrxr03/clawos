# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sandboxd health check."""
import logging

log = logging.getLogger("sandboxd")


def health() -> dict:
    try:
        from services.sandboxd.v2.sandbox import SandboxManager
        manager = SandboxManager()
        active_sandboxes = len(manager.list_active()) if hasattr(manager, 'list_active') else 0
        return {
            "status": "ok",
            "active_sandboxes": active_sandboxes,
            "sandbox_v2_ready": True,
        }
    except (ImportError, OSError, AttributeError) as e:
        log.warning(f"Sandboxd health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
