"""
agentd — Agent Lifecycle Manager
==================================
Receives tasks from any channel, routes to AgentRuntime.
One session per workspace_id — cached and reused.
"""
import asyncio
import logging
from typing import Optional
from clawos_core.constants import DEFAULT_WORKSPACE, DEFAULT_MODEL
from clawos_core.models import Task, TaskStatus
from clawos_core.util.time import now_iso
from clawos_core.events.bus import get_bus, EV_TASK_UPDATE, EV_LOG

log = logging.getLogger("agentd")


class AgentManager:
    def __init__(self):
        self._sessions:  dict = {}   # workspace_id → AgentRuntime
        self._tasks:     dict = {}   # task_id → Task
        self._queue:     asyncio.Queue = asyncio.Queue()
        self._running:   bool = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._worker())
        log.info("agentd started")

    async def stop(self):
        self._running = False

    async def _get_session(self, workspace_id: str):
        if workspace_id not in self._sessions:
            # Tier D: check VRAM before starting new parallel session
            try:
                from services.modeld.service import get_vram_scheduler
                sched = get_vram_scheduler()
                ok, reason = sched.can_start(workspace_id)
                if not ok:
                    log.warning(f"VRAM guard blocked new session: {reason}")
                    raise RuntimeError(f"VRAM limit: {reason}")
                sched.register(workspace_id, "")
            except ImportError:
                pass

            from runtimes.agent.runtime import build_runtime
            self._sessions[workspace_id] = await build_runtime(workspace_id)
            log.info(f"New session for workspace: {workspace_id}")
        return self._sessions[workspace_id]

    async def submit(self, intent: str, workspace_id: str = DEFAULT_WORKSPACE,
                     channel: str = "cli") -> Task:
        task = Task(intent=intent, workspace=workspace_id, channel=channel)
        self._tasks[task.task_id] = task
        await self._queue.put(task)
        await get_bus().emit_task(task.task_id, "queued")
        return task

    async def _worker(self):
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            await self._run_task(task)

    async def _run_task(self, task: Task):
        task.status     = TaskStatus.RUNNING
        task.started_at = now_iso()
        await get_bus().emit_task(task.task_id, "running", task.intent[:60])

        try:
            session = await self._get_session(task.workspace)
            result  = await session.chat(task.intent)
            task.result      = result
            task.status      = TaskStatus.COMPLETED
            task.finished_at = now_iso()
            await get_bus().emit_task(task.task_id, "completed", result[:120])
        except Exception as e:
            task.error       = str(e)
            task.status      = TaskStatus.FAILED
            task.finished_at = now_iso()
            log.error(f"Task {task.task_id} failed: {e}")
            await get_bus().emit_task(task.task_id, "failed", str(e))

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> list[dict]:
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    async def chat_direct(self, message: str,
                          workspace_id: str = DEFAULT_WORKSPACE) -> str:
        """Direct chat — bypasses task queue for interactive CLI use."""
        session = await self._get_session(workspace_id)
        return await session.chat(message)

    async def chat_direct_with_steps(self, message: str,
                                      workspace_id: str = DEFAULT_WORKSPACE) -> dict:
        """Direct chat returning reply + tool_steps for dashboard display."""
        session = await self._get_session(workspace_id)
        return await session.chat_with_steps(message)

    async def reset_session(self, workspace_id: str):
        if workspace_id in self._sessions:
            await self._sessions[workspace_id].reset()
            log.info(f"Session reset: {workspace_id}")


    async def start_api(self):
        """Start agentd HTTP API on PORT_AGENTD for dashboard integration."""
        try:
            from fastapi import FastAPI
            import uvicorn
            from clawos_core.constants import PORT_AGENTD, DEFAULT_WORKSPACE
            api = FastAPI(title="agentd API")

            @api.get("/tasks")
            def list_tasks_endpoint():
                return self.list_tasks(50)

            @api.post("/submit")
            async def submit_endpoint(body: dict):
                intent = body.get("intent", "")
                workspace = body.get("workspace", DEFAULT_WORKSPACE)
                if not intent:
                    return {"error": "no intent"}
                task = await self.submit(intent, workspace)
                return {"task_id": task.task_id, "status": "queued"}

            config = uvicorn.Config(api, host="127.0.0.1", port=PORT_AGENTD,
                                    log_level="warning")
            await uvicorn.Server(config).serve()
        except Exception as e:
            log.warning(f"agentd API not started: {e}")



_mgr: Optional[AgentManager] = None

def get_manager() -> AgentManager:
    global _mgr
    if _mgr is None:
        _mgr = AgentManager()
    return _mgr
