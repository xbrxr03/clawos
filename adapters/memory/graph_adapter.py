# SPDX-License-Identifier: AGPL-3.0-or-later
"""
SQLite knowledge graph adapter — public API for graph layer.
Wraps the graph functions in memd/service.py for clean imports.
"""


def add(text: str, workspace_id: str, source: str = "memory"):
    """Extract entities and relationships from text, add to graph."""
    try:
        from services.memd.service import add_to_graph
        add_to_graph(text, workspace_id, source)
    except Exception:
        pass


def query(entity: str, workspace_id: str) -> str:
    """Return related entities as context string."""
    try:
        from services.memd.service import query_graph
        return query_graph(entity, workspace_id)
    except Exception:
        return ""
