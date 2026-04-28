# SPDX-License-Identifier: AGPL-3.0-or-later
"""LLMd health check."""
import logging

log = logging.getLogger("llmd")


def health() -> dict:
    try:
        from services.llmd.service import get_model_manager
        manager = get_model_manager()
        models = manager.list_models() if hasattr(manager, 'list_models') else []
        active = manager.get_active_model() if hasattr(manager, 'get_active_model') else None
        return {
            "status": "ok",
            "models_loaded": len(models),
            "active_model": active.get("name") if active else None,
        }
    except Exception as e:
        log.warning(f"LLMd health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
