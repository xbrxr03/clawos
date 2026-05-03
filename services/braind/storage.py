# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Kizuna — Graph Storage.
Persists NetworkX graph to JSON + SQLite for fast node lookup.
"""
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger("braind.storage")

from clawos_core.constants import CLAWOS_DIR

BRAIN_DIR = CLAWOS_DIR / "brain"
GRAPH_JSON = BRAIN_DIR / "graph.json"
BRAIN_DB = BRAIN_DIR / "brain.db"


def _ensure_dirs():
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)


class BrainStorage:
    """Handles persistence of the Kizuna graph."""

    def __init__(self):
        _ensure_dirs()
        self._lock = threading.Lock()
        self._db: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        self._db = sqlite3.connect(str(BRAIN_DB), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                community INTEGER DEFAULT 0,
                pagerank REAL DEFAULT 0.0,
                agent_added INTEGER DEFAULT 0,
                mention_count INTEGER DEFAULT 1,
                sources TEXT DEFAULT '[]',
                created_at REAL
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                src TEXT NOT NULL,
                tgt TEXT NOT NULL,
                predicate TEXT,
                agent_added INTEGER DEFAULT 0,
                source TEXT DEFAULT '',
                PRIMARY KEY (src, tgt, predicate)
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                chunks_processed INTEGER,
                triples_extracted INTEGER,
                completed_at REAL
            )
        """)
        self._db.commit()

    def save_graph(self, graph_data: dict):
        """Save {nodes, links} dict to graph.json."""
        with self._lock:
            try:
                GRAPH_JSON.write_text(json.dumps(graph_data, ensure_ascii=False))
                self._sync_to_db(graph_data)
                log.debug(f"Graph saved: {len(graph_data.get('nodes', []))} nodes, {len(graph_data.get('links', []))} links")
            except (TypeError, ValueError) as e:
                log.error(f"Failed to save graph: {e}")

    def _sync_to_db(self, graph_data: dict):
        """Sync graph to SQLite for fast queries."""
        import time
        nodes = graph_data.get("nodes", [])
        links = graph_data.get("links", [])

        with self._lock:
            self._db.execute("DELETE FROM nodes")
            self._db.execute("DELETE FROM edges")

            for node in nodes:
                self._db.execute(
                    "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                    (
                        node["id"], node.get("label", ""),
                        node.get("community", 0), node.get("pagerank", 0.0),
                        1 if node.get("agent_added") else 0,
                        node.get("mention_count", 1),
                        json.dumps(node.get("sources", [])),
                        time.time(),
                    )
                )

            for link in links:
                self._db.execute(
                    "INSERT OR REPLACE INTO edges VALUES (?,?,?,?,?)",
                    (
                        link["source"], link["target"],
                        link.get("predicate", "relates_to"),
                        1 if link.get("agent_added") else 0,
                        link.get("source_file", ""),
                    )
                )
            self._db.commit()

    def load_graph(self) -> dict:
        """Load graph from JSON. Returns {nodes, links} or empty."""
        if not GRAPH_JSON.exists():
            return {"nodes": [], "links": []}
        try:
            return json.loads(GRAPH_JSON.read_text())
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"Failed to load graph: {e}")
            return {"nodes": [], "links": []}

    def search_nodes(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search on node labels."""
        try:
            query_like = f"%{query}%"
            rows = self._db.execute(
                "SELECT node_id, label, community, pagerank, agent_added FROM nodes "
                "WHERE label LIKE ? ORDER BY pagerank DESC LIMIT ?",
                (query_like, limit)
            ).fetchall()
            return [
                {"id": r[0], "label": r[1], "community": r[2],
                 "pagerank": r[3], "agent_added": bool(r[4])}
                for r in rows
            ]
        except (sqlite3.Error, OSError) as e:
            log.error(f"Node search failed: {e}")
            return []

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get single node by ID."""
        try:
            row = self._db.execute(
                "SELECT node_id, label, community, pagerank, agent_added, mention_count, sources "
                "FROM nodes WHERE node_id = ?", (node_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0], "label": row[1], "community": row[2],
                "pagerank": row[3], "agent_added": bool(row[4]),
                "mention_count": row[5], "sources": json.loads(row[6] or "[]"),
            }
        except (json.JSONDecodeError, ValueError):
            return None

    def log_ingestion(self, filename: str, chunks: int, triples: int):
        import time
        try:
            self._db.execute(
                "INSERT INTO ingestion_log (filename, chunks_processed, triples_extracted, completed_at) VALUES (?,?,?,?)",
                (filename, chunks, triples, time.time())
            )
            self._db.commit()
        except (sqlite3.Error, OSError):
            log.debug(f"failed: {e}")
            pass
            pass

    def stats(self) -> dict:
        try:
            node_count = self._db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            edge_count = self._db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            community_count = self._db.execute("SELECT COUNT(DISTINCT community) FROM nodes").fetchone()[0]
            return {"node_count": node_count, "edge_count": edge_count, "community_count": community_count}
        except (sqlite3.Error, OSError):
            return {"node_count": 0, "edge_count": 0, "community_count": 0}


# ── Singleton ──────────────────────────────────────────────────────────────────
_storage: Optional[BrainStorage] = None


def get_storage() -> BrainStorage:
    global _storage
    if _storage is None:
        _storage = BrainStorage()
    return _storage
