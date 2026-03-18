"""
Local policy adapter — thin wrapper around PolicyEngine.
Used by toolbridge and agentd to check permissions.
"""
import logging
log = logging.getLogger("policy_adapter")

class LocalPolicyAdapter:
    def __init__(self, workspace_id: str, task_id: str, granted_tools: list[str]):
        self.workspace_id  = workspace_id
        self.task_id       = task_id
        self.granted_tools = granted_tools
        self._engine       = None

    def _get_engine(self):
        if self._engine is None:
            from services.policyd.service import get_engine
            self._engine = get_engine()
        return self._engine

    async def check(self, tool: str, target: str, content: str = "") -> tuple[str, str]:
        engine = self._get_engine()
        decision, reason = await engine.evaluate(
            tool=tool, target=target, task_id=self.task_id,
            workspace_id=self.workspace_id,
            granted_tools=self.granted_tools, content=content,
        )
        return decision.value, reason

    def register_before_hook(self, name: str, fn):
        self._get_engine().hooks.register_before(name, fn)

    def register_after_hook(self, name: str, fn):
        self._get_engine().hooks.register_after(name, fn)

    def get_audit_tail(self, n: int = 10) -> list[dict]:
        return self._get_engine().get_audit_tail(n)

    def decide_approval(self, request_id: str, approve: bool) -> bool:
        return self._get_engine().decide_approval(request_id, approve)
