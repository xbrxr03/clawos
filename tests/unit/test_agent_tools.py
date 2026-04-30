# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Unit tests for runtimes/agent/tools — registry shape + a couple of
non-network tool calls.
"""
import asyncio
from pathlib import Path

import pytest

from runtimes.agent.tools import NATIVE_TOOLS, dispatch_tool
from runtimes.agent.tool_schemas import ALL_TOOLS, schemas_for_tier, FAST_TOOL_SET, SENSITIVE_TOOLS


# ── registry shape ──────────────────────────────────────────────────────────

def test_every_schema_has_an_implementation():
    for name in ALL_TOOLS:
        assert name in NATIVE_TOOLS, f"schema {name!r} has no implementation"


def test_every_implementation_has_a_schema():
    for name in NATIVE_TOOLS:
        assert name in ALL_TOOLS, f"impl {name!r} has no JSON schema"


def test_fast_tier_filters():
    fast = schemas_for_tier("fast", set(ALL_TOOLS.keys()))
    fast_names = {t["function"]["name"] for t in fast}
    assert fast_names <= FAST_TOOL_SET


def test_sensitive_tools_in_catalog():
    for name in SENSITIVE_TOOLS:
        assert name in ALL_TOOLS


def test_dispatch_unknown_tool():
    result = asyncio.run(dispatch_tool("nope", {}, {}))
    assert "Unknown tool" in result


# ── concrete tool calls (no network, no GUI) ────────────────────────────────

def test_get_time_returns_string():
    r = asyncio.run(dispatch_tool("get_time", {}, {}))
    assert isinstance(r, str)
    assert any(d in r for d in ["2025", "2026", "2027", "2028"])  # year present


def test_recall_without_memory_service():
    r = asyncio.run(dispatch_tool("recall", {"query": "anything"}, {}))
    assert "[ERROR]" in r


def test_remember_requires_text():
    r = asyncio.run(dispatch_tool("remember", {}, {"workspace_id": "x"}))
    assert "text required" in r


def test_files_list_in_tmp(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hi")
    (tmp_path / "b.md").write_text("hi")
    r = asyncio.run(dispatch_tool("list_files", {"path": "."}, {"ws_root": tmp_path}))
    assert "a.txt" in r
    assert "b.md" in r


def test_files_read_in_tmp(tmp_path: Path):
    p = tmp_path / "hello.txt"
    p.write_text("hello world")
    r = asyncio.run(dispatch_tool("read_file", {"path": "hello.txt"}, {"ws_root": tmp_path}))
    assert "hello world" in r


def test_files_write_creates(tmp_path: Path):
    r = asyncio.run(dispatch_tool(
        "write_file",
        {"path": "out/inner.txt", "content": "abc"},
        {"ws_root": tmp_path},
    ))
    assert "[OK]" in r
    assert (tmp_path / "out" / "inner.txt").read_text() == "abc"


def test_open_url_rejects_non_http():
    r = asyncio.run(dispatch_tool("open_url", {"url": "javascript:alert(1)"}, {}))
    assert "[ERROR]" in r


def test_run_command_rejects_disallowed():
    r = asyncio.run(dispatch_tool("run_command", {"command": "rm -rf /"}, {}))
    assert "[DENIED]" in r or "[ERROR]" in r


def test_read_file_rejects_workspace_escape(tmp_path: Path):
    """Verify read_file cannot escape workspace via ../../../etc/passwd"""
    r = asyncio.run(dispatch_tool("read_file", {"path": "../../../etc/passwd"}, {"ws_root": tmp_path}))
    assert "[ERROR]" in r
    # Verify the file was NOT actually read
    assert "root:" not in r  # /etc/passwd contains root user entries
