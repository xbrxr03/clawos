# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Native-args tool dispatch for the Nexus agent loop.

Each tool is a coroutine `async def tool_name(args: dict, ctx: dict) -> str`.
Tools live in submodules grouped by category; this __init__.py wires them
into a single NATIVE_TOOLS registry that ToolBridge.run_native consults.

ctx contains:
    workspace_id : str
    ws_root      : Path
    memory       : MemoryService | None
    bridge       : ToolBridge       (for tools that delegate, e.g. write_text)
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from runtimes.agent.tools import (
    compose, desktop, files, knowledge,
    productivity, system, web, workflows,
)

log = logging.getLogger("agent.tools")

ToolFn = Callable[[dict, dict], Awaitable[str]]

NATIVE_TOOLS: dict[str, ToolFn] = {
    # knowledge
    "remember":            knowledge.remember,
    "recall":              knowledge.recall,
    "pin_fact":            knowledge.pin_fact,
    # system
    "open_app":            system.open_app,
    "focus_window":        system.focus_window,
    "close_app":           system.close_app,
    "set_volume":          system.set_volume,
    "get_volume":          system.get_volume,
    "system_stats":        system.system_stats,
    # desktop
    "set_clipboard":       desktop.set_clipboard,
    "get_clipboard":       desktop.get_clipboard,
    "paste_to_app":        desktop.paste_to_app,
    "type_in_app":         desktop.type_in_app,
    "screenshot":          desktop.screenshot,
    # compose
    "write_text":          compose.write_text,
    # files
    "read_file":           files.read_file,
    "write_file":          files.write_file,
    "list_files":          files.list_files,
    "open_file":           files.open_file,
    "open_url":            files.open_url,
    # productivity
    "add_reminder":        productivity.add_reminder,
    "list_reminders":      productivity.list_reminders,
    "remove_reminder":     productivity.remove_reminder,
    "get_time":            productivity.get_time,
    "get_weather":         productivity.get_weather,
    "get_calendar_events": productivity.get_calendar_events,
    "get_news":            productivity.get_news,
    # workflows
    "list_workflows":      workflows.list_workflows,
    "run_workflow":        workflows.run_workflow,
    # web
    "web_search":          web.web_search,
    # shell
    "run_command":         system.run_command,
}


async def dispatch_tool(name: str, args: dict, ctx: dict) -> str:
    """
    Look up a native tool and call it. Returns a string result.

    Read-mostly tools (weather, news, calendar, list_*) hit the per-tool TTL
    cache first. Mutating tools (set_*, add_*, remove_*, write_*) skip cache.
    """
    fn = NATIVE_TOOLS.get(name)
    if fn is None:
        return f"[ERROR] Unknown tool: {name}"

    # Cache lookup (only for tools whitelisted in cache._TOOL_TTL)
    from runtimes.agent import cache as _cache
    cached = _cache.get(name, args or {})
    if cached is not None:
        return cached

    try:
        result = await fn(args or {}, ctx or {})
    except Exception as e:
        log.exception(f"tool {name} crashed")
        return f"[ERROR] {name}: {e}"

    text = result if isinstance(result, str) else str(result)
    # Don't cache error / offline strings
    if not text.startswith(("[ERROR]", "[DENIED]", "[OFFLINE]", "[PENDING")):
        _cache.put(name, args or {}, text)
    return text


__all__ = ["NATIVE_TOOLS", "dispatch_tool"]
