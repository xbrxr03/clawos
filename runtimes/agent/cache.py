# SPDX-License-Identifier: AGPL-3.0-or-later
"""
TTL cache for time-stable tool results.

Idea: when the LLM asks for the weather twice in the same minute, the second
call should not hit the network. Per-tool TTLs are conservative — system_stats
is fresh on every call (TTL=0), weather is 5 minutes, news is 15 minutes.

Cache keys are (tool_name, frozenset of arg items). Mutating tools never cache.
"""
from __future__ import annotations

import time
from typing import Any

# Per-tool TTL in seconds. Tools not listed here are NOT cached.
_TOOL_TTL: dict[str, int] = {
    "get_weather":         300,   # 5 min
    "get_news":            900,   # 15 min
    "get_calendar_events": 60,    # 1 min
    "list_workflows":      300,   # 5 min
    "list_reminders":      30,    # half a minute
    "system_stats":        5,     # CPU/RAM samples are stale fast
    "get_time":            0,     # always live
}

_cache: dict[tuple[str, frozenset], tuple[float, Any]] = {}


def _key(name: str, args: dict) -> tuple[str, frozenset]:
    # Hashable args — fall back to repr for nested values
    items: list[tuple[str, Any]] = []
    for k, v in (args or {}).items():
        try:
            hash(v)
            items.append((k, v))
        except TypeError:
            items.append((k, repr(v)))
    return name, frozenset(items)


def get(name: str, args: dict) -> Any | None:
    ttl = _TOOL_TTL.get(name)
    if not ttl:
        return None
    entry = _cache.get(_key(name, args))
    if entry is None:
        return None
    saved_at, value = entry
    if (time.time() - saved_at) > ttl:
        return None
    return value


def put(name: str, args: dict, value: Any) -> None:
    ttl = _TOOL_TTL.get(name)
    if not ttl:
        return
    _cache[_key(name, args)] = (time.time(), value)


def clear(name: str | None = None) -> None:
    """Clear one tool's cache (for tests/debug) or everything if None."""
    if name is None:
        _cache.clear()
    else:
        for k in [k for k in _cache if k[0] == name]:
            del _cache[k]


def is_cacheable(name: str) -> bool:
    return name in _TOOL_TTL and _TOOL_TTL[name] > 0
