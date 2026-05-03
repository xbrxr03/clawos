# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Compose tools — generate written content using the local LLM.

write_text uses a second LLM call (with no tools) to produce content. This
keeps the agent loop's LLM call (which has tools attached) focused on
control-flow, while content generation can run on a different model tier
(usually SMART or CODER for higher quality).
"""
from __future__ import annotations

import asyncio
import logging

from clawos_core.constants import OLLAMA_HOST
from runtimes.agent.router import SMART_MODEL

log = logging.getLogger("agent.tools.compose")


async def write_text(args: dict, ctx: dict) -> str:
    """
    Generate written content. Returns the raw text. Does not save or paste.
    """
    topic  = (args.get("topic") or "").strip()
    length = (args.get("length") or "medium").strip()
    tone   = (args.get("tone") or "neutral").strip()
    if not topic:
        return "[ERROR] topic required"

    try:
        import ollama
    except ImportError:
        return "[ERROR] ollama not installed"

    # Translate "length" hints into approximate token guidance for the model
    length_l = length.lower()
    if "word" in length_l:
        # "1000 words" → aim for ~1000 words
        try:
            words = int("".join(c for c in length_l if c.isdigit()))
        except ValueError:
            words = 400
        target = f"approximately {words} words"
    elif length_l in ("short", "brief"):
        target = "a short response, 100-200 words"
    elif length_l in ("long", "detailed", "in-depth"):
        target = "a detailed response, 800-1200 words"
    elif "paragraph" in length_l:
        target = length
    else:
        target = "a medium-length response, 300-500 words"

    sys_prompt = (
        f"You are a writing assistant. Produce {target} on the requested topic. "
        f"Tone: {tone}. Output the prose only — no preamble, no commentary, no "
        "headers unless the prose naturally calls for them."
    )
    user = f"Write about: {topic}"

    loop = asyncio.get_running_loop()
    def _sync():
        client = ollama.Client(host=OLLAMA_HOST)
        # Bigger context for long-form generation
        resp = client.chat(
            model    = SMART_MODEL,
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": user},
            ],
            options  = {"temperature": 0.7, "num_ctx": 8192},
        )
        msg = resp["message"] if isinstance(resp, dict) else resp.message
        return (msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")) or ""

    try:
        text = await loop.run_in_executor(None, _sync)
    except (ConnectionError, OSError, KeyError, TypeError) as e:
        return f"[ERROR] write_text: {e}"

    return text.strip() or "[ERROR] empty generation"
