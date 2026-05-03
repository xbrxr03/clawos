# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Knowledge / memory tools — wrappers over services/memd MemoryService.
"""
from __future__ import annotations

import logging

log = logging.getLogger("agent.tools.knowledge")


async def remember(args: dict, ctx: dict) -> str:
    text = str(args.get("text", "")).strip()
    if not text:
        return "[ERROR] text required"
    memory = ctx.get("memory")
    if not memory:
        return "[ERROR] memory service unavailable"
    ws = ctx.get("workspace_id") or "default"
    try:
        await memory.remember_async(text, ws, source="agent_remember")
    except (ConnectionError, OSError, AttributeError) as e:
        return f"[ERROR] {e}"
    return f"[OK] remembered: {text[:120]}"


async def recall(args: dict, ctx: dict) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return "[ERROR] query required"
    memory = ctx.get("memory")
    if not memory:
        return "[ERROR] memory service unavailable"
    ws = ctx.get("workspace_id") or "default"
    try:
        hits = memory.recall(query, ws, n=5)
    except (ConnectionError, OSError, AttributeError) as e:
        return f"[ERROR] {e}"
    if not hits:
        return "(no matches)"
    return "\n".join(f"- {h[:300]}" for h in hits)


async def pin_fact(args: dict, ctx: dict) -> str:
    fact = str(args.get("fact", "")).strip()
    if not fact:
        return "[ERROR] fact required"
    memory = ctx.get("memory")
    if not memory:
        return "[ERROR] memory service unavailable"
    ws = ctx.get("workspace_id") or "default"
    try:
        memory.append_pinned(ws, fact)
    except (ConnectionError, OSError, AttributeError) as e:
        return f"[ERROR] {e}"
    return f"[OK] pinned: {fact[:120]}"
