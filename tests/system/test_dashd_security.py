# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Dashboard production-hardening tests.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_dashboard_settings_force_loopback_without_auth():
    from services.dashd.api import load_dashboard_settings

    settings = load_dashboard_settings({
        "host": "0.0.0.0",
        "auth_required": False,
        "token": "",
    })

    assert settings.host == "127.0.0.1"
    assert settings.auth_required is False


def test_dashboard_requires_login_and_sends_snapshot(monkeypatch):
    from services.dashd.api import create_app

    class IncompleteSetupState:
        completion_marker = False

    monkeypatch.setattr("services.dashd.api._setup_state", lambda: IncompleteSetupState())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        session = client.get("/api/session")
        assert session.status_code == 200
        assert session.json() == {"auth_required": True, "authenticated": False}

        assert client.get("/api/tasks").status_code == 401
        assert client.get("/api/setup/state").status_code == 401
        assert client.get("/api/setup/state", headers={"X-ClawOS-Setup": "1"}).status_code == 200
        assert client.post("/api/login", json={"token": "wrong"}).status_code == 401

        login = client.post("/api/login", json={"token": "dash-token"})
        assert login.status_code == 200
        assert client.cookies.get("dash_session") != "dash-token"

        session = client.get("/api/session")
        assert session.json() == {"auth_required": True, "authenticated": True}

        assert client.post("/api/setup/repair", headers={"X-ClawOS-Setup": "1"}).status_code == 200

        with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:7070"}) as websocket:
            message = websocket.receive_json()

        assert message["type"] == "snapshot"
        assert "services" in message["data"]
        assert "models" in message["data"]

        with client.websocket_connect("/ws/setup?setup=1", headers={"origin": "http://127.0.0.1:7070"}) as websocket:
            message = websocket.receive_json()

        assert message["type"] == "setup_state"
        assert "progress_stage" in message["data"]


def test_dashboard_websocket_forwards_workflow_events(monkeypatch):
    from services.dashd.api import create_app
    from workflows.engine import WorkflowResult, WorkflowStatus

    class FakeEngine:
        def load_registry(self):
            return None

        async def run(self, workflow_id, args, workspace_id="nexus_default"):
            from clawos_core.events.bus import get_bus

            await get_bus().publish(
                "workflow_progress",
                {
                    "id": workflow_id,
                    "status": "running",
                    "phase": "scan",
                    "progress": 28,
                    "message": "Scanning the folder",
                },
            )
            await get_bus().publish(
                "workflow_progress",
                {
                    "id": workflow_id,
                    "status": "ok",
                    "phase": "complete",
                    "progress": 100,
                    "message": "Workflow finished",
                    "output": "done",
                },
            )
            return WorkflowResult(status=WorkflowStatus.OK, output="done", metadata={"files_moved": 2})

    monkeypatch.setattr("workflows.engine.get_engine", lambda: FakeEngine())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    def _receive_workflow_event(websocket):
        for _ in range(6):
            message = websocket.receive_json()
            if message["type"] == "workflow_progress":
                return message
        raise AssertionError("workflow_progress event not received")

    with TestClient(app) as client:
        login = client.post("/api/login", json={"token": "dash-token"})
        assert login.status_code == 200

        with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:7070"}) as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "snapshot"

            response = client.post("/api/workflows/organize-downloads/run", json={"args": {"dry_run": True}})
            assert response.status_code == 200

            first = _receive_workflow_event(websocket)
            second = _receive_workflow_event(websocket)

        assert first["data"]["phase"] == "scan"
        assert first["data"]["message"] == "Scanning the folder"
        assert second["data"]["status"] == "ok"
        assert second["data"]["output"] == "done"


def test_dashboard_docs_and_evolution_require_auth(monkeypatch):
    from services.dashd.api import create_app

    class IncompleteSetupState:
        completion_marker = False

    monkeypatch.setattr("services.dashd.api._setup_state", lambda: IncompleteSetupState())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        for path in ("/api/docs", "/api/redoc", "/api/openapi.json", "/api/evolution"):
            assert client.get(path).status_code == 401

        for path in ("/api/docs", "/api/redoc", "/api/openapi.json", "/api/evolution"):
            assert client.get(path, headers={"Authorization": "Bearer dash-token"}).status_code == 200


def test_dashboard_cookie_websocket_requires_trusted_origin(monkeypatch):
    from services.dashd.api import create_app

    class IncompleteSetupState:
        completion_marker = False

    monkeypatch.setattr("services.dashd.api._setup_state", lambda: IncompleteSetupState())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        assert client.post("/api/login", json={"token": "dash-token"}).status_code == 200

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws", headers={"origin": "http://evil.test"}):
                pass

        with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:7070"}) as websocket:
            message = websocket.receive_json()

        assert message["type"] == "snapshot"


def test_brain_websocket_requires_auth_and_trusted_origin(monkeypatch):
    from services.dashd.api import create_app

    class IncompleteSetupState:
        completion_marker = False

    class FakeBrain:
        def __init__(self):
            self.callbacks = []

        def register_ws_callback(self, callback):
            self.callbacks.append(callback)

        def unregister_ws_callback(self, callback):
            if callback in self.callbacks:
                self.callbacks.remove(callback)

        def get_status(self):
            return {"node_count": 7, "edge_count": 3, "ingesting": False}

    monkeypatch.setattr("services.dashd.api._setup_state", lambda: IncompleteSetupState())
    monkeypatch.setattr("services.braind.service.get_brain", lambda: FakeBrain())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/brain"):
                pass

        assert client.post("/api/login", json={"token": "dash-token"}).status_code == 200

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/brain", headers={"origin": "http://evil.test"}):
                pass

        with client.websocket_connect("/ws/brain", headers={"origin": "http://127.0.0.1:7070"}) as websocket:
            message = websocket.receive_json()

        assert message["event"] == "status"
        assert message["node_count"] == 7


def test_setup_header_is_rejected_after_setup_completion(monkeypatch):
    from services.dashd.api import create_app

    class CompleteSetupState:
        completion_marker = True

    monkeypatch.setattr("services.dashd.api._setup_state", lambda: CompleteSetupState())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        assert client.get("/api/setup/state", headers={"X-ClawOS-Setup": "1"}).status_code == 401


def test_dashboard_session_rotation_changes_cookie_secret(monkeypatch, workspace_tmp_dir):
    from services.dashd.api import _load_dashboard_session_token, rotate_dashboard_session_token

    session_file = workspace_tmp_dir / "dashboard.session"
    monkeypatch.setattr("services.dashd.api._dashboard_session_token_file", lambda: session_file)

    first = _load_dashboard_session_token(True)
    rotated = rotate_dashboard_session_token()
    second = _load_dashboard_session_token(True)

    assert first
    assert rotated == second
    assert first != second


def test_setup_requires_auth_when_dashboard_is_not_loopback():
    from services.dashd.api import create_app

    app = create_app({
        "host": "0.0.0.0",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        assert client.get("/api/setup/state").status_code == 401


def test_desktop_posture_requires_auth_and_supports_launch_toggle(monkeypatch):
    from services.dashd.api import create_app

    calls = []
    monkeypatch.setattr(
        "clawos_core.desktop_integration.desktop_posture",
        lambda: {
            "platform": "linux",
            "autostart_kind": "autostart-desktop",
            "launch_on_login_supported": True,
            "launch_on_login_enabled": bool(calls),
            "launch_on_login_path": "/tmp/clawos-command-center.desktop",
            "paths": {"logs": "/tmp/logs"},
        },
    )
    monkeypatch.setattr(
        "clawos_core.desktop_integration.enable_launch_on_login",
        lambda command=None: calls.append(command or "default") or "/tmp/clawos-command-center.desktop",
    )

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        assert client.get("/api/desktop/posture").status_code == 401
        assert client.post("/api/desktop/launch-on-login", json={"enabled": True}).status_code == 401

        login = client.post("/api/login", json={"token": "dash-token"})
        assert login.status_code == 200

        posture = client.get("/api/desktop/posture")
        assert posture.status_code == 200
        assert posture.json()["launch_on_login_supported"] is True

        toggle = client.post("/api/desktop/launch-on-login", json={"enabled": True})
        assert toggle.status_code == 200
        assert toggle.json()["message"] == "Launch on login enabled"
        assert calls == ["default"]
