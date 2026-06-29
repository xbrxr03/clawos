# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Auto-Skill Creation — Issue #64
=======================================
Detects complex, repeatable tasks from agent history and auto-generates
SKILL.md files. Runs as a fire-and-forget background task — never blocks
the agent loop.

Heuristics:
  - ≥3 tool calls in the conversation, OR
  - ≥2 user turns in the conversation

If an LLM is available (qwen2.5:3b), it generates a rich SKILL.md.
Otherwise, falls back to a template-based generation.

Duplicate detection uses BM25 similarity on the trigger field via
skilld's existing SkillLoader. If a similar skill exists, it's updated
instead of creating a duplicate.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from clawos_core.constants import (
    AUTO_SKILLS_DIR,
    AUTO_SKILL_MIN_TOOLS,
    AUTO_SKILL_MIN_TURNS,
)

log = logging.getLogger("skilld.auto_skill")

# ── Detection ─────────────────────────────────────────────────────────────────

def should_auto_skill(history: list[dict]) -> bool:
    """
    True if the completed task was complex enough to warrant a skill.
    Triggers on >= AUTO_SKILL_MIN_TOOLS tool calls OR >= AUTO_SKILL_MIN_TURNS user turns.
    """
    tool_call_count = 0
    user_turn_count = 0

    for entry in history:
        role = entry.get("role", "")
        if role == "user":
            user_turn_count += 1
        # Count tool calls embedded in assistant messages (Ollama format)
        if role == "assistant" and entry.get("tool_calls"):
            tool_call_count += len(entry["tool_calls"])
        # Also count tool result messages as proxy for completed tool calls
        if role == "tool":
            tool_call_count += 1

    return tool_call_count >= AUTO_SKILL_MIN_TOOLS or user_turn_count >= AUTO_SKILL_MIN_TURNS


# ── Skill generation ───────────────────────────────────────────────────────────

def generate_skill(history: list[dict]) -> tuple[str, str]:
    """
    Generate a SKILL.md from completed task history.
    Returns (slug, content) where content is the full SKILL.md text.
    Tries LLM generation first, falls back to template-based.
    """
    content = _generate_with_llm(history)
    if not content:
        content = _generate_template(history)

    # Extract slug from frontmatter name field, or derive from first user message
    slug = _extract_slug(content)
    if not slug:
        slug = _slug_from_history(history)

    return slug, content


def _extract_slug(content: str) -> str:
    """Extract the name from frontmatter and convert to slug."""
    match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    if match:
        name = match.group(1).strip()
        return name.lower().replace(" ", "-").replace("_", "-")
    return ""


def _slug_from_history(history: list[dict]) -> str:
    """Derive a slug from the first user message in history."""
    for entry in history:
        if entry.get("role") == "user":
            text = entry.get("content", "").strip()
            # Take first meaningful phrase
            words = re.sub(r"[^a-z0-9\s]", "", text.lower()).split()[:5]
            slug = "-".join(w for w in words if len(w) > 2)
            if slug:
                return f"auto-{slug}"
    return f"auto-skill-{int(time.time())}"


def _generate_with_llm(history: list[dict]) -> str:
    """
    Use LLM to generate skill content from history.
    Returns empty string if LLM unavailable.
    """
    try:
        import ollama as _ollama_lib
    except ImportError:
        log.debug("ollama not available, skipping LLM skill generation")
        return ""

    # Build a condensed summary of the conversation for the prompt
    summary_lines = _summarize_history(history)
    if not summary_lines:
        return ""

    prompt = (
        "You are a skill extraction engine. Given the following task transcript, "
        "extract a reusable SKILL.md. Follow this EXACT format:\n\n"
        "---\n"
        "name: <short-kebab-name>\n"
        "trigger: <when to activate this skill — one short phrase>\n"
        "pinned: false\n"
        "---\n\n"
        "# <Skill Name>\n\n"
        "## When to use\n"
        "<1-2 sentence description of when this skill applies>\n\n"
        "## Steps\n"
        "<numbered list of steps to follow>\n\n"
        "## Tools used\n"
        "- <tool>: <what it was used for>\n\n"
        "## Example input\n"
        "<the original user request>\n\n"
        "IMPORTANT: Output ONLY the SKILL.md content, nothing else. "
        "Keep it concise and actionable.\n\n"
        f"Task transcript:\n{chr(10).join(summary_lines)}"
    )

    try:
        client = _ollama_lib.Client(
            host="http://localhost:11434",
            timeout=30,
        )
        resp = client.chat(
            model="qwen2.5:3b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2, "num_ctx": 2048},
        )
        text = resp.get("message", {}).get("content", "") if isinstance(resp, dict) else ""
        if not text:
            text = getattr(resp, "message", None)
            text = getattr(text, "content", "") if text else ""
        text = text.strip()

        # Validate: must have frontmatter
        if text.startswith("---") and "trigger:" in text:
            return text
        log.debug("LLM output lacked valid frontmatter, falling back to template")
        return ""
    except Exception as e:
        log.debug(f"LLM skill generation failed: {e}")
        return ""


def _generate_template(history: list[dict]) -> str:
    """
    Fallback: template-based skill generation when LLM unavailable.
    Extracts tool names and user messages directly from history.
    """
    # Collect user messages and tool names
    user_messages = []
    tool_names = []

    for entry in history:
        role = entry.get("role", "")
        if role == "user":
            content = entry.get("content", "").strip()
            if content:
                user_messages.append(content)
        if role == "assistant" and entry.get("tool_calls"):
            for tc in entry["tool_calls"]:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                name = fn.get("name", "") if isinstance(fn, dict) else ""
                if name and name not in tool_names:
                    tool_names.append(name)
        if role == "tool":
            name = entry.get("tool_name", "")
            if name and name not in tool_names:
                tool_names.append(name)

    if not user_messages:
        user_messages = ["(auto-generated from task history)"]

    first_message = user_messages[0][:120]
    # Derive a human-readable name from the first message
    name_words = re.sub(r"[^a-z0-9\s]", "", first_message.lower()).split()
    name_words = [w for w in name_words if len(w) > 2][:4]
    skill_name = " ".join(w.capitalize() for w in name_words) if name_words else "Auto Generated Skill"
    slug = name_words[0] + "-" + "-".join(name_words[1:]) if len(name_words) > 1 else name_words[0] if name_words else "auto"

    trigger = first_message[:80].rstrip(".!?") if first_message else "auto-detected pattern"

    steps_lines = []
    steps_lines.append("1. Understand the user request")
    for i, tool in enumerate(tool_names, 2):
        steps_lines.append(f"{i}. Use {tool} to accomplish the task")
    steps_lines.append(f"{len(tool_names) + 2}. Summarize results to the user")

    tools_section = "\n".join(f"- {t}: used during task execution" for t in tool_names)
    if not tools_section:
        tools_section = "- (none detected)"

    datetime.now(timezone.utc).strftime("%Y-%m-%d")

    content = f"""\
---
name: {slug}
trigger: {trigger}
pinned: false
---

# {skill_name}

## When to use
Auto-generated skill for tasks similar to: {trigger}

## Steps
{chr(10).join(steps_lines)}

## Tools used
{tools_section}

## Example input
{first_message}
"""
    return content


def _summarize_history(history: list[dict], max_entries: int = 20) -> list[str]:
    """Condense history into summary lines suitable for an LLM prompt."""
    lines = []
    for entry in history[-max_entries:]:
        role = entry.get("role", "")
        content = entry.get("content", "").strip()
        if not content and not entry.get("tool_calls"):
            continue

        if role == "user":
            lines.append(f"User: {content[:200]}")
        elif role == "assistant":
            if content:
                lines.append(f"Assistant: {content[:200]}")
            tcs = entry.get("tool_calls", [])
            if tcs:
                for tc in tcs:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    name = fn.get("name", "?") if isinstance(fn, dict) else "?"
                    args = fn.get("arguments", {}) if isinstance(fn, dict) else {}
                    if isinstance(args, dict):
                        args_str = ", ".join(f"{k}={v!r}" for k, v in list(args.items())[:4])
                    else:
                        args_str = str(args)[:60]
                    lines.append(f"  Tool call: {name}({args_str})")
        elif role == "tool":
            name = entry.get("tool_name", "?")
            lines.append(f"  Tool result [{name}]: {content[:120]}")

    return lines


# ── Save / Update ─────────────────────────────────────────────────────────────

def save_auto_skill(slug: str, content: str) -> Path:
    """
    Save generated skill to ~/.claw/skills/auto/<slug>/SKILL.md
    Creates the directory if it doesn't exist.
    """
    skill_dir = AUTO_SKILLS_DIR / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")
    log.info(f"auto-skill saved: {skill_path}")
    return skill_path


def update_auto_skill(slug: str, content: str) -> Path:
    """
    Update an existing auto-skill instead of creating a duplicate.
    Increments version in the name if present, or appends v2.
    """
    skill_dir = AUTO_SKILLS_DIR / slug
    if not skill_dir.exists():
        # Doesn't actually exist — just save as new
        return save_auto_skill(slug, content)

    # Increment version in name field
    version_match = re.search(r"v(\d+)", content)
    if version_match:
        new_version = int(version_match.group(1)) + 1
        content = re.sub(r"v(\d+)", f"v{new_version}", content, count=1)
    else:
        # Append v2 to the name
        content = re.sub(r"^(name:\s*)", r"\1", content, count=1)
        name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
        if name_match:
            old_name = name_match.group(1).strip()
            content = content.replace(f"name: {old_name}", f"name: {old_name}-v2", 1)

    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")
    log.info(f"auto-skill updated: {skill_path}")
    return skill_path


# ── Duplicate detection ────────────────────────────────────────────────────────

def find_similar_skill(trigger: str) -> Optional[str]:
    """
    Check if a similar skill already exists using BM25 similarity on the
    trigger field via skilld's existing SkillLoader.
    Returns slug if found, None otherwise.
    """
    if not trigger:
        return None

    try:
        from services.skilld.service import SkillLoader, SCORE_THRESHOLD, SKILL_PATHS
        # Include auto directory in search paths
        paths = list(SKILL_PATHS) + [AUTO_SKILLS_DIR]
        loader = SkillLoader(skill_paths=paths)
        matches = loader.score(trigger)
        for m in matches:
            if m.score >= SCORE_THRESHOLD:
                return m.skill.name
    except Exception as e:
        log.debug(f"BM25 similarity check failed: {e}")

    return None