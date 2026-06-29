# SPDX-License-Identifier: AGPL-3.0-or-later
"""
SubAgentRunner — isolated child agent that runs a single task and returns results.

Subagents inherit the workspace but get a fresh context window (no conversation
history from the parent). They run with timeout protection and return a structured
SubAgentResult that the parent agent can surface to the user.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from clawos_core.constants import DEFAULT_WORKSPACE, SUBAGENT_TIMEOUT
from runtimes.agent.router import FAST_MODEL

log = logging.getLogger("agent.subagent")


@dataclass
class SubAgentResult:
    """Result from a subagent run."""
    success: bool
    output: str
    tool_calls: list[dict] = field(default_factory=list)
    subagent_id: str = ""
    model: str = ""
    elapsed_s: float = 0.0


class SubAgentRunner:
    """Isolated child agent that runs a single task and returns results.

    Key properties:
    - Inherits workspace_id but NOT conversation history
    - Gets its own AgentRuntime with empty history
    - Runs with timeout (default: SUBAGENT_TIMEOUT)
    - Returns structured SubAgentResult
    """

    def __init__(
        self,
        task: str,
        model: str = FAST_MODEL,
        workspace_id: str = DEFAULT_WORKSPACE,
        timeout: int = SUBAGENT_TIMEOUT,
    ):
        self.task = task
        self.model = model
        self.workspace_id = workspace_id
        self.timeout = timeout
        self.subagent_id = str(uuid.uuid4())[:8]

    async def run(self) -> SubAgentResult:
        """Run the subagent and return results."""
        from runtimes.agent.runtime import AgentRuntime

        start = asyncio.get_event_loop().time()
        runtime = AgentRuntime(
            workspace_id=self.workspace_id,
            model=self.model,
            memory=None,       # isolated — no parent memory context
            tool_bridge=None,   # will use lightweight defaults
            policy_client=None,
        )
        # Ensure empty history (isolation from parent)
        runtime._history = []
        runtime._turn = 0

        try:
            log.info(f"[subagent:{self.subagent_id}] Spawning for task: {self.task[:80]}...")
            result = await asyncio.wait_for(
                runtime.chat(self.task),
                timeout=self.timeout,
            )
            elapsed = asyncio.get_event_loop().time() - start
            log.info(f"[subagent:{self.subagent_id}] Completed in {elapsed:.1f}s")

            # Collect tool calls from history — any assistant message with
            # tool_calls followed by tool messages indicates execution.
            tool_calls = []
            for msg in runtime._history:
                tcs = msg.get("tool_calls")
                if tcs:
                    for tc in tcs:
                        fn = tc.get("function") or {}
                        tool_calls.append({
                            "tool": fn.get("name", ""),
                            "args": fn.get("arguments") or {},
                        })

            return SubAgentResult(
                success=True,
                output=result or "",
                tool_calls=tool_calls,
                subagent_id=self.subagent_id,
                model=self.model,
                elapsed_s=elapsed,
            )
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - start
            log.warning(f"[subagent:{self.subagent_id}] Timed out after {self.timeout}s")
            return SubAgentResult(
                success=False,
                output=f"Subagent timed out after {self.timeout}s",
                tool_calls=[],
                subagent_id=self.subagent_id,
                model=self.model,
                elapsed_s=elapsed,
            )
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start
            log.error(f"[subagent:{self.subagent_id}] Failed: {e}")
            return SubAgentResult(
                success=False,
                output=f"Subagent error: {e}",
                tool_calls=[],
                subagent_id=self.subagent_id,
                model=self.model,
                elapsed_s=elapsed,
            )