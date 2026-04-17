# SPDX-License-Identifier: AGPL-3.0-or-later
"""
OMI transcript parser — utilities for processing OMI webhook payloads.

Handles:
  - Segment text extraction (full or user-only)
  - Command detection ("nexus, <command>" prefix)
  - Knowledge graph triple extraction from action items + structured titles
"""
import re
from typing import Optional


# ── Command prefix ────────────────────────────────────────────────────────────
_COMMAND_PREFIX_RE = re.compile(
    r"^\s*(?:hey\s+)?nexus[,.:!]?\s+",
    re.IGNORECASE,
)


def segments_to_text(segments: list[dict], user_only: bool = False) -> str:
    """
    Concatenate transcript segments into plain text.

    Args:
        segments: List of OMI segment dicts with at least 'text' key.
                  Optional: 'is_user', 'speaker', 'speaker_name'.
        user_only: If True, only include segments where is_user is True.

    Returns:
        Joined text string.
    """
    parts = []
    for seg in segments:
        if user_only and not seg.get("is_user", False):
            continue
        text = seg.get("text", "").strip()
        if text:
            speaker = seg.get("speaker_name") or seg.get("speaker", "")
            if speaker and not user_only:
                parts.append(f"{speaker}: {text}")
            else:
                parts.append(text)
    return " ".join(parts)


def extract_command(text: str) -> Optional[str]:
    """
    Detect "nexus, <command>" or "hey nexus, <command>" pattern.

    Returns the command portion (everything after the prefix) if detected,
    or None if no command prefix found.

    Examples:
        "nexus, what time is it?" -> "what time is it?"
        "hey nexus, summarize my day" -> "summarize my day"
        "hello there" -> None
    """
    m = _COMMAND_PREFIX_RE.match(text)
    if m:
        command = text[m.end():].strip()
        return command if command else None
    return None


def segments_to_kg_triples(
    segments: list[dict],
    structured: Optional[dict] = None,
) -> list[dict]:
    """
    Extract knowledge graph triples from OMI conversation data.

    Sources:
      1. structured.action_items -> (user, should_do, <action_item>)
      2. structured.title -> (user, discussed, <title>)
      3. structured.category -> (conversation, category, <category>)

    Returns list of triple dicts: {subject, predicate, object}
    """
    triples = []

    if structured:
        # Action items -> task triples
        for item in structured.get("action_items", []):
            if isinstance(item, str) and item.strip():
                triples.append({
                    "subject": "user",
                    "predicate": "should_do",
                    "object": item.strip(),
                })

        # Title -> topic triple
        title = structured.get("title", "")
        if title and isinstance(title, str):
            triples.append({
                "subject": "user",
                "predicate": "discussed",
                "object": title.strip(),
            })

        # Category -> classification triple
        category = structured.get("category", "")
        if category and isinstance(category, str):
            triples.append({
                "subject": "conversation",
                "predicate": "category",
                "object": category.strip(),
            })

    # Extract mentioned names from user segments as relationship hints
    user_text = segments_to_text(segments, user_only=True)
    for name_match in re.finditer(r"\bwith\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", user_text):
        triples.append({
            "subject": "user",
            "predicate": "met_with",
            "object": name_match.group(1),
        })

    return triples


def build_summary_prompt(transcript_text: str, structured: Optional[dict] = None) -> str:
    """
    Build a prompt for Nexus to summarize an OMI conversation.
    Returns a string suitable as user_input to the agent runtime.
    """
    parts = ["Summarize this conversation in 1-2 sentences. Focus on key decisions and action items."]
    if structured:
        title = structured.get("title", "")
        if title:
            parts.append(f"Topic: {title}")
        actions = structured.get("action_items", [])
        if actions:
            parts.append(f"Action items: {', '.join(str(a) for a in actions)}")
    parts.append(f"\nTranscript:\n{transcript_text[:2000]}")
    return "\n".join(parts)
