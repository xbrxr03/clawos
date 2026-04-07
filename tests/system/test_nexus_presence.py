# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Nexus presence and autonomy contract tests.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

SETUP_HEADERS = {"X-ClawOS-Setup": "1"}


def test_presence_state_roundtrip_and_mission_start(monkeypatch):
    from clawos_core import presence

    monkeypatch.setattr(
        presence,
        "_load_setup_defaults",
        lambda: {
            "assistant_identity": "Nexus",
            "primary_pack": "daily-briefing-os",
            "voice_mode": "push_to_talk",
            "quiet_hours": {"start": "22:00", "end": "07:00"},
            "primary_goals": ["daily briefing"],
            "briefing_enabled": True,
            "provider_profile": "local-ollama",
            "workspace": "nexus_default",
        },
    )

    store = presence._default_state()

    monkeypatch.setattr(presence, "load_presence_state", lambda path=None: json.loads(json.dumps(store)))
    monkeypatch.setattr(
        presence,
        "save_presence_state",
        lambda state, path=None: store.clear() or store.update(json.loads(json.dumps(state))) or state,
    )

    state_path = Path("presence_state.json")
    payload = presence.get_presence_payload(state_path)
    assert payload["profile"]["assistant_identity"] == "Nexus"
    assert payload["voice_session"]["mode"] == "push_to_talk"

    updated = presence.update_presence_profile({"tone": "crisp-executive", "preferred_voice_mode": "wake_word"}, state_path)
    assert updated["profile"]["tone"] == "crisp-executive"
    assert updated["voice_session"]["mode"] == "wake_word"

    session = presence.set_voice_mode("continuous", state_path)
    assert session["mode"] == "continuous"

    mission = presence.start_mission("Refresh briefing", "Rebuild the morning packet.", path=state_path)
    assert mission["title"] == "Refresh briefing"
    assert presence.list_missions(state_path)[0]["title"] == "Refresh briefing"


def test_setupd_presence_and_autonomy_endpoints(monkeypatch):
    from services.setupd import service as setup_service
    from services.setupd.state import SetupState

    seed_state = SetupState(
        install_channel="desktop",
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        selected_models=["qwen2.5:7b"],
    )

    monkeypatch.setattr(setup_service.SetupState, "load", classmethod(lambda cls: seed_state))
    monkeypatch.setattr(setup_service.SetupState, "save", lambda self, path=None: None)
    monkeypatch.setattr(setup_service, "record_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_service, "sync_presence_from_setup", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        setup_service,
        "update_presence_profile",
        lambda updates: {
            "profile": {**seed_state.presence_profile, **updates},
            "autonomy_policy": seed_state.autonomy_policy,
            "voice_session": {"mode": updates.get("preferred_voice_mode", seed_state.voice_mode), "state": "idle"},
        },
    )
    monkeypatch.setattr(
        setup_service,
        "update_autonomy_policy",
        lambda updates: {
            "profile": seed_state.presence_profile,
            "autonomy_policy": {**seed_state.autonomy_policy, **updates},
            "voice_session": {"mode": seed_state.voice_mode, "state": "idle"},
        },
    )
    monkeypatch.setattr(setup_service, "set_voice_mode", lambda mode: {"mode": mode, "state": "idle"})

    setup_service._SERVICE = None
    app = setup_service.create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/setup/presence",
            headers=SETUP_HEADERS,
            json={
                "assistant_identity": "Nexus",
                "voice_mode": "wake_word",
                "presence_profile": {"tone": "crisp-executive"},
                "primary_goals": ["daily briefing", "meeting prep"],
            },
        )
        assert response.status_code == 200
        assert response.json()["voice_mode"] == "wake_word"
        assert response.json()["presence_profile"]["tone"] == "crisp-executive"

        autonomy = client.post(
            "/api/setup/autonomy",
            headers=SETUP_HEADERS,
            json={
                "autonomy_policy": {"mode": "mostly-autonomous"},
                "quiet_hours": {"start": "23:00", "end": "07:30"},
            },
        )
        assert autonomy.status_code == 200
        assert autonomy.json()["autonomy_policy"]["mode"] == "mostly-autonomous"
        assert autonomy.json()["quiet_hours"]["start"] == "23:00"


def test_dashd_exposes_nexus_presence_surface(monkeypatch):
    from services.dashd.api import create_app
    from services.setupd.state import SetupState

    state = SetupState(
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        selected_provider_profile="local-ollama",
        primary_pack="daily-briefing-os",
    )

    monkeypatch.setattr("services.setupd.state.SetupState.load", classmethod(lambda cls: state))
    monkeypatch.setattr("services.setupd.state.SetupState.save", lambda self, path=None: None)
    monkeypatch.setattr(
        "services.dashd.api.get_presence_payload",
        lambda: {
            "profile": {"assistant_identity": "Nexus", "tone": "crisp-executive"},
            "autonomy_policy": {"mode": "mostly-autonomous"},
            "voice_session": {"mode": "push_to_talk", "state": "idle"},
        },
    )
    monkeypatch.setattr(
        "services.dashd.api.build_today_briefing",
        lambda **kwargs: {
            "title": "Today's briefing",
            "headline": "Nexus is tracking your day.",
            "summary": "Only high-signal updates.",
            "items": [{"title": "Now", "body": "Ready.", "priority": "high"}],
        },
    )
    monkeypatch.setattr(
        "services.dashd.api.build_attention_events",
        lambda **kwargs: [
            {"id": "1", "title": "Approval waiting", "summary": "A message draft needs approval.", "urgency": "medium", "surface": "visual"}
        ],
    )
    monkeypatch.setattr(
        "services.dashd.api.list_missions",
        lambda: [{"id": "m1", "title": "Morning briefing", "status": "active", "trust_lane": "automatic"}],
    )
    monkeypatch.setattr("services.dashd.api.start_mission", lambda title, summary="", trust_lane="trusted-automatic": {"id": "m2", "title": title, "trust_lane": trust_lane})
    class FakeVoiceService:
        def session(self):
            return {"mode": "wake_word", "state": "idle"}

        async def set_mode(self, mode: str):
            return {"mode": mode, "state": "idle"}

    monkeypatch.setattr("services.dashd.api._voice_service", lambda: FakeVoiceService())
    monkeypatch.setattr("services.dashd.api.record_trace", lambda *_args, **_kwargs: None)

    app = create_app({"host": "127.0.0.1", "auth_required": True, "token": "dash-token", "cookie_name": "dash_session"})

    with TestClient(app) as client:
        assert client.post("/api/login", json={"token": "dash-token"}).status_code == 200

        presence = client.get("/api/presence")
        assert presence.status_code == 200
        assert presence.json()["profile"]["assistant_identity"] == "Nexus"

        briefing = client.get("/api/briefings/today")
        assert briefing.status_code == 200
        assert briefing.json()["headline"] == "Nexus is tracking your day."

        attention = client.get("/api/attention")
        assert attention.status_code == 200
        assert attention.json()[0]["title"] == "Approval waiting"

        missions = client.get("/api/missions")
        assert missions.status_code == 200
        assert missions.json()[0]["title"] == "Morning briefing"

        started = client.post("/api/missions", json={"title": "Inbox triage"})
        assert started.status_code == 200
        assert started.json()["mission"]["title"] == "Inbox triage"

        session = client.get("/api/voice/session")
        assert session.status_code == 200
        assert session.json()["mode"] == "wake_word"


def test_support_bundle_redacts_presence_state(monkeypatch):
    from tools.support import support_bundle

    class FakeArchive:
        def __init__(self):
            self.files: dict[str, str] = {}

        def writestr(self, arcname: str, content: str):
            self.files[arcname] = content

        def write(self, path, arcname=None):
            raise AssertionError("Binary write path should not be used in this test")

    class FakePath:
        name = "presence_state.json"

        def read_text(self, encoding="utf-8"):
            return json.dumps(
                {
                    "voice_session": {"mode": "wake_word", "last_utterance": "book dinner", "last_response": "Done"},
                    "missions": [{"id": "m1", "title": "Very private mission", "summary": "Sensitive", "status": "active", "trust_lane": "trusted-automatic"}],
                }
            )

    archive = FakeArchive()
    support_bundle._write_text_or_raw(archive, FakePath(), "config/presence_state.json")
    payload = json.loads(archive.files["config/presence_state.json"])

    assert payload["voice_session"]["last_utterance"] == "[REDACTED]"
    assert payload["voice_session"]["last_response"] == "[REDACTED]"
    assert payload["missions"][0]["status"] == "active"
    assert "title" not in payload["missions"][0]
