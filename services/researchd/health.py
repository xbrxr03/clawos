# SPDX-License-Identifier: AGPL-3.0-or-later
"""Researchd health check."""
import logging

log = logging.getLogger("researchd")


def health() -> dict:
    try:
        from services.researchd.service import get_research_engine
        engine = get_research_engine()
        active_jobs = engine.active_jobs() if hasattr(engine, 'active_jobs') else 0
        return {
            "status": "ok",
            "active_research_jobs": active_jobs,
            "engine_ready": True,
        }
    except Exception as e:
        log.warning(f"Researchd health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
