# SPDX-License-Identifier: AGPL-3.0-or-later
"""
A2A production-hardening tests.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def test_a2a_settings_force_loopback_without_token():
    from services.a2ad.service import load_a2a_settings

    settings = load_a2a_settings({
        "host": "0.0.0.0",
        "auth_token": "",
        "mdns_enabled": True,
    })

    assert settings.host == "127.0.0.1"
    assert settings.mdns_enabled is False


def test_a2a_send_requires_auth_when_token_configured(monkeypatch):
    async def fake_handle_task(_task):
        return "handled"

    monkeypatch.setattr("services.a2ad.task_handler.handle_task", fake_handle_task)

    from services.a2ad.service import create_app

    app = create_app({
        "host": "127.0.0.1",
        "auth_token": "secret-token",
        "mdns_enabled": False,
    })

    body = {
        "id": "task-1",
        "message": {"parts": [{"type": "text", "text": "hello from peer"}]},
        "metadata": {"workspace": "nexus_default"},
    }

    with TestClient(app) as client:
        assert client.post("/a2a/tasks/send", json=body).status_code == 401
        assert client.get("/a2a/peers").status_code == 401

        response = client.post(
            "/a2a/tasks/send",
            json=body,
            headers={"Authorization": "Bearer secret-token"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"]["state"] == "completed"
        assert payload["artifacts"][0]["parts"][0]["text"] == "handled"
