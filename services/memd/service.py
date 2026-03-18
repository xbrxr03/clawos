"""
ClawOS memd — Memory Service
============================
4-layer memory architecture (from Nanobot + MemOS research):

  Layer 1 — PINNED.md      always injected, human-editable durable facts
  Layer 2 — WORKFLOW.md    current task state
  Layer 3 — ChromaDB       semantic vector search
  Layer 4 — SQLite FTS5    keyword search + HISTORY.md log

Lifecycle: ADD / UPDATE / DELETE / NOOP (prevents memory bloat).
Async writes: agent loop never blocks on memory writes.
"""
import asyncio
import logging
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from clawos_core.constants import MEMORY_DIR
from clawos_core.util.time import now_iso, now_stamp
from clawos_core.util.paths import (
    memory_path, pinned_path, workflow_path, history_path,
    soul_path, agents_path, heartbeat_path
)

log = logging.getLogger("memd")

# ── ChromaDB (optional) ───────────────────────────────────────────────────────
try:
    import chromadb
    _chroma = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma"))
    CHROMA_OK = True
except Exception as e:
    log.warning(f"ChromaDB unavailable: {e}")
    CHROMA_OK = False
    _chroma = None

# ── SQLite FTS5 ───────────────────────────────────────────────────────────────
_FTS_DB_PATH = MEMORY_DIR / "fts.db"

def _open_fts() -> sqlite3.Connection:
    """New connection per call — safe for thread pool use."""
    _FTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_FTS_DB_PATH), check_same_thread=False)
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories USING fts5(
            memory_id, workspace_id, text, source, created_at,
            tokenize='porter ascii'
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS memories_meta (
            memory_id    TEXT PRIMARY KEY,
            workspace_id TEXT,
            text         TEXT,
            source       TEXT,
            created_at   TEXT,
            lifecycle    TEXT DEFAULT 'ACTIVE'
        )
    """)
    db.commit()
    return db


# ── MemoryService ─────────────────────────────────────────────────────────────
class MemoryService:

    # ── File layer helpers ────────────────────────────────────────────────────
    def read_file(self, path: Path) -> str:
        return path.read_text() if path.exists() else ""

    def write_file(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    # ── PINNED.md ─────────────────────────────────────────────────────────────
    def read_pinned(self, ws: str) -> str:
        return self.read_file(pinned_path(ws))

    def append_pinned(self, ws: str, fact: str):
        p = pinned_path(ws)
        existing = p.read_text() if p.exists() else ""
        p.write_text(existing + f"\n- [{now_stamp()[:10]}] {fact}")

    def write_pinned(self, ws: str, content: str):
        self.write_file(pinned_path(ws), content)

    # ── WORKFLOW.md ───────────────────────────────────────────────────────────
    def read_workflow(self, ws: str) -> str:
        return self.read_file(workflow_path(ws))

    def write_workflow(self, ws: str, content: str):
        self.write_file(workflow_path(ws), content)

    def clear_workflow(self, ws: str):
        p = workflow_path(ws)
        if p.exists():
            p.unlink()

    # ── HISTORY.md ────────────────────────────────────────────────────────────
    def append_history(self, ws: str, entry: str):
        p = history_path(ws)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            f.write(f"\n[{now_stamp()}] {entry}")

    def read_history_tail(self, ws: str, lines: int = 10) -> str:
        p = history_path(ws)
        if not p.exists():
            return ""
        all_lines = [l for l in p.read_text().strip().split("\n") if l.strip()]
        return "\n".join(all_lines[-lines:])

    # ── SOUL / AGENTS / HEARTBEAT ─────────────────────────────────────────────
    def read_soul(self, ws: str) -> str:
        return self.read_file(soul_path(ws))

    def read_agents(self, ws: str) -> str:
        return self.read_file(agents_path(ws))

    def read_heartbeat(self, ws: str) -> str:
        return self.read_file(heartbeat_path(ws))

    # ── Core: remember() ──────────────────────────────────────────────────────
    def remember(self, text: str, workspace_id: str, source: str = "agent",
                 force_add: bool = False) -> str:
        if not text or not text.strip():
            return ""
        memory_id = str(uuid.uuid4())[:12]
        created   = now_iso()

        # ADD/UPDATE lifecycle — check for near-duplicate first
        if not force_add:
            existing = self._find_similar(text, workspace_id)
            if existing:
                self._update_fts(existing["memory_id"], text, workspace_id)
                self.append_history(workspace_id, f"[UPDATE] {text[:80]}")
                return existing["memory_id"]

        # ADD new
        db = _open_fts()
        db.execute("INSERT INTO memories VALUES (?,?,?,?,?)",
                   (memory_id, workspace_id, text, source, created))
        db.execute("INSERT INTO memories_meta VALUES (?,?,?,?,?,?)",
                   (memory_id, workspace_id, text, source, created, "ACTIVE"))
        db.commit()
        self.append_history(workspace_id, f"[ADD] {text[:80]}")
        return memory_id

    async def remember_async(self, text: str, workspace_id: str,
                             source: str = "agent") -> str:
        """Non-blocking version — agent loop continues immediately."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.remember, text, workspace_id, source
        )

    # ── Recall ────────────────────────────────────────────────────────────────
    def recall(self, query: str, workspace_id: str, n: int = 5) -> list[str]:
        """Hybrid 4-layer recall. Always includes PINNED + WORKFLOW."""
        results = []

        # Layer 1: PINNED.md
        pinned = self.read_pinned(workspace_id)
        if pinned.strip():
            results.append(f"[PINNED]\n{pinned.strip()}")

        # Layer 2: WORKFLOW.md
        workflow = self.read_workflow(workspace_id)
        if workflow.strip():
            results.append(f"[WORKFLOW]\n{workflow.strip()}")

        # Layer 3: ChromaDB semantic
        chroma_ids = set()
        if CHROMA_OK:
            try:
                col = _chroma.get_or_create_collection(
                    f"ws_{workspace_id}", metadata={"hnsw:space": "cosine"}
                )
                if col.count() > 0:
                    cr = col.query(query_texts=[query],
                                   n_results=min(n, col.count()))
                    for doc, mid in zip(cr["documents"][0], cr["ids"][0]):
                        results.append(doc)
                        chroma_ids.add(mid)
            except Exception as e:
                log.debug(f"ChromaDB recall: {e}")

        # Layer 4: SQLite FTS5
        try:
            db  = _open_fts()
            cq  = re.sub(r'[^\w\s]', '', query)
            if cq.strip():
                rows = db.execute(
                    "SELECT memory_id, text FROM memories "
                    "WHERE workspace_id=? AND memories MATCH ? "
                    "ORDER BY rank LIMIT ?",
                    (workspace_id, cq, n)
                ).fetchall()
                for mid, text in rows:
                    if mid not in chroma_ids:
                        results.append(text)
                        chroma_ids.add(mid)
        except Exception as e:
            log.debug(f"FTS5 recall: {e}")

        # Recent history
        hist = self.read_history_tail(workspace_id, lines=5)
        if hist:
            results.append(f"[RECENT]\n{hist}")

        return results[:n + 3]

    def build_context_block(self, query: str, workspace_id: str) -> str:
        """Build memory context string for agent prompts."""
        memories = self.recall(query, workspace_id)
        if not memories:
            return ""
        parts = ["## Memory Context"]
        for m in memories:
            parts.append(f"- {m[:200]}")
        return "\n".join(parts)

    # ── Delete ────────────────────────────────────────────────────────────────
    def forget(self, memory_id: str, workspace_id: str):
        try:
            db = _open_fts()
            db.execute("UPDATE memories_meta SET lifecycle='DELETED' WHERE memory_id=?",
                       (memory_id,))
            db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
            db.commit()
        except Exception as e:
            log.warning(f"forget() failed: {e}")
        if CHROMA_OK:
            try:
                col = _chroma.get_collection(f"ws_{workspace_id}")
                col.delete(ids=[memory_id])
            except Exception:
                pass

    def get_all(self, workspace_id: str, limit: int = 100) -> list[dict]:
        try:
            db = _open_fts()
            rows = db.execute(
                "SELECT memory_id, text, source, created_at FROM memories_meta "
                "WHERE workspace_id=? AND lifecycle='ACTIVE' "
                "ORDER BY created_at DESC LIMIT ?",
                (workspace_id, limit)
            ).fetchall()
            return [{"memory_id": r[0], "text": r[1], "source": r[2], "created_at": r[3]}
                    for r in rows]
        except Exception:
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _find_similar(self, text: str, workspace_id: str,
                      threshold: float = 0.8) -> Optional[dict]:
        try:
            words = set(text.lower().split())
            if len(words) < 3:
                return None
            db = _open_fts()
            rows = db.execute(
                "SELECT memory_id, text FROM memories_meta "
                "WHERE workspace_id=? AND lifecycle='ACTIVE' "
                "ORDER BY created_at DESC LIMIT 50",
                (workspace_id,)
            ).fetchall()
            for mid, existing in rows:
                ew = set(existing.lower().split())
                if not ew:
                    continue
                overlap = len(words & ew) / max(len(words), len(ew))
                if overlap >= threshold:
                    return {"memory_id": mid, "text": existing}
        except Exception:
            pass
        return None

    def _update_fts(self, memory_id: str, new_text: str, workspace_id: str):
        try:
            db = _open_fts()
            db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
            db.execute("INSERT INTO memories VALUES (?,?,?,?,?)",
                       (memory_id, workspace_id, new_text, "update", now_iso()))
            db.execute("UPDATE memories_meta SET text=?, lifecycle='ACTIVE' WHERE memory_id=?",
                       (new_text, memory_id))
            db.commit()
        except Exception as e:
            log.warning(f"FTS update failed: {e}")

    async def _write_chroma_async(self, memory_id: str, text: str,
                                   workspace_id: str, source: str):
        try:
            col = _chroma.get_or_create_collection(
                f"ws_{workspace_id}", metadata={"hnsw:space": "cosine"}
            )
            col.add(documents=[text], ids=[memory_id],
                    metadatas=[{"source": source, "workspace": workspace_id}])
        except Exception as e:
            log.debug(f"ChromaDB async write: {e}")
