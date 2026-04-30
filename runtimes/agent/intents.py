# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Deterministic intent classifier for the Nexus agent loop.

Pure regex — zero LLM calls. Routes 60-70% of real user inputs to a
fast-path that bypasses the LLM entirely. Patterns are intentionally
conservative: we only return a non-LLM intent when we're highly confident.
Anything ambiguous falls through to the LLM.

Inspired by Nexus Windows orchestrator.py priority pipeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    GREETING = "greeting"           # "hi", "hello", "good morning"
    ACK = "ack"                     # "ok", "thanks", "got it"
    MORNING_BRIEFING = "morning_briefing"  # "good morning, briefing", "what's on today"
    REMINDER_ADD = "reminder_add"   # "remind me to X at Y"
    REMINDER_LIST = "reminder_list" # "what are my reminders"
    VOLUME_SET = "volume_set"       # "set volume to 50", "volume up"
    APP_OPEN = "app_open"           # "open spotify", "launch firefox"
    TIME_QUERY = "time_query"       # "what time is it", "what's the date"
    MEMORY_RECALL = "memory_recall" # "what did I tell you about X", "remind me what X is"
    LLM_NEEDED = "llm_needed"       # everything else — punt to LLM


@dataclass
class IntentMatch:
    intent: Intent
    args: dict          # extracted parameters (volume_level, app_name, etc.)
    confidence: float   # 0.0–1.0 — only > 0.8 trusted for fast-path
    raw_match: str = ""


# ── Patterns ────────────────────────────────────────────────────────────────

_GREETING = re.compile(
    r"^(hi|hello|hey|yo|sup|hiya|howdy|good\s+(morning|afternoon|evening|day))[!.?\s]*$",
    re.IGNORECASE,
)

_ACK = re.compile(
    r"^(ok|okay|k|kk|yes|yeah|yep|yup|no|nope|sure|thanks|thank\s+you|"
    r"got\s+it|alright|cool|nice|great|good|done|please|continue|go\s+ahead)[!.?\s]*$",
    re.IGNORECASE,
)

_MORNING_BRIEFING = re.compile(
    r"^(good\s+morning(\s+nexus)?(\s+briefing)?|morning\s+briefing|"
    r"what'?s\s+(on|happening)\s+today|what'?s\s+my\s+(day|schedule)|"
    r"brief\s+me|daily\s+briefing|catch\s+me\s+up|"
    r"give\s+me\s+(my|the)\s+briefing|run\s+(my\s+)?morning\s+briefing)[!.?]*$",
    re.IGNORECASE,
)

# "remind me to walk the dog at 7pm"
# "set a reminder for tomorrow 9am to call mum"
_REMINDER_ADD = re.compile(
    r"^(remind\s+me\s+to|set\s+(a\s+)?reminder\s+(to|for|about))\s+(?P<task>.+?)"
    r"(\s+(at|on|in|tomorrow|today|tonight)\s+(?P<when>.+?))?[!.?]*$",
    re.IGNORECASE,
)

_REMINDER_LIST = re.compile(
    r"^(what\s+(are\s+)?my\s+reminders|list\s+(my\s+)?reminders|"
    r"show\s+(me\s+)?(my\s+)?reminders|reminders[?]?)[!.?\s]*$",
    re.IGNORECASE,
)

# "set volume to 50", "volume 30", "volume up", "turn the volume down"
_VOLUME = re.compile(
    r"^(set\s+(the\s+)?volume\s+to\s+(?P<level>\d{1,3})|"
    r"volume\s+(?P<level2>\d{1,3})|"
    r"(turn\s+(the\s+)?)?volume\s+(?P<dir>up|down)|"
    r"(turn\s+)?(?P<dir2>mute|unmute))[!.?\s]*$",
    re.IGNORECASE,
)

# "open spotify", "launch firefox", "start vscode"
# Two-word minimum to avoid clashing with one-word ack ("open?")
_APP_OPEN = re.compile(
    r"^(open|launch|start|run)\s+(?P<app>[a-z0-9\-\s\.]{2,40})[!.?\s]*$",
    re.IGNORECASE,
)

# block app names that are likely conversational, not actual apps
_APP_OPEN_BLOCKLIST = {
    "up", "down", "in", "out", "the door", "your mouth", "a window",
    "an issue", "a ticket", "the file", "a file", "the document",
    # if the user says "open the X file", that's fs.read territory, not app launch
}

_TIME_QUERY = re.compile(
    r"^(what'?s?\s+the\s+time|what\s+time\s+is\s+it|current\s+time|"
    r"what\s+(day|date)\s+is\s+(it|today)|what'?s?\s+today'?s?\s+date|"
    r"what\s+day\s+of\s+the\s+week)[!.?\s]*$",
    re.IGNORECASE,
)

# "what did I tell you about X", "remind me what X is", "do you remember X"
_MEMORY_RECALL = re.compile(
    r"^(what\s+did\s+i\s+(tell|say)\s+(you\s+)?about\s+(?P<topic>.+?)|"
    r"remind\s+me\s+(what|who|where|when)\s+(?P<topic2>.+?)\s+(is|was|are|were)|"
    r"do\s+you\s+remember\s+(?P<topic3>.+?))[!.?]*$",
    re.IGNORECASE,
)


def classify(user_input: str) -> IntentMatch:
    """
    Classify user input into an intent. Returns LLM_NEEDED if no fast-path match.
    Pure regex, no I/O, no LLM. Safe to call on every input.
    """
    s = (user_input or "").strip()
    if not s:
        return IntentMatch(Intent.LLM_NEEDED, {}, 0.0)

    # Order matters: more-specific patterns first.

    # 1. Morning briefing (must come before greeting — "good morning briefing")
    m = _MORNING_BRIEFING.match(s)
    if m:
        return IntentMatch(Intent.MORNING_BRIEFING, {}, 0.95, m.group(0))

    # 2. Greetings
    m = _GREETING.match(s)
    if m:
        return IntentMatch(Intent.GREETING, {"text": m.group(0)}, 0.99, m.group(0))

    # 3. Acks
    m = _ACK.match(s)
    if m:
        return IntentMatch(Intent.ACK, {"text": m.group(0)}, 0.99, m.group(0))

    # 4. Time queries
    m = _TIME_QUERY.match(s)
    if m:
        return IntentMatch(Intent.TIME_QUERY, {}, 0.95, m.group(0))

    # 5. Volume control
    m = _VOLUME.match(s)
    if m:
        level = m.group("level") or m.group("level2")
        direction = m.group("dir") or m.group("dir2")
        args = {}
        if level is not None:
            args["level"] = max(0, min(100, int(level)))
        if direction:
            args["direction"] = direction.lower()
        return IntentMatch(Intent.VOLUME_SET, args, 0.95, m.group(0))

    # 6. Reminders (list before add — "list my reminders" vs "remind me to list")
    m = _REMINDER_LIST.match(s)
    if m:
        return IntentMatch(Intent.REMINDER_LIST, {}, 0.95, m.group(0))

    m = _REMINDER_ADD.match(s)
    if m:
        return IntentMatch(
            Intent.REMINDER_ADD,
            {"task": (m.group("task") or "").strip(), "when": (m.group("when") or "").strip()},
            0.85,
            m.group(0),
        )

    # 7. App launching
    m = _APP_OPEN.match(s)
    if m:
        app = (m.group("app") or "").strip().lower()
        if app and app not in _APP_OPEN_BLOCKLIST and not app.endswith("file"):
            return IntentMatch(Intent.APP_OPEN, {"app": app}, 0.85, m.group(0))

    # 8. Memory recall
    m = _MEMORY_RECALL.match(s)
    if m:
        topic = (m.group("topic") or m.group("topic2") or m.group("topic3") or "").strip()
        if topic:
            return IntentMatch(Intent.MEMORY_RECALL, {"topic": topic}, 0.9, m.group(0))

    # No match — punt to LLM
    return IntentMatch(Intent.LLM_NEEDED, {}, 0.0)
