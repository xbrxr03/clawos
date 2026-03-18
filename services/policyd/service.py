"""
ClawOS policyd — Permission Gate
=================================
Every tool call passes through here. No exceptions.

Refactored from policyd.py to use clawos_core primitives.
"""
import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from clawos_core.constants import (
    POLICYD_DB, CLAWOS_DIR, TOOL_SCORE_QUEUE, APPROVAL_TIMEOUT_S
)
from clawos_core.models import Decision, AuditEntry, ApprovalRequest
from clawos_core.util.ids import entry_id, req_id
from clawos_core.util.time import now_iso
import clawos_core.logging.audit as audit_log

log = logging.getLogger("policyd")

# ── Tool risk scores ──────────────────────────────────────────────────────────
TOOL_SCORES: dict[str, int] = {
    "fs.read":          10,
    "fs.list":          8,
    "fs.write":         30,
    "fs.delete":        70,
    "fs.search":        12,
    "web.search":       15,
    "web.fetch":        20,
    "web.download":     40,
    "shell.restricted": 45,
    "shell.elevated":   90,
    "memory.read":      5,
    "memory.write":     10,
    "memory.delete":    40,
    "api.external":     35,
    "device.access":    80,
    "workspace.create": 20,
    "workspace.delete": 75,
    "system.info":      8,
}

BLOCKED_PATHS = [
    "/etc/passwd", "/etc/shadow", "/etc/sudoers",
    "/.ssh/", "/proc/", "/sys/",
]


class HookRegistry:
    """BeforeToolCall / AfterToolCall lifecycle hooks (from Moltis)."""

    def __init__(self):
        self._before: list = []
        self._after:  list = []

    def register_before(self, name: str, fn):
        self._before.append({"name": name, "fn": fn, "enabled": True, "failures": 0})

    def register_after(self, name: str, fn):
        self._after.append({"name": name, "fn": fn, "enabled": True, "failures": 0})

    async def run_before(self, tool: str, target: str, ctx: dict) -> bool:
        for hook in self._before:
            if not hook["enabled"]:
                continue
            try:
                result = hook["fn"](tool, target, ctx)
                if asyncio.iscoroutine(result):
                    result = await result
                if result is False:
                    return False
                hook["failures"] = 0
            except Exception as e:
                hook["failures"] += 1
                log.error(f"Hook '{hook['name']}' error: {e}")
                if hook["failures"] >= 3:  # circuit breaker
                    hook["enabled"] = False
        return True

    async def run_after(self, tool: str, target: str, result: str, ctx: dict):
        for hook in self._after:
            if not hook["enabled"]:
                continue
            try:
                r = hook["fn"](tool, target, result, ctx)
                if asyncio.iscoroutine(r):
                    await r
                hook["failures"] = 0
            except Exception as e:
                hook["failures"] += 1
                if hook["failures"] >= 3:
                    hook["enabled"] = False


class PolicyEngine:
    """
    Core permission engine. asyncio.Event per request — no deadlocks.
    """

    def __init__(self):
        self._pending: dict[str, ApprovalRequest] = {}
        self.hooks = HookRegistry()
        self._db: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        POLICYD_DB.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(POLICYD_DB), check_same_thread=False)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                request_id TEXT PRIMARY KEY, task_id TEXT, workspace TEXT,
                tool TEXT, target TEXT, content TEXT,
                decision TEXT, created_at TEXT, decided_at TEXT
            )
        """)
        self._db.commit()

    def _is_blocked_path(self, target: str) -> bool:
        expanded = target.replace("~", str(Path.home()))
        return any(b.replace("~", str(Path.home())) in expanded for b in BLOCKED_PATHS)

    def _is_within_workspace(self, target: str, workspace_id: str) -> bool:
        from clawos_core.constants import CLAWOS_DIR as _cdir
        ws_root = _cdir / "workspace" / workspace_id
        try:
            tp = Path(target).expanduser().resolve()
            return str(tp).startswith(str(ws_root.resolve()))
        except Exception:
            return True

    def _record(self, decision: Decision, reason: str, tool: str,
                target: str, task_id: str, workspace_id: str) -> tuple:
        entry = AuditEntry(
            tool=tool, target=target[:200], decision=decision.value,
            reason=reason, task_id=task_id, workspace=workspace_id,
        )
        audit_log.write(entry)
        if decision == Decision.DENY:
            log.warning(f"DENY  [{entry.entry_id}] {tool} on '{target[:50]}' — {reason}")
        elif decision == Decision.ALLOW:
            log.debug(f"ALLOW [{entry.entry_id}] {tool}")
        return decision, reason

    async def evaluate(self, tool: str, target: str, task_id: str,
                       workspace_id: str, granted_tools: list[str],
                       content: str = "") -> tuple[Decision, str]:
        ctx = {"task_id": task_id, "workspace_id": workspace_id}

        if not await self.hooks.run_before(tool, target, ctx):
            return self._record(Decision.DENY, "blocked by hook", tool, target, task_id, workspace_id)

        if tool not in granted_tools:
            return self._record(Decision.DENY, "tool not granted", tool, target, task_id, workspace_id)

        if self._is_blocked_path(target):
            return self._record(Decision.DENY, "blocked path", tool, target, task_id, workspace_id)

        if tool in ("fs.read", "fs.write", "fs.list", "fs.delete", "fs.search"):
            if not self._is_within_workspace(target, workspace_id):
                return self._record(
                    Decision.DENY, f"path outside workspace ({workspace_id})",
                    tool, target, task_id, workspace_id
                )

        score = TOOL_SCORES.get(tool, 50)
        if score >= TOOL_SCORE_QUEUE:
            decision, reason = await self._queue_for_approval(
                tool, target, task_id, workspace_id, content
            )
            return self._record(decision, reason, tool, target, task_id, workspace_id)

        return self._record(Decision.ALLOW, "policy pass", tool, target, task_id, workspace_id)

    async def _queue_for_approval(self, tool: str, target: str, task_id: str,
                                   workspace_id: str, content: str) -> tuple:
        req = ApprovalRequest(
            tool=tool, target=target, content=content,
            task_id=task_id, workspace=workspace_id,
        )
        self._pending[req.request_id] = req

        self._db.execute(
            "INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?)",
            (req.request_id, task_id, workspace_id, tool, target,
             content[:500], "PENDING", now_iso(), None)
        )
        self._db.commit()

        # Emit event to dashboard / WhatsApp approval bridge
        try:
            from clawos_core.events.bus import get_bus
            await get_bus().emit_approval(req.request_id, tool, target, workspace_id)
        except Exception:
            pass

        # Terminal prompt (fallback when no dashboard/WhatsApp)
        print(f"\n  ⏸  Approval required [{req.request_id}]")
        print(f"     Tool:   {tool}")
        print(f"     Target: {target[:80]}")
        if content:
            print(f"     Content: {content[:100]}...")
        print(f"     [a]pprove / [d]eny: ", end="", flush=True)

        loop = asyncio.get_event_loop()
        try:
            choice = await asyncio.wait_for(
                loop.run_in_executor(None, input, ""),
                timeout=APPROVAL_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            choice = "d"
            print("timeout — auto-denied")

        decision = Decision.ALLOW if choice.strip().lower() in ("a", "approve", "y", "yes", "") \
                   else Decision.DENY
        reason = f"human {'approved' if decision == Decision.ALLOW else 'denied'} [{req.request_id}]"

        req.decision = decision
        req.event.set()
        del self._pending[req.request_id]

        self._db.execute(
            "UPDATE approvals SET decision=?, decided_at=? WHERE request_id=?",
            (decision.value, now_iso(), req.request_id)
        )
        self._db.commit()
        print()
        return decision, reason

    def get_pending_approvals(self) -> list[dict]:
        return [{"request_id": r.request_id, "tool": r.tool,
                 "target": r.target, "task_id": r.task_id}
                for r in self._pending.values()]

    def decide_approval(self, request_id: str, approve: bool) -> bool:
        """Decide from dashboard or WhatsApp reply."""
        if request_id not in self._pending:
            return False
        req = self._pending[request_id]
        req.decision = Decision.ALLOW if approve else Decision.DENY
        req.event.set()
        return True

    def get_audit_tail(self, n: int = 20) -> list[dict]:
        return audit_log.tail(n)


# ── Singleton ──────────────────────────────────────────────────────────────────
_engine: Optional[PolicyEngine] = None

def get_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine
