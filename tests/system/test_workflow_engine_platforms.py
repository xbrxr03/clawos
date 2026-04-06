# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio

from workflows.engine import WorkflowEngine, WorkflowMeta, WorkflowResult, WorkflowStatus


def test_engine_skips_agent_for_direct_workflow():
    class DirectWorkflow:
        META = WorkflowMeta(
            id="direct-test",
            name="Direct Test",
            category="system",
            description="direct execution test",
            needs_agent=False,
            platforms=["linux", "macos", "windows"],
        )

        @staticmethod
        async def run(args, agent):
            assert agent is None
            return WorkflowResult(status=WorkflowStatus.OK, output="ok")

    engine = WorkflowEngine()
    engine._registry = {"direct-test": DirectWorkflow}

    result = asyncio.run(engine.run("direct-test", {}))
    assert result.status == WorkflowStatus.OK
    assert result.output == "ok"


def test_engine_skips_unsupported_platform():
    unsupported = "linux"
    if WorkflowEngine()._current_platform() == "linux":
        unsupported = "macos"

    class UnsupportedWorkflow:
        META = WorkflowMeta(
            id="unsupported-test",
            name="Unsupported Test",
            category="system",
            description="unsupported platform test",
            needs_agent=False,
            platforms=[unsupported],
        )

        @staticmethod
        async def run(args, agent):
            return WorkflowResult(status=WorkflowStatus.OK, output="should not run")

    engine = WorkflowEngine()
    engine._registry = {"unsupported-test": UnsupportedWorkflow}

    result = asyncio.run(engine.run("unsupported-test", {}))
    assert result.status == WorkflowStatus.SKIPPED
    assert "supported platforms" in (result.error or "")
