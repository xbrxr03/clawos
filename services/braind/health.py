# SPDX-License-Identifier: AGPL-3.0-or-later
"""Kizuna health check."""
import logging

log = logging.getLogger("braind")


def health() -> dict:
    try:
        from services.braind.service import get_brain
        brain = get_brain()
        stats = brain.stats()
        return {
            "status": "ok",
            "nodes": stats.get("node_count", 0),
            "edges": stats.get("edge_count", 0),
            "communities": stats.get("community_count", 0),
            "ingesting": stats.get("ingesting", False),
        }
    except (ImportError, OSError, AttributeError) as e:
        log.warning(f"Kizuna health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
