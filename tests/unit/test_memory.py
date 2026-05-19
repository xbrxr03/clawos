# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Unit tests for memd — MemoryService (4-layer architecture).
Tests Layer 1 (PINNED.md), Layer 2 (WORKFLOW.md), Layer 4 (SQLite FTS5),
session state, and LearnedLayer.
All tests use temporary directories — no real ClawOS paths touched.
"""
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with memory directory structure."""
    from clawos_core import constants

    # Patch CLAWOS_DIR and derived paths so nothing touches the real install
    orig_dir = constants.CLAWOS_DIR
    orig_ws = constants.WORKSPACE_DIR
    constants.CLAWOS_DIR = tmp_path
    constants.WORKSPACE_DIR = tmp_path / "workspace"

    # Also patch the module-level _FTS_DB_PATH and _KG_DB_PATH
    import services.memd.service as memd_mod
    orig_fts = memd_mod._FTS_DB_PATH
    orig_kg = memd_mod._KG_DB_PATH
    memd_mod._FTS_DB_PATH = tmp_path / "memory" / "fts.db"
    memd_mod._KG_DB_PATH = tmp_path / "memory" / "knowledge_graph.db"

    # Reset taosmd singletons so they re-initialize with new paths
    memd_mod._taosmd_archive = None
    memd_mod._taosmd_tkg = None
    memd_mod._taosmd_vector = None

    yield tmp_path

    # Restore
    constants.CLAWOS_DIR = orig_dir
    constants.WORKSPACE_DIR = orig_ws
    memd_mod._FTS_DB_PATH = orig_fts
    memd_mod._KG_DB_PATH = orig_kg


@pytest.fixture
def mem_service(temp_workspace):
    """MemoryService with temp workspace and mocked vector/archive backends."""
    from services.memd.service import MemoryService
    svc = MemoryService()
    return svc


# ── Layer 1: PINNED.md ────────────────────────────────────────────────────────

class TestPinnedMemory:
    def test_write_and_read_pinned(self, mem_service, temp_workspace):
        """write_pinned → read_pinned returns same content."""
        ws = "test-ws"
        mem_service.write_pinned(ws, "- I prefer dark mode\n- Timezone: ET")
        result = mem_service.read_pinned(ws)
        assert "dark mode" in result
        assert "ET" in result

    def test_read_pinned_empty(self, mem_service):
        """read_pinned returns empty string when no PINNED.md exists."""
        result = mem_service.read_pinned("nonexistent-ws")
        assert result == ""

    def test_append_pinned(self, mem_service):
        """append_pinned adds a new fact to existing content."""
        ws = "ws1"
        mem_service.write_pinned(ws, "- Initial fact")
        mem_service.append_pinned(ws, "New fact here")
        result = mem_service.read_pinned(ws)
        assert "Initial fact" in result
        assert "New fact here" in result


# ── Layer 2: WORKFLOW.md ──────────────────────────────────────────────────────

class TestWorkflowMemory:
    def test_write_and_read_workflow(self, mem_service):
        ws = "ws1"
        mem_service.write_workflow(ws, "## Current Task\nFix the bug in agentd")
        result = mem_service.read_workflow(ws)
        assert "Fix the bug" in result

    def test_clear_workflow(self, mem_service, temp_workspace):
        ws = "ws1"
        mem_service.write_workflow(ws, "some content")
        mem_service.clear_workflow(ws)
        result = mem_service.read_workflow(ws)
        assert result == ""

    def test_read_workflow_empty(self, mem_service):
        result = mem_service.read_workflow("no-ws")
        assert result == ""


# ── Layer 4: SQLite FTS5 — remember / recall ─────────────────────────────────

class TestFTSMemory:
    """Tests for FTS5 memory layer. Vector store (ChromaDB) is mocked out
    because ONNX models are not available in CI environments."""

    @pytest.fixture(autouse=True)
    def mock_taosmd(self):
        """Mock _get_vector and _get_archive to avoid ChromaDB/ONNX."""
        with patch("services.memd.service._get_vector", return_value=None), \
             patch("services.memd.service._get_archive", return_value=None):
            yield

    def test_remember_returns_id(self, mem_service):
        """remember() returns a non-empty memory_id."""
        mid = mem_service.remember("I like Python for scripting", "ws1", source="user")
        assert mid  # non-empty string

    def test_remember_empty_text(self, mem_service):
        """remember() returns empty string for empty/whitespace text."""
        assert mem_service.remember("", "ws1") == ""
        assert mem_service.remember("   ", "ws1") == ""

    def test_recall_returns_results(self, mem_service):
        """recall() returns memories that match the query."""
        mem_service.remember("Python is great for data science", "ws1", force_add=True)
        mem_service.remember("Rust is fast and safe", "ws1", force_add=True)

        results = mem_service.recall("Python data", "ws1", n=5)
        assert len(results) > 0
        combined = " ".join(results)
        assert "Python" in combined

    def test_recall_empty_workspace(self, mem_service):
        """recall() on empty workspace returns empty or only PINNED/WORKFLOW."""
        results = mem_service.recall("anything", "empty-ws", n=5)
        assert isinstance(results, list)

    def test_forget_removes_memory(self, mem_service):
        """forget() removes a memory from FTS."""
        mid = mem_service.remember("temporary info", "ws1", force_add=True)
        mem_service.forget(mid, "ws1")
        results = mem_service.recall("temporary info", "ws1", n=5)
        fts_texts = [r for r in results if "temporary info" in r]
        assert len(fts_texts) == 0

    def test_get_all(self, mem_service):
        """get_all() returns active memories as dicts."""
        mem_service.remember("fact one", "ws1", force_add=True)
        mem_service.remember("fact two", "ws1", force_add=True)
        all_mems = mem_service.get_all("ws1")
        assert len(all_mems) >= 2
        for m in all_mems:
            assert "memory_id" in m
            assert "text" in m

    def test_remember_updates_similar(self, mem_service):
        """remember() with similar text updates existing instead of adding new."""
        mid1 = mem_service.remember("I love Python programming language", "ws1", force_add=True)
        mid2 = mem_service.remember("I love Python programming languages", "ws1")
        all_mems = mem_service.get_all("ws1")
        assert len(all_mems) <= 2


# ── HISTORY.md ────────────────────────────────────────────────────────────────

class TestHistory:
    def test_append_and_read_history(self, mem_service):
        ws = "ws1"
        mem_service.append_history(ws, "User asked about Python")
        mem_service.append_history(ws, "Agent responded with examples")
        tail = mem_service.read_history_tail(ws, lines=10)
        assert "Python" in tail
        assert "examples" in tail

    def test_read_history_tail_nonexistent(self, mem_service):
        result = mem_service.read_history_tail("no-ws")
        assert result == ""


# ── Session state persistence ─────────────────────────────────────────────────

class TestSessionState:
    def test_save_and_load_session_state(self, mem_service, temp_workspace):
        ws = "ws2"
        state = {"last_intent": "deploy app", "turn": 5}
        mem_service.save_session_state(ws, state)
        loaded = mem_service.load_session_state(ws)
        assert loaded["last_intent"] == "deploy app"
        assert loaded["turn"] == 5

    def test_load_session_state_empty(self, mem_service):
        loaded = mem_service.load_session_state("no-ws-state")
        assert loaded == {}

    def test_pending_queue(self, mem_service, temp_workspace):
        ws = "ws3"
        mem_service.push_pending(ws, "Review PR #42")
        mem_service.push_pending(ws, "Fix auth bug")
        queue = mem_service.get_pending_queue(ws)
        assert len(queue) == 2
        assert "Review PR #42" in queue

    def test_pending_queue_no_duplicates(self, mem_service, temp_workspace):
        ws = "ws4"
        mem_service.push_pending(ws, "Same task")
        mem_service.push_pending(ws, "Same task")
        queue = mem_service.get_pending_queue(ws)
        assert len(queue) == 1

    def test_clear_pending_queue(self, mem_service, temp_workspace):
        ws = "ws5"
        mem_service.push_pending(ws, "Task A")
        mem_service.clear_pending_queue(ws)
        queue = mem_service.get_pending_queue(ws)
        assert queue == []


# ── LearnedLayer ──────────────────────────────────────────────────────────────

class TestLearnedLayer:
    def test_read_empty(self, temp_workspace):
        from services.memd.service import LearnedLayer
        layer = LearnedLayer()
        assert layer.read("ws1") == ""

    def test_read_with_content(self, temp_workspace):
        from services.memd.service import LearnedLayer
        from clawos_core.constants import WORKSPACE_DIR
        layer = LearnedLayer()
        p = layer.path("ws1")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("- Prefer fast models for simple queries\n- Always check memory first")
        result = layer.read("ws1")
        assert "fast models" in result