# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def test_agentd_submit_contract_uses_submit_and_intent_only():
    from services.agentd.service import AgentManager, create_api

    manager = AgentManager()
    app = create_api(manager)

    with TestClient(app) as client:
        response = client.post("/submit", json={"intent": "summarize repo", "workspace": "ws-1", "channel": "dashboard"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "queued"
        assert payload["task_id"]

        legacy_payload = client.post("/submit", json={"task": "legacy field"})
        assert legacy_payload.status_code == 400

        legacy_route = client.post("/tasks", json={"intent": "legacy route"})
        assert legacy_route.status_code == 405

        listed = client.get("/tasks")
        assert listed.status_code == 200
        assert len(listed.json()) == 1


def test_destructive_workflow_is_gated_through_policyd(monkeypatch, workspace_tmp_dir):
    from clawos_core.models import Decision
    from workflows.engine import WorkflowEngine, WorkflowStatus

    class FakePolicyEngine:
        async def evaluate(self, **kwargs):
            return Decision.DENY, "policy deny"

    monkeypatch.setattr("services.policyd.service.get_engine", lambda: FakePolicyEngine())

    target = workspace_tmp_dir / "workspace"
    (target / "empty").mkdir(parents=True)

    engine = WorkflowEngine()
    engine.load_registry()
    result = asyncio.run(engine.run("clean-empty-dirs", {"dir": str(target)}, workspace_id="nexus_default"))

    assert result.status == WorkflowStatus.SKIPPED
    assert result.error == "Denied by policy"


def test_shell_restricted_is_the_only_shell_tool_alias():
    from services.toolbridge.service import ALL_TOOL_DESCRIPTIONS, TOOL_ALIASES

    assert TOOL_ALIASES == {}
    assert "shell.run" not in ALL_TOOL_DESCRIPTIONS
    assert "Alias" not in ALL_TOOL_DESCRIPTIONS["shell.restricted"]
