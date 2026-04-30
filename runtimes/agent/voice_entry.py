# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Voice entry helpers — bridge between voiced and the new Nexus runtime.

`speak_morning_briefing(workspace_id, tts_fn)` is a one-shot helper meant to
be triggered by:
  - a scheduled job at user's morning time (cron / timer)
  - the wake word followed by "good morning" / "brief me"
  - a tray menu item

It builds (or reuses) a runtime, asks for the briefing, and pipes the result
through whatever tts_fn was passed in (typically VoiceService.synth_to_speaker).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from clawos_core.constants import DEFAULT_WORKSPACE
from runtimes.agent.briefing import morning_briefing
from runtimes.agent.runtime import build_runtime

log = logging.getLogger("agent.voice_entry")

TTSFn = Callable[[str], Awaitable[None] | None]


async def speak_morning_briefing(
    tts_fn: TTSFn,
    workspace_id: str = DEFAULT_WORKSPACE,
    runtime=None,
) -> str:
    """Generate and speak the morning briefing. Returns the spoken text."""
    if runtime is None:
        runtime = await build_runtime(workspace_id=workspace_id)
    text = await morning_briefing(runtime)
    try:
        result = tts_fn(text)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        log.warning(f"tts failed: {e}")
    return text


async def voice_chat_once(
    user_text: str,
    tts_fn: TTSFn,
    workspace_id: str = DEFAULT_WORKSPACE,
    runtime=None,
) -> str:
    """Single voice exchange: text → agent → speak → return what was spoken."""
    if runtime is None:
        runtime = await build_runtime(workspace_id=workspace_id)
    reply = await runtime.chat(user_text)
    try:
        result = tts_fn(reply)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        log.warning(f"tts failed: {e}")
    return reply
