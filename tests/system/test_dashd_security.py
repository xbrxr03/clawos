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
        assert client.post("/api/login", json={"token": "wrong"}).status_code == 401

        login = client.post("/api/login", json={"token": "dash-token"})
        assert login.status_code == 200

        session = client.get("/api/session")
        assert session.json() == {"auth_required": True, "authenticated": True}

        with client.websocket_connect("/ws") as websocket:
            message = websocket.receive_json()

        assert message["type"] == "snapshot"
        assert "services" in message["data"]
        assert "models" in message["data"]
