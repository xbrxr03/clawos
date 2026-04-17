# SPDX-License-Identifier: AGPL-3.0-or-later
"""
knowledge_graph — Temporal Knowledge Graph with validity windows.

SQLite only. Supports:
- add_triple_with_contradiction_check() — auto-invalidates superseded facts
- query_entity(name, as_of=timestamp) — point-in-time queries
- 10 predicates: uses, created, works_on, prefers, manages, has,
                 supports, depends_on, monitors, is_a
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("memd.kg")

# Predicates that are mutually exclusive per (subject, predicate) pair.
# Adding a new triple for one of these predicates invalidates prior ones.
_EXCLUSIVE_PREDICATES = {
    "uses",       # "nexus uses langchain" → "nexus uses smolagents" (supersedes)
    "prefers",    # "user prefers dark mode" → updated preference
    "manages",    # single active manager for an entity
    "is_a",       # identity — an entity has one type
}

_ALL_PREDICATES = {
    "uses", "created", "works_on", "prefers", "manages",
    "has", "supports", "depends_on", "monitors", "is_a",
}


@dataclass
class Triple:
    id: int
    subject: str
    predicate: str
    obj: str
    agent: str
    valid_from: float
    valid_until: Optional[float]  # None = currently valid
    confidence: float
    source: str

    @property
    def is_valid(self) -> bool:
        return self.valid_until is None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.obj,
            "agent": self.agent,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "confidence": self.confidence,
            "source": self.source,
        }


class TemporalKnowledgeGraph:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_schema()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_triple_with_contradiction_check(
        self,
        subject: str,
        predicate: str,
        obj: str,
        agent: str = "nexus",
        confidence: float = 0.8,
        source: str = "inference",
        auto_resolve: bool = True,
        now: float | None = None,
    ) -> int:
        """
        Add (subject, predicate, object) triple.

        If predicate is exclusive and a valid triple already exists for
        (subject, predicate), the old triple is invalidated (valid_until = now)
        and the new one is inserted.  Returns the new triple's rowid.
        """
        if predicate not in _ALL_PREDICATES:
            log.debug("kg: unknown predicate %r — adding anyway", predicate)
        if now is None:
            now = time.time()

        db = self._open()
        try:
            if auto_resolve and predicate in _EXCLUSIVE_PREDICATES:
                # Invalidate any currently valid triple for this (subject, predicate)
                db.execute(
                    "UPDATE triples SET valid_until=? "
                    "WHERE subject=? AND predicate=? AND valid_until IS NULL",
                    (now, subject.lower(), predicate),
                )
            cursor = db.execute(
                "INSERT INTO triples "
                "(subject, predicate, object, agent, valid_from, valid_until, confidence, source) "
                "VALUES (?,?,?,?,?,NULL,?,?)",
                (subject.lower(), predicate, obj.lower(), agent, now, confidence, source),
            )
            db.commit()
            return cursor.lastrowid
        finally:
            db.close()

    def query_entity(
        self,
        name: str,
        as_of: float | None = None,
        predicate: str | None = None,
    ) -> list[Triple]:
        """
        Return all triples where subject = *name* valid at *as_of* (default: now).
        Optionally filter by predicate.
        """
        if as_of is None:
            as_of = time.time()
        db = self._open()
        try:
            if predicate:
                rows = db.execute(
                    "SELECT id, subject, predicate, object, agent, valid_from, valid_until, "
                    "confidence, source FROM triples "
                    "WHERE subject=? AND predicate=? "
                    "AND valid_from <= ? AND (valid_until IS NULL OR valid_until > ?)"
                    "ORDER BY valid_from DESC",
                    (name.lower(), predicate, as_of, as_of),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, subject, predicate, object, agent, valid_from, valid_until, "
                    "confidence, source FROM triples "
                    "WHERE subject=? "
                    "AND valid_from <= ? AND (valid_until IS NULL OR valid_until > ?)"
                    "ORDER BY valid_from DESC",
                    (name.lower(), as_of, as_of),
                ).fetchall()
        finally:
            db.close()
        return [_row_to_triple(r) for r in rows]

    def query_object(
        self,
        obj: str,
        predicate: str | None = None,
        as_of: float | None = None,
    ) -> list[Triple]:
        """Return triples pointing to *obj* (reverse lookup)."""
        if as_of is None:
            as_of = time.time()
        db = self._open()
        try:
            if predicate:
                rows = db.execute(
                    "SELECT id, subject, predicate, object, agent, valid_from, valid_until, "
                    "confidence, source FROM triples "
                    "WHERE object=? AND predicate=? "
                    "AND valid_from <= ? AND (valid_until IS NULL OR valid_until > ?) "
                    "ORDER BY valid_from DESC",
                    (obj.lower(), predicate, as_of, as_of),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, subject, predicate, object, agent, valid_from, valid_until, "
                    "confidence, source FROM triples "
                    "WHERE object=? "
                    "AND valid_from <= ? AND (valid_until IS NULL OR valid_until > ?) "
                    "ORDER BY valid_from DESC",
                    (obj.lower(), as_of, as_of),
                ).fetchall()
        finally:
            db.close()
        return [_row_to_triple(r) for r in rows]

    def get_active_triples(self, limit: int = 100) -> list[Triple]:
        """Return currently valid triples ordered by recency."""
        now = time.time()
        db = self._open()
        try:
            rows = db.execute(
                "SELECT id, subject, predicate, object, agent, valid_from, valid_until, "
                "confidence, source FROM triples "
                "WHERE valid_until IS NULL AND valid_from <= ? "
                "ORDER BY valid_from DESC LIMIT ?",
                (now, limit),
            ).fetchall()
        finally:
            db.close()
        return [_row_to_triple(r) for r in rows]

    def invalidate(self, triple_id: int, now: float | None = None) -> bool:
        if now is None:
            now = time.time()
        db = self._open()
        try:
            db.execute(
                "UPDATE triples SET valid_until=? WHERE id=? AND valid_until IS NULL",
                (now, triple_id),
            )
            db.commit()
            return db.total_changes > 0
        finally:
            db.close()

    def format_for_context(self, name: str, max_triples: int = 20) -> str:
        """Return a compact text block of current KG facts about *name*."""
        triples = self.query_entity(name)[:max_triples]
        if not triples:
            return ""
        lines = [f"[KG: {name}]"]
        for t in triples:
            lines.append(f"  {t.subject} {t.predicate} {t.obj}  (conf={t.confidence:.2f})")
        return "\n".join(lines)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _open(self) -> sqlite3.Connection:
        return self._ensure_schema()

    def _ensure_schema(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("""
            CREATE TABLE IF NOT EXISTS triples (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject     TEXT NOT NULL,
                predicate   TEXT NOT NULL,
                object      TEXT NOT NULL,
                agent       TEXT DEFAULT 'nexus',
                valid_from  REAL NOT NULL,
                valid_until REAL,
                confidence  REAL DEFAULT 0.8,
                source      TEXT DEFAULT 'inference'
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_triples_object  ON triples(object)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_triples_pred    ON triples(predicate)")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_triples_valid ON triples(valid_until, valid_from)"
        )
        db.commit()
        return db


def _row_to_triple(row: tuple) -> Triple:
    return Triple(
        id=row[0],
        subject=row[1],
        predicate=row[2],
        obj=row[3],
        agent=row[4],
        valid_from=row[5],
        valid_until=row[6],
        confidence=row[7],
        source=row[8],
    )
