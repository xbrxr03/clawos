# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Browser Session Manager.
Maps workspace_id → PlaywrightAdapter instance.
Enforces one browser instance per workspace. Auto-cleans idle sessions.
"""
import asyncio
import logging
import time
from typing import Optional

log = logging.getLogger("browser_sessions")

# Module-level imports so tests can patch them cleanly
try:
    from adapters.browser.playwright_adapter import PlaywrightAdapter, is_available
except Exception:
    PlaywrightAdapter = None  # type: ignore[assignment,misc]
    def is_available() -> bool:
        return False

# Idle timeout: close browser after 5 minutes of inactivity
_IDLE_TIMEOUT_S = 300


class SessionManager:
    """Thread-safe registry of active browser sessions."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}  # workspace_id → {adapter, last_used}
        self._lock = asyncio.Lock()

    async def get(self, workspace_id: str) -> "PlaywrightAdapter":
        """
        Get or create a PlaywrightAdapter for the given workspace.
        Raises RuntimeError if Playwright is not available.
        """
        if not is_available():
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )

        async with self._lock:
            if workspace_id in self._sessions:
                session = self._sessions[workspace_id]
                session["last_used"] = time.time()
                return session["adapter"]

            from clawos_core.config.loader import get
            headless = get("browser.headless", True)
            timeout_ms = get("browser.timeout_ms", 30000)

            adapter = PlaywrightAdapter(
                workspace_id=workspace_id,
                headless=headless,
                timeout_ms=timeout_ms,
            )
            self._sessions[workspace_id] = {
                "adapter": adapter,
                "last_used": time.time(),
            }
            log.info(f"Created browser session for workspace {workspace_id}")
            return adapter

    async def close(self, workspace_id: str) -> bool:
        """Close and remove a browser session."""
        async with self._lock:
            if workspace_id not in self._sessions:
                return False
            adapter = self._sessions.pop(workspace_id)["adapter"]
            await adapter.shutdown()
            log.info(f"Closed browser session for workspace {workspace_id}")
            return True

    async def close_idle(self):
        """Close sessions that have been idle longer than _IDLE_TIMEOUT_S."""
        now = time.time()
        idle = [
            ws_id for ws_id, s in self._sessions.items()
            if now - s["last_used"] > _IDLE_TIMEOUT_S
        ]
        for ws_id in idle:
            log.info(f"Closing idle browser session: {ws_id}")
            await self.close(ws_id)

    async def shutdown_all(self):
        """Close all sessions — called on ClawOS shutdown."""
        async with self._lock:
            for ws_id, session in list(self._sessions.items()):
                try:
                    await session["adapter"].shutdown()
                except Exception:
                    pass
            self._sessions.clear()
            log.info("All browser sessions closed")

    def active_sessions(self) -> list[str]:
        """Return list of workspace IDs with active browser sessions."""
        return list(self._sessions.keys())


# ── Singleton ──────────────────────────────────────────────────────────────────
_manager: Optional[SessionManager] = None


def get_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
