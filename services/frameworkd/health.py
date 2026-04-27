# SPDX-License-Identifier: AGPL-3.0-or-later
"""Frameworkd health check."""
import logging

log = logging.getLogger("frameworkd")


def health() -> dict:
    try:
        from services.frameworkd.service import get_framework_store
        store = get_framework_store()
        frameworks = store.list_frameworks()
        return {
            "status": "ok",
            "frameworks_available": len(frameworks),
            "store_initialized": True,
        }
    except Exception as e:
        log.warning(f"Frameworkd health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
