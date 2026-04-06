# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Competitive feature-acquisition contract tests.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

SETUP_HEADERS = {"X-ClawOS-Setup": "1"}


def test_catalog_detects_openclaw_manifest(monkeypatch):
    from clawos_core import catalog

    openclaw_dir = Path.home() / ".openclaw"

    class FakeSkillDir:
        name = "custom-briefing"

        def is_dir(self):
            return True

    class Result:
        stdout = "openclaw 1.2.3"
        stderr = ""

    monkeypatch.setattr(catalog, "_openclaw_dir", lambda path_hint="": openclaw_dir)
    monkeypatch.setattr(
        catalog,
        "_read_json",
        lambda path: {
            "channels": {"whatsapp": {}, "discord": {}},
            "models": {"providers": {"ollama": {}, "openrouter": {}}},
            "skills": {"web-browser": {}, "calendar": {}},
        },
    )
    monkeypatch.setattr(catalog.shutil, "which", lambda name: "openclaw" if name == "openclaw" else None)
    monkeypatch.setattr(catalog.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: str(self).endswith("openclaw.json") or str(self).endswith("skills"),
    )
    monkeypatch.setattr(
        Path,
        "iterdir",
        lambda self: [FakeSkillDir()] if str(self).endswith("skills") else [],
    )

    manifest = catalog.detect_openclaw_install()

    assert manifest.detected_version == "openclaw 1.2.3"
    assert "whatsapp" in manifest.channels
    assert "ollama" in manifest.providers
    assert "custom-briefing" in manifest.skills
    assert manifest.suggested_primary_pack == "chat-app-command-center"
    assert manifest.env_summary["anthropic_key"] is True


def test_setupd_supports_pack_selection_and_openclaw_import(monkeypatch):
    from clawos_core.models import OpenClawImportManifest
    from services.setupd import service as setup_service
    from services.setupd.state import SetupState

    seed_state = SetupState(
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        detected_hardware={"summary": "Tier B - 16 GB RAM - CPU only", "tier": "B"},
        selected_models=["qwen2.5:7b"],
    )

    monkeypatch.setattr(setup_service.SetupState, "load", classmethod(lambda cls: seed_state))
    monkeypatch.setattr(setup_service.SetupState, "save", lambda self, path=None: None)
    monkeypatch.setattr(setup_service, "record_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_service, "sync_presence_from_setup", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        setup_service,
        "detect_openclaw_install",
        lambda source_path="": OpenClawImportManifest(
            source_path=source_path or str(Path.home() / ".openclaw"),
            config_path=str(Path.home() / ".openclaw" / "openclaw.json"),
            detected_version="openclaw 1.2.3",
            channels=["whatsapp"],
            providers=["ollama"],
            skills=["web-browser"],
            migration_actions=["Import safe config"],
            suggested_primary_pack="chat-app-command-center",
        ),
    )

    setup_service._SERVICE = None
    app = setup_service.create_app()

    with TestClient(app) as client:
        inspect_payload = client.post("/api/setup/inspect", headers=SETUP_HEADERS)
        assert inspect_payload.status_code == 200
        assert inspect_payload.json()["state"]["progress_stage"] == "inspected"

        select_payload = client.post(
            "/api/setup/select-pack",
            headers=SETUP_HEADERS,
            json={"pack_id": "coding-autopilot", "provider_profile": "local-ollama"},
        )
        assert select_payload.status_code == 200
        assert select_payload.json()["primary_pack"] == "coding-autopilot"

        import_payload = client.post("/api/setup/import/openclaw", headers=SETUP_HEADERS, json={})
        assert import_payload.status_code == 200
        assert import_payload.json()["suggested_primary_pack"] == "chat-app-command-center"


def test_dashd_exposes_competitive_surface(monkeypatch):
    from services.dashd.api import create_app
    from services.setupd.state import SetupState

    state = SetupState(
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        selected_provider_profile="local-ollama",
        primary_pack="daily-briefing-os",
        secondary_packs=["coding-autopilot"],
        installed_extensions=["mcp-manager"],
    )

    monkeypatch.setattr("services.setupd.state.SetupState.load", classmethod(lambda cls: state))
    monkeypatch.setattr("services.setupd.state.SetupState.save", lambda self, path=None: None)
    monkeypatch.setattr(
        "services.dashd.api.test_provider_profile",
        lambda profile_id: {"ok": profile_id == "local-ollama", "status": "configured", "detail": "ready"},
    )
    monkeypatch.setattr("services.dashd.api.record_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.a2ad.discovery.get_local_ip", lambda: "127.0.0.1")
    monkeypatch.setattr("services.a2ad.discovery.get_peers", lambda: [{"name": "Peer A", "url": "http://127.0.0.1:7083/a2a"}])
    async def _delegate_to_peer(peer_url, intent, workspace):
        return "delegated-result"

    monkeypatch.setattr("services.gatewayd.service.delegate_to_peer", _delegate_to_peer)

    app = create_app(
        {
            "host": "127.0.0.1",
            "auth_required": True,
            "token": "dash-token",
            "cookie_name": "dash_session",
        }
    )

    with TestClient(app) as client:
        assert client.post("/api/login", json={"token": "dash-token"}).status_code == 200

        packs = client.get("/api/packs")
        assert packs.status_code == 200
        assert any(item["primary"] for item in packs.json())

        providers = client.get("/api/providers")
        assert providers.status_code == 200
        assert any(item["selected"] for item in providers.json())

        extensions = client.get("/api/extensions")
        assert extensions.status_code == 200
        assert any(item["installed"] for item in extensions.json())

        evals = client.get("/api/evals")
        assert evals.status_code == 200
        assert any(item["active"] for item in evals.json())

        card = client.get("/api/a2a/agent-card")
        assert card.status_code == 200
        assert card.json()["card"]["name"].startswith("ClawOS-")

        delegate = client.post(
            "/api/a2a/tasks",
            json={"peer_url": "http://127.0.0.1:7083/a2a", "intent": "summarize repo"},
        )
        assert delegate.status_code == 200
        assert delegate.json()["result"] == "delegated-result"
