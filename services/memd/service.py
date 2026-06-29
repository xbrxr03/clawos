# SPDX-License-Identifier: AGPL-3.0-or-later
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
import json
import logging
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from clawos_core.constants import MEMORY_DIR
from clawos_core.util.time import now_iso, now_stamp
from clawos_core.util.paths import (
    pinned_path, workflow_path, history_path,
    soul_path, agents_path, heartbeat_path
)

log = logging.getLogger("memd")

# ── taosmd backends ───────────────────────────────────────────────────────────
try:
    from services.memd.taosmd.secret_filter import redact_secrets as _redact_secrets
    from services.memd.taosmd.archive import ArchiveStore as _ArchiveStore
    from services.memd.taosmd.knowledge_graph import TemporalKnowledgeGraph as _TemporalKG
    from services.memd.taosmd.intent_classifier import classify_intent as _classify_intent, route_to_backends as _route_to_backends
    from services.memd.taosmd.vector_memory import VectorMemory as _VectorMemory
    _TAOSMD_OK = True
except ImportError as _e:
    log.debug("taosmd modules not loaded: %s", _e)
    _TAOSMD_OK = False
    def _redact_secrets(t): return t, []  # type: ignore[misc]

# ── ChromaDB (optional) ───────────────────────────────────────────────────────
try:
    import chromadb
    _chroma = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma"))
    CHROMA_OK = True
except (ImportError, ModuleNotFoundError) as e:
    log.warning(f"ChromaDB unavailable: {e}")
    CHROMA_OK = False
    _chroma = None

# ── SQLite FTS5 ───────────────────────────────────────────────────────────────
_FTS_DB_PATH = MEMORY_DIR / "fts.db"
_SESSION_DB_PATH = MEMORY_DIR / "sessions.db"

# ── taosmd singletons (initialized lazily on first use) ───────────────────────
_taosmd_archive: "object | None" = None
_taosmd_tkg: "object | None" = None
_taosmd_vector: "object | None" = None


def _get_archive():
    global _taosmd_archive
    if _TAOSMD_OK and _taosmd_archive is None:
        _taosmd_archive = _ArchiveStore(MEMORY_DIR / "archive")
    return _taosmd_archive


def _get_tkg():
    global _taosmd_tkg
    if _TAOSMD_OK and _taosmd_tkg is None:
        _taosmd_tkg = _TemporalKG(MEMORY_DIR / "tkg.db")
    return _taosmd_tkg


def _get_vector():
    global _taosmd_vector
    if _TAOSMD_OK and _taosmd_vector is None:
        _taosmd_vector = _VectorMemory(
            MEMORY_DIR / "vm_fts.db",
            chroma_path=MEMORY_DIR / "chroma",
        )
    return _taosmd_vector

def _open_fts() -> sqlite3.Connection:
    """New connection per call — safe for thread pool use."""
    _FTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_FTS_DB_PATH), check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
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


def _open_session_db() -> sqlite3.Connection:
    """Open the sessions database with FTS5 full-text search.

    Uses content= mode so the FTS index stays in sync with the
    session_turns table via triggers (no data duplication).
    """
    _SESSION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_SESSION_DB_PATH), check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")
    # ── sessions table ────────────────────────────────────────────────────
    db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id           TEXT PRIMARY KEY,
            workspace_id TEXT,
            started_at   TEXT,
            ended_at     TEXT,
            turn_count   INTEGER DEFAULT 0
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS ix_sessions_ws ON sessions(workspace_id)")
    # ── session_turns table ───────────────────────────────────────────────
    db.execute("""
        CREATE TABLE IF NOT EXISTS session_turns (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            timestamp  TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS ix_turns_session ON session_turns(session_id)")
    # ── FTS5 virtual table (content= mode) ────────────────────────────────
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS session_turns_fts USING fts5(
            content, content='session_turns', content_rowid='id'
        )
    """)
    # ── Triggers to keep FTS in sync with content table ───────────────────
    db.execute("""
        CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON session_turns BEGIN
            INSERT INTO session_turns_fts(rowid, content)
            VALUES (new.id, new.content);
        END
    """)
    db.execute("""
        CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON session_turns BEGIN
            INSERT INTO session_turns_fts(session_turns_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
        END
    """)
    db.execute("""
        CREATE TRIGGER IF NOT EXISTS turns_au AFTER UPDATE ON session_turns BEGIN
            INSERT INTO session_turns_fts(session_turns_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
            INSERT INTO session_turns_fts(rowid, content)
            VALUES (new.id, new.content);
        END
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
        all_lines = [line for line in p.read_text().strip().split("\n") if line.strip()]
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

        # Secret filter — never persist credentials
        text, _redacted = _redact_secrets(text)

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
        try:
            db.execute("INSERT INTO memories VALUES (?,?,?,?,?)",
                       (memory_id, workspace_id, text, source, created))
            db.execute("INSERT INTO memories_meta VALUES (?,?,?,?,?,?)",
                       (memory_id, workspace_id, text, source, created, "ACTIVE"))
            db.commit()
        finally:
            db.close()
        self.append_history(workspace_id, f"[ADD] {text[:80]}")

        # taosmd: archive + vector store
        try:
            archive = _get_archive()
            if archive:
                archive.record("memory_add", {"content": text, "workspace": workspace_id}, agent_name=source)
            vector = _get_vector()
            if vector:
                vector.add(text, memory_id=memory_id, metadata={"workspace": workspace_id, "source": source})
        except (OSError, sqlite3.Error, AttributeError) as _e:
            log.debug("taosmd write error (non-fatal): %s", _e)

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

        # taosmd: intent-routed prefetch (non-blocking, additive)
        if _TAOSMD_OK:
            try:
                intent = _classify_intent(query)
                backends = _route_to_backends(intent)
                if "archive" in backends[:1]:
                    archive = _get_archive()
                    if archive:
                        hits = archive.search(query, limit=3)
                        for h in hits:
                            snippet = h.get("snippet", "")
                            if snippet:
                                results.append(f"[RECENT] {snippet[:200]}")
                if "kg" in backends[:1]:
                    tkg = _get_tkg()
                    if tkg:
                        # Extract likely entity from first few words
                        entity = query.split()[0] if query.strip() else ""
                        if entity:
                            kg_text = tkg.format_for_context(entity)
                            if kg_text:
                                results.append(kg_text)
            except (OSError, sqlite3.Error, AttributeError) as _e:
                log.debug("taosmd intent recall error (non-fatal): %s", _e)

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
            except (OSError, AttributeError, RuntimeError) as e:
                log.debug(f"ChromaDB recall: {e}")

        # Layer 4: SQLite FTS5
        db = None
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
        except (sqlite3.Error, OSError) as e:
            log.debug(f"FTS5 recall: {e}")
        finally:
            if db is not None:
                db.close()

        # Recent history — skip for greetings/acks to prevent session bleed
        _skip_words = {"ok", "okay", "hi", "hello", "hey", "yes", "no",
                       "sure", "thanks", "k", "yep", "good", "great",
                       "cool", "done", "alright", "nice", "got it"}
        _q = query.strip().lower().rstrip("!.,?")
        if _q not in _skip_words and len(query.split()) > 2:
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
        db = None
        try:
            db = _open_fts()
            db.execute("UPDATE memories_meta SET lifecycle='DELETED' WHERE memory_id=?",
                       (memory_id,))
            db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
            db.commit()
        except (sqlite3.Error, OSError) as e:
            log.warning(f"forget() failed: {e}")
        finally:
            if db is not None:
                db.close()
        if CHROMA_OK:
            try:
                col = _chroma.get_collection(f"ws_{workspace_id}")
                col.delete(ids=[memory_id])
            except (OSError, AttributeError, RuntimeError) as e:
                log.debug(f"unexpected: {e}")
                pass
                pass

    def get_all(self, workspace_id: str, limit: int = 100) -> list[dict]:
        db = None
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
        except (sqlite3.Error, OSError):
            return []
        finally:
            if db is not None:
                db.close()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _find_similar(self, text: str, workspace_id: str,
                      threshold: float = 0.8) -> Optional[dict]:
        db = None
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
        except (sqlite3.Error, OSError) as e:
            log.debug(f"suppressed: {e}")
        finally:
            if db is not None:
                db.close()
        return None

    def _update_fts(self, memory_id: str, new_text: str, workspace_id: str):
        db = None
        try:
            db = _open_fts()
            db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
            db.execute("INSERT INTO memories VALUES (?,?,?,?,?)",
                       (memory_id, workspace_id, new_text, "update", now_iso()))
            db.execute("UPDATE memories_meta SET text=?, lifecycle='ACTIVE' WHERE memory_id=?",
                       (new_text, memory_id))
            db.commit()
        except (sqlite3.Error, OSError) as e:
            log.warning(f"FTS update failed: {e}")
        finally:
            if db is not None:
                db.close()

    async def _write_chroma_async(self, memory_id: str, text: str,
                                   workspace_id: str, source: str):
        try:
            col = _chroma.get_or_create_collection(
                f"ws_{workspace_id}", metadata={"hnsw:space": "cosine"}
            )
            col.add(documents=[text], ids=[memory_id],
                    metadatas=[{"source": source, "workspace": workspace_id}])
        except (OSError, AttributeError, RuntimeError) as e:
            log.debug(f"ChromaDB async write: {e}")

    # ── Session continuity (AIPass pattern) ───────────────────────────────────

    def save_session_state(self, workspace_id: str, state: dict) -> None:
        """Persist current session state so JARVIS can resume on next wake."""
        import json
        from clawos_core.constants import WORKSPACE_DIR
        session_dir = WORKSPACE_DIR / workspace_id / ".session"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "local.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_session_state(self, workspace_id: str) -> dict:
        """Load last session state. Returns {} if none exists."""
        import json
        from clawos_core.constants import WORKSPACE_DIR
        p = WORKSPACE_DIR / workspace_id / ".session" / "local.json"
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return {}

    def push_pending(self, workspace_id: str, task: str) -> None:
        """Add a task to the pending queue for next session."""
        import json
        from clawos_core.constants import WORKSPACE_DIR
        session_dir = WORKSPACE_DIR / workspace_id / ".session"
        session_dir.mkdir(parents=True, exist_ok=True)
        q_path = session_dir / "pending_queue.json"
        queue: list[str] = []
        if q_path.exists():
            try:
                queue = json.loads(q_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                queue = []
        if task not in queue:
            queue.append(task)
        q_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_pending_queue(self, workspace_id: str) -> list[str]:
        """Return the pending task queue for this workspace."""
        import json
        from clawos_core.constants import WORKSPACE_DIR
        q_path = WORKSPACE_DIR / workspace_id / ".session" / "pending_queue.json"
        if not q_path.exists():
            return []
        try:
            return json.loads(q_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return []

    def clear_pending_queue(self, workspace_id: str) -> None:
        """Clear the pending queue (called after briefing delivered)."""
        from clawos_core.constants import WORKSPACE_DIR
        q_path = WORKSPACE_DIR / workspace_id / ".session" / "pending_queue.json"
        if q_path.exists():
            q_path.write_text("[]", encoding="utf-8")

    # ── Session search (FTS5) ──────────────────────────────────────────────────

    def ingest_session_start(self, session_id: str, workspace_id: str,
                             started_at: str | None = None) -> None:
        """Record the start of a new session."""
        db = None
        try:
            db = _open_session_db()
            db.execute(
                "INSERT OR IGNORE INTO sessions (id, workspace_id, started_at, turn_count) "
                "VALUES (?, ?, ?, 0)",
                (session_id, workspace_id, started_at or now_iso()),
            )
            db.commit()
        except (sqlite3.Error, OSError) as e:
            log.warning("ingest_session_start failed: %s", e)
        finally:
            if db is not None:
                db.close()

    def ingest_session_end(self, session_id: str, ended_at: str | None = None) -> None:
        """Record session end and final turn count."""
        db = None
        try:
            db = _open_session_db()
            turn_count = db.execute(
                "SELECT COUNT(*) FROM session_turns WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
            db.execute(
                "UPDATE sessions SET ended_at=?, turn_count=? WHERE id=?",
                (ended_at or now_iso(), turn_count, session_id),
            )
            db.commit()
        except (sqlite3.Error, OSError) as e:
            log.warning("ingest_session_end failed: %s", e)
        finally:
            if db is not None:
                db.close()

    def ingest_turn(self, session_id: str, role: str, content: str,
                    workspace_id: str, timestamp: str | None = None) -> None:
        """Ingest a single conversation turn into the session search index.

        Ensures the session row exists (auto-creates if needed), then inserts
        the turn row. FTS5 index is updated via the AFTER INSERT trigger.
        """
        if not content or not content.strip():
            return
        # Truncate very long turns to keep the index reasonable
        if len(content) > 4000:
            content = content[:4000]
        db = None
        try:
            db = _open_session_db()
            # Ensure session exists (upsert)
            db.execute(
                "INSERT OR IGNORE INTO sessions (id, workspace_id, started_at, turn_count) "
                "VALUES (?, ?, ?, 0)",
                (session_id, workspace_id, timestamp or now_iso()),
            )
            # Insert the turn (FTS trigger fires automatically)
            db.execute(
                "INSERT INTO session_turns (session_id, role, content, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, timestamp or now_iso()),
            )
            # Bump turn count
            db.execute(
                "UPDATE sessions SET turn_count = turn_count + 1 WHERE id = ?",
                (session_id,),
            )
            db.commit()
        except (sqlite3.Error, OSError) as e:
            log.warning("ingest_turn failed: %s", e)
        finally:
            if db is not None:
                db.close()

    def recall_cross_session(self, query: str, workspace_id: str,
                              n: int = 5) -> list[dict]:
        """FTS5 search across all past session turns for a workspace.

        Returns list of dicts with: session_id, role, content, timestamp, rank.
        Uses snippet() for match highlighting.
        """
        if not query or not query.strip():
            return []
        db = None
        try:
            db = _open_session_db()
            cq = re.sub(r'[^\w\s]', '', query)
            if not cq.strip():
                return []
            rows = db.execute(
                """
                SELECT
                    t.session_id, t.role, t.content, t.timestamp,
                    s.workspace_id,
                    snippet(session_turns_fts, 0, '⟫ ', ' ⟪', '…', 16) AS highlight,
                    rank
                FROM session_turns_fts f
                JOIN session_turns t ON t.id = f.rowid
                JOIN sessions s ON s.id = t.session_id
                WHERE session_turns_fts MATCH ?
                  AND s.workspace_id = ?
                ORDER BY rank
                LIMIT ?
                """,
                (cq, workspace_id, n),
            ).fetchall()
            return [
                {
                    "session_id": r[0],
                    "role": r[1],
                    "content": r[2],
                    "timestamp": r[3],
                    "workspace_id": r[4],
                    "highlight": r[5],
                    "rank": r[6],
                }
                for r in rows
            ]
        except (sqlite3.Error, OSError) as e:
            log.debug("recall_cross_session failed: %s", e)
            return []
        finally:
            if db is not None:
                db.close()


# ── RAGd A2A server ───────────────────────────────────────────────────────────
async def start_ragd_a2a_server():
    """Start RAGd A2A endpoint for document retrieval via OpenClaw peers."""
    try:
        from fastapi import FastAPI
        import uvicorn
        from clawos_core.constants import A2A_PORT_RAGD, DEFAULT_WORKSPACE

        app = FastAPI(title="RAGd A2A")

        @app.get("/.well-known/agent-card.json")
        def agent_card():
            return {
                "name": "RAGd",
                "description": "Document retrieval agent. Answers questions from uploaded "
                               "project documents with citations.",
                "url": f"http://localhost:{A2A_PORT_RAGD}/a2a",
                "version": "1.0",
                "skills": [
                    {"name": "rag_search", "description": "Search project documents and return cited answers"},
                    {"name": "doc_list",   "description": "List ingested documents in the current project"},
                ],
                "provider": {"name": "ClawOS", "url": "https://github.com/xbrxr03/clawos"},
            }

        @app.post("/a2a/tasks/send")
        async def receive_task(body: dict):
            query = body.get("message", {}).get("parts", [{}])[0].get("text", "")
            workspace = body.get("metadata", {}).get("workspace", DEFAULT_WORKSPACE)
            if not query:
                return {"error": "no query"}
            try:
                from services.ragd.service import get_rag
                from clawos_core.util.paths import workspace_path
                ws_root = workspace_path(workspace)
                rag = get_rag(workspace, ws_root)
                result = rag.answer(query)
                answer = result.get("answer", "[No answer]")
                citations = result.get("citations", [])
                text = answer
                if citations:
                    text += "\n\n" + "\n".join(
                        f"[{c['file']} p.{c.get('page', '?')}]" for c in citations
                    )
            except (ImportError, ModuleNotFoundError) as e:
                text = f"[RAGd error: {e}]"
            return {
                "id": body.get("id", ""),
                "status": {"state": "completed"},
                "artifacts": [{"parts": [{"type": "text", "text": text}]}],
            }

        config = uvicorn.Config(app, host="127.0.0.1",
                                port=A2A_PORT_RAGD, log_level="warning")
        await uvicorn.Server(config).serve()
    except (ImportError, ModuleNotFoundError) as e:
        log.warning(f"RAGd A2A server not started: {e}")



# ══════════════════════════════════════════════════════════════════════════════
# Layer 5: LEARNED.md — ACE Self-Improving Loop
# ══════════════════════════════════════════════════════════════════════════════

LEARNED_MAX_KB = 2   # default; overridden by gaming.yaml to 4KB


class LearnedLayer:
    """
    ACE (Agentic Context Engineering) loop — arXiv 2025.
    After each completed task, a Curator coroutine extracts learnings
    and appends them to LEARNED.md. Injected into every agent turn.
    +10.6% benchmark improvement without fine-tuning.
    """

    def path(self, workspace_id: str) -> Path:
        from clawos_core.constants import WORKSPACE_DIR
        return WORKSPACE_DIR / workspace_id / "LEARNED.md"

    def read(self, workspace_id: str) -> str:
        p = self.path(workspace_id)
        return p.read_text() if p.exists() else ""

    def _prune_if_over(self, p: Path, max_kb: int):
        """Keep LEARNED.md under max_kb by dropping oldest bullet points."""
        if p.stat().st_size <= max_kb * 1024:
            return
        lines = p.read_text().splitlines()
        # Drop from top (oldest) until under limit
        while lines and len("\n".join(lines).encode()) > max_kb * 1024:
            lines.pop(0)
        p.write_text("\n".join(lines))

    async def extract_and_append(self, task_result: str, workspace_id: str,
                                  ollama_host: str = "http://localhost:11434",
                                  model: str = "qwen2.5:1.5b"):
        """
        Run async after task completion. Uses the smallest model (1.5b)
        to extract 1-3 learnings — cheap and fast.
        """
        if not task_result or len(task_result) < 50:
            return
        prompt = (
            "Extract 1-3 concrete, reusable learnings from this task result. "
            "Write each as a short bullet point (one line). "
            "Focus on facts that will help future tasks. "
            "If no useful learnings, output: NONE\n\n"
            f"Task result:\n{task_result[:1500]}"
        )
        try:
            import json as _json
            import urllib.request
            payload = _json.dumps({
                "model": model, "prompt": prompt,
                "stream": False, "options": {"temperature": 0.1}
            }).encode()
            req = urllib.request.Request(
                f"{ollama_host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = _json.loads(resp.read())
            learnings = resp_data.get("response", "").strip()
            if not learnings or learnings.upper() == "NONE":
                return

            p = self.path(workspace_id)
            p.parent.mkdir(parents=True, exist_ok=True)
            from clawos_core.util.time import now_stamp
            with p.open("a") as f:
                f.write(f"\n<!-- {now_stamp()} -->\n")
                for line in learnings.splitlines():
                    line = line.strip()
                    if line and not line.startswith("NONE"):
                        f.write(f"{line}\n")

            # Prune if over limit
            from clawos_core.config.loader import get
            max_kb = get("memory.learned_md_max_kb", LEARNED_MAX_KB)
            self._prune_if_over(p, max_kb)
            log.debug(f"LEARNED.md updated for workspace: {workspace_id}")
        except (json.JSONDecodeError, ValueError) as e:
            log.debug(f"ACE extract failed (non-fatal): {e}")


_learned = LearnedLayer()


def get_learned(workspace_id: str) -> str:
    """Public API — read LEARNED.md for injection into prompts."""
    return _learned.read(workspace_id)


async def run_ace_loop(task_result: str, workspace_id: str):
    """Call after task completion. Fire-and-forget async."""
    from clawos_core.constants import OLLAMA_HOST
    await _learned.extract_and_append(task_result, workspace_id, OLLAMA_HOST)


# ══════════════════════════════════════════════════════════════════════════════
# Knowledge Graph Layer — SQLite adjacency list
# ══════════════════════════════════════════════════════════════════════════════

_KG_DB_PATH = MEMORY_DIR / "knowledge_graph.db"


def _open_kg() -> sqlite3.Connection:
    _KG_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_KG_DB_PATH), check_same_thread=False)
    db.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            entity_id    TEXT PRIMARY KEY,
            workspace_id TEXT,
            name         TEXT NOT NULL,
            entity_type  TEXT DEFAULT 'concept',
            created_at   TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            rel_id       TEXT PRIMARY KEY,
            workspace_id TEXT,
            from_entity  TEXT,
            relation     TEXT,
            to_entity    TEXT,
            source_text  TEXT DEFAULT '',
            created_at   TEXT
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS ix_entities_ws ON entities(workspace_id)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_rels_from ON relationships(from_entity)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_rels_to ON relationships(to_entity)")
    db.commit()
    return db


def _extract_entities(text: str) -> list[str]:
    """
    Lightweight NER via regex noun-phrase extraction.
    No external deps — spaCy not required.
    Extracts capitalized multi-word phrases and quoted strings.
    """
    import re
    # Capitalized words / multi-word proper nouns
    caps = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*)\b', text)
    # Quoted strings
    quoted = re.findall(r'"([^"]{2,40})"', text)
    # Filter stop words
    stop = {"I", "The", "A", "An", "This", "That", "It", "He", "She",
            "We", "You", "They", "Is", "Are", "Was", "Were", "Be",
            "And", "Or", "But", "For", "With", "From", "To", "Of"}
    return list({e.strip() for e in caps + quoted if e.strip() not in stop and len(e) > 1})


def add_to_graph(text: str, workspace_id: str, source: str = "memory"):
    """Extract entities from text and add to knowledge graph."""
    import uuid
    entities = _extract_entities(text)
    if len(entities) < 2:
        return
    db = _open_kg()
    ts = now_iso()
    entity_ids = {}
    for name in entities:
        eid = f"{workspace_id}::{name.lower().replace(' ', '_')}"
        entity_ids[name] = eid
        db.execute("""
            INSERT OR IGNORE INTO entities (entity_id, workspace_id, name, entity_type, created_at)
            VALUES (?, ?, ?, 'concept', ?)
        """, (eid, workspace_id, name, ts))

    # Create co-occurrence relationships between entities in same sentence
    import re
    sentences = re.split(r'[.!?]\s', text)
    for sent in sentences:
        ents_in_sent = [n for n in entities if n.lower() in sent.lower()]
        for i, a in enumerate(ents_in_sent):
            for b in ents_in_sent[i+1:]:
                rid = str(uuid.uuid4())[:16]
                db.execute("""
                    INSERT OR IGNORE INTO relationships
                    (rel_id, workspace_id, from_entity, relation, to_entity, source_text, created_at)
                    VALUES (?, ?, ?, 'co-occurs', ?, ?, ?)
                """, (rid, workspace_id, entity_ids[a], entity_ids[b], sent[:200], ts))
    db.commit()
    db.close()


def query_graph(entity_name: str, workspace_id: str, depth: int = 1) -> str:
    """Return related entities from knowledge graph as text context."""
    try:
        db = _open_kg()
        eid = f"{workspace_id}::{entity_name.lower().replace(' ', '_')}"
        rows = db.execute("""
            SELECT r.relation, e2.name, r.source_text
            FROM relationships r
            JOIN entities e2 ON e2.entity_id = r.to_entity
            WHERE r.from_entity = ? AND r.workspace_id = ?
            LIMIT 10
        """, (eid, workspace_id)).fetchall()
        db.close()
        if not rows:
            return ""
        lines = [f"Knowledge graph context for '{entity_name}':"]
        for rel, related, source in rows:
            lines.append(f"  - {rel} → {related}  (from: {source[:60]})")
        return "\n".join(lines)
    except (sqlite3.Error, OSError):
        return ""
