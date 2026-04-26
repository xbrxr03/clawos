# SPDX-License-Identifier: AGPL-3.0-or-later
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


def test_setup_state_roundtrip(monkeypatch):
    from services.setupd.state import SetupState

    storage: dict[str, str] = {}
    path = Path("virtual_setup_state.json")

    monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: None)
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda self, text, encoding="utf-8": storage.__setitem__(str(self), text) or len(text),
    )
    monkeypatch.setattr(Path, "read_text", lambda self, encoding="utf-8": storage[str(self)])
    monkeypatch.setattr(Path, "exists", lambda self: str(self) in storage)

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
    monkeypatch.setattr(setup_service.SetupState, "save", lambda self, path=None: None)
    monkeypatch.setattr("bootstrap.bootstrap.run", lambda **_: {"ok": True})
    monkeypatch.setattr("bootstrap.model_provision.ensure_model", lambda model, show=True, progress_callback=None: True)
    monkeypatch.setattr(setup_service, "start_service", lambda _name: (True, "started"))
    monkeypatch.setattr(setup_service, "autostart_supported", lambda: True)
    monkeypatch.setattr(setup_service, "enable_launch_on_login", lambda: Path("/tmp/clawos-command-center.desktop"))
    monkeypatch.setattr(setup_service, "record_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_service, "sync_presence_from_setup", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_service, "install_picoclaw", lambda: (True, "picoclaw ready (mock)"))
    monkeypatch.setattr(setup_service, "install_openclaw", lambda: (True, "openclaw ready (mock)"))
    monkeypatch.setattr(setup_service, "install_openclaude", lambda: (True, "openclaude ready (mock)"))

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


def test_setupd_options_and_model_preparation(monkeypatch):
    from services.setupd import service as setup_service
    from services.setupd.state import SetupState

    seed_state = SetupState(
        install_channel="desktop",
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        detected_hardware={"summary": "Tier B - 16 GB RAM - CPU only", "tier": "B", "has_mic": True},
        selected_models=["qwen2.5:7b"],
        selected_provider_profile="local-ollama",
    )

    def fake_ensure_model(model, show_progress=True, progress_callback=None):
        if progress_callback:
            progress_callback({"model": model, "status": "pulling manifest", "percent": 12, "eta_seconds": 40})
            progress_callback({"model": model, "status": "ready", "percent": 100, "eta_seconds": 0})
        return True

    monkeypatch.setattr(setup_service.SetupState, "load", classmethod(lambda cls: seed_state))
    monkeypatch.setattr(setup_service.SetupState, "save", lambda self, path=None: None)
    monkeypatch.setattr(setup_service, "record_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_service, "sync_presence_from_setup", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("bootstrap.model_provision.ensure_model", fake_ensure_model)

    setup_service._SERVICE = None
    app = setup_service.create_app()

    with TestClient(app) as client:
        options = client.post(
            "/api/setup/options",
            headers=SETUP_HEADERS,
            json={"selected_models": ["qwen2.5-coder:7b"], "launch_on_login": False},
        )
        assert options.status_code == 200
        assert options.json()["selected_models"] == ["qwen2.5-coder:7b"]
        assert options.json()["launch_on_login"] is False

        prepare = client.post("/api/setup/model", headers=SETUP_HEADERS, json={"model": "qwen2.5-coder:7b"})
        assert prepare.status_code == 200

        for _ in range(20):
            current = client.get("/api/setup/state", headers=SETUP_HEADERS).json()
            if current["progress_stage"] == "model-ready":
                break
            time.sleep(0.05)

        final_state = client.get("/api/setup/state", headers=SETUP_HEADERS).json()
        assert final_state["progress_stage"] == "model-ready"
        assert final_state["model_pull_progress"]["percent"] == 100
        assert final_state["model_pull_progress"]["model"] == "qwen2.5-coder:7b"
