# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for subagent delegation (ClawOS issue #66)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from runtimes.agent.subagent import SubAgentRunner, SubAgentResult
from clawos_core.constants import MAX_SUBAGENTS, SUBAGENT_TIMEOUT


# ── SubAgentResult dataclass ──────────────────────────────────────────────────

def test_subagent_result_fields():
    """SubAgentResult has all expected fields with defaults."""
    r = SubAgentResult(success=True, output="hello")
    assert r.success is True
    assert r.output == "hello"
    assert r.tool_calls == []
    assert r.subagent_id == ""
    assert r.model == ""
    assert r.elapsed_s == 0.0


def test_subagent_result_full():
    """SubAgentResult with all fields populated."""
    r = SubAgentResult(
        success=True,
        output="done",
        tool_calls=[{"tool": "read_file", "args": {"path": "/tmp/x"}}],
        subagent_id="abc12345",
        model="qwen2.5:3b",
        elapsed_s=3.2,
    )
    assert r.success is True
    assert len(r.tool_calls) == 1
    assert r.subagent_id == "abc12345"
    assert r.model == "qwen2.5:3b"
    assert r.elapsed_s == 3.2


# ── SubAgentRunner creation ───────────────────────────────────────────────────

def test_subagent_runner_defaults():
    """SubAgentRunner uses defaults for model, workspace, and timeout."""
    runner = SubAgentRunner(task="summarize this doc")
    assert runner.task == "summarize this doc"
    assert runner.workspace_id == "nexus_default"
    assert runner.timeout == SUBAGENT_TIMEOUT
    assert len(runner.subagent_id) == 8  # uuid[:8]


def test_subagent_runner_custom():
    """SubAgentRunner accepts custom model, workspace, and timeout."""
    runner = SubAgentRunner(
        task="test task",
        model="qwen2.5-coder:7b",
        workspace_id="ws_42",
        timeout=60,
    )
    assert runner.model == "qwen2.5-coder:7b"
    assert runner.workspace_id == "ws_42"
    assert runner.timeout == 60


# ── Delegate tool ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delegate_tool_missing_task():
    """delegate() returns error when task is empty."""
    from runtimes.agent.tools.delegate import delegate
    result = await delegate({}, {"workspace_id": "test"})
    assert "[ERROR]" in result
    assert "task" in result.lower()


@pytest.mark.asyncio
async def test_delegate_tool_empty_task():
    """delegate() returns error when task is whitespace-only."""
    from runtimes.agent.tools.delegate import delegate
    result = await delegate({"task": "   "}, {"workspace_id": "test"})
    assert "[ERROR]" in result


@pytest.mark.asyncio
async def test_delegate_tool_concurrency_limit():
    """delegate() refuses when MAX_SUBAGENTS are already active."""
    from runtimes.agent.tools.delegate import delegate
    import runtimes.agent.tools.delegate as delegate_mod

    # Simulate max subagents already active
    original = delegate_mod._active_subagents
    delegate_mod._active_subagents = MAX_SUBAGENTS
    try:
        result = await delegate({"task": "should fail"}, {"workspace_id": "test"})
        assert "[ERROR]" in result
        assert str(MAX_SUBAGENTS) in result
    finally:
        delegate_mod._active_subagents = original


@pytest.mark.asyncio
async def test_delegate_tool_success():
    """delegate() returns subagent result on success."""
    from runtimes.agent.tools.delegate import delegate

    mock_result = SubAgentResult(
        success=True,
        output="summary of the doc",
        tool_calls=[],
        subagent_id="deadbeef",
        model="qwen2.5:3b",
        elapsed_s=1.5,
    )

    with patch.object(SubAgentRunner, "run", new_callable=AsyncMock, return_value=mock_result):
        result = await delegate({"task": "summarize this"}, {"workspace_id": "test"})
        assert "deadbeef" in result
        assert "summary of the doc" in result
        assert "1.5s" in result


@pytest.mark.asyncio
async def test_delegate_tool_timeout():
    """delegate() returns failure result when subagent times out."""
    from runtimes.agent.tools.delegate import delegate

    mock_result = SubAgentResult(
        success=False,
        output="Subagent timed out after 120s",
        tool_calls=[],
        subagent_id="cafe1234",
        model="qwen2.5:3b",
        elapsed_s=120.0,
    )

    with patch.object(SubAgentRunner, "run", new_callable=AsyncMock, return_value=mock_result):
        result = await delegate({"task": "long task"}, {"workspace_id": "test"})
        assert "failed" in result.lower() or "timed out" in result.lower()


# ── Tool schemas ──────────────────────────────────────────────────────────────

def test_delegate_schema_in_all_tools():
    """delegate tool schema is in ALL_TOOLS."""
    from runtimes.agent.tool_schemas import ALL_TOOLS
    assert "delegate" in ALL_TOOLS
    schema = ALL_TOOLS["delegate"]
    func = schema["function"]
    assert func["name"] == "delegate"
    assert "task" in func["parameters"]["properties"]
    assert "task" in func["parameters"]["required"]


def test_delegate_in_sensitive_tools():
    """delegate is in SENSITIVE_TOOLS (requires approval)."""
    from runtimes.agent.tool_schemas import SENSITIVE_TOOLS
    assert "delegate" in SENSITIVE_TOOLS


# ── Policy engine ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_policy_first_delegate_needs_approval():
    """First delegate call in a session requires approval (queues it)."""
    from services.policyd.service import PolicyEngine
    from clawos_core.models import Decision

    engine = PolicyEngine()
    # Clear any pending from other tests
    engine._pending.clear()
    engine._delegate_approved_sessions.clear()

    # First delegate call should go to approval queue (not auto-allow)
    # We can't easily test the full flow since it waits for approval,
    # but we can verify it's not in the auto-approved set.
    assert "ws1:task1" not in engine._delegate_approved_sessions

    # Simulate: the evaluate method should route to _queue_for_approval
    # We'll patch _queue_for_approval to return ALLOW immediately
    original_queue = engine._queue_for_approval
    engine._queue_for_approval = AsyncMock(return_value=(Decision.ALLOW, "approved"))

    decision, reason = await engine.evaluate(
        tool="delegate",
        target="test task",
        task_id="task1",
        workspace_id="ws1",
        granted_tools=["delegate"],
        content="",
    )
    assert decision == Decision.ALLOW
    # After approval, this session should be marked
    assert "ws1:task1" in engine._delegate_approved_sessions
    engine._queue_for_approval = original_queue
    engine.close()


@pytest.mark.asyncio
async def test_policy_subsequent_delegate_auto_approved():
    """Second delegate call in same session is auto-approved."""
    from services.policyd.service import PolicyEngine
    from clawos_core.models import Decision

    engine = PolicyEngine()
    engine._pending.clear()
    engine._delegate_approved_sessions.clear()

    # Pre-mark the session as approved
    engine._delegate_approved_sessions.add("ws1:task1")

    decision, reason = await engine.evaluate(
        tool="delegate",
        target="another task",
        task_id="task1",
        workspace_id="ws1",
        granted_tools=["delegate"],
        content="",
    )
    assert decision == Decision.ALLOW
    assert "auto-approved" in reason
    engine.close()


# ── Constants ─────────────────────────────────────────────────────────────────

def test_constants_exist():
    """MAX_SUBAGENTS and SUBAGENT_TIMEOUT are defined."""
    assert MAX_SUBAGENTS == 3
    assert SUBAGENT_TIMEOUT == 120