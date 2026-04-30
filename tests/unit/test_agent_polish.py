# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Tests for Phase 5 polish layer: tool result caching + context budget.
"""
import asyncio

from runtimes.agent import cache
from runtimes.agent.context_budget import DEFAULT_BUDGET_TOKENS, fit_blocks
from runtimes.agent.tools import dispatch_tool


def setup_function(_):
    cache.clear()


# ── caching ─────────────────────────────────────────────────────────────────

def test_cache_skips_uncacheable_tools():
    assert not cache.is_cacheable("set_volume")
    assert not cache.is_cacheable("write_file")


def test_cache_caches_cacheable_tools():
    cache.put("get_weather", {"location": "berlin"}, "Berlin: ☀️ +14°C")
    assert cache.get("get_weather", {"location": "berlin"}) == "Berlin: ☀️ +14°C"


def test_cache_misses_on_different_args():
    cache.put("get_weather", {"location": "berlin"}, "Berlin")
    assert cache.get("get_weather", {"location": "tokyo"}) is None


def test_get_time_caches_zero_ttl():
    # get_time has TTL=0 → not cached
    cache.put("get_time", {}, "9 AM")
    assert cache.get("get_time", {}) is None


def test_dispatch_does_not_cache_errors():
    """Calling list_workflows when no engine is registered returns either
    a string (engine present) or [ERROR]. Either way, no error is cached."""
    asyncio.run(dispatch_tool("list_workflows", {}, {}))
    # The cache shouldn't contain an error string
    snapshot = cache._cache  # type: ignore[attr-defined]
    for (name, _), (_, value) in snapshot.items():
        assert not value.startswith("[ERROR]"), f"cached error for {name}: {value}"


# ── context budget ──────────────────────────────────────────────────────────

def test_fit_blocks_under_budget_keeps_all():
    blocks = [("memory", "abc"), ("learned", "def"), ("rag", "ghi")]
    out = fit_blocks(blocks, budget_tokens=1000)
    assert len(out) == 3


def test_fit_blocks_drops_low_priority_when_tight():
    big = "x" * 8000  # ~2000 tokens
    blocks = [("memory", big), ("learned", "should drop"), ("rag", "also drop")]
    out = fit_blocks(blocks, budget_tokens=2000)
    labels = [l for l, _ in out]
    assert "memory" in labels
    # Lower-priority blocks fall off
    assert "learned" not in labels and "rag" not in labels


def test_fit_blocks_truncates_block_at_boundary():
    blocks = [("memory", "x" * 4000), ("learned", "y" * 4000)]
    out = fit_blocks(blocks, budget_tokens=600)
    # First block fully in (or truncated), second block trimmed/dropped
    assert out
    assert out[0][0] == "memory"


def test_fit_blocks_skips_empty():
    blocks = [("memory", ""), ("learned", "abc")]
    out = fit_blocks(blocks, budget_tokens=1000)
    assert len(out) == 1
    assert out[0][0] == "learned"


def test_default_budget_constant_is_reasonable():
    # Sanity: the default should leave headroom for system + history in a 4k ctx
    assert 1000 <= DEFAULT_BUDGET_TOKENS <= 3000
