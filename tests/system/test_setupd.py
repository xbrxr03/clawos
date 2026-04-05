"""
setupd contract tests.
"""
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

SETUP_HEADERS = {"X-ClawOS-Setup": "1"}


def test_setup_state_roundtrip(tmp_path):
    from services.setupd.state import SetupState

    path = tmp_path / "setup_state.json"
    state = SetupState(
        install_channel="desktop",
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        workspace="project_alpha",
        selected_models=["qwen2.5:7b"],
        selected_runtimes=["nexus", "openclaw"],
    )
    state.save(path)

    loaded = SetupState.load(path)
    assert loaded.workspace == "project_alpha"
    assert loaded.selected_models == ["qwen2.5:7b"]
    assert loaded.selected_runtimes == ["nexus", "openclaw"]


def test_setupd_plan_apply_repair_and_diagnostics(monkeypatch):
    from services import setupd as setupd_pkg  # noqa: F401
    from services.setupd import service as setup_service
    from services.setupd.state import SetupState

    seed_state = SetupState(
        install_channel="desktop",
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        detected_hardware={"summary": "Tier B · 16 GB RAM · CPU only", "tier": "B"},
        recommended_profile="balanced",
        selected_runtimes=["nexus", "picoclaw"],
        selected_models=["qwen2.5:7b"],
    )

    monkeypatch.setattr(setup_service.SetupState, "load", classmethod(lambda cls: seed_state))
    monkeypatch.setattr("bootstrap.bootstrap.run", lambda **_: {"ok": True})
    monkeypatch.setattr(setup_service, "start_service", lambda _name: (True, "started"))
    monkeypatch.setattr(setup_service, "autostart_supported", lambda: True)
    monkeypatch.setattr(setup_service, "enable_launch_on_login", lambda: Path("/tmp/clawos-command-center.desktop"))

    setup_service._SERVICE = None
    app = setup_service.create_app()

    with TestClient(app) as client:
        state = client.get("/api/setup/state", headers=SETUP_HEADERS)
        assert state.status_code == 200
        assert state.json()["recommended_profile"] == "balanced"

        plan = client.post("/api/setup/plan", headers=SETUP_HEADERS)
        assert plan.status_code == 200
        assert plan.json()["steps"]

        repair_resp = client.post("/api/setup/repair", headers=SETUP_HEADERS)
        assert repair_resp.status_code == 200

        for _ in range(20):
            current = client.get("/api/setup/state", headers=SETUP_HEADERS).json()
            if current["progress_stage"] in {"planned", "complete"}:
                break
            time.sleep(0.05)

        repaired_state = client.get("/api/setup/state", headers=SETUP_HEADERS).json()
        assert any("Repair checks complete" in entry for entry in repaired_state["logs"])

        diagnostics = client.get("/api/setup/diagnostics", headers=SETUP_HEADERS)
        assert diagnostics.status_code == 200
        assert "service_manager" in diagnostics.json()
        assert "desktop" in diagnostics.json()

        apply_resp = client.post("/api/setup/apply", headers=SETUP_HEADERS)
        assert apply_resp.status_code == 200

        for _ in range(20):
            current = client.get("/api/setup/state", headers=SETUP_HEADERS).json()
            if current["progress_stage"] == "complete":
                break
            time.sleep(0.05)

        final_state = client.get("/api/setup/state", headers=SETUP_HEADERS).json()
        assert final_state["completion_marker"] is True
        assert any("Setup complete" in entry for entry in final_state["logs"])
        assert any("Launch on login enabled" in entry for entry in final_state["logs"])
