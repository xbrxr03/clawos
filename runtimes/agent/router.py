# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Dynamic model router for the Nexus agent loop.

Picks between three local models based on the task:
  - FAST  (qwen2.5:3b)         small, simple lookups, single-tool turns
  - SMART (qwen2.5:7b-instruct) default for multi-step + reasoning
  - CODER (qwen2.5-coder:7b)    file/code/shell-heavy tasks

Routing happens BEFORE the LLM is called, so we never waste tokens on the
wrong model. Falls back to whatever's installed in Ollama if a tier is missing.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("agent.router")

# Tier definitions. Override via env vars.
FAST_MODEL  = os.environ.get("CLAWOS_MODEL_FAST",  "qwen2.5:3b")
SMART_MODEL = os.environ.get("CLAWOS_MODEL_SMART", "qwen2.5:7b")
CODER_MODEL = os.environ.get("CLAWOS_MODEL_CODER", "qwen2.5-coder:7b")

# Tools that benefit from the coder model (file/code/shell ops)
_CODER_TOOLS = frozenset({
    "read_file", "write_file", "list_files", "open_file",
    "fs.read", "fs.write", "fs.list", "fs.search",
    "run_command", "shell.restricted",
    "run_workflow",  # workflows often process structured data
})

# Tools that suggest a simple single-shot turn (FAST is enough)
_FAST_TOOLS = frozenset({
    "get_time", "get_volume", "set_volume",
    "list_reminders", "remove_reminder",
    "get_clipboard", "set_clipboard",
    "open_app", "focus_window", "close_app",
    "system_stats",
})


@dataclass
class RouteDecision:
    model: str
    tier: str          # "fast" | "smart" | "coder"
    reason: str


def pick_model(
    user_input: str,
    likely_tools: list[str] | None = None,
    history_tokens: int = 0,
    explicit_tier: str | None = None,
) -> RouteDecision:
    """
    Decide which model to use for this turn.

    Args:
      user_input:    the user's raw text (used for length/complexity heuristics)
      likely_tools:  tools the deterministic intent or planner expects to be
                     called. None = unknown, default to SMART.
      history_tokens: rough token count of conversation history.
      explicit_tier: caller can force "fast" / "smart" / "coder".

    Returns:
      RouteDecision with model name + reason.
    """
    if explicit_tier:
        tier = explicit_tier.lower()
        if tier == "fast":  return RouteDecision(FAST_MODEL,  "fast",  "explicit override")
        if tier == "coder": return RouteDecision(CODER_MODEL, "coder", "explicit override")
        return RouteDecision(SMART_MODEL, "smart", "explicit override")

    tools = set(likely_tools or [])

    # Coder beats everything if any code/file/shell tool is in play
    if tools & _CODER_TOOLS:
        return RouteDecision(CODER_MODEL, "coder",
                             f"code/file tool: {next(iter(tools & _CODER_TOOLS))}")

    text = (user_input or "").strip()
    word_count = len(text.split())

    # Long history → SMART regardless of input
    if history_tokens > 1500:
        return RouteDecision(SMART_MODEL, "smart",
                             f"history {history_tokens} tokens > 1500")

    # Long or wordy input → SMART
    if word_count > 25 or len(text) > 200:
        return RouteDecision(SMART_MODEL, "smart",
                             f"input length {word_count} words")

    # Multiple tools likely → SMART
    if len(tools) > 1:
        return RouteDecision(SMART_MODEL, "smart",
                             f"multi-tool turn ({len(tools)} tools)")

    # Single fast-tier tool → FAST
    if tools and tools <= _FAST_TOOLS:
        return RouteDecision(FAST_MODEL, "fast",
                             f"fast-tier tool: {next(iter(tools))}")

    # Short input, no tools known → FAST (covers casual chat, simple Qs)
    if word_count <= 12 and not tools:
        return RouteDecision(FAST_MODEL, "fast",
                             "short input, no tools")

    # Default
    return RouteDecision(SMART_MODEL, "smart", "default")
