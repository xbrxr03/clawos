# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Browser tool definitions for ClawOS.
8 tools: browser.open, browser.read, browser.click, browser.type,
         browser.screenshot, browser.close, browser.scroll, browser.wait

All calls are gated through policyd (browser_control permission required).
Tool execution is handled by ToolBridge via dispatch table.
"""

BROWSER_TOOL_DESCRIPTIONS = {
    "browser.open":
        "Open a URL in the browser. Input: full URL (https://...). "
        "Returns page title and status.",
    "browser.read":
        "Read visible text from the current browser page. "
        "Returns cleaned page text (up to 6000 chars).",
    "browser.click":
        "Click an element on the current page. "
        "Input: CSS selector or text (e.g. 'button#submit' or 'text=Submit').",
    "browser.type":
        "Type text into an input field. "
        "Input format: 'selector|text to type' (e.g. 'input#q|search term').",
    "browser.screenshot":
        "Take a screenshot of the current page. "
        "Input: optional filename (default: timestamped PNG). "
        "Saved to workspace screenshots dir.",
    "browser.scroll":
        "Scroll the current page. Input: 'down' | 'up' | 'top' | 'bottom'. Default: down.",
    "browser.wait":
        "Wait for a selector to appear, or wait N milliseconds. "
        "Input: CSS selector (e.g. '#result') or milliseconds (e.g. '2000').",
    "browser.close":
        "Close the current browser page and release resources.",
}

# Tool → required permission in policyd
BROWSER_TOOL_PERMISSIONS = {tool: "browser_control" for tool in BROWSER_TOOL_DESCRIPTIONS}

# Risk scores for policyd TOOL_SCORES
BROWSER_TOOL_SCORES = {
    "browser.open":       35,
    "browser.read":       15,
    "browser.click":      40,
    "browser.type":       45,
    "browser.screenshot": 20,
    "browser.scroll":     10,
    "browser.wait":       5,
    "browser.close":      5,
}
