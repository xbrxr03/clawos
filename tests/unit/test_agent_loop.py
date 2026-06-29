# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Unit tests for agentd — AgentManager lifecycle and task routing.
Mocks all external deps (Ollama, event bus, runtime, etc.).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clawos_core.models import Task, TaskStatus


# ── AgentManager: initialization ──────────────────────────────────────────────

def test_manager_init():
    """AgentManager initializes with empty sessions, tasks, and not running."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    assert mgr._sessions == {}
    assert mgr._tasks == {}
    assert mgr._running is False


# ── AgentManager: submit creates a Task ───────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_creates_task():
    """submit() creates a Task with correct intent and returns it."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()

    with patch("services.agentd.service.get_bus") as mock_bus:
        mock_bus.return_value.emit_task = AsyncMock()
        task = await mgr.submit("hello world", workspace_id="test-ws", channel="cli")

    assert isinstance(task, Task)
    assert task.intent == "hello world"
    assert task.workspace == "test-ws"
    assert task.channel == "cli"
    assert task.status == TaskStatus.QUEUED
    assert task.task_id  # non-empty
    assert task.task_id in mgr._tasks


# ── AgentManager: get_task retrieves submitted task ──────────────────────────

@pytest.mark.asyncio
async def test_get_task():
    """get_task() returns the task by ID."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    with patch("services.agentd.service.get_bus") as mock_bus:
        mock_bus.return_value.emit_task = AsyncMock()
        task = await mgr.submit("do something", workspace_id="ws1")
    retrieved = mgr.get_task(task.task_id)
    assert retrieved is task


def test_get_task_missing():
    """get_task() returns None for unknown ID."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    assert mgr.get_task("nonexistent") is None


# ── AgentManager: list_tasks returns ordered list ────────────────────────────

@pytest.mark.asyncio
async def test_list_tasks():
    """list_tasks() returns dicts sorted by created_at descending."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    with patch("services.agentd.service.get_bus") as mock_bus:
        mock_bus.return_value.emit_task = AsyncMock()
        await mgr.submit("first", workspace_id="ws1")
        await mgr.submit("second", workspace_id="ws1")

    tasks = mgr.list_tasks(limit=10)
    assert len(tasks) == 2
    for t in tasks:
        assert "task_id" in t
        assert "intent" in t


# ── AgentManager: start and stop ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_sets_running():
    """start() sets _running to True."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    await mgr.start()
    assert mgr._running is True
    await mgr.stop()


@pytest.mark.asyncio
async def test_stop_sets_not_running():
    """stop() sets _running to False."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    await mgr.start()
    await mgr.stop()
    assert mgr._running is False


# ── AgentManager: _derive_channel ────────────────────────────────────────────

def test_derive_channel_explicit():
    """_derive_channel returns explicit channel if not 'cli'."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    assert mgr._derive_channel(channel="voice") == "voice"


def test_derive_channel_from_source():
    """_derive_channel extracts channel from source when channel is cli."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    assert mgr._derive_channel(channel="cli", source="telegram:123") == "telegram"


def test_derive_channel_default():
    """_derive_channel defaults to 'cli' when no info."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()
    assert mgr._derive_channel() == "cli"


# ── AgentManager: _run_task with mocked runtime ──────────────────────────────

@pytest.mark.asyncio
async def test_run_task_completes():
    """_run_task sets task to COMPLETED with result from runtime."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()

    mock_session = AsyncMock()
    mock_session.chat = AsyncMock(return_value="Hello, I am Nexus.")

    mock_bus_instance = MagicMock()
    mock_bus_instance.emit_task = AsyncMock()

    with patch("services.agentd.service.get_bus", return_value=mock_bus_instance), \
         patch.object(mgr, "_get_session", return_value=mock_session):
        with patch("services.agentd.service.get_bus") as mb:
            mb.return_value = mock_bus_instance
            task = await mgr.submit("greet", workspace_id="ws1")

        await mgr._run_task(task)

    assert task.status == TaskStatus.COMPLETED
    assert task.result == "Hello, I am Nexus."
    assert task.finished_at is not None


# ── AgentManager: _run_task handles failure ──────────────────────────────────

@pytest.mark.asyncio
async def test_run_task_failure():
    """_run_task sets task to FAILED when session raises."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()

    mock_bus_instance = MagicMock()
    mock_bus_instance.emit_task = AsyncMock()

    async def _get_session_fail(ws):
        raise OSError("Ollama not running")

    with patch("services.agentd.service.get_bus", return_value=mock_bus_instance), \
         patch.object(mgr, "_get_session", side_effect=_get_session_fail):
        task = await mgr.submit("bad request", workspace_id="ws1")
        await mgr._run_task(task)

    assert task.status == TaskStatus.FAILED
    assert task.error is not None
    assert "Ollama not running" in task.error


# ── AgentManager: chat_direct ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_direct():
    """chat_direct bypasses task queue and returns agent reply."""
    from services.agentd.service import AgentManager
    mgr = AgentManager()

    mock_session = AsyncMock()
    mock_session.chat = AsyncMock(return_value="Sure thing!")
    mock_session.session = MagicMock()

    with patch.object(mgr, "_get_session", return_value=mock_session):
        result = await mgr.chat_direct("do something", workspace_id="ws1")

    assert result == "Sure thing!"