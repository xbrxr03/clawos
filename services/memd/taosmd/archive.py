# SPDX-License-Identifier: AGPL-3.0-or-later
"""
archive — Append-only JSONL event store with FTS5 index.

Daily files: memory/archive/YYYY-MM-DD.jsonl
FTS5 index with Porter stemming tokenizer.
compress_old_files() gzips completed days (called by scheduler at 3AM).
Zero extra dependencies beyond stdlib + sqlite3.
"""
from __future__ import annotations

import gzip
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("memd.archive")


class ArchiveStore:
    def __init__(self, archive_dir: str | Path):
        self.archive_dir = Path(archive_dir)
        self._db_path = self.archive_dir / "fts_index.db"
        self._ensure_db()

    # ── Public API ────────────────────────────────────────────────────────────

    def record(
        self,
        event_type: str,
        payload: dict[str, Any],
        agent_name: str = "nexus",
        ts: float | None = None,
    ) -> str:
        """Append an event to today's JSONL file and index in FTS5."""
        if ts is None:
            ts = time.time()
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        event_id = f"{agent_name}-{int(ts*1000)}"
        entry = {
            "id": event_id,
            "event_type": event_type,
            "agent": agent_name,
            "ts": ts,
            "iso": dt.isoformat(),
            "payload": payload,
        }
        self._write_jsonl(dt, entry)
        self._index_entry(event_id, event_type, agent_name, payload, dt.isoformat())
        return event_id

    def search(
        self,
        query: str,
        limit: int = 10,
        event_type: str | None = None,
        agent: str | None = None,
    ) -> list[dict]:
        """FTS5 keyword search over indexed archive entries."""
        clean_q = _clean_fts_query(query)
        if not clean_q:
            return []
        db = self._open_db()
        try:
            if event_type and agent:
                rows = db.execute(
                    "SELECT id, event_type, agent, ts, iso, snippet FROM archive_fts "
                    "WHERE archive_fts MATCH ? AND event_type=? AND agent=? "
                    "ORDER BY rank LIMIT ?",
                    (clean_q, event_type, agent, limit),
                ).fetchall()
            elif event_type:
                rows = db.execute(
                    "SELECT id, event_type, agent, ts, iso, snippet FROM archive_fts "
                    "WHERE archive_fts MATCH ? AND event_type=? ORDER BY rank LIMIT ?",
                    (clean_q, event_type, limit),
                ).fetchall()
            elif agent:
                rows = db.execute(
                    "SELECT id, event_type, agent, ts, iso, snippet FROM archive_fts "
                    "WHERE archive_fts MATCH ? AND agent=? ORDER BY rank LIMIT ?",
                    (clean_q, agent, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, event_type, agent, ts, iso, snippet FROM archive_fts "
                    "WHERE archive_fts MATCH ? ORDER BY rank LIMIT ?",
                    (clean_q, limit),
                ).fetchall()
        except Exception as exc:
            log.debug("archive FTS search error: %s", exc)
            return []
        finally:
            db.close()
        return [
            {"id": r[0], "event_type": r[1], "agent": r[2],
             "ts": r[3], "iso": r[4], "snippet": r[5]}
            for r in rows
        ]

    def recent(
        self,
        limit: int = 20,
        event_type: str | None = None,
        agent: str | None = None,
    ) -> list[dict]:
        """Return most recent archive entries in reverse-chronological order."""
        db = self._open_db()
        try:
            if event_type:
                rows = db.execute(
                    "SELECT id, event_type, agent, ts, iso, snippet FROM archive_index "
                    "WHERE event_type=? ORDER BY ts DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            elif agent:
                rows = db.execute(
                    "SELECT id, event_type, agent, ts, iso, snippet FROM archive_index "
                    "WHERE agent=? ORDER BY ts DESC LIMIT ?",
                    (agent, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, event_type, agent, ts, iso, snippet FROM archive_index "
                    "ORDER BY ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        except Exception as exc:
            log.debug("archive recent error: %s", exc)
            return []
        finally:
            db.close()
        return [
            {"id": r[0], "event_type": r[1], "agent": r[2],
             "ts": r[3], "iso": r[4], "snippet": r[5]}
            for r in rows
        ]

    def compress_old_files(self, keep_days: int = 7) -> int:
        """
        Gzip JSONL files older than *keep_days* days.
        Returns number of files compressed. Safe to call repeatedly.
        """
        compressed = 0
        cutoff = time.time() - keep_days * 86400
        for jsonl_path in self.archive_dir.glob("*.jsonl"):
            try:
                mtime = jsonl_path.stat().st_mtime
                if mtime < cutoff:
                    gz_path = jsonl_path.with_suffix(".jsonl.gz")
                    if not gz_path.exists():
                        with jsonl_path.open("rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                            f_out.write(f_in.read())
                    jsonl_path.unlink()
                    compressed += 1
            except Exception as exc:
                log.warning("compress_old_files: %s: %s", jsonl_path.name, exc)
        return compressed

    # ── Internals ─────────────────────────────────────────────────────────────

    def _write_jsonl(self, dt: datetime, entry: dict) -> None:
        day_file = self.archive_dir / f"{dt.strftime('%Y-%m-%d')}.jsonl"
        day_file.parent.mkdir(parents=True, exist_ok=True)
        with day_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _index_entry(
        self,
        event_id: str,
        event_type: str,
        agent: str,
        payload: dict,
        iso: str,
    ) -> None:
        snippet = _payload_snippet(payload)
        ts = time.time()
        db = self._open_db()
        try:
            # FTS virtual table
            db.execute(
                "INSERT OR REPLACE INTO archive_fts(id, event_type, agent, ts, iso, snippet) "
                "VALUES (?,?,?,?,?,?)",
                (event_id, event_type, agent, ts, iso, snippet),
            )
            # Regular index for recency queries
            db.execute(
                "INSERT OR REPLACE INTO archive_index(id, event_type, agent, ts, iso, snippet) "
                "VALUES (?,?,?,?,?,?)",
                (event_id, event_type, agent, ts, iso, snippet),
            )
            db.commit()
        except Exception as exc:
            log.debug("archive index error: %s", exc)
        finally:
            db.close()

    def _open_db(self) -> sqlite3.Connection:
        return self._ensure_db()

    def _ensure_db(self) -> sqlite3.Connection:
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS archive_fts USING fts5(
                id UNINDEXED,
                event_type UNINDEXED,
                agent UNINDEXED,
                ts UNINDEXED,
                iso UNINDEXED,
                snippet,
                tokenize='porter ascii'
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS archive_index (
                id         TEXT PRIMARY KEY,
                event_type TEXT,
                agent      TEXT,
                ts         REAL,
                iso        TEXT,
                snippet    TEXT
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_archive_ts ON archive_index(ts DESC)")
        db.commit()
        return db


def _payload_snippet(payload: dict, max_len: int = 300) -> str:
    """Extract a human-readable text snippet from a payload dict."""
    for key in ("content", "text", "message", "summary", "output", "result"):
        val = payload.get(key, "")
        if val and isinstance(val, str):
            return val[:max_len]
    # Fall back to JSON dump truncated
    return json.dumps(payload, ensure_ascii=False)[:max_len]


def _clean_fts_query(query: str) -> str:
    """Strip FTS5-unsafe characters and return cleaned query string."""
    import re
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    tokens = [t for t in cleaned.split() if len(t) > 1]
    return " ".join(tokens)
