# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Workflow loading and execution for built-in ClawOS workflows.

Each workflow lives at workflows/<name>/workflow.py and must expose:
  META: WorkflowMeta
  async def run(args: dict, agent) -> WorkflowResult
"""

from __future__ import annotations

import asyncio
import contextvars
import importlib
import sys
import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from clawos_core.platform import platform_key

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_WORKFLOWS_DIR = Path(__file__).parent
_PLATFORM_ALIASES = {
    "macos": "darwin",
    "osx": "darwin",
}
_CURRENT_WORKFLOW_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_workflow_id",
    default="",
)
_CURRENT_WORKFLOW_NAME: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_workflow_name",
    default="",
)


class WorkflowStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowMeta:
    id: str
    name: str
    category: str
    description: str
    tags: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    destructive: bool = False
    platforms: List[str] = field(default_factory=list)
    needs_agent: bool = True
    timeout_s: int = 120


@dataclass
class WorkflowResult:
    status: WorkflowStatus
    output: str
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None


async def emit_workflow_progress(
    message: str,
    *,
    phase: str | None = None,
    progress: int | None = None,
    workflow_id: str | None = None,
    name: str | None = None,
    output: str | None = None,
    extra: dict | None = None,
) -> None:
    resolved_id = workflow_id or _CURRENT_WORKFLOW_ID.get()
    if not resolved_id:
        return

    payload: dict[str, object] = {
        "id": resolved_id,
        "status": "running",
        "message": str(message or "").strip(),
    }
    resolved_name = name or _CURRENT_WORKFLOW_NAME.get()
    if resolved_name:
        payload["name"] = resolved_name
    if phase:
        payload["phase"] = phase
    if progress is not None:
        payload["progress"] = max(0, min(100, int(progress)))
    if output:
        payload["output"] = output[:500]
    if extra:
        payload.update(extra)

    try:
        from clawos_core.events.bus import get_bus

        await get_bus().publish("workflow_progress", payload)
    except (ImportError, ModuleNotFoundError):
        return


class WorkflowEngine:
    def __init__(self):
        self._registry: dict = {}
        self._loaded: bool = False

    def load_registry(self) -> None:
        if self._loaded:
            return
        for wf_dir in sorted(_WORKFLOWS_DIR.iterdir()):
            if not wf_dir.is_dir():
                continue
            wf_file = wf_dir / "workflow.py"
            if not wf_file.exists():
                continue
            module_name = f"workflows.{wf_dir.name}.workflow"
            try:
                mod = importlib.import_module(module_name)
                meta = getattr(mod, "META", None)
                if meta is None or not isinstance(meta, WorkflowMeta):
                    warnings.warn(f"[workflow] {module_name}: no valid META - skipped")
                    continue
                self._registry[meta.id] = mod
            except (AttributeError, TypeError) as exc:
                warnings.warn(f"[workflow] {module_name}: import error - {exc}")
        self._loaded = True

    def list_workflows(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[WorkflowMeta]:
        metas = [mod.META for mod in self._registry.values()]
        if category:
            metas = [m for m in metas if m.category == category]
        if search:
            query = search.lower()
            metas = [
                m for m in metas
                if query in m.name.lower()
                or query in m.description.lower()
                or any(query in tag.lower() for tag in m.tags)
            ]
        return sorted(metas, key=lambda m: (m.category, m.name))

    async def run(
        self,
        workflow_id: str,
        args: dict,
        workspace_id: str = "nexus_default",
    ) -> WorkflowResult:
        if workflow_id not in self._registry:
            raise KeyError(f"Unknown workflow: {workflow_id}")

        mod = self._registry[workflow_id]
        meta = mod.META

        if not self._supports_platform(meta):
            return WorkflowResult(
                status=WorkflowStatus.SKIPPED,
                output="",
                error=(
                    f"Unsupported on {self._current_platform()}; "
                    f"supported platforms: {', '.join(meta.platforms)}"
                ),
            )

        workflow_token = _CURRENT_WORKFLOW_ID.set(workflow_id)
        name_token = _CURRENT_WORKFLOW_NAME.set(meta.name)
        try:
            await emit_workflow_progress(
                "Preparing workflow runtime",
                workflow_id=workflow_id,
                name=meta.name,
                phase="prepare",
                progress=5,
            )

            if meta.destructive:
                allowed = await self._gate_policyd(workflow_id, workspace_id)
                if not allowed:
                    return WorkflowResult(
                        status=WorkflowStatus.SKIPPED,
                        output="",
                        error="Denied by policy",
                    )

            agent = None
            if meta.needs_agent:
                await emit_workflow_progress(
                    "Connecting workflow agent",
                    phase="prepare",
                    progress=12,
                )
                agent = await self._get_agent(workspace_id)

            await emit_workflow_progress(
                "Workflow execution started",
                phase="run",
                progress=18,
            )

            try:
                result = await asyncio.wait_for(mod.run(args, agent), timeout=meta.timeout_s)
            except asyncio.TimeoutError:
                result = WorkflowResult(
                    status=WorkflowStatus.FAILED,
                    output="",
                    error=f"Timed out after {meta.timeout_s}s",
                )
            except (RuntimeError, OSError, TypeError) as exc:
                result = WorkflowResult(
                    status=WorkflowStatus.FAILED,
                    output="",
                    error=str(exc),
                )

            payload = {
                "id": workflow_id,
                "status": result.status.value,
                "name": meta.name,
                "output": result.output[:500] if result.output else "",
                "error": result.error,
                "progress": 100,
                "phase": "complete",
                "message": result.error or "Workflow finished",
            }
            event_type = "workflow_progress" if result.status != WorkflowStatus.FAILED else "workflow_error"
            await self._emit(event_type, payload)
            return result
        finally:
            _CURRENT_WORKFLOW_ID.reset(workflow_token)
            _CURRENT_WORKFLOW_NAME.reset(name_token)

    async def _gate_policyd(self, workflow_id: str, workspace_id: str) -> bool:
        try:
            from services.policyd.service import get_engine
            from clawos_core.models import Decision
            from clawos_core.util.ids import task_id as next_task_id

            engine = get_engine()
            decision, _ = await engine.evaluate(
                tool="workflow.destructive",
                target=workflow_id,
                task_id=next_task_id(),
                workspace_id=workspace_id,
                granted_tools=["workflow.destructive"],
            )
            return decision == Decision.ALLOW
        except (ImportError, ModuleNotFoundError):
            return False

    async def _get_agent(self, workspace_id: str):
        try:
            from services.agentd.service import get_manager

            manager = get_manager()
            return await manager._get_session(workspace_id)
        except (ImportError, ModuleNotFoundError):
            from clawos_core.constants import DEFAULT_MODEL
            from runtimes.agent.runtime import build_runtime

            return await build_runtime(workspace_id, DEFAULT_MODEL)

    async def _emit(self, event_type: str, data: dict) -> None:
        try:
            from clawos_core.events.bus import get_bus

            await get_bus().publish(event_type, data)
        except (ImportError, ModuleNotFoundError):
            pass
            pass

    def _current_platform(self) -> str:
        return platform_key()

    def _normalize_platform(self, name: str) -> str:
        lowered = name.strip().lower()
        return _PLATFORM_ALIASES.get(lowered, lowered)

    def _supports_platform(self, meta: WorkflowMeta) -> bool:
        if not meta.platforms:
            return True
        current = self._normalize_platform(self._current_platform())
        supported = {self._normalize_platform(name) for name in meta.platforms}
        return current in supported

    def _ensure_agentd(self) -> None:
        import urllib.request

        try:
            urllib.request.urlopen("http://localhost:7072/health", timeout=2)
        except (OSError, ConnectionRefusedError, TimeoutError) as exc:
            raise RuntimeError(
                "agentd is not running. Start ClawOS first: clawctl start"
            ) from exc


_engine: Optional[WorkflowEngine] = None


def get_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
