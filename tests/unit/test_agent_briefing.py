# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Tests for runtimes/agent/briefing.py and the deterministic morning-briefing
fallback path. Does NOT call Ollama — we verify the orchestration code,
fallback synthesis, and parallel tool gathering.
"""
import asyncio
import types

from runtimes.agent.briefing import _fallback_text, _gather_briefing_data


class FakeRuntime:
    """Minimal runtime stub for the briefing module to consume."""
    def __init__(self):
        self.workspace_id = "test_ws"
        self.memory = None
        self.bridge = None


def test_fallback_text_includes_known_sections():
    data = {
        "time":      "Tuesday, April 29, 2026 · 7:30 AM PDT",
        "weather":   "Berlin: ☀️ +14°C",
        "calendar":  "- 10:00 AM — Standup",
        "reminders": "- [a1b2c3] 09:00 AM — buy milk",
        "memory":    "- worked on the agent loop yesterday",
    }
    text = _fallback_text(data)
    assert "Good morning" in text
    assert "Berlin" in text or "+14" in text
    assert "Standup" in text
    assert "buy milk" in text


def test_fallback_skips_offline_sections():
    data = {
        "time":      "Tuesday, April 29, 2026 · 7:30 AM PDT",
        "weather":   "[OFFLINE] weather unavailable (no internet)",
        "calendar":  "No events for Tue Apr 29.",
        "reminders": "No upcoming reminders.",
        "memory":    "(no matches)",
    }
    text = _fallback_text(data)
    assert "Good morning" in text
    # The offline weather string should NOT leak into the briefing
    assert "[OFFLINE]" not in text
    # Empty calendar/reminders should be skipped
    assert "No events" not in text
    assert "No upcoming" not in text


def test_gather_runs_all_tools_in_parallel():
    """get_time + get_weather etc. should all dispatch through dispatch_tool.
    We can't run a real LLM but get_time always returns a string."""
    rt = FakeRuntime()
    data = asyncio.run(_gather_briefing_data(rt))
    assert set(data.keys()) == {"time", "weather", "calendar", "reminders", "memory"}
    # get_time always works (no network); should look like a date string
    assert any(d in data["time"] for d in ("2025", "2026", "2027", "2028"))
    # recall without memory returns ERROR — that's expected, just verify a string
    assert isinstance(data["memory"], str)
