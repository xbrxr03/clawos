# SPDX-License-Identifier: AGPL-3.0-or-later
"""Delegate tool — spawn isolated subagents for parallel task execution."""
from __future__ import annotations

import asyncio
import logging

from runtimes.agent.subagent import SubAgentRunner
from clawos_core.constants import MAX_SUBAGENTS, SUBAGENT_TIMEOUT
from runtimes.agent.router import FAST_MODEL

log = logging.getLogger("agent.tools.delegate")

# Track active subagents for concurrency limiting.
# Uses an asyncio Lock to ensure thread-safety in concurrent coroutines.
_lock = asyncio.Lock()
_active_subagents: int = 0


async def delegate(args: dict, ctx: dict) -> str:
    """Spawn an isolated subagent to handle a task.

    Args:
        task: What the subagent should do (required)
        model: Model to use (optional, defaults to fast model)
        timeout: Timeout in seconds (optional, defaults to SUBAGENT_TIMEOUT)

    Returns:
        Subagent output or error message
    """
    global _active_subagents

    task = args.get("task", "").strip()
    if not task:
        return "[ERROR] delegate requires a 'task' argument"

    model = args.get("model") or FAST_MODEL
    timeout = args.get("timeout") or SUBAGENT_TIMEOUT

    # Concurrency guard (async-safe)
    async with _lock:
        if _active_subagents >= MAX_SUBAGENTS:
            return f"[ERROR] Maximum {MAX_SUBAGENTS} concurrent subagents reached. Try again later."
        _active_subagents += 1

    workspace_id = ctx.get("workspace_id", "nexus_default")
    runner = SubAgentRunner(
        task=task,
        model=model,
        workspace_id=workspace_id,
        timeout=int(timeout),
    )
    try:
        result = await runner.run()
        if result.success:
            return (
                f"[Subagent {result.subagent_id} completed in {result.elapsed_s:.1f}s "
                f"using {result.model}]\n\n{result.output}"
            )
        else:
            return f"[Subagent {result.subagent_id} failed: {result.output}]"
    finally:
        async with _lock:
            _active_subagents -= 1