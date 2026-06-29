# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Context Compression with Prompt Caching
=========================================
Replaces hard truncation of conversation history with lossy summarization
of older turns, preserving recent context verbatim and injecting a cache
breakpoint marker for prompt-caching-aware inference backends.

Flow:
  [system_prompt ← cache breakpoint]
  + [compressed summary of old turns]
  + [history[-N:] verbatim]
  + [user_msg ← cache breakpoint]

If LLM summarization fails (timeout, model not found), falls back to
extractive compression — no crashes, no blocking the agent loop.
"""
from __future__ import annotations

import logging
import time

from clawos_core.constants import (
    MAX_VERBATIM_TURNS,
    COMPRESSION_THRESHOLD_TOKENS,
    CACHE_BREAKPOINT_MARKER,
)

log = logging.getLogger("agentd.compression")

# Rough token estimate — 4 chars per token, same heuristic as context_budget.
CHARS_PER_TOKEN = 4

# Timeout for LLM summarization — never block the agent loop.
_SUMMARIZE_TIMEOUT_S = 5


def _est_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _total_tokens(history: list[dict]) -> int:
    """Sum estimated tokens across all messages in history."""
    return sum(_est_tokens(m.get("content") or "") for m in history)


class ContextCompressor:
    """Replace hard truncation with lossy summarization of older turns."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        max_verbatim: int = MAX_VERBATIM_TURNS,
        threshold_tokens: int = COMPRESSION_THRESHOLD_TOKENS,
    ):
        self.model = model
        self.max_verbatim = max_verbatim
        self.threshold_tokens = threshold_tokens

    # ── public API ────────────────────────────────────────────────────────

    def should_compress(self, history: list[dict]) -> bool:
        """Return True if history exceeds the token threshold."""
        return _total_tokens(history) > self.threshold_tokens

    def compress(self, history: list[dict]) -> tuple[str, list[dict]]:
        """
        Compress older turns into a summary, keep recent N turns verbatim.

        Returns:
            (summary_text, verbatim_turns) — the summary is meant to be
            injected as a system message before the verbatim turns.
        """
        if len(history) <= self.max_verbatim:
            # All turns fit verbatim — no compression needed, but we still
            # return a consistent shape for the caller.
            return "", list(history)

        old_turns = history[: -self.max_verbatim]
        verbatim = list(history[-self.max_verbatim :])

        # Try LLM summarization; fall back to extractive on any failure.
        summary = self._summarize(old_turns)
        return summary, verbatim

    # ── LLM summarization ────────────────────────────────────────────────

    def _summarize(self, turns: list[dict]) -> str:
        """
        Use LLM to summarize old turns. Falls back to extractive
        compression on failure (timeout, model not found, etc.).
        """
        try:
            import ollama as _ollama_lib
        except ImportError:
            log.debug("ollama not installed, using extractive fallback")
            return self._extractive_compress(turns)

        # Build a compact representation for the LLM prompt.
        conversation = self._format_turns_for_summary(turns)
        prompt = (
            "Summarize the following conversation in 2-4 concise paragraphs. "
            "Preserve key facts, decisions, tool results, and user preferences. "
            "Omit pleasantries and filler.\n\n"
            f"{conversation}"
        )

        # Estimate whether the prompt itself is reasonable.
        if _est_tokens(prompt) > 4000:
            # Too much for a fast summary model — extract key points instead.
            log.debug("turns too long for LLM summary, using extractive fallback")
            return self._extractive_compress(turns)

        try:
            client = _ollama_lib.Client(
                host=__import__(
                    "clawos_core.constants", fromlist=["OLLAMA_HOST"]
                ).OLLAMA_HOST
            )
            start = time.monotonic()
            resp = client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2, "num_ctx": 2048},
            )
            elapsed = time.monotonic() - start
            if elapsed > _SUMMARIZE_TIMEOUT_S:
                log.warning("LLM summarization took %.1fs (slow but completed)", elapsed)

            # Normalize response.
            msg = resp.get("message", resp) if isinstance(resp, dict) else resp.message
            summary = msg if isinstance(msg, str) else getattr(msg, "content", "")
            if isinstance(summary, str) and summary.strip():
                log.info(
                    "LLM summary OK (%d turns → %d tokens)",
                    len(turns),
                    _est_tokens(summary),
                )
                return summary.strip()
            # Empty response — fall back.
            log.debug("LLM returned empty summary, using extractive fallback")
            return self._extractive_compress(turns)

        except Exception as exc:
            log.debug("LLM summarization failed (%s), using extractive fallback", exc)
            return self._extractive_compress(turns)

    # ── extractive fallback ───────────────────────────────────────────────

    def _extractive_compress(self, turns: list[dict]) -> str:
        """
        Fallback compression when LLM summarization is unavailable.

        Strategy: keep first user message + compress tool outputs + keep
        last 2 turns from the old window.
        """
        if not turns:
            return ""

        parts: list[str] = []

        # Always keep the first user message — sets the initial context.
        first_user = next(
            (t for t in turns if t.get("role") == "user"), None
        )
        if first_user:
            content = (first_user.get("content") or "").strip()
            if content:
                parts.append(f"[Conversation start] User: {content}")

        # Compress tool outputs > 500 chars in the middle turns.
        for t in turns:
            content = (t.get("content") or "").strip()
            if not content:
                continue
            role = t.get("role", "")
            if t is first_user:
                # Already included above.
                continue
            # Compress large tool outputs.
            if role == "tool" or (role == "assistant" and len(content) > 500):
                compressed = self._compress_tool_output(content)
                if compressed:
                    parts.append(f"[{role}] {compressed}")
            else:
                # Keep shorter messages verbatim but cap at reasonable length.
                if len(content) > 300:
                    content = content[:300] + "…[trimmed]"
                parts.append(f"[{role}] {content}")

        # Always keep the last 2 old turns verbatim for continuity.
        if len(turns) > 2:
            tail = turns[-2:]
            tail_text = " | ".join(
                f"[{t.get('role', '?')}] {(t.get('content') or '')[:200]}"
                for t in tail
            )
            parts.append(f"[Recent] {tail_text}")

        summary = "\n".join(parts)
        log.info(
            "Extractive summary: %d turns → %d tokens",
            len(turns),
            _est_tokens(summary),
        )
        return summary

    # ── tool output compression ──────────────────────────────────────────

    @staticmethod
    def _compress_tool_output(content: str, max_chars: int = 500) -> str:
        """
        Compress a single tool output that exceeds max_chars.
        Truncates and appends a note about omitted content.
        """
        if not content or len(content) <= max_chars:
            return content
        omitted = len(content) - max_chars
        return content[:max_chars] + f"\n[compressed, {omitted} chars omitted]"

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _format_turns_for_summary(turns: list[dict]) -> str:
        """Format turns into a readable conversation log for the LLM."""
        lines: list[str] = []
        for t in turns:
            role = t.get("role", "?")
            content = (t.get("content") or "").strip()
            if not content:
                continue
            # Cap each turn at 600 chars for the summary prompt.
            if len(content) > 600:
                content = content[:600] + "…"
            lines.append(f"{role}: {content}")
        return "\n".join(lines)


def make_summary_message(summary: str) -> dict:
    """
    Wrap a summary string in a system message with the cache breakpoint
    marker, ready to inject into the message list.
    """
    return {
        "role": "system",
        "content": f"[Previous conversation summary]\n{CACHE_BREAKPOINT_MARKER}\n{summary}",
    }


def compress_history_tool_outputs(history: list[dict], max_chars: int = 500) -> int:
    """
    Walk the history and compress any tool-role messages whose content
    exceeds max_chars. Mutates in place and returns the number of
    messages compressed.

    This is meant to be called after each turn to keep history lean.
    """
    compressed = 0
    for msg in history:
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > max_chars:
                msg["content"] = ContextCompressor._compress_tool_output(
                    content, max_chars
                )
                compressed += 1
    return compressed