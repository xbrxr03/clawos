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


def test_dashboard_settings_force_loopback_without_auth():
    from services.dashd.api import load_dashboard_settings

    settings = load_dashboard_settings({
        "host": "0.0.0.0",
        "auth_required": False,
        "token": "",
    })

    assert settings.host == "127.0.0.1"
    assert settings.auth_required is False


def test_dashboard_requires_login_and_sends_snapshot():
    from services.dashd.api import create_app

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

        session = client.get("/api/session")
        assert session.json() == {"auth_required": True, "authenticated": True}

        assert client.post("/api/setup/repair", headers={"X-ClawOS-Setup": "1"}).status_code == 200

        with client.websocket_connect("/ws") as websocket:
            message = websocket.receive_json()

        assert message["type"] == "snapshot"
        assert "services" in message["data"]
        assert "models" in message["data"]

        with client.websocket_connect("/ws/setup?setup=1", headers={"origin": "http://127.0.0.1:7070"}) as websocket:
            message = websocket.receive_json()

        assert message["type"] == "setup_state"
        assert "progress_stage" in message["data"]


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
