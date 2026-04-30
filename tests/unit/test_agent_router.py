# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for runtimes/agent/router.py — dynamic model router."""
from runtimes.agent.router import (
    pick_model, FAST_MODEL, SMART_MODEL, CODER_MODEL,
)


def test_explicit_override_wins():
    r = pick_model("write a 1000 word essay", explicit_tier="fast")
    assert r.model == FAST_MODEL


def test_coder_routed_for_file_tools():
    r = pick_model("save this to disk", likely_tools=["write_file"])
    assert r.model == CODER_MODEL
    assert "code/file" in r.reason


def test_coder_routed_for_shell():
    r = pick_model("run pwd", likely_tools=["run_command"])
    assert r.model == CODER_MODEL


def test_long_history_forces_smart():
    r = pick_model("hi", history_tokens=2000)
    assert r.model == SMART_MODEL
    assert "history" in r.reason


def test_long_input_forces_smart():
    long_input = " ".join(["word"] * 30)
    r = pick_model(long_input)
    assert r.model == SMART_MODEL


def test_multi_tool_forces_smart():
    r = pick_model("hi", likely_tools=["get_time", "get_weather"])
    assert r.model == SMART_MODEL
    assert "multi-tool" in r.reason


def test_fast_for_simple_tool():
    r = pick_model("what time is it", likely_tools=["get_time"])
    assert r.model == FAST_MODEL


def test_fast_for_short_chat():
    r = pick_model("hello there")
    assert r.model == FAST_MODEL


def test_short_no_tools_routes_fast():
    # Short input (≤12 words), no tools known → FAST tier
    r = pick_model("can you help me think about a problem")
    assert r.model == FAST_MODEL


def test_medium_input_routes_smart():
    # 13-25 words with no tools should land on SMART (above the FAST cutoff)
    r = pick_model(
        "can you help me think through a moderately tricky problem about caching "
        "and edge cases please"
    )
    assert r.model == SMART_MODEL
