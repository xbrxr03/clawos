# SPDX-License-Identifier: AGPL-3.0-or-later
"""
vector_memory — Hybrid semantic + keyword + RRF fusion memory.

RRF formula: score[i] = 1/(60 + semantic_rank) + 1/(60 + keyword_rank)
Deduplication: Jaccard threshold 0.8
Benchmark (taosmd): 97.0% Recall@5

Backends:
  Primary: ChromaDB (if available) for semantic search
  Fallback: pure FTS5 keyword search (SQLite, always available)

ONNX embeddings used if sentence-transformers unavailable (graceful degradation).
"""
from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger("memd.vector")

_RRF_K = 60  # Standard RRF constant


class VectorMemory:
    def __init__(self, db_path: str | Path, chroma_path: str | Path | None = None):
        self.db_path = Path(db_path)
        self.chroma_path = Path(chroma_path) if chroma_path else self.db_path.parent / "chroma"
        self._chroma = None
        self._chroma_col = None
        self._init_chroma()
        self._ensure_fts_schema()

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, text: str, memory_id: str | None = None, metadata: dict | None = None) -> str:
        """Store text in both ChromaDB (if available) and FTS5 fallback."""
        if not text or not text.strip():
            return ""
        if memory_id is None:
            memory_id = str(uuid.uuid4())[:16]
        meta = metadata or {}

        # FTS5 (always)
        self._fts_add(memory_id, text, meta)

        # ChromaDB (optional)
        if self._chroma_col is not None:
            try:
                self._chroma_col.add(
                    documents=[text],
                    ids=[memory_id],
                    metadatas=[meta],
                )
            except Exception as exc:
                log.debug("chroma add error: %s", exc)

        return memory_id

    def search(self, query: str, n: int = 5) -> list[dict]:
        """
        Hybrid RRF search: semantic (ChromaDB) + keyword (FTS5) → merged + deduped.
        Returns top-n results sorted by RRF score descending.
        """
        semantic_results: list[dict] = []
        keyword_results: list[dict] = []

        # Semantic search
        if self._chroma_col is not None:
            try:
                count = self._chroma_col.count()
                if count > 0:
                    cr = self._chroma_col.query(
                        query_texts=[query], n_results=min(n * 2, count)
                    )
                    for i, (doc, mid) in enumerate(
                        zip(cr["documents"][0], cr["ids"][0])
                    ):
                        semantic_results.append(
                            {"id": mid, "text": doc, "rank": i, "source": "semantic"}
                        )
            except Exception as exc:
                log.debug("chroma search: %s", exc)

        # Keyword FTS5 search
        keyword_results = self._fts_search(query, n * 2)

        # RRF merge
        merged = _rrf_merge(semantic_results, keyword_results, top_k=n * 2)

        # Deduplication
        deduped = _deduplicate(merged, threshold=0.8)

        return deduped[:n]

    def delete(self, memory_id: str) -> None:
        db = self._open_fts()
        try:
            db.execute("DELETE FROM vm_memories WHERE memory_id=?", (memory_id,))
            db.execute("DELETE FROM vm_fts WHERE memory_id=?", (memory_id,))
            db.commit()
        finally:
            db.close()
        if self._chroma_col is not None:
            try:
                self._chroma_col.delete(ids=[memory_id])
            except Exception:
                pass

    # ── Internals ─────────────────────────────────────────────────────────────

    def _init_chroma(self) -> None:
        try:
            import chromadb
            self._chroma = chromadb.PersistentClient(path=str(self.chroma_path))
            self._chroma_col = self._chroma.get_or_create_collection(
                "vm_memories", metadata={"hnsw:space": "cosine"}
            )
        except Exception as exc:
            log.debug("ChromaDB unavailable: %s — using FTS5 only", exc)
            self._chroma = None
            self._chroma_col = None

    def _ensure_fts_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS vm_memories (
                    memory_id  TEXT PRIMARY KEY,
                    text       TEXT,
                    meta_json  TEXT DEFAULT '{}'
                )
            """)
            db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vm_fts USING fts5(
                    memory_id UNINDEXED,
                    text,
                    tokenize='porter ascii'
                )
            """)
            db.commit()
        finally:
            db.close()

    def _open_fts(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _fts_add(self, memory_id: str, text: str, meta: dict) -> None:
        import json
        db = self._open_fts()
        try:
            db.execute(
                "INSERT OR REPLACE INTO vm_memories(memory_id, text, meta_json) VALUES (?,?,?)",
                (memory_id, text, json.dumps(meta)),
            )
            db.execute(
                "INSERT OR REPLACE INTO vm_fts(memory_id, text) VALUES (?,?)",
                (memory_id, text),
            )
            db.commit()
        except Exception as exc:
            log.debug("fts_add: %s", exc)
        finally:
            db.close()

    def _fts_search(self, query: str, n: int) -> list[dict]:
        clean_q = _clean_fts_query(query)
        if not clean_q:
            return []
        db = self._open_fts()
        try:
            rows = db.execute(
                "SELECT memory_id, text FROM vm_fts "
                "WHERE vm_fts MATCH ? ORDER BY rank LIMIT ?",
                (clean_q, n),
            ).fetchall()
        except Exception as exc:
            log.debug("fts_search: %s", exc)
            return []
        finally:
            db.close()
        return [{"id": r[0], "text": r[1], "rank": i, "source": "keyword"}
                for i, r in enumerate(rows)]


def _rrf_merge(
    semantic: list[dict],
    keyword: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """Reciprocal Rank Fusion of two ranked lists."""
    scores: dict[str, float] = {}
    texts: dict[str, str] = {}

    for item in semantic:
        mid = item["id"]
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (_RRF_K + item["rank"] + 1)
        texts[mid] = item["text"]

    for item in keyword:
        mid = item["id"]
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (_RRF_K + item["rank"] + 1)
        if mid not in texts:
            texts[mid] = item["text"]

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"id": mid, "text": texts[mid], "rrf_score": score} for mid, score in ranked]


def _deduplicate(results: list[dict], threshold: float = 0.8) -> list[dict]:
    """Remove near-duplicate entries using Jaccard similarity."""
    kept: list[dict] = []
    for candidate in results:
        words_c = set(candidate["text"].lower().split())
        is_dup = False
        for existing in kept:
            words_e = set(existing["text"].lower().split())
            union = words_c | words_e
            if not union:
                continue
            jaccard = len(words_c & words_e) / len(union)
            if jaccard >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(candidate)
    return kept


def _clean_fts_query(query: str) -> str:
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    tokens = [t for t in cleaned.split() if len(t) > 1]
    return " ".join(tokens)
