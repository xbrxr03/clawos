# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Voice pipeline contract tests for dashd and setupd.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

SETUP_HEADERS = {"X-ClawOS-Setup": "1"}


class FakeVoiceService:
    def __init__(self):
        self._session = {
            "mode": "push_to_talk",
            "state": "idle",
            "device_label": "Fake microphone",
            "follow_up_open": False,
            "last_utterance": "",
            "last_response": "",
        }
        self._listeners = []

    def session(self):
        return dict(self._session)

    def add_session_listener(self, listener):
        self._listeners.append(listener)

    def remove_session_listener(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self):
        for listener in list(self._listeners):
            result = listener(self.session())
            if hasattr(result, "__await__"):
                try:
                    asyncio.get_running_loop().create_task(result)
                except RuntimeError:
                    asyncio.run(result)

    def health(self):
        return {
            "status": "running",
            "enabled": True,
            "mode": self._session["mode"],
            "state": self._session["state"],
            "running": True,
            "stt_ok": True,
            "tts_ok": True,
            "wake_word_ok": True,
            "microphone_ok": True,
            "microphone_backend": "fake-recorder",
            "playback_backend": "fake-player",
            "device_label": self._session["device_label"],
            "sample_rate_hz": 44100,
            "follow_up_open": False,
        }

    async def set_mode(self, mode: str):
        self._session["mode"] = mode
        self._session["state"] = "idle"
        self._notify()
        return self.session()

    async def test_microphone(self, duration_s: float = 3.0):
        return {
            "kind": "microphone",
            "ok": True,
            "state": "passed",
            "mode": self._session["mode"],
            "device_label": self._session["device_label"],
            "sample_rate_hz": 44100,
            "microphone_backend": "fake-recorder",
            "transcript": "testing one two",
            "issues": [],
        }

    async def test_pipeline(self, sample_text: str = "Voice pipeline ready.", duration_s: float = 3.0):
        return {
            "kind": "pipeline",
            "ok": True,
            "state": "passed",
            "mode": self._session["mode"],
            "device_label": self._session["device_label"],
            "sample_rate_hz": 44100,
            "microphone_backend": "fake-recorder",
            "transcript": "testing one two",
            "playback_ok": True,
            "sample_text": sample_text,
            "issues": [],
        }

    async def test_wake_word(self):
        return {
            "kind": "wake_word",
            "ok": True,
            "state": "passed",
            "mode": self._session["mode"],
            "wake_word_ok": True,
            "armed": True,
            "wake_word_phrase": "Hey Claw",
            "issues": [],
        }

    async def push_to_talk(self):
        self._session["state"] = "idle"
        self._session["last_utterance"] = "open the dashboard"
        self._session["last_response"] = "I heard: open the dashboard"
        self._notify()
        return {
            "ok": True,
            "trigger": "push_to_talk",
            "transcript": self._session["last_utterance"],
            "response": self._session["last_response"],
            "playback_ok": True,
            "session": self.session(),
        }


def test_setupd_voice_test_updates_state_and_diagnostics(monkeypatch):
    from services.setupd import service as setup_service
    from services.setupd.state import SetupState

    seed_state = SetupState(
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        voice_mode="push_to_talk",
        voice_enabled=True,
    )

    monkeypatch.setattr(setup_service.SetupState, "load", classmethod(lambda cls: seed_state))
    monkeypatch.setattr(setup_service.SetupState, "save", lambda self, path=None: None)
    monkeypatch.setattr(setup_service, "record_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_service, "sync_presence_from_setup", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.voiced.service.get_service", lambda: FakeVoiceService())

    setup_service._SERVICE = None
    app = setup_service.create_app()

    with TestClient(app) as client:
      response = client.post("/api/setup/voice-test", headers=SETUP_HEADERS, json={"sample_text": "Voice pipeline ready."})
      assert response.status_code == 200
      payload = response.json()
      assert payload["voice_test"]["ok"] is True
      assert payload["voice_test"]["transcript"] == "testing one two"

      diagnostics = client.get("/api/setup/diagnostics", headers=SETUP_HEADERS)
      assert diagnostics.status_code == 200
      assert diagnostics.json()["voice"]["microphone_backend"] == "fake-recorder"


def test_setupd_wake_word_voice_test_requires_wake_detector(monkeypatch):
    from services.setupd import service as setup_service
    from services.setupd.state import SetupState

    seed_state = SetupState(
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        voice_mode="wake_word",
        voice_enabled=True,
    )

    monkeypatch.setattr(setup_service.SetupState, "load", classmethod(lambda cls: seed_state))
    monkeypatch.setattr(setup_service.SetupState, "save", lambda self, path=None: None)
    monkeypatch.setattr(setup_service, "record_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup_service, "sync_presence_from_setup", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.voiced.service.get_service", lambda: FakeVoiceService())

    setup_service._SERVICE = None
    app = setup_service.create_app()

    with TestClient(app) as client:
      response = client.post("/api/setup/voice-test", headers=SETUP_HEADERS, json={"sample_text": "Voice pipeline ready."})
      assert response.status_code == 200
      payload = response.json()
      assert payload["voice_test"]["wake_word_ok"] is True
      assert payload["voice_test"]["wake_word_armed"] is True
      assert payload["voice_test"]["wake_word_phrase"] == "Hey Claw"


def test_dashd_voice_endpoints_use_voice_service(monkeypatch):
    from services.dashd.api import create_app
    from services.setupd.state import SetupState

    voice = FakeVoiceService()
    state = SetupState(
        platform="linux",
        architecture="x86_64",
        service_manager="systemd",
        voice_mode="push_to_talk",
        voice_enabled=True,
    )

    monkeypatch.setattr("services.dashd.api._voice_service", lambda: voice)
    monkeypatch.setattr("services.dashd.api._collect_models", lambda: [])
    monkeypatch.setattr("services.dashd.api._approval_payloads", lambda: [])
    monkeypatch.setattr("services.dashd.api._collect_service_health", lambda: {"dashd": {"status": "up", "latency_ms": 0}})
    monkeypatch.setattr("services.setupd.state.SetupState.load", classmethod(lambda cls: state))
    monkeypatch.setattr("services.setupd.state.SetupState.save", lambda self, path=None: None)
    monkeypatch.setattr("services.dashd.api.sync_presence_from_setup", lambda *_args, **_kwargs: None)

    app = create_app({"host": "127.0.0.1", "auth_required": True, "token": "dash-token", "cookie_name": "dash_session"})

    with TestClient(app) as client:
        assert client.post("/api/login", json={"token": "dash-token"}).status_code == 200

        session = client.get("/api/voice/session")
        assert session.status_code == 200
        assert session.json()["mode"] == "push_to_talk"

        health = client.get("/api/voice/health")
        assert health.status_code == 200
        assert health.json()["tts_ok"] is True

        mode = client.post("/api/voice/mode", json={"mode": "wake_word"})
        assert mode.status_code == 200
        assert mode.json()["mode"] == "wake_word"

        test = client.post("/api/voice/test", json={"kind": "pipeline", "sample_text": "Voice pipeline ready."})
        assert test.status_code == 200
        assert test.json()["ok"] is True
        assert test.json()["playback_ok"] is True

        wake = client.post("/api/voice/test", json={"kind": "wake_word"})
        assert wake.status_code == 200
        assert wake.json()["wake_word_ok"] is True
        assert wake.json()["wake_word_phrase"] == "Hey Claw"

        talk = client.post("/api/voice/push-to-talk")
        assert talk.status_code == 200
        assert talk.json()["ok"] is True
        assert talk.json()["transcript"] == "open the dashboard"
