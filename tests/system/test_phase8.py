"""
ClawOS Phase 8 Test Suite
==========================
Tests: Secrets store, Project commands, RAG service (unit + integration).

Usage:
  python3 tests/system/test_phase8.py
  python3 tests/system/test_phase8.py --e2e   (needs Ollama + nomic-embed-text)
"""
import sys
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

E2E    = "--e2e" in sys.argv
passed = failed = 0


def ok(name):
    global passed; passed += 1
    print(f"  \u2713  {name}")


def fail(name, reason=""):
    global failed; failed += 1
    print(f"  \u2717  {name}" + (f" \u2014 {reason}" if reason else ""))


def section(title):
    print(f"\n  \u2500\u2500 {title}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Secrets store
# ─────────────────────────────────────────────────────────────────────────────
section("1. Secrets store imports and basics")

try:
    from services.secretd.service import SecretsStore, get_store
    ok("secretd module imports cleanly")
except Exception as e:
    fail("secretd import", str(e))

try:
    with tempfile.TemporaryDirectory() as td:
        import services.secretd.service as _s
        orig_file = _s.SECRETS_FILE
        orig_key  = _s.KEY_FILE
        _s.SECRETS_FILE = Path(td) / "secrets.enc"
        _s.KEY_FILE     = Path(td) / "secrets.key"

        store = SecretsStore()
        assert store.list_names() == [], "Should start empty"
        ok("SecretsStore initialises empty")

        assert store.set("GITHUB_TOKEN", "ghp_test123")
        assert store.get("GITHUB_TOKEN") == "ghp_test123"
        ok("set() and get() round-trip")

        assert "GITHUB_TOKEN" in store.list_names()
        ok("list_names() returns stored key")

        # Reload from disk
        store2 = SecretsStore()
        assert store2.get("GITHUB_TOKEN") == "ghp_test123"
        ok("Secrets persist across instances (encrypted on disk)")

        assert store.remove("GITHUB_TOKEN")
        assert store.get("GITHUB_TOKEN") is None
        assert store.list_names() == []
        ok("remove() deletes secret")

        assert not store.remove("NONEXISTENT")
        ok("remove() returns False for missing key")

        _s.SECRETS_FILE = orig_file
        _s.KEY_FILE     = orig_key
except Exception as e:
    fail("SecretsStore round-trip", str(e))

try:
    with tempfile.TemporaryDirectory() as td:
        import services.secretd.service as _s
        _s.SECRETS_FILE = Path(td) / "secrets.enc"
        _s.KEY_FILE     = Path(td) / "secrets.key"

        store = SecretsStore()
        store.set("API_KEY", "secret123")
        store.set("DB_PASS", "hunter2")

        env = store.inject_env({})
        assert env["API_KEY"] == "secret123"
        assert env["DB_PASS"] == "hunter2"
        ok("inject_env() merges secrets into env dict")

        # Invalid name rejected
        assert not store.set("bad name!", "value")
        assert not store.set("", "value")
        ok("set() rejects invalid names")

        _s.SECRETS_FILE = orig_file if 'orig_file' in dir() else _s.SECRETS_FILE
        _s.KEY_FILE     = orig_key  if 'orig_key'  in dir() else _s.KEY_FILE
except Exception as e:
    fail("SecretsStore inject_env + validation", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Encryption
# ─────────────────────────────────────────────────────────────────────────────
section("2. Encryption correctness")

try:
    from services.secretd.service import _xor_encrypt, _encrypt, _decrypt, _get_or_create_key
    import secrets as _secrets

    key = _secrets.token_bytes(32)
    for plaintext in ["hello", "ghp_test123", "a" * 500, "unicode: \u00e9\u00e0\u00fc"]:
        enc = _encrypt(plaintext, key)
        dec = _decrypt(enc, key)
        assert dec == plaintext, f"Round-trip failed for {plaintext[:20]!r}"
    ok("_encrypt/_decrypt round-trips for various inputs")
except Exception as e:
    fail("encryption round-trip", str(e))

try:
    from services.secretd.service import _xor_encrypt
    key = b"x" * 32
    data = b"hello world"
    enc  = _xor_encrypt(data, key)
    dec  = _xor_encrypt(enc, key)
    assert dec == data
    ok("XOR cipher is its own inverse")
except Exception as e:
    fail("XOR cipher", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 3. RAG service imports and text utilities
# ─────────────────────────────────────────────────────────────────────────────
section("3. RAGService imports and text utilities")

try:
    from services.ragd.service import RAGService, get_rag
    ok("ragd module imports cleanly")
except Exception as e:
    fail("ragd import", str(e))

try:
    from services.ragd.service import RAGService
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "workspace" / "test"
        ws.mkdir(parents=True)
        rag = RAGService("test", ws)

        # normalize_text
        raw = "Hello\r\n\n\n\nworld  \x00 \ufb01le"
        normalized = rag._normalize(raw)
        assert "\r" not in normalized
        assert "\x00" not in normalized
        assert "file" in normalized   # fi ligature replaced
        ok("_normalize() cleans control chars and ligatures")

        # is_boilerplate
        assert rag._is_boilerplate("All rights reserved. No part of this book may be reproduced.")
        assert rag._is_boilerplate("ISBN 978-0-000-00000-0")
        assert not rag._is_boilerplate("The patient presented with acute symptoms.")
        ok("_is_boilerplate() catches copyright/TOC patterns")

        # is_toc_page
        assert rag._is_toc_page("Chapter 1 ........ 5\nChapter 2 ........ 12\nChapter 3 ........ 18", 3)
        assert not rag._is_toc_page("The quick brown fox jumps over the lazy dog. " * 10, 1)
        ok("_is_toc_page() detects table of contents")
except Exception as e:
    fail("RAGService text utilities", str(e))

try:
    from services.ragd.service import RAGService
    from services.ragd.service import MIN_CHUNK_SCORE as MIN_CHUNK_SCORE_VAL
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws" / "test"
        ws.mkdir(parents=True)
        rag = RAGService("test", ws)

        # chunk_quality_score
        good_text = (
            "The patient should be administered 500mg of ibuprofen every six hours. "
            "Care must be taken to monitor blood pressure and kidney function. "
            "Discontinue if adverse reactions occur. Consult a physician before use."
        ) * 3
        bad_text = "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n" * 10

        good_score = rag._chunk_quality_score(good_text)
        bad_score  = rag._chunk_quality_score(bad_text)
        assert good_score > MIN_CHUNK_SCORE_VAL, f"Good text scored {good_score}"
        assert bad_score  < good_score,          f"Bad text should score lower"
        ok(f"_chunk_quality_score() — good={good_score:.2f} bad={bad_score:.2f}")

        # detect_chunk_type
        warning_text = "WARNING: Do not mix with other chemicals. Toxic if ingested."
        assert rag._detect_chunk_type(warning_text) == "warning"

        proc_text = "1. Apply pressure to the wound. 2. Elevate the limb. 3. Call for help."
        assert rag._detect_chunk_type(proc_text) == "procedure"

        ok("_detect_chunk_type() correctly identifies warning and procedure")
except Exception as e:
    fail("chunk quality + type detection", str(e))


try:
    from services.ragd.service import RAGService
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws" / "test"
        ws.mkdir(parents=True)
        rag = RAGService("test", ws)

        long_text = ("The quick brown fox jumps over the lazy dog. " * 20).strip()
        chunks = rag._chunk_text(long_text)
        assert len(chunks) > 0
        # All chunks should be tuples of (text, word_count)
        assert all(isinstance(c, tuple) and len(c) == 2 for c in chunks)
        # Word counts should be reasonable
        assert all(c[1] <= 220 + 10 for c in chunks)
        ok(f"_chunk_text() produces {len(chunks)} chunks with correct structure")

        # chunk_id is stable for same content
        from pathlib import Path as P
        f1 = P("/tmp/test.pdf")
        id1 = rag._build_chunk_id(f1, 1, 1, "hello world content here")
        id2 = rag._build_chunk_id(f1, 1, 1, "hello world content here")
        assert id1 == id2
        ok("_build_chunk_id() is deterministic for same content")
except Exception as e:
    fail("chunk_text + build_chunk_id", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 4. RAG text extraction (non-PDF)
# ─────────────────────────────────────────────────────────────────────────────
section("4. File extraction — txt and md")

try:
    from services.ragd.service import RAGService
    with tempfile.TemporaryDirectory() as td:
        ws    = Path(td) / "ws" / "test"
        ws.mkdir(parents=True)
        rag   = RAGService("test", ws)

        # Write a test .txt file
        txt_file = Path(td) / "test.txt"
        txt_file.write_text(
            "This is a test document. " * 30 +
            "\n\nSecond paragraph here. " * 20
        )
        pages = rag._extract_text(txt_file)
        assert len(pages) > 0
        assert all(isinstance(p, tuple) and len(p) == 2 for p in pages)
        ok(f"_extract_text() produces {len(pages)} virtual pages from .txt")

        # Markdown file
        md_file = Path(td) / "test.md"
        md_file.write_text(
            "# Title\n\n" +
            "Some content here. " * 40 +
            "\n\n## Section 2\n\n" +
            "More content. " * 30
        )
        md_pages = rag._extract_text(md_file)
        assert len(md_pages) > 0
        ok(f"_extract_text() produces {len(md_pages)} virtual pages from .md")
except Exception as e:
    fail("text/md extraction", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 5. RAG SQLite ingestion (mocked embed)
# ─────────────────────────────────────────────────────────────────────────────
section("5. RAG SQLite ingestion (mocked embeddings)")

try:
    from services.ragd.service import RAGService
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws" / "testproject"
        ws.mkdir(parents=True)
        rag = RAGService("testproject", ws)

        # Write a test txt file with enough content
        src = Path(td) / "budget.txt"
        src.write_text(
            "Q3 Revenue target is 240000 dollars. Marketing spend was 45000. "
            "The team headcount grew from 8 to 12 people during the quarter. "
            "Operating expenses totalled 180000 dollars. "
            "Net margin improved to 18 percent compared to 12 percent in Q2. " * 8
        )

        # Mock _embed and _get_collection to avoid needing Ollama + ChromaDB
        with patch.object(rag, "_embed", return_value=[[0.1] * 768]):
            with patch.object(rag, "_get_collection", return_value=None):
                with patch.object(rag, "_ensure_embed_model", return_value=True):
                    stats = rag.ingest(src)

        assert not stats.get("skipped"), f"Should not skip: {stats}"
        assert stats["chunks_kept"] > 0, "Should have kept at least 1 chunk"
        ok(f"ingest() produced {stats['chunks_kept']} chunks, {stats['chunk_types']}")

        # Verify SQLite has the data
        db = rag._get_db()
        doc_count   = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        chunk_count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        assert doc_count == 1
        assert chunk_count == stats["chunks_kept"]
        ok(f"SQLite has {doc_count} doc, {chunk_count} chunks")

        # Idempotency — second ingest should skip
        with patch.object(rag, "_embed", return_value=[[0.1] * 768]):
            with patch.object(rag, "_get_collection", return_value=None):
                stats2 = rag.ingest(src)
        assert stats2.get("skipped")
        assert stats2.get("skip_reason") == "already ingested"
        ok("Second ingest of same file is skipped (idempotent)")

        # list_files
        files = rag.list_files()
        assert len(files) == 1
        assert files[0]["title"] == "budget"
        ok("list_files() returns ingested doc")

        # forget
        ok_rm = rag.forget("budget.txt")
        assert ok_rm
        files2 = rag.list_files()
        assert len(files2) == 0
        ok("forget() removes document from index")
except Exception as e:
    fail("RAG SQLite ingestion", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 6. RAG retrieval (mocked)
# ─────────────────────────────────────────────────────────────────────────────
section("6. RAG retrieval and answer generation (mocked)")

try:
    from services.ragd.service import RAGService
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws" / "testproject"
        ws.mkdir(parents=True)
        rag = RAGService("testproject", ws)

        # Mock retrieve to return fake results
        fake_results = [
            {
                "content":    "Q3 Revenue target is 240000 dollars. Net margin was 18 percent.",
                "title":      "budget",
                "page":       1,
                "chunk_type": "reference",
                "quality":    0.72,
                "distance":   0.41,
                "file_path":  "/tmp/budget.txt",
            },
            {
                "content":    "Marketing spend was 45000 dollars during the quarter.",
                "title":      "budget",
                "page":       1,
                "chunk_type": "reference",
                "quality":    0.68,
                "distance":   0.55,
                "file_path":  "/tmp/budget.txt",
            },
        ]

        with patch.object(rag, "retrieve", return_value=fake_results):
            with patch.object(rag, "_call_ollama",
                              return_value="Answer: Q3 revenue target was 240000 dollars with 18% net margin.\nCited Sources: [1]"):
                result = rag.answer("what is the Q3 budget?")

        assert "answer" in result
        assert "trust_label" in result
        assert "sources" in result
        assert len(result["answer"]) > 10
        assert result["trust_label"] in ("Source-Grounded", "Speculative", "Deterministic-Fallback")
        ok(f"answer() returns structured result — trust: {result['trust_label']}")

        # Test no results case
        with patch.object(rag, "retrieve", return_value=[]):
            result_empty = rag.answer("something unrelated")
        assert "No relevant" in result_empty["answer"]
        assert result_empty["trust_label"] == "No Results"
        ok("answer() handles empty retrieval gracefully")
except Exception as e:
    fail("RAG retrieval + answer", str(e))


try:
    from services.ragd.service import RAGService
    assert "procedure" in RAGService._detect_preferred_types("how do I set up the server?")
    assert "definition" in RAGService._detect_preferred_types("what is a load balancer?")
    assert "warning" in RAGService._detect_preferred_types("toxic exposure hazard levels")
    assert RAGService._detect_preferred_types("hello") == []
    ok("_detect_preferred_types() maps query intent to chunk types")
except Exception as e:
    fail("detect_preferred_types", str(e))



# ─────────────────────────────────────────────────────────────────────────────
# 7. Sanitize output (DoomsdayDeck pattern)
# ─────────────────────────────────────────────────────────────────────────────
section("7. Output sanitization and fallback")

try:
    from services.ragd.service import RAGService
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws" / "test"
        ws.mkdir(parents=True)
        rag = RAGService("test", ws)

        results = [{"content": "Revenue was 240k.", "title": "budget", "page": 1,
                    "chunk_type": "reference", "quality": 0.7, "distance": 0.4, "file_path": ""}]

        # Good output passes through
        good = "Answer: Revenue was 240k.\nCited Sources: [1]"
        fallback = lambda: "Answer: Fallback.\nCited Sources: [1]"
        out = rag._sanitize_output(good, "query", results, fallback)
        assert "240k" in out
        ok("_sanitize_output() passes valid answer through")

        # Banned patterns trigger fallback
        bad = "Answer: Based on user input, the prompt says...\nCited Sources: [1]"
        out2 = rag._sanitize_output(bad, "query", results, fallback)
        assert "Fallback" in out2 or "Revenue" in out2
        ok("_sanitize_output() triggers fallback on banned patterns")

        # Missing format triggers fallback
        bad2 = "Just some raw text with no format."
        out3 = rag._sanitize_output(bad2, "query", results, fallback)
        assert "Answer:" in out3
        ok("_sanitize_output() triggers fallback on missing format")
except Exception as e:
    fail("output sanitization", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 8. nexus CLI has secret + project commands
# ─────────────────────────────────────────────────────────────────────────────
section("8. nexus CLI wiring")

try:
    text = (ROOT / "nexus" / "cli.py").read_text()
    assert "cmd_secret" in text
    assert "cmd_project" in text
    assert '"secret"' in text
    assert '"project"' in text
    assert "RESERVED" in text
    # Both in RESERVED
    reserved_block = text[text.find("RESERVED = {"):text.find("}", text.find("RESERVED = {"))]
    assert "secret" in reserved_block
    assert "project" in reserved_block
    ok("nexus CLI has cmd_secret, cmd_project wired and in RESERVED")
except Exception as e:
    fail("nexus CLI wiring", str(e))

try:
    text = (ROOT / "nexus" / "cli.py").read_text()
    # secret subcommands
    assert "nexus secret set" in text
    assert "nexus secret get" in text
    assert "nexus secret list" in text
    assert "nexus secret remove" in text
    ok("nexus secret has all 4 subcommands")
except Exception as e:
    fail("nexus secret subcommands", str(e))

try:
    text = (ROOT / "nexus" / "cli.py").read_text()
    # project subcommands
    assert "project start" in text
    assert "project upload" in text
    assert "project files" in text
    assert "project forget" in text
    assert "project list" in text
    assert "project switch" in text
    ok("nexus project has all 6 subcommands")
except Exception as e:
    fail("nexus project subcommands", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 9. Runtime RAG injection
# ─────────────────────────────────────────────────────────────────────────────
section("9. Agent runtime RAG injection")

try:
    text = (ROOT / "runtimes" / "agent" / "runtime.py").read_text()
    assert "_get_rag_context" in text
    assert "get_rag" in text
    assert "rag_ctx" in text
    ok("runtime.py has _get_rag_context() wired")
except Exception as e:
    fail("runtime RAG injection", str(e))

try:
    text = (ROOT / "runtimes" / "agent" / "prompts.py").read_text()
    assert "rag_context" in text
    assert "Project Documents" in text or "rag_context" in text
    ok("prompts.py accepts rag_context parameter")
except Exception as e:
    fail("prompts.py rag_context", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Full import chain
# ─────────────────────────────────────────────────────────────────────────────
section("10. Full import chain")

try:
    import importlib
    modules = [
        "services.ragd.service",
        "services.secretd.service",
        "nexus.cli",
        "runtimes.agent.runtime",
        "runtimes.agent.prompts",
    ]
    for mod in modules:
        importlib.import_module(mod)
    ok(f"All {len(modules)} Phase 8 modules import cleanly")
except Exception as e:
    fail("import chain", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 11. E2E (needs Ollama + nomic-embed-text)
# ─────────────────────────────────────────────────────────────────────────────
if E2E:
    section("11. E2E — live Ollama embedding")
    try:
        from services.ragd.service import RAGService
        with tempfile.TemporaryDirectory() as td:
            ws  = Path(td) / "ws" / "e2e"
            ws.mkdir(parents=True)
            rag = RAGService("e2e", ws)
            ok_embed = rag._ensure_embed_model()
            ok(f"_ensure_embed_model() returned {ok_embed}")
            if ok_embed:
                emb = rag._embed(["test sentence for embedding"])
                assert emb[0] is not None and len(emb[0]) > 0
                ok(f"Live embedding returned vector of length {len(emb[0])}")
    except Exception as e:
        fail("E2E embedding", str(e))
else:
    print("\n  (skip e2e — run with --e2e for live Ollama tests)")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n  {chr(9472)*46}")
print(f"  {passed}/{total} passed", end="")
if failed:
    print(f"  |  {failed} FAILED  \u2190")
else:
    print(f"  \u2713  all passed")
print()
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)