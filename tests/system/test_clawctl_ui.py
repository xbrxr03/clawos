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
