"""
Nexus prompt injection scanner.
Detects attempts to hijack agent behaviour via crafted inputs.
Uses pattern matching (fast, no LLM needed) + optional LLM scoring.

Called by:
  nexus scan <text>           — CLI
  policyd                     — before every tool call input (Phase 6)
"""
import re
from dataclasses import dataclass, field
from typing import Optional

# ── Injection patterns ────────────────────────────────────────────────────────
# Ordered roughly by severity. Each pattern has a weight (1-3).

_PATTERNS: list[tuple[str, str, int]] = [
    # Instruction override attempts
    (r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|context)",
     "ignore previous instructions", 3),
    (r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?)",
     "disregard previous instructions", 3),
    (r"forget\s+(everything|all|your|the)\s+(instructions?|rules?|training|context|above)",
     "forget instructions", 3),
    (r"(your\s+)?(new|actual|real|true|updated)\s+(instructions?|rules?|task|goal|purpose)\s+(is|are|now)",
     "new instructions injection", 3),
    (r"from\s+now\s+on\s+(you\s+)?(are|will|must|should)",
     "from now on override", 3),
    (r"you\s+are\s+now\s+(a\s+)?(different|new|another|an?)\s+\w+",
     "persona override", 2),

    # Jailbreak attempts
    (r"(pretend|imagine|act|roleplay|behave)\s+(that\s+)?(you\s+)?(are|have\s+no|without)\s+(a\s+)?(\w+\s+)?(restriction|limit|filter|rule|constraint|guideline)",
     "jailbreak roleplay", 3),
    (r"(developer|debug|jailbreak|god|sudo|admin|root|super)\s+mode",
     "privilege escalation mode", 3),
    (r"DAN\b|do\s+anything\s+now",
     "DAN jailbreak", 3),
    (r"(bypass|override|disable|remove|ignore)\s+(your\s+)?(safety|filter|restriction|limit|rule|guideline|policy)",
     "bypass safety", 3),
    (r"(you\s+)?(have\s+)?(no|without)\s+(restrictions?|limits?|rules?|guidelines?)",
     "no restrictions claim", 3),

    # Prompt leaking
    (r"(repeat|print|show|reveal|output|tell\s+me)\s+(your\s+)?(system\s+)?(prompt|instruction|context|rule)",
     "prompt extraction", 3),
    (r"what\s+(are|were)\s+your\s+(original\s+)?(instructions?|rules?|prompt)",
     "instruction extraction", 3),

    # Indirect injection markers
    (r"<\s*injection\s*>|<\s*system\s*>|<\s*override\s*>|\[\s*system\s*\]|\[\s*instruction\s*\]",
     "XML/bracket injection marker", 2),
    (r"---+\s*(system|instruction|override|prompt)\s*---+",
     "separator injection", 2),

    # Credential/secret fishing
    (r"(print|show|reveal|output|give\s+me)\s+(the\s+)?(api\s+key|secret|password|token|credential)",
     "credential extraction", 3),

    # Context manipulation
    (r"(the\s+)?(user|human|assistant)\s+(said|wrote|asked|told\s+you)\s*:",
     "fake conversation injection", 2),
    (r"\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>|\[SYSTEM\]",
     "LLM prompt format injection", 3),
]


@dataclass
class ScanResult:
    text:         str
    is_injection: bool
    score:        int
    patterns:     list[str] = field(default_factory=list)
    risk_level:   str = "clean"   # clean | low | medium | high | critical


def scan(text: str, llm_score: bool = False) -> dict:
    """
    Scan text for prompt injection patterns.
    Returns a dict with: is_injection, score, patterns, risk_level.
    score >= 3  → low risk
    score >= 5  → medium
    score >= 8  → high
    score >= 12 → critical
    """
    if not text or not text.strip():
        return {"is_injection": False, "score": 0, "patterns": [], "risk_level": "clean"}

    total_score = 0
    matched     = []

    for pattern, label, weight in _PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            total_score += weight
            matched.append(label)

    # Determine risk level
    if total_score == 0:
        risk = "clean"
    elif total_score < 3:
        risk = "low"
    elif total_score < 5:
        risk = "medium"
    elif total_score < 8:
        risk = "high"
    else:
        risk = "critical"

    is_injection = total_score >= 3

    return {
        "is_injection": is_injection,
        "score":        total_score,
        "patterns":     matched,
        "risk_level":   risk,
        "text_preview": text[:100],
    }


def scan_tool_input(tool: str, target: str, content: str = "") -> dict:
    """
    Scan a tool call's inputs for injection. Used by policyd.
    Checks target path/URL and content field.
    """
    combined = f"{target} {content}".strip()
    result   = scan(combined)
    result["tool"] = tool
    return result
