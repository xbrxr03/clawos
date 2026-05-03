# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Playwright browser adapter for ClawOS.
Wraps a single Chromium instance per workspace session.

Policy: all browser.* calls are gated through policyd (browser_control permission).
Screenshots saved to ~/.clawos/workspaces/{id}/screenshots/ only.
"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger("browser_adapter")

_PLAYWRIGHT_OK = False
try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright
    _PLAYWRIGHT_OK = True
except ImportError as e:
    log.debug(f"suppressed: {e}")


def is_available() -> bool:
    return _PLAYWRIGHT_OK


class PlaywrightAdapter:
    """
    Manages a single headless Chromium browser instance per workspace.
    One page at a time — call open() to navigate, then use other methods.
    """

    def __init__(self, workspace_id: str, headless: bool = True, timeout_ms: int = 30000):
        if not _PLAYWRIGHT_OK:
            raise RuntimeError(
                "playwright not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
        self.workspace_id = workspace_id
        self.headless = headless
        self.timeout_ms = timeout_ms

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._current_url: str = ""

        # Screenshots go to workspace dir only
        from clawos_core.constants import CLAWOS_DIR
        self._screenshot_dir = CLAWOS_DIR / "workspaces" / workspace_id / "screenshots"
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def _ensure_browser(self):
        """Lazy init browser."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            log.info(f"Chromium launched (headless={self.headless}) for workspace {self.workspace_id}")

    async def _ensure_page(self):
        await self._ensure_browser()
        if self._page is None or self._page.is_closed():
            self._page = await self._browser.new_page()
            self._page.set_default_timeout(self.timeout_ms)

    def _check_allowlist(self, url: str, allowlist: list[str]) -> bool:
        """Return True if URL is allowed (empty allowlist = allow all)."""
        if not allowlist:
            return True
        for pattern in allowlist:
            try:
                if re.search(pattern, url, re.IGNORECASE):
                    return True
            except re.error:
                if pattern in url:
                    return True
        return False

    def _get_config(self) -> dict:
        try:
            from clawos_core.config import get
            return {
                "headless": get("browser.headless", True),
                "timeout_ms": get("browser.timeout_ms", 30000),
                "url_allowlist": get("browser.url_allowlist", []),
            }
        except (ImportError, ModuleNotFoundError):
            return {"headless": True, "timeout_ms": 30000, "url_allowlist": []}

    async def open(self, url: str) -> str:
        """Navigate to a URL. Returns page title."""
        cfg = self._get_config()
        if not self._check_allowlist(url, cfg["url_allowlist"]):
            return f"[BROWSER DENIED] URL not in allowlist: {url}"

        await self._ensure_page()
        try:
            response = await self._page.goto(url, wait_until="domcontentloaded",
                                              timeout=cfg["timeout_ms"])
            self._current_url = self._page.url
            title = await self._page.title()
            status = response.status if response else "?"
            log.debug(f"browser.open {url} → {status} '{title}'")
            return f"[OK] Opened: {title} (status {status}) | URL: {self._current_url}"
        except (OSError, RuntimeError, TimeoutError) as e:
            log.warning(f"browser.open failed: {e}")
            return f"[BROWSER ERROR] {e}"

    async def read(self) -> str:
        """Extract visible text from current page."""
        if self._page is None or self._page.is_closed():
            return "[BROWSER ERROR] No page open. Call browser.open first."
        try:
            # Use evaluate to get clean text
            text = await self._page.evaluate("""() => {
                const clone = document.cloneNode(true);
                // Remove scripts, styles, nav, footer
                for (const tag of ['script','style','nav','footer','header','aside']) {
                    clone.querySelectorAll(tag).forEach(el => el.remove());
                }
                return (clone.body || clone).innerText || '';
            }""")
            text = re.sub(r'\n{3,}', '\n\n', text.strip())
            if len(text) > 6000:
                text = text[:6000] + f"\n...[truncated, {len(text)} total chars]"
            return text or "[BROWSER] Page appears empty"
        except (OSError, RuntimeError, TimeoutError) as e:
            return f"[BROWSER ERROR] read failed: {e}"

    async def click(self, selector: str) -> str:
        """Click an element by CSS selector or text."""
        if self._page is None or self._page.is_closed():
            return "[BROWSER ERROR] No page open."
        try:
            await self._page.click(selector, timeout=self.timeout_ms)
            await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            self._current_url = self._page.url
            return f"[OK] Clicked '{selector}' | Now at: {self._current_url}"
        except (OSError, RuntimeError, TimeoutError) as e:
            return f"[BROWSER ERROR] click('{selector}'): {e}"

    async def type_text(self, selector_and_text: str) -> str:
        """
        Type into an input field.
        Format: "selector|text to type"
        Example: "#search|hello world"
        """
        if "|" not in selector_and_text:
            return "[BROWSER ERROR] format: 'selector|text to type'"
        selector, text = selector_and_text.split("|", 1)
        if self._page is None or self._page.is_closed():
            return "[BROWSER ERROR] No page open."
        try:
            await self._page.fill(selector.strip(), text.strip())
            return f"[OK] Typed into '{selector.strip()}'"
        except (OSError, RuntimeError, TimeoutError) as e:
            return f"[BROWSER ERROR] type('{selector}'): {e}"

    async def screenshot(self, filename: str = "") -> str:
        """Take a screenshot. Saves to workspace screenshots dir."""
        if self._page is None or self._page.is_closed():
            return "[BROWSER ERROR] No page open."
        try:
            if not filename:
                import time
                filename = f"screenshot_{int(time.time())}.png"
            if not filename.endswith(".png"):
                filename += ".png"
            # Force into workspace screenshots dir — never allow arbitrary paths
            safe_name = Path(filename).name
            path = self._screenshot_dir / safe_name
            await self._page.screenshot(path=str(path), full_page=False)
            return f"[OK] Screenshot saved: {path}"
        except (OSError, RuntimeError, TimeoutError) as e:
            return f"[BROWSER ERROR] screenshot: {e}"

    async def scroll(self, direction: str = "down") -> str:
        """Scroll the page. direction: 'down' | 'up' | 'top' | 'bottom'"""
        if self._page is None or self._page.is_closed():
            return "[BROWSER ERROR] No page open."
        scripts = {
            "down":   "window.scrollBy(0, window.innerHeight)",
            "up":     "window.scrollBy(0, -window.innerHeight)",
            "top":    "window.scrollTo(0, 0)",
            "bottom": "window.scrollTo(0, document.body.scrollHeight)",
        }
        script = scripts.get(direction.lower(), scripts["down"])
        try:
            await self._page.evaluate(script)
            return f"[OK] Scrolled {direction}"
        except (OSError, RuntimeError, TimeoutError) as e:
            return f"[BROWSER ERROR] scroll: {e}"

    async def wait(self, selector_or_ms: str = "1000") -> str:
        """Wait for selector to appear, or wait N milliseconds."""
        if self._page is None or self._page.is_closed():
            return "[BROWSER ERROR] No page open."
        try:
            ms = int(selector_or_ms)
            await asyncio.sleep(ms / 1000)
            return f"[OK] Waited {ms}ms"
        except ValueError:
            # It's a selector
            try:
                await self._page.wait_for_selector(selector_or_ms, timeout=self.timeout_ms)
                return f"[OK] Selector appeared: {selector_or_ms}"
            except (OSError, RuntimeError, TimeoutError) as e:
                return f"[BROWSER ERROR] wait for '{selector_or_ms}': {e}"

    async def close(self) -> str:
        """Close the current page."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
                self._page = None
            return "[OK] Browser page closed"
        except (OSError, RuntimeError, TimeoutError) as e:
            return f"[BROWSER ERROR] close: {e}"

    async def shutdown(self):
        """Full shutdown — close browser and playwright."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
        except (OSError, RuntimeError, TimeoutError) as e:
            log.debug(f"unexpected: {e}")
            pass
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
        except (OSError, RuntimeError, TimeoutError) as e:
            log.debug(f"unexpected: {e}")
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except (OSError, RuntimeError, TimeoutError) as e:
            log.debug(f"unexpected: {e}")
            pass
        log.info(f"Browser adapter shut down for workspace {self.workspace_id}")
