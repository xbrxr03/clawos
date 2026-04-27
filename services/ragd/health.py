# SPDX-License-Identifier: AGPL-3.0-or-later
"""RAGd health check."""
import logging

log = logging.getLogger("ragd")


def health() -> dict:
    try:
        from services.ragd.service import get_vector_store
        store = get_vector_store()
        stats = store.get_stats() if hasattr(store, 'get_stats') else {}
        return {
            "status": "ok",
            "documents_indexed": stats.get("document_count", 0),
            "chunks_indexed": stats.get("chunk_count", 0),
        }
    except Exception as e:
        log.warning(f"RAGd health check failed: {e}")
        return {"status": "degraded", "error": str(e)}
