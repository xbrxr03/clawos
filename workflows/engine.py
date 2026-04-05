"""
ClawOS Workflow Engine — Phase 11
==================================
Loads, lists, and executes pre-built workflows.

Each workflow lives at workflows/<name>/workflow.py and must expose:
  META: WorkflowMeta
  async def run(args: dict, agent) -> WorkflowResult
"""
import asyncio
import importlib
import sys
import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_WORKFLOWS_DIR = Path(__file__).parent


# ── Data classes ─────────────────────────────────────────────────────────────

class WorkflowStatus(str, Enum):
    OK      = "ok"
    FAILED  = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowMeta:
    id:          str
    name:        str
    category:    str          # files|documents|developer|content|system|data
    description: str
    tags:        List[str] = field(default_factory=list)
    requires:    List[str] = field(default_factory=list)   # binaries: ["git", "pandoc"]
    destructive: bool      = False                          # gates through policyd
    timeout_s:   int       = 120


@dataclass
class WorkflowResult:
    status:   WorkflowStatus
    output:   str
    metadata: dict         = field(default_factory=dict)
    error:    Optional[str] = None


# ── Engine ────────────────────────────────────────────────────────────────────

class WorkflowEngine:
    def __init__(self):
        self._registry: dict = {}   # id → workflow module
        self._loaded:   bool = False

    # ── Registry ─────────────────────────────────────────────────────────────

    def load_registry(self) -> None:
        """Walk workflows/*/workflow.py, import each, register by META.id.
        Per-module import errors are caught and warned — never raised."""
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
                    warnings.warn(f"[workflow] {module_name}: no valid META — skipped")
                    continue
                self._registry[meta.id] = mod
            except Exception as exc:
                warnings.warn(f"[workflow] {module_name}: import error — {exc}")
        self._loaded = True

    def list_workflows(
        self,
        category: Optional[str] = None,
        search:   Optional[str] = None,
    ) -> List[WorkflowMeta]:
        """Return registry as sorted list, optionally filtered."""
        metas = [mod.META for mod in self._registry.values()]
        if category:
            metas = [m for m in metas if m.category == category]
        if search:
            q = search.lower()
            metas = [m for m in metas
                     if q in m.name.lower() or q in m.description.lower()
                     or any(q in t for t in m.tags)]
        return sorted(metas, key=lambda m: (m.category, m.name))

    # ── Execution ─────────────────────────────────────────────────────────────

    async def run(
        self,
        workflow_id:  str,
        args:         dict,
        workspace_id: str = "nexus_default",
    ) -> WorkflowResult:
        """
        1. Resolve workflow from registry.
        2. Gate destructive workflows through policyd.
        3. Get AgentRuntime via agentd session.
        4. Execute workflow.run(args, agent) with timeout.
        5. Emit progress events on event bus.
        """
        if workflow_id not in self._registry:
            raise KeyError(f"Unknown workflow: {workflow_id}")

        mod  = self._registry[workflow_id]
        meta = mod.META

        # Destructive gate
        if meta.destructive:
            allowed = await self._gate_policyd(workflow_id, workspace_id)
            if not allowed:
                return WorkflowResult(
                    status=WorkflowStatus.SKIPPED,
                    output="",
                    error="Denied by policy",
                )

        # Get agent
        agent = await self._get_agent(workspace_id)

        # Emit start event
        await self._emit("workflow_progress", {
            "id": workflow_id, "status": "running", "name": meta.name
        })

        try:
            result = await asyncio.wait_for(
                mod.run(args, agent),
                timeout=meta.timeout_s,
            )
        except asyncio.TimeoutError:
            result = WorkflowResult(
                status=WorkflowStatus.FAILED,
                output="",
                error=f"Timed out after {meta.timeout_s}s",
            )
        except Exception as exc:
            result = WorkflowResult(
                status=WorkflowStatus.FAILED,
                output="",
                error=str(exc),
            )

        # Emit completion event
        event_type = "workflow_progress" if result.status == WorkflowStatus.OK else "workflow_error"
        await self._emit(event_type, {
            "id":     workflow_id,
            "status": result.status.value,
            "output": result.output[:500] if result.output else "",
            "error":  result.error,
        })

        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _gate_policyd(self, workflow_id: str, workspace_id: str) -> bool:
        """Gate destructive workflow through policyd. Returns True = allowed."""
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
        except Exception:
            # If policyd unavailable, default deny for destructive
            return False

    async def _get_agent(self, workspace_id: str):
        """Get or create an AgentRuntime session for this workspace."""
        try:
            from services.agentd.service import get_manager
            manager = get_manager()
            return await manager._get_session(workspace_id)
        except Exception:
            # Fallback: build a fresh runtime directly
            from runtimes.agent.runtime import build_runtime
            from clawos_core.constants import DEFAULT_MODEL
            return await build_runtime(workspace_id, DEFAULT_MODEL)

    async def _emit(self, event_type: str, data: dict) -> None:
        """Emit to event bus if available — never raises."""
        try:
            from clawos_core.events.bus import get_bus
            await get_bus().publish(event_type, data)
        except Exception:
            pass

    def _ensure_agentd(self) -> None:
        """Raise RuntimeError with a clear message if agentd is unreachable."""
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:7072/health", timeout=2)
        except Exception:
            raise RuntimeError(
                "agentd is not running. Start ClawOS first: clawctl start"
            )


# ── Singleton ─────────────────────────────────────────────────────────────────

_engine: Optional[WorkflowEngine] = None


def get_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
