# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression tests for the ClawOS CLI terminal helpers."""
from __future__ import annotations

import io
import sys


def test_banner_helpers_are_safe_on_cp1252(monkeypatch):
    from clawctl.ui import banner

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)

    banner.print_banner()
    banner.table([("daily-briefing-os", "wave-1", "primary")], headers=("id", "wave", "status"))
    banner.success("ready")
    banner.error("failed")
    banner.info("details")
    banner.warn("warning")
    stream.flush()

    rendered = stream.buffer.getvalue().decode("cp1252")
    assert "ClawOS" in rendered
    assert "daily-briefing-os" in rendered
    assert "[ok]" in rendered


def test_status_command_is_safe_on_cp1252(monkeypatch):
    from clawctl.commands import status

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    # Mock _http_get to return no response (service down)
    monkeypatch.setattr(status, "_http_get", lambda url, timeout=2: (None, None))
    # Mock _check_pid to return unknown (no PID file)
    monkeypatch.setattr(status, "_check_pid", lambda name: ("unknown", ""))
    # Mock ollama host to something unreachable
    monkeypatch.setattr(status, "OLLAMA_HOST", "http://127.0.0.1:19999")

    status.run()
    stream.flush()

    rendered = stream.buffer.getvalue().decode("cp1252")
    assert "CLAWOS" in rendered
    assert "service status" in rendered
    assert "Services" in rendered
