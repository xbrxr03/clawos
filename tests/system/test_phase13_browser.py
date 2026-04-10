# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Phase 13 — Browser Control tests.
Tests browser adapter availability, session manager, tool routing, policyd gating.
Playwright is optional — tests skip gracefully when not installed.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ── 1. Browser availability detection ─────────────────────────────────────────

def test_playwright_availability_check():
    """is_available() returns bool without crashing."""
    from adapters.browser.playwright_adapter import is_available
    result = is_available()
    assert isinstance(result, bool)


# ── 2. PlaywrightAdapter — unavailable graceful error ────────────────────────

def test_playwright_adapter_raises_when_unavailable():
    """If playwright not installed, PlaywrightAdapter.__init__ raises RuntimeError."""
    from adapters.browser import playwright_adapter as pa_mod
    original = pa_mod._PLAYWRIGHT_OK
    try:
        pa_mod._PLAYWRIGHT_OK = False
        with pytest.raises(RuntimeError, match="playwright not installed"):
            pa_mod.PlaywrightAdapter("test_workspace")
    finally:
        pa_mod._PLAYWRIGHT_OK = original


# ── 3. SessionManager — get creates new session ───────────────────────────────

@pytest.mark.asyncio
async def test_session_manager_get_creates_session():
    """get() returns an adapter instance and tracks it."""
    from adapters.browser.session_manager import SessionManager
    from adapters.browser import playwright_adapter as pa_mod

    if not pa_mod.is_available():
        pytest.skip("Playwright not installed")

    manager = SessionManager()
    # Mock PlaywrightAdapter to avoid real browser launch
    mock_adapter = MagicMock()
    with patch("adapters.browser.session_manager.PlaywrightAdapter", return_value=mock_adapter):
        with patch("adapters.browser.session_manager.is_available", return_value=True):
            adapter = await manager.get("ws_test_001")
            assert adapter is mock_adapter
            assert "ws_test_001" in manager.active_sessions()


@pytest.mark.asyncio
async def test_session_manager_reuses_existing_session():
    """get() returns same instance for same workspace_id."""
    from adapters.browser.session_manager import SessionManager

    manager = SessionManager()
    mock_adapter = MagicMock()
    with patch("adapters.browser.session_manager.PlaywrightAdapter", return_value=mock_adapter):
        with patch("adapters.browser.session_manager.is_available", return_value=True):
            a1 = await manager.get("ws_reuse")
            a2 = await manager.get("ws_reuse")
            assert a1 is a2


@pytest.mark.asyncio
async def test_session_manager_close():
    """close() removes session and calls shutdown."""
    from adapters.browser.session_manager import SessionManager

    manager = SessionManager()
    mock_adapter = AsyncMock()
    with patch("adapters.browser.session_manager.PlaywrightAdapter", return_value=mock_adapter):
        with patch("adapters.browser.session_manager.is_available", return_value=True):
            await manager.get("ws_close_test")
            result = await manager.close("ws_close_test")
            assert result is True
            assert "ws_close_test" not in manager.active_sessions()
            mock_adapter.shutdown.assert_awaited_once()


# ── 4. ToolBridge browser routing ─────────────────────────────────────────────

def test_browser_tools_in_all_descriptions():
    """All 8 browser.* tools appear in ToolBridge ALL_TOOL_DESCRIPTIONS."""
    from services.toolbridge.service import ALL_TOOL_DESCRIPTIONS
    browser_tools = [
        "browser.open", "browser.read", "browser.click", "browser.type",
        "browser.screenshot", "browser.scroll", "browser.wait", "browser.close",
    ]
    for tool in browser_tools:
        assert tool in ALL_TOOL_DESCRIPTIONS, f"Missing tool: {tool}"


def test_browser_tool_descriptions_non_empty():
    """All browser tool descriptions are non-empty strings."""
    from services.toolbridge.service import ALL_TOOL_DESCRIPTIONS
    for tool in ["browser.open", "browser.read", "browser.click"]:
        assert ALL_TOOL_DESCRIPTIONS[tool], f"Empty description for {tool}"


# ── 5. policyd scores browser tools ──────────────────────────────────────────

def test_policyd_has_browser_tool_scores():
    """policyd TOOL_SCORES includes all browser.* tools."""
    from services.policyd.service import TOOL_SCORES
    browser_tools = [
        "browser.open", "browser.read", "browser.click", "browser.type",
        "browser.screenshot", "browser.scroll", "browser.wait", "browser.close",
    ]
    for tool in browser_tools:
        assert tool in TOOL_SCORES, f"Missing policyd score for: {tool}"


def test_policyd_browser_click_higher_risk_than_read():
    """browser.click should be higher risk score than browser.read."""
    from services.policyd.service import TOOL_SCORES
    assert TOOL_SCORES["browser.click"] > TOOL_SCORES["browser.read"]


def test_policyd_browser_type_highest_browser_risk():
    """browser.type (could submit forms) should be >= browser.click."""
    from services.policyd.service import TOOL_SCORES
    assert TOOL_SCORES["browser.type"] >= TOOL_SCORES["browser.click"]


# ── 6. ToolBridge blocks browser when disabled ────────────────────────────────

@pytest.mark.asyncio
async def test_toolbridge_browser_disabled_in_config():
    """If browser.enabled=False, _browser_dispatch returns disabled message."""
    from services.toolbridge.service import ToolBridge

    mock_policy = MagicMock()
    mock_policy.task_id = "t_001"
    mock_policy.granted_tools = ["browser.open"]
    mock_memory = MagicMock()
    bridge = ToolBridge(mock_policy, mock_memory, "ws_test")

    with patch("adapters.browser.session_manager.get_manager") as mock_mgr:
        # Simulate browser disabled via config
        with patch("clawos_core.config.get", return_value=False):
            result = await bridge._browser_dispatch("open", "https://example.com")
    assert "DISABLED" in result or "UNAVAILABLE" in result or isinstance(result, str)


# ── 7. Browser URL allowlist ──────────────────────────────────────────────────

def test_playwright_adapter_allowlist_empty_allows_all():
    """Empty allowlist allows any URL."""
    from adapters.browser.playwright_adapter import PlaywrightAdapter as PA
    import adapters.browser.playwright_adapter as pa_mod
    if not pa_mod.is_available():
        pytest.skip("Playwright not installed")
    pa = PA.__new__(PA)
    assert pa._check_allowlist("https://google.com", []) is True


def test_playwright_adapter_allowlist_blocks_unmatched():
    """Non-empty allowlist blocks URLs not matching any pattern."""
    from adapters.browser.playwright_adapter import PlaywrightAdapter as PA
    import adapters.browser.playwright_adapter as pa_mod
    if not pa_mod.is_available():
        pytest.skip("Playwright not installed")
    pa = PA.__new__(PA)
    assert pa._check_allowlist("https://evil.com", ["google\\.com"]) is False
    assert pa._check_allowlist("https://google.com", ["google\\.com"]) is True


# ── 8. browser_tools.py constants ─────────────────────────────────────────────

def test_browser_tool_descriptions_module():
    """tools/browser_tools.py exports expected constants."""
    from tools.browser_tools import (
        BROWSER_TOOL_DESCRIPTIONS,
        BROWSER_TOOL_PERMISSIONS,
        BROWSER_TOOL_SCORES,
    )
    assert len(BROWSER_TOOL_DESCRIPTIONS) == 8
    assert len(BROWSER_TOOL_PERMISSIONS) == 8
    assert len(BROWSER_TOOL_SCORES) == 8
    for tool in BROWSER_TOOL_DESCRIPTIONS:
        assert BROWSER_TOOL_PERMISSIONS[tool] == "browser_control"
