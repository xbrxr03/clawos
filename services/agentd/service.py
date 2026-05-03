# SPDX-License-Identifier: AGPL-3.0-or-later
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
            except ImportError as e:
                log.debug(f"suppressed: {e}")

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

            # ── Kizuna GraphRAG: prepend brain context to intent ──────────────
            enriched_intent = task.intent
            try:
                from services.braind.service import get_brain
                brain = get_brain()
                if brain.stats().get("node_count", 0) > 0:
                    ctx = brain.get_context(task.intent, top_n=6)
                    if ctx.get("context_text"):
                        enriched_intent = f"{ctx['context_text']}\n\n{task.intent}"
                        log.debug(f"Kizuna context injected: {len(ctx['nodes'])} nodes")
            except (ImportError, ModuleNotFoundError) as brain_err:
                log.debug(f"Kizuna context skipped: {brain_err}")

            result = await session.chat(enriched_intent)
            task.result      = result
            task.status      = TaskStatus.COMPLETED
            task.finished_at = now_iso()
            await get_bus().emit_task(task.task_id, "completed", result[:120])

            # ── Kizuna write-back: add new knowledge from result ─────────────
            try:
                from services.braind.service import get_brain
                brain = get_brain()
                asyncio.create_task(
                    brain.expand_from_agent(result, source="agentd", task_id=task.task_id)
                )
            except (ImportError, ModuleNotFoundError) as expand_err:
                log.debug(f"Kizuna expand skipped: {expand_err}")

        except (OSError, ValueError) as e:
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

    def _derive_channel(self, channel: str = "cli", source: str = "") -> str:
        if channel and channel != "cli":
            return channel
        if source:
            return source.split(":", 1)[0]
        return channel or "cli"

    def _apply_session_context(self, session, channel: str = "cli", source: str = "") -> None:
        try:
            session.session.channel = self._derive_channel(channel, source)
            if source:
                session.session.contact_id = source
        except (OSError, RuntimeError, AttributeError) as e:
            log.debug(f"unexpected: {e}")
            pass
            pass

    async def chat_direct(self, message: str,
                          workspace_id: str = DEFAULT_WORKSPACE,
                          channel: str = "cli",
                          source: str = "") -> str:
        """Direct chat — bypasses task queue for interactive CLI use."""
        session = await self._get_session(workspace_id)
        self._apply_session_context(session, channel=channel, source=source)
        return await session.chat(message)

    async def chat_direct_with_steps(self, message: str,
                                      workspace_id: str = DEFAULT_WORKSPACE,
                                      channel: str = "cli",
                                      source: str = "") -> dict:
        """Direct chat returning reply + tool_steps for dashboard display."""
        session = await self._get_session(workspace_id)
        self._apply_session_context(session, channel=channel, source=source)
        return await session.chat_with_steps(message)

    async def reset_session(self, workspace_id: str):
        if workspace_id in self._sessions:
            await self._sessions[workspace_id].reset()
            log.info(f"Session reset: {workspace_id}")

    async def start_api(self):
        """Start agentd HTTP API on PORT_AGENTD for dashboard integration."""
        try:
            import uvicorn
            from clawos_core.constants import PORT_AGENTD

            api = create_api(self)
            config = uvicorn.Config(api, host="127.0.0.1", port=PORT_AGENTD,
                                    log_level="warning")
            await uvicorn.Server(config).serve()
        except (ImportError, ModuleNotFoundError) as e:
            log.warning(f"agentd API not started: {e}")


def create_api(manager: Optional[AgentManager] = None):
    from fastapi import FastAPI, HTTPException

    from clawos_core.constants import DEFAULT_WORKSPACE

    manager = manager or get_manager()
    api = FastAPI(title="agentd API")

    def _parse_body(body: dict | None) -> tuple[str, str, str]:
        body = body or {}
        intent = str(body.get("intent", "")).strip()
        workspace = str(body.get("workspace") or DEFAULT_WORKSPACE).strip() or DEFAULT_WORKSPACE
        channel = str(body.get("channel") or "api").strip() or "api"
        return intent, workspace, manager._derive_channel(channel=channel)

    async def _submit_from_body(body: dict | None):
        intent, workspace, channel = _parse_body(body)
        if not intent:
            raise HTTPException(status_code=400, detail="intent required")
        task = await manager.submit(intent, workspace, channel=channel)
        return {"task_id": task.task_id, "status": "queued"}

    @api.get("/health")
    def health_endpoint():
        return {
            "status": "ok",
            "running": manager._running,
            "tasks": len(manager._tasks),
            "sessions": len(manager._sessions),
        }

    @api.get("/tasks")
    def list_tasks_endpoint(limit: int = 50):
        return manager.list_tasks(limit)

    @api.post("/submit")
    async def submit_endpoint(body: dict):
        return await _submit_from_body(body)

    return api



_mgr: Optional[AgentManager] = None

def get_manager() -> AgentManager:
    global _mgr
    if _mgr is None:
        _mgr = AgentManager()
    return _mgr
