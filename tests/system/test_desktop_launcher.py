"""
Desktop launcher contract tests.
"""
from types import SimpleNamespace


def test_command_center_url_uses_loopback(monkeypatch):
    from clients.desktop import launch_command_center

    monkeypatch.setattr(
        launch_command_center,
        "load_dashboard_settings",
        lambda: SimpleNamespace(host="0.0.0.0", port=7123),
    )

    assert launch_command_center.dashboard_base_url() == "http://127.0.0.1:7123"
    assert launch_command_center.command_center_url("/setup") == "http://127.0.0.1:7123/setup"


def test_wait_for_dashboard_retries_until_ready(monkeypatch):
    from clients.desktop import launch_command_center

    attempts = {"count": 0}

    def fake_health(_base_url: str) -> bool:
        attempts["count"] += 1
        return attempts["count"] >= 2

    monkeypatch.setattr(launch_command_center, "_health_ok", fake_health)
    monkeypatch.setattr(launch_command_center.time, "sleep", lambda _seconds: None)

    assert launch_command_center.wait_for_dashboard("http://127.0.0.1:7070", timeout=0.2, interval=0.01) is True
    assert attempts["count"] >= 2
