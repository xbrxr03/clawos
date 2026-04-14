# SPDX-License-Identifier: AGPL-3.0-or-later
"""
JARVIS OpenClaw integration tests.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_openclaw_adapter_patches_config_for_responses(tmp_path, monkeypatch):
    from openclaw_integration import responses_api

    config_path = tmp_path / "openclaw.json"
    openclaw_dir = tmp_path / ".openclaw"
    token_path = openclaw_dir / "gateway.token"

    monkeypatch.setattr(responses_api, "CONFIG_PATH", config_path)
    monkeypatch.setattr(responses_api, "OPENCLAW_DIR", openclaw_dir)
    monkeypatch.setattr(responses_api, "GATEWAY_TOKEN_PATH", token_path)

    config_path.write_text(json.dumps({"gateway": {"http": {"endpoints": {}}, "auth": {}}}), encoding="utf-8")

    summary = responses_api.ensure_responses_endpoint()
    saved = json.loads(config_path.read_text(encoding="utf-8"))

    assert summary["responses_enabled"] is True
    assert summary["token_present"] is True
    assert summary["config_changed"] is True
    assert saved["gateway"]["http"]["endpoints"]["responses"]["enabled"] is True
    assert saved["gateway"]["auth"]["mode"] == "token"
    assert token_path.exists()
    assert token_path.read_text(encoding="utf-8").strip()


def test_openclaw_adapter_auto_starts_gateway(monkeypatch):
    from openclaw_integration import responses_api

    calls = []
    states = [
        {"installed": True, "running": False, "gateway_port": 18789, "gateway_url": "http://127.0.0.1:18789", "responses_enabled": True},
        {"installed": True, "running": True, "gateway_port": 18789, "gateway_url": "http://127.0.0.1:18789", "responses_enabled": True},
    ]

    def fake_health():
        return states[min(len(calls), 1)] | {
            "auth_mode": "token",
            "token_present": True,
            "config_path": "openclaw.json",
            "token_path": "gateway.token",
            "config_present": True,
            "agent_id": "main",
            "raw_config": {},
        }

    monkeypatch.setattr(responses_api, "gateway_health", fake_health)
    monkeypatch.setattr(responses_api, "start", lambda: calls.append("start"))

    info = responses_api.ensure_gateway_ready()

    assert calls == ["start"]
    assert info["running"] is True


def test_jarvis_service_tracks_separate_threads_with_shared_memory(tmp_path, monkeypatch):
    from services.jarvisd import service as jarvis_service

    state_path = tmp_path / "jarvis_state.json"

    monkeypatch.setattr(jarvis_service, "JARVIS_STATE_JSON", state_path)
    monkeypatch.setattr(jarvis_service, "cfg_get", lambda _key, default=None: default)
    monkeypatch.setattr(jarvis_service, "get_api_key", lambda: "test-elevenlabs-key")
    monkeypatch.setattr(jarvis_service, "gateway_health", lambda: {
        "installed": True,
        "running": True,
        "gateway_port": 18789,
        "gateway_url": "http://127.0.0.1:18789",
        "responses_enabled": True,
        "auth_mode": "token",
        "token_present": True,
        "config_path": "openclaw.json",
        "token_path": "gateway.token",
        "config_present": True,
        "agent_id": "main",
        "raw_config": {},
    })
    monkeypatch.setattr(jarvis_service, "request_response", lambda message, *, session_key, channel, instructions="", previous_response_id="": {
        "text": f"OpenClaw handled {session_key}",
        "response_id": f"resp-{session_key}",
        "session_key": session_key,
        "channel": channel,
        "raw": {"message": message},
    })
    monkeypatch.setattr(jarvis_service, "active_provider", lambda preferred="elevenlabs": preferred or "elevenlabs")
    monkeypatch.setattr(jarvis_service, "available_recorder", lambda: "fake-recorder")
    monkeypatch.setattr(jarvis_service, "default_device_label", lambda: "Fake microphone")
    monkeypatch.setattr(jarvis_service.JarvisService, "_playback_backend", lambda self: "fake-player")

    svc = jarvis_service.JarvisService()

    first = asyncio.run(svc.chat("We were working on project Atlas", thread_key="jarvis-ui", source="jarvis-ui:text", speak_reply=False))
    second = asyncio.run(svc.chat("Status sync", thread_key="whatsapp:15551234567@s.whatsapp.net", source="whatsapp", speak_reply=False))

    state = jarvis_service._load_state()

    assert first["spoken"] is False
    assert second["spoken"] is False
    assert sorted(state["threads"].keys()) == ["jarvis-ui", "whatsapp:15551234567@s.whatsapp.net"]
    assert state["threads"]["jarvis-ui"]["response_id"] == "resp-jarvis-ui"
    assert state["threads"]["whatsapp:15551234567@s.whatsapp.net"]["response_id"] == "resp-whatsapp:15551234567@s.whatsapp.net"
    assert state["shared_memory"]["last_project"] == "Atlas"
    assert svc.health()["briefing_sources"]["last_project"] == "live"
