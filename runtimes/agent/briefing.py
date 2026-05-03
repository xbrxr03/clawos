# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Morning briefing — the showcase workflow.

Parallelises 5 independent tool calls (time, weather, calendar, reminders,
recent memory) and synthesises one short JARVIS-style spoken briefing.
Fully offline-capable: weather and news fall back to "[OFFLINE] …" lines and
the briefing is still useful.

Wired into the agent loop via runtime._try_deterministic when classify()
returns Intent.MORNING_BRIEFING.
"""
from __future__ import annotations

import asyncio
import logging

from clawos_core.constants import OLLAMA_HOST
from runtimes.agent.router import SMART_MODEL
from runtimes.agent.tools import dispatch_tool

log = logging.getLogger("agent.briefing")


_SYNTHESIS_PROMPT = """\
You are JARVIS-style assistant Nexus, delivering a short spoken morning
briefing. Use the data below to produce a 4-7 sentence briefing, conversational
and warm, suitable for text-to-speech. Never read the field names aloud, never
say "according to the weather tool", just deliver the information naturally.
If a section is missing or shows [OFFLINE] / [ERROR], skip it gracefully.
Keep total length under 100 words.
"""


async def _gather_briefing_data(runtime) -> dict[str, str]:
    """Run all 5 briefing tool calls in parallel."""
    ws_id = getattr(runtime, "workspace_id", "default")
    memory = getattr(runtime, "memory", None)
    ws_root = None
    if memory:
        try:
            from clawos_core.util.paths import workspace_path
            ws_root = workspace_path(ws_id)
        except (ImportError, OSError, AttributeError) as e:
            log.debug(f"suppressed: {e}")
    ctx = {"workspace_id": ws_id, "memory": memory, "ws_root": ws_root, "bridge": runtime.bridge}

    async def _call(name: str, args: dict) -> str:
        try:
            return await dispatch_tool(name, args, ctx)
        except Exception as e:  # dispatch_tool may fail in many ways
            return f"[ERROR] {e}"

    results = await asyncio.gather(
        _call("get_time",            {}),
        _call("get_weather",         {}),
        _call("get_calendar_events", {"start": "today", "end": "today"}),
        _call("list_reminders",      {"days_ahead": 1}),
        _call("recall",              {"query": "yesterday work"}),
        return_exceptions=False,
    )
    return {
        "time":      results[0],
        "weather":   results[1],
        "calendar":  results[2],
        "reminders": results[3],
        "memory":    results[4],
    }


async def _synthesise(data: dict[str, str]) -> str:
    """Send the data to the SMART model for natural synthesis."""
    try:
        import ollama
    except ImportError:
        return _fallback_text(data)

    user = (
        f"TIME: {data['time']}\n"
        f"WEATHER: {data['weather']}\n"
        f"CALENDAR (today): {data['calendar']}\n"
        f"REMINDERS (next 24h): {data['reminders']}\n"
        f"FROM MEMORY (yesterday's work): {data['memory']}\n"
    )

    loop = asyncio.get_running_loop()
    def _sync():
        client = ollama.Client(host=OLLAMA_HOST)
        resp = client.chat(
            model    = SMART_MODEL,
            messages = [
                {"role": "system", "content": _SYNTHESIS_PROMPT},
                {"role": "user",   "content": user},
            ],
            options  = {"temperature": 0.5, "num_ctx": 4096},
        )
        msg = resp["message"] if isinstance(resp, dict) else resp.message
        return (msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")) or ""

    try:
        text = await loop.run_in_executor(None, _sync)
    except (OSError, ConnectionError, RuntimeError) as e:
        log.debug(f"briefing synth fell back: {e}")
        return _fallback_text(data)
    return text.strip() or _fallback_text(data)


def _fallback_text(data: dict[str, str]) -> str:
    """Used when the LLM is unreachable — still gives a useful briefing."""
    parts = ["Good morning."]
    if data["time"] and not data["time"].startswith("["):
        parts.append(f"It's {data['time'].split('·')[1].strip() if '·' in data['time'] else data['time']}.")
    if data["weather"] and not data["weather"].startswith("["):
        parts.append(f"Weather: {data['weather']}.")
    if data["calendar"] and not data["calendar"].startswith(("No events", "[")):
        parts.append("Today's events:\n" + data["calendar"])
    if data["reminders"] and not data["reminders"].startswith(("No upcoming", "[")):
        parts.append("Reminders:\n" + data["reminders"])
    return "\n\n".join(parts)


async def morning_briefing(runtime) -> str:
    """Public entry — gather + synthesise. Returns text suitable for TTS."""
    data = await _gather_briefing_data(runtime)
    return await _synthesise(data)
