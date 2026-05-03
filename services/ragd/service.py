# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS RAGd — Per-workspace document RAG service
=================================================
Ingests PDF, txt, md, docx files into a workspace-scoped SQLite + ChromaDB
index. Retrieves relevant chunks at query time with citations.

Ported from DoomsdayDeck v4 (ingest_v3.py + rag_shell_v4.py).
Key changes from original:
  - Workspace-scoped paths (not hardcoded /data/knowledge/)
  - Ollama nomic-embed-text instead of sentence-transformers
  - domain = workspace name (not filename-guessed)
  - Supports PDF, txt, md, docx (not just PDF)
  - Integrated into ClawOS runtime — not a standalone shell
"""

import hashlib
import json
import logging
import re
import sqlite3
import unicodedata
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
import subprocess

log = logging.getLogger("ragd")

# ── Config ────────────────────────────────────────────────────────────────────

CHUNK_WORDS      = 220
CHUNK_OVERLAP    = 40
MIN_CHUNK_WORDS  = 40
MIN_CHUNK_SCORE  = 0.0
TOC_SCAN_MAX_PAGE = 20
TOP_K            = 5
DISTANCE_THRESH  = 400.0
EMBED_MODEL      = "nomic-embed-text"   # via Ollama

# Read from constants so OLLAMA_HOST env var works everywhere
try:
    from clawos_core.constants import OLLAMA_HOST
except ImportError:
    import os
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# ── CrossEncoder reranking (Aether pattern) ──────────────────────────────────
# Optional — gracefully skipped when cross-encoder package unavailable.
# Reduces hallucination by 70% according to Aether benchmarks.

_RERANK_THRESHOLD = 0.7    # minimum cross-encoder score to keep
_RERANK_TOP_K_IN  = 10     # how many candidates to feed the reranker

_cross_encoder = None
_cross_encoder_tried = False


def _get_cross_encoder():
    global _cross_encoder, _cross_encoder_tried
    if _cross_encoder_tried:
        return _cross_encoder
    _cross_encoder_tried = True
    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        log.info("ragd: CrossEncoder reranker loaded")
    except (ImportError, OSError, RuntimeError) as exc:
        log.debug("ragd: CrossEncoder unavailable (%s) — using vector-only ranking", exc)
        _cross_encoder = None
    return _cross_encoder


def _crossencoder_rerank(query: str, results: list, top_k: int = 5) -> list:
    """
    Rerank *results* using CrossEncoder. Returns top_k above threshold.
    Falls back to the original order if CrossEncoder unavailable.
    """
    if not results:
        return results
    model = _get_cross_encoder()
    if model is None:
        return results
    candidates = results[:_RERANK_TOP_K_IN]
    try:
        pairs = [(query, r["content"]) for r in candidates]
        scores = model.predict(pairs)
        scored = sorted(
            zip(scores, candidates), key=lambda x: x[0], reverse=True
        )
        reranked = [r for score, r in scored if score >= _RERANK_THRESHOLD]
        if not reranked:
            # Nothing passed threshold — return top by score regardless
            reranked = [r for _, r in scored]
        return reranked[:top_k]
    except (OSError, RuntimeError, AttributeError) as exc:
        log.debug("ragd: CrossEncoder rerank error: %s", exc)
        return results


# ── Boilerplate patterns (from DoomsdayDeck v4) ───────────────────────────────

_BOILERPLATE = [
    r"all rights reserved",
    r"no part of this (book|publication|document|work) may be",
    r"printed in the (united states|u\.s\.a)",
    r"library of congress",
    r"isbn[\s:\-\u2013\u2014][\dX\-]{5,}",
    r"copyright\s*[\u00a9\(c\)]\s*\d{4}",
    r"visit (our )?(web\s*site|website|www\.|homepage)",
    r"^\s*www\.\S+\.(com|org|net|io)\s*$",
    r"^\s*(table of contents|contents)\s*$",
    r"^\s*(index|bibliography|references|glossary|appendix|foreword|preface|acknowledgements?)\s*$",
    r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$",
    r"^\s*\d+\s*$",
    r"(\.{4,}\s*\d+\s*\n?){3,}",
    r"^\s*[-\u2013\u2014]{10,}\s*$",
]

# ── Chunk type detection rules (from DoomsdayDeck v4) ─────────────────────────

_CHUNK_TYPE_RULES = [
    ("warning", [
        r"(?i)^(warning|caution|danger|note|important|critical)[:\s!]",
        r"(?i)\b(do not|never|always|must not|hazardous|toxic|lethal|fatal)\b",
        r"(?i)(WARNING|CAUTION|DANGER):",
    ]),
    ("procedure", [
        r"(?m)^\s*\d+[\.]\s+[A-Z]",
        r"(?m)^\s*step\s+\d+",
        r"(?i)\b(apply|insert|remove|press|turn|connect|disconnect|install|attach|pull|push|fill|drain|heat|cool|tie|cut|place|position)\b",
    ]),
    ("table", [
        r"(?m)^(\s*[\w\d\.\-]+\s{2,}){3,}",
        r"(?i)(mg|ml|kg|lb|oz|psi|rpm|volt|amp)\s*/\s*",
        r"\|\s*\w+\s*\|",
    ]),
    ("definition", [
        r"(?i)\b\w+ (is|are|refers to|means|defined as|describes) ",
        r"(?i)^definition[:\s]",
        r"(?i)^(term|glossary)[:\s]",
    ]),
    ("reference", [
        r"(?i)(formula|equation|ratio|rate|concentration|dosage|specification)",
        r"\d+\s*(mg|ml|kg|lb|oz|psi|rpm|°[CF]|watts?|amps?|volts?)",
        r"(?i)(see also|refer to|reference|source|citation|ibid|et al)",
        r"(?i)(table \d+|figure \d+|appendix)",
    ]),
    ("narrative", [
        r"(?i)\b(in this chapter|the following|as we have seen|historically|it is important to understand)\b",
        r"(?i)\b(background|overview|introduction|context|history)\b",
    ]),
]

# Query intent → preferred chunk types (from DoomsdayDeck v4)
_INTENT_PATTERNS = [
    (r"\b(how do i|how to|steps to|procedure for|instructions|process for)\b",
     ["procedure", "warning", "reference"]),
    (r"\b(what is|define|definition of|meaning of|what does .+ mean)\b",
     ["definition", "reference", "narrative"]),
    (r"\b(how much|ratio|dosage|dose|concentration|amount|proportion)\b",
     ["table", "reference", "warning"]),
    (r"\b(warnings?|dangers?|hazards?|risks?|caution|toxic|lethal|unsafe)\b",
     ["warning", "procedure", "reference"]),
    (r"\b(compare|difference|vs\.?|versus|pros and cons|better)\b",
     ["narrative", "reference", "table"]),
    (r"\b(calculate|formula|equation|convert|conversion)\b",
     ["table", "reference"]),
]

# Ligature / unicode map (from DoomsdayDeck v4)
_LIGATURE_MAP = str.maketrans({
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
    "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
    "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2022": "-", "\u00a0": " ",
})

# ── SQLite schema ─────────────────────────────────────────────────────────────

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS docs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    domain      TEXT,
    file_path   TEXT NOT NULL UNIQUE,
    file_type   TEXT DEFAULT 'pdf',
    page_count  INTEGER,
    chunk_count INTEGER DEFAULT 0,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      INTEGER NOT NULL REFERENCES docs(id),
    chunk_id    TEXT NOT NULL UNIQUE,
    page_number INTEGER,
    word_count  INTEGER,
    quality     REAL,
    chunk_type  TEXT DEFAULT 'unknown',
    content     TEXT NOT NULL,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_docs_file_path  ON docs(file_path);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id   ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_quality  ON chunks(quality);
CREATE INDEX IF NOT EXISTS idx_chunks_type     ON chunks(chunk_type);
"""


# ── RAGService ────────────────────────────────────────────────────────────────

class RAGService:
    """
    Per-workspace document RAG.
    Each workspace gets its own SQLite DB and ChromaDB collection.
    """

    def __init__(self, workspace_name: str, workspace_root: Path):
        self.workspace   = workspace_name
        self.root        = workspace_root
        self.rag_dir     = workspace_root / "rag"
        self.db_path     = self.rag_dir / "library.db"
        self.chroma_dir  = self.rag_dir / "chroma"
        self.uploads_dir = workspace_root / "uploads"

        self.rag_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

        self._db         = None
        self._collection = None

    # ── Setup ──────────────────────────────────────────────────────────────

    def _get_db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(self.db_path, check_same_thread=False)
            self._db.executescript(_SCHEMA)
            self._db.commit()
        return self._db

    def _get_collection(self):
        if self._collection is None:
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(self.chroma_dir))
                self._collection = client.get_or_create_collection(
                    name=f"rag_{self.workspace}",
                    metadata={"workspace": self.workspace},
                    embedding_function=chromadb.utils.embedding_functions.DefaultEmbeddingFunction(),
                )
            except ImportError:
                log.warning("chromadb not installed — RAG unavailable")
                return None
        return self._collection

    # ── Text cleaning (DoomsdayDeck v4) ───────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        text = text.translate(_LIGATURE_MAP)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
        text = re.sub(r"\r", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _is_boilerplate(text: str) -> bool:
        lower = text.lower()
        for pat in _BOILERPLATE:
            if re.search(pat, lower, re.MULTILINE | re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _is_toc_page(text: str, page_num: int) -> bool:
        if page_num > TOC_SCAN_MAX_PAGE:
            return False
        words = text.split()
        if len(words) < 8:
            return True
        dot_leaders = len(re.findall(r"\.{4,}", text))
        page_refs   = len(re.findall(r"\b\d{1,4}\b", text))
        if dot_leaders >= 3:
            return True
        if words and page_refs / len(words) > 0.35:
            return True
        return False

    @staticmethod
    def _chunk_quality_score(text: str) -> float:
        words = text.split()
        if len(words) < MIN_CHUNK_WORDS:
            return 0.0
        alpha_words   = sum(1 for w in words if re.search(r"[a-zA-Z]{3,}", w))
        alpha_ratio   = alpha_words / len(words)
        numeric_words = sum(1 for w in words if re.fullmatch(r"[\d\W]+", w))
        numeric_ratio = numeric_words / len(words)
        lines         = [l.strip() for l in text.splitlines() if l.strip()]
        short_lines   = sum(1 for l in lines if len(l.split()) <= 3)
        short_ratio   = short_lines / max(len(lines), 1)
        sent_ends     = len(re.findall(r"[.!?]", text))
        expected      = max(len(words) / 15, 1)
        sent_ratio    = min(sent_ends / expected, 1.0)
        score = (
            alpha_ratio   * 0.45 +
            (1-numeric_ratio) * 0.20 +
            (1-short_ratio)   * 0.20 +
            sent_ratio        * 0.15
        )
        return round(min(score, 1.0), 4)

    @staticmethod
    def _detect_chunk_type(text: str) -> str:
        for chunk_type, patterns in _CHUNK_TYPE_RULES:
            for pat in patterns:
                if re.search(pat, text):
                    return chunk_type
        words     = text.split()
        sentences = len(re.findall(r"[.!?]", text))
        expected  = max(len(words) / 15, 1)
        if sentences / expected > 0.5:
            return "narrative"
        return "unknown"

    @staticmethod
    def _chunk_text(text: str):
        """Paragraph-boundary aware sliding window chunking."""
        paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
        real_words = []
        for para in paragraphs:
            real_words.extend(para.split())

        chunks = []
        start  = 0
        while start < len(real_words):
            end   = min(start + CHUNK_WORDS, len(real_words))
            chunk = " ".join(real_words[start:end]).strip()
            if chunk:
                chunks.append((chunk, end - start))
            if end >= len(real_words):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
        return chunks

    @staticmethod
    def _build_chunk_id(file_path: Path, page_num: int,
                        chunk_idx: int, content: str) -> str:
        digest = hashlib.sha1(content.encode()).hexdigest()[:12]
        return f"{file_path.stem}-p{page_num:04d}-c{chunk_idx:03d}-{digest}"

    # ── File extraction ────────────────────────────────────────────────────

    def _extract_pages(self, path: Path) -> list:
        """
        Returns list of (page_num, text) tuples.
        Supports pdf, txt, md, docx.
        """
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return self._extract_pdf(path)
        elif suffix in (".txt", ".md"):
            return self._extract_text(path)
        elif suffix == ".docx":
            return self._extract_docx(path)
        else:
            # Try as plain text
            return self._extract_text(path)

    def _extract_pdf(self, path: Path) -> list:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            try:
                import pypdf as _pypdf
                PdfReader = _pypdf.PdfReader
            except ImportError:
                log.error("PyPDF2 or pypdf required: pip install pypdf")
                return []

        pages = []
        try:
            reader = PdfReader(str(path), strict=False)
        except (OSError, ValueError, ImportError) as e:
            log.error(f"Cannot open PDF {path.name}: {e}")
            return []

        for i, page in enumerate(reader.pages):
            page_num = i + 1
            try:
                raw = page.extract_text() or ""
            except (OSError, ValueError, AttributeError) as e:
                log.warning(f"Page {page_num} extraction error: {e}")
                continue
            text = self._normalize(raw)
            if len(text.split()) < 8:
                continue
            if self._is_toc_page(text, page_num):
                continue
            if self._is_boilerplate(text):
                continue
            pages.append((page_num, text))
        return pages

    def _extract_text(self, path: Path) -> list:
        try:
            raw  = path.read_text(errors="replace")
            text = self._normalize(raw)
            if not text.strip():
                return []
            # Split into virtual "pages" of ~500 words each
            words    = text.split()
            page_size = 500
            pages    = []
            for i in range(0, len(words), page_size):
                chunk_text = " ".join(words[i:i + page_size])
                if chunk_text.strip():
                    pages.append((i // page_size + 1, chunk_text))
            return pages
        except (OSError, UnicodeDecodeError) as e:
            log.error(f"Cannot read {path.name}: {e}")
            return []

    def _extract_docx(self, path: Path) -> list:
        try:
            import docx
            doc   = docx.Document(str(path))
            full  = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return self._extract_text_from_string(full)
        except ImportError:
            log.warning("python-docx not installed, reading .docx as zip text")
            return self._extract_text(path)
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            log.error(f"Cannot read docx {path.name}: {e}")
            return []

    def _extract_text_from_string(self, text: str) -> list:
        text  = self._normalize(text)
        words = text.split()
        pages = []
        page_size = 500
        for i in range(0, len(words), page_size):
            chunk = " ".join(words[i:i + page_size])
            if chunk.strip():
                pages.append((i // page_size + 1, chunk))
        return pages

    # ── Embeddings via Ollama ──────────────────────────────────────────────

    def _embed(self, texts: list) -> list:
        """Get embeddings from Ollama nomic-embed-text."""
        embeddings = []
        for text in texts:
            try:
                payload = json.dumps({
                    "model": EMBED_MODEL,
                    "prompt": text,
                }).encode()
                req = urllib.request.Request(
                    f"{OLLAMA_HOST}/api/embeddings",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read())
                embeddings.append(data["embedding"])
            except (json.JSONDecodeError, ValueError) as e:
                log.warning(f"Embed error: {e}")
                embeddings.append(None)
        return embeddings

    def _ensure_embed_model(self) -> bool:
        """Pull nomic-embed-text if not present."""
        try:
            r = urllib.request.urlopen(
                f"{OLLAMA_HOST}/api/tags", timeout=5
            )
            tags = json.loads(r.read())
            models = [m["name"] for m in tags.get("models", [])]
            if any("nomic-embed-text" in m for m in models):
                return True
            # Pull it
            log.info("Pulling nomic-embed-text embedding model...")
            payload = json.dumps({"name": EMBED_MODEL}).encode()
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
            return True
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(f"Could not ensure embed model: {e}")
            return False

    # ── Ingestion ──────────────────────────────────────────────────────────

    def ingest(self, file_path: Path, force: bool = False) -> dict:
        """
        Ingest a document into this workspace's RAG index.
        Returns stats dict.
        """
        stats = {
            "file": file_path.name,
            "skipped": False,
            "skip_reason": "",
            "page_count": 0,
            "chunks_kept": 0,
            "chunks_dropped": 0,
            "chunk_types": {},
        }

        db = self._get_db()

        # Check duplicate
        if not force:
            existing = db.execute(
                "SELECT id FROM docs WHERE file_path = ?", (str(file_path),)
            ).fetchone()
            if existing:
                stats["skipped"]     = True
                stats["skip_reason"] = "already ingested"
                return stats

        # Remove if force
        if force:
            row = db.execute(
                "SELECT id FROM docs WHERE file_path = ?", (str(file_path),)
            ).fetchone()
            if row:
                db.execute("DELETE FROM chunks WHERE doc_id = ?", (row[0],))
                db.execute("DELETE FROM docs WHERE id = ?", (row[0],))
                db.commit()

        # Extract pages
        pages = self._extract_pages(file_path)
        if not pages:
            stats["skipped"]     = True
            stats["skip_reason"] = "no usable text extracted"
            return stats

        stats["page_count"] = len(pages)
        title     = file_path.stem
        file_type = file_path.suffix.lstrip(".").lower()
        domain    = self.workspace

        # Insert doc
        cur = db.cursor()
        cur.execute(
            "INSERT INTO docs (title, domain, file_path, file_type, page_count)"
            " VALUES (?, ?, ?, ?, ?)",
            (title, domain, str(file_path), file_type, len(pages)),
        )
        doc_id = cur.lastrowid
        db.commit()

        # Chunk, score, insert
        all_chunks   = []  # (chunk_id, page_num, word_count, quality, chunk_type, content)
        type_counts  = {}
        kept = dropped = 0

        for page_num, page_text in pages:
            raw_chunks = self._chunk_text(page_text)
            for chunk_idx, (chunk, word_count) in enumerate(raw_chunks, 1):
                quality = self._chunk_quality_score(chunk)
                if quality < MIN_CHUNK_SCORE:
                    dropped += 1
                    continue
                chunk_type = self._detect_chunk_type(chunk)
                chunk_id   = self._build_chunk_id(file_path, page_num, chunk_idx, chunk)
                type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
                all_chunks.append((chunk_id, page_num, word_count, quality, chunk_type, chunk))
                kept += 1

        # Batch insert into SQLite
        for chunk_id, page_num, word_count, quality, chunk_type, content in all_chunks:
            try:
                db.execute(
                    "INSERT INTO chunks"
                    " (doc_id, chunk_id, page_number, word_count, quality, chunk_type, content)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (doc_id, chunk_id, page_num, word_count, quality, chunk_type, content),
                )
            except sqlite3.IntegrityError:
                kept -= 1
        db.execute("UPDATE docs SET chunk_count = ? WHERE id = ?", (kept, doc_id))
        db.commit()

        # Embed and index into ChromaDB
        collection = self._get_collection()
        if collection and all_chunks:
            self._ensure_embed_model()
            contents   = [c[5] for c in all_chunks]
            embeddings = self._embed(contents)
            ids, docs_batch, metas, embeds = [], [], [], []
            for (chunk_id, page_num, word_count, quality, chunk_type, content), emb in zip(all_chunks, embeddings):
                if emb is None:
                    continue
                ids.append(chunk_id)
                docs_batch.append(content)
                metas.append({
                    "title":      title,
                    "domain":     domain,
                    "page_number": page_num,
                    "chunk_type": chunk_type,
                    "quality":    quality,
                    "file_path":  str(file_path),
                })
                embeds.append(emb)
            if ids:
                # Batch in groups of 64
                for i in range(0, len(ids), 64):
                    collection.add(
                        ids=ids[i:i+64],
                        documents=docs_batch[i:i+64],
                        metadatas=metas[i:i+64],
                        embeddings=embeds[i:i+64],
                    )

        stats["chunks_kept"]    = kept
        stats["chunks_dropped"] = dropped
        stats["chunk_types"]    = type_counts
        log.info(f"Ingested {file_path.name}: {kept} chunks kept, {dropped} dropped")
        return stats

    def forget(self, filename: str) -> bool:
        """Remove a document and all its chunks from the index."""
        db  = self._get_db()
        col = self._get_collection()

        row = db.execute(
            "SELECT id FROM docs WHERE title = ? OR file_path LIKE ?",
            (Path(filename).stem, f"%{filename}%"),
        ).fetchone()

        if not row:
            return False

        doc_id = row[0]
        # Get chunk IDs for ChromaDB removal
        chunk_ids = [r[0] for r in db.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchall()]

        db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        db.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
        db.commit()

        if col and chunk_ids:
            try:
                col.delete(ids=chunk_ids)
            except (OSError, AttributeError, RuntimeError) as e:
                log.warning(f"ChromaDB delete error: {e}")

        log.info(f"Removed {filename} from RAG index")
        return True

    # ── Retrieval ──────────────────────────────────────────────────────────

    @staticmethod
    def _detect_preferred_types(query: str) -> list:
        q = query.lower()
        for pattern, types in _INTENT_PATTERNS:
            if re.search(pattern, q):
                return types
        return []

    def retrieve(self, query: str, top_k: int = TOP_K) -> list:
        """
        Retrieve top_k relevant chunks for query.
        Returns list of result dicts with content + citation metadata.
        """
        collection = self._get_collection()
        if not collection:
            return []

        # Embed query via Ollama directly (same model used at ingest time)
        import urllib.request as _ur, json as _json
        try:
            _payload = _json.dumps({"model": EMBED_MODEL, "prompt": query}).encode()
            _req = _ur.Request(f"{OLLAMA_HOST}/api/embeddings", data=_payload,
                               headers={"Content-Type": "application/json"})
            with _ur.urlopen(_req, timeout=30) as _r:
                query_emb = _json.loads(_r.read())["embedding"]
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(f"Embed query failed: {e}")
            return []

        try:
            raw = collection.query(
                query_embeddings=[query_emb],
                n_results=top_k * 3,
                include=["documents", "metadatas", "distances"],
            )
        except (OSError, AttributeError, RuntimeError) as e:
            log.warning(f"ChromaDB query error: {e}")
            return []

        docs      = raw.get("documents", [[]])[0]
        metas     = raw.get("metadatas",  [[]])[0]
        distances = raw.get("distances",  [[]])[0]

        results = []
        for doc, meta, dist in zip(docs, metas, distances):
            quality = float(meta.get("quality", 0.0))
            if quality < MIN_CHUNK_SCORE or dist > DISTANCE_THRESH:
                continue
            results.append({
                "content":    doc,
                "title":      meta.get("title", "unknown"),
                "page":       meta.get("page_number", "?"),
                "chunk_type": meta.get("chunk_type", "unknown"),
                "quality":    quality,
                "distance":   dist,
                "file_path":  meta.get("file_path", ""),
            })

        # CrossEncoder reranking (Aether pattern) — graceful skip if unavailable
        results = _crossencoder_rerank(query, results, top_k=top_k)
        if not results:
            # Fallback: rerank by preferred chunk types
            preferred = self._detect_preferred_types(query)
            if preferred and results:
                def sort_key(r):
                    try:
                        return preferred.index(r["chunk_type"])
                    except ValueError:
                        return len(preferred)
                results.sort(key=sort_key)

        return results[:top_k]

    # ── Answer generation ──────────────────────────────────────────────────

    @staticmethod
    def _score_sentence(query: str, sentence: str) -> int:
        """BM25-style sentence scoring (from DoomsdayDeck v4)."""
        q_words = {
            w.lower() for w in re.findall(r"[a-zA-Z0-9_+#]+", query)
            if len(w) >= 3
        }
        s_words = {
            w.lower() for w in re.findall(r"[a-zA-Z0-9_+#]+", sentence)
            if len(w) >= 3
        }
        return len(q_words & s_words) * 5

    def _build_extractive_context(self, query: str, results: list) -> str:
        picked, seen = [], set()
        for source_num, row in enumerate(results, 1):
            for sent in re.split(r"(?<=[.!?])\s+", row["content"]):
                s = sent.strip()
                if len(s) < 50:
                    continue
                norm = s.lower()
                if norm in seen:
                    continue
                seen.add(norm)
                score = self._score_sentence(query, s)
                picked.append((source_num, s, score))

        picked.sort(key=lambda x: x[2], reverse=True)
        final, used = [], set()
        for source_num, sent, _ in picked:
            if sent in used:
                continue
            used.add(sent)
            final.append((source_num, sent))
            if len(final) >= 5:
                break

        if not final:
            return "No useful extracted sentences found."
        return "\n".join(
            f"[FACT {i}] source=[{sn}] {s}"
            for i, (sn, s) in enumerate(final, 1)
        )

    @staticmethod
    def _build_deterministic_fallback(results: list) -> str:
        parts, seen_sources = [], []
        for source_num, row in enumerate(results[:3], 1):
            text = " ".join(row["content"].split()[:60])
            if source_num not in seen_sources:
                seen_sources.append(source_num)
                parts.append(text)
        answer = " ".join(parts[:2])
        if len(answer) < 40:
            answer = "The retrieved sources only partially answer this."
        cited = ", ".join(f"[{n}]" for n in seen_sources[:3])
        return f"Answer: {answer}\nCited Sources: {cited}"

    @staticmethod
    def _sanitize_output(raw: str, query: str, results: list,
                         fallback_fn) -> str:
        """Remove hallucinations, enforce Answer + Cited Sources format."""
        text    = raw.strip()
        banned  = ["user input", "prompt", "instructions", "system"]
        lowered = text.lower()
        for pat in banned:
            if pat in lowered:
                return fallback_fn()

        a_match = re.search(
            r"Answer:\s*(.*?)(?:\nCited Sources:|\Z)", text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        c_match = re.search(
            r"Cited Sources:\s*(.*)", text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if not a_match or not c_match:
            return fallback_fn()

        answer_body = " ".join(a_match.group(1).split())
        cited_body  = c_match.group(1).strip()
        if not answer_body:
            return fallback_fn()

        valid_refs  = {f"[{i}]" for i in range(1, len(results) + 1)}
        found_refs  = [r for r in re.findall(r"\[\d+\]", cited_body) if r in valid_refs]
        if not found_refs:
            found_refs = ["[1]"]

        return f"Answer: {answer_body}\nCited Sources: {', '.join(dict.fromkeys(found_refs))}"

    def _call_ollama(self, prompt: str, model: str) -> Optional[str]:
        try:
            from clawos_core.constants import DEFAULT_MODEL, OLLAMA_HOST as OH
            _model = model or DEFAULT_MODEL
            _host  = OH
        except ImportError:
            _model = model or "qwen2.5:7b"
            _host  = OLLAMA_HOST

        try:
            payload = json.dumps({
                "model":  _model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "top_p": 0.8, "num_predict": 200},
            }).encode()
            req = urllib.request.Request(
                f"{_host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read()).get("response", "").strip()
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(f"Ollama call failed: {e}")
            return None

    def answer(self, query: str, model: str = None) -> dict:
        """
        Full RAG pipeline: retrieve → extract context → LLM answer → citations.
        Returns dict with answer, trust_label, sources list.
        """
        results = self.retrieve(query)

        if not results:
            return {
                "answer":      "No relevant documents found in this project's index.",
                "trust_label": "No Results",
                "sources":     [],
            }

        context = self._build_extractive_context(query, results)
        prompt  = (
            "Answer the question using ONLY the extracted facts below.\n"
            "Hard rules:\n"
            "- Use only the facts below.\n"
            "- Do not invent anything.\n"
            "- Keep the answer to 2-5 sentences.\n"
            "- If facts only partially answer, say: "
            "\"The retrieved sources only partially answer this.\"\n"
            "- End with exactly: Cited Sources: [1], [2]\n\n"
            f"Question:\n{query}\n\n"
            f"Extracted Facts:\n{context}\n\n"
            "Output format:\n"
            "Answer: <2-5 grounded sentences>\n"
            "Cited Sources: [n], [m]\n"
        )

        raw = self._call_ollama(prompt, model)

        def fallback():
            return self._build_deterministic_fallback(results)

        if raw:
            final = self._sanitize_output(raw, query, results, fallback)
        else:
            final = fallback()

        # Parse answer + cited sources from final
        a_match = re.search(r"Answer:\s*(.*?)(?:\nCited|$)", final, re.DOTALL)
        c_match = re.search(r"Cited Sources:\s*(.*)", final)
        answer_text  = a_match.group(1).strip() if a_match else final
        cited_refs   = re.findall(r"\[(\d+)\]", c_match.group(1) if c_match else "")

        # Build source list for cited refs
        sources = []
        for ref in cited_refs:
            idx = int(ref) - 1
            if 0 <= idx < len(results):
                r = results[idx]
                sources.append({
                    "ref":        f"[{ref}]",
                    "title":      r["title"],
                    "page":       r["page"],
                    "chunk_type": r["chunk_type"],
                    "distance":   round(r["distance"], 4),
                })

        # Trust label
        trust = "Source-Grounded" if (
            results and results[0]["distance"] <= 0.90
        ) else "Speculative"

        return {
            "answer":      answer_text,
            "trust_label": trust,
            "sources":     sources,
            "raw_results": results,
        }

    # ── File listing ───────────────────────────────────────────────────────

    def list_files(self) -> list:
        """List all ingested documents in this workspace."""
        db = self._get_db()
        rows = db.execute(
            "SELECT title, file_type, chunk_count, added_at FROM docs ORDER BY added_at DESC"
        ).fetchall()
        return [
            {"title": r[0], "type": r[1], "chunks": r[2], "added": r[3]}
            for r in rows
        ]

    def stats(self) -> dict:
        db  = self._get_db()
        col = self._get_collection()
        doc_count   = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        chunk_count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        vec_count   = 0
        try:
            if col:
                vec_count = col.count()
        except (OSError, AttributeError, RuntimeError) as e:
            log.debug(f"unexpected: {e}")
            pass
        return {
            "workspace":   self.workspace,
            "documents":   doc_count,
            "chunks":      chunk_count,
            "vectors":     vec_count,
            "embed_model": EMBED_MODEL,
        }

    def close(self):
        if self._db:
            self._db.close()
            self._db = None


# ── Registry: one RAGService per workspace ────────────────────────────────────

_registry: dict = {}


def get_rag(workspace_name: str, workspace_root: Path) -> RAGService:
    key = workspace_name
    if key not in _registry:
        _registry[key] = RAGService(workspace_name, workspace_root)
    return _registry[key]
