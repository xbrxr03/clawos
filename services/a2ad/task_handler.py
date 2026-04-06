# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes inbound A2A tasks to agentd."""
import asyncio
import logging
from clawos_core.models import A2ATask
from clawos_core.constants import DEFAULT_WORKSPACE

log = logging.getLogger("a2ad")


async def handle_task(a2a_task: A2ATask) -> str:
    """Submit task to agentd and return result (blocking up to 120s)."""
    try:
        from services.agentd.service import get_manager
        manager = get_manager()
        task = await manager.submit(
            intent       = a2a_task.intent,
            workspace_id = a2a_task.workspace or DEFAULT_WORKSPACE,
            channel      = "a2a",
        )
        # Wait for completion (max 120s)
        for _ in range(240):
            await asyncio.sleep(0.5)
            t = manager._tasks.get(task.task_id)
            if t and t.status.value in ("completed", "failed", "cancelled"):
                return t.result or t.error or "[completed]"
        return "[TIMEOUT] Task did not complete within 120s"
    except Exception as e:
        log.error(f"A2A task handler error: {e}")
        return f"[ERROR] {e}"
