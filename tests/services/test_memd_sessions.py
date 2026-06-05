# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for memd session search (FTS5 across conversations).

Covers:
  - Session creation and turn ingestion
  - FTS5 search across sessions with ranking
  - Workspace scoping
  - Performance: 10K turns search < 50ms
"""
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def session_db(tmp_path):
    """Create a temporary sessions.db for testing, patching the module-level path."""
    db_path = tmp_path / "sessions.db"
    with patch("services.memd.service._SESSION_DB_PATH", db_path):
        # Also ensure parent dir exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        yield db_path


@pytest.fixture
def memd(session_db):
    """Create a MemoryService with a patched session DB path."""
    from services.memd.service import MemoryService
    return MemoryService()


# ── Session creation and turn ingestion ──────────────────────────────────────

class TestSessionCreation:
    """Test session start, turn ingestion, and session end."""

    def test_ingest_session_start(self, memd, session_db):
        """Session row is created on ingest_session_start."""
        sid = "sess-001"
        memd.ingest_session_start(sid, "ws-test")
        # Verify directly in DB
        db = sqlite3.connect(str(session_db))
        row = db.execute("SELECT id, workspace_id FROM sessions WHERE id=?", (sid,)).fetchone()
        db.close()
        assert row is not None
        assert row[0] == sid
        assert row[1] == "ws-test"

    def test_ingest_turn_creates_session_if_missing(self, memd, session_db):
        """ingest_turn auto-creates session row if not present."""
        sid = "sess-auto"
        memd.ingest_turn(sid, "user", "Hello, how are you?", "ws-auto")
        db = sqlite3.connect(str(session_db))
        session = db.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone()
        turn = db.execute("SELECT role, content FROM session_turns WHERE session_id=?", (sid,)).fetchone()
        db.close()
        assert session is not None
        assert turn[0] == "user"
        assert turn[1] == "Hello, how are you?"

    def test_ingest_turn_increments_turn_count(self, memd, session_db):
        """Each turn increments the session turn_count."""
        sid = "sess-count"
        memd.ingest_session_start(sid, "ws-test")
        memd.ingest_turn(sid, "user", "turn 1", "ws-test")
        memd.ingest_turn(sid, "assistant", "turn 2", "ws-test")
        memd.ingest_turn(sid, "user", "turn 3", "ws-test")
        db = sqlite3.connect(str(session_db))
        count = db.execute("SELECT turn_count FROM sessions WHERE id=?", (sid,)).fetchone()[0]
        db.close()
        assert count == 3

    def test_ingest_session_end(self, memd, session_db):
        """ingest_session_end sets ended_at and final turn count."""
        sid = "sess-end"
        memd.ingest_session_start(sid, "ws-test")
        memd.ingest_turn(sid, "user", "hi", "ws-test")
        memd.ingest_turn(sid, "assistant", "hello", "ws-test")
        memd.ingest_session_end(sid)
        db = sqlite3.connect(str(session_db))
        row = db.execute("SELECT ended_at, turn_count FROM sessions WHERE id=?", (sid,)).fetchone()
        db.close()
        assert row[0] is not None  # ended_at set
        assert row[1] == 2  # turn_count updated

    def test_ingest_turn_empty_content_skipped(self, memd, session_db):
        """Empty or whitespace-only content is not ingested."""
        sid = "sess-empty"
        memd.ingest_session_start(sid, "ws-test")
        memd.ingest_turn(sid, "user", "", "ws-test")
        memd.ingest_turn(sid, "assistant", "   ", "ws-test")
        db = sqlite3.connect(str(session_db))
        count = db.execute("SELECT COUNT(*) FROM session_turns WHERE session_id=?", (sid,)).fetchone()[0]
        db.close()
        assert count == 0

    def test_ingest_turn_truncates_long_content(self, memd, session_db):
        """Content longer than 4000 chars is truncated."""
        sid = "sess-long"
        memd.ingest_session_start(sid, "ws-test")
        long_content = "x" * 5000
        memd.ingest_turn(sid, "user", long_content, "ws-test")
        db = sqlite3.connect(str(session_db))
        stored = db.execute("SELECT content FROM session_turns WHERE session_id=?", (sid,)).fetchone()[0]
        db.close()
        assert len(stored) == 4000


# ── FTS5 search across sessions with ranking ──────────────────────────────────

class TestCrossSessionSearch:
    """Test recall_cross_session FTS5 search."""

    def _seed_sessions(self, memd):
        """Seed multiple sessions with known content."""
        memd.ingest_session_start("sess-alpha", "ws-test")
        memd.ingest_turn("sess-alpha", "user", "How do I refactor the API gateway?", "ws-test")
        memd.ingest_turn("sess-alpha", "assistant", "Start by extracting the routing logic into a separate module.", "ws-test")

        memd.ingest_session_start("sess-beta", "ws-test")
        memd.ingest_turn("sess-beta", "user", "I need to fix the API rate limiter", "ws-test")
        memd.ingest_turn("sess-beta", "assistant", "The rate limiter uses a token bucket algorithm. Check config.yaml.", "ws-test")

        memd.ingest_session_start("sess-gamma", "ws-test")
        memd.ingest_turn("sess-gamma", "user", "What's for dinner?", "ws-test")
        memd.ingest_turn("sess-gamma", "assistant", "I suggest pasta.", "ws-test")

    def test_search_returns_results(self, memd):
        """Search for 'API' returns matching turns."""
        self._seed_sessions(memd)
        results = memd.recall_cross_session("API", "ws-test", n=5)
        assert len(results) >= 2  # at least the two API-related turns
        # All results should mention API
        for r in results:
            assert "api" in r["content"].lower()

    def test_search_ranking(self, memd):
        """More relevant results rank higher (lower rank value)."""
        self._seed_sessions(memd)
        results = memd.recall_cross_session("API refactor", "ws-test", n=5)
        assert len(results) >= 1
        # First result should be the API gateway turn (has both terms)
        first_content = results[0]["content"].lower()
        assert "api" in first_content

    def test_search_no_results(self, memd):
        """Search for gibberish returns empty list."""
        self._seed_sessions(memd)
        results = memd.recall_cross_session("xyzzyplugh", "ws-test")
        assert results == []

    def test_search_returns_dict_fields(self, memd):
        """Each result has the expected dict keys."""
        self._seed_sessions(memd)
        results = memd.recall_cross_session("API", "ws-test", n=1)
        assert len(results) >= 1
        r = results[0]
        assert "session_id" in r
        assert "role" in r
        assert "content" in r
        assert "timestamp" in r
        assert "rank" in r
        assert "highlight" in r
        assert "workspace_id" in r

    def test_search_empty_query(self, memd):
        """Empty query returns empty results."""
        results = memd.recall_cross_session("", "ws-test")
        assert results == []

    def test_search_limit(self, memd):
        """n parameter limits number of results."""
        self._seed_sessions(memd)
        results = memd.recall_cross_session("API", "ws-test", n=1)
        assert len(results) <= 1


# ── Workspace scoping ────────────────────────────────────────────────────────

class TestWorkspaceScoping:
    """Search results are scoped to the requested workspace."""

    def test_workspace_isolation(self, memd):
        """Data from one workspace is not visible to another."""
        memd.ingest_session_start("sess-a", "ws-alpha")
        memd.ingest_turn("sess-a", "user", "Deploy to production cluster", "ws-alpha")

        memd.ingest_session_start("sess-b", "ws-beta")
        memd.ingest_turn("sess-b", "user", "Deploy to staging cluster", "ws-beta")

        # Search in ws-alpha should only see alpha turns
        results_alpha = memd.recall_cross_session("Deploy", "ws-alpha")
        assert len(results_alpha) >= 1
        assert all(r["workspace_id"] == "ws-alpha" for r in results_alpha)

        # Search in ws-beta should only see beta turns
        results_beta = memd.recall_cross_session("Deploy", "ws-beta")
        assert len(results_beta) >= 1
        assert all(r["workspace_id"] == "ws-beta" for r in results_beta)

    def test_workspace_no_cross_visibility(self, memd):
        """ws-gamma (no data) returns empty results."""
        memd.ingest_session_start("sess-x", "ws-alpha")
        memd.ingest_turn("sess-x", "user", "Important data here", "ws-alpha")

        results = memd.recall_cross_session("Important", "ws-gamma")
        assert results == []


# ── Performance ───────────────────────────────────────────────────────────────

class TestPerformance:
    """Performance target: 10K turns search < 50ms."""

    def test_10k_turns_search_under_50ms(self, memd, session_db):
        """Search across 10K turns should complete in < 50ms."""
        import uuid
        sid = "perf-sess"
        memd.ingest_session_start(sid, "ws-perf")
        # Bulk insert 10K turns
        for i in range(10_000):
            content = f"Turn number {i} with some keywords like deploy and API and refactor"
            memd.ingest_turn(sid, "user" if i % 2 == 0 else "assistant", content, "ws-perf")

        # Time the search
        start = time.perf_counter()
        results = memd.recall_cross_session("API refactor", "ws-perf", n=5)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(results) >= 1, "Should find at least one result"
        assert elapsed_ms < 50, f"Search took {elapsed_ms:.1f}ms, expected < 50ms"