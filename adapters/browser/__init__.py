# SPDX-License-Identifier: AGPL-3.0-or-later
"""Browser control adapter — Playwright-backed."""
from .playwright_adapter import PlaywrightAdapter
from .session_manager import SessionManager

__all__ = ["PlaywrightAdapter", "SessionManager"]
