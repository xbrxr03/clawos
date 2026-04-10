# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Kizuna — Significance Filter.
Decides whether agent output is worth adding to the knowledge graph.

Strategy: only add content that represents durable new knowledge —
not task confirmations, status messages, or transient outputs.

Two-pass approach:
  1. Fast heuristic filter (no LLM) — rejects obvious non-knowledge
  2. LLM significance scorer — rates 0.0–1.0, threshold 0.65
"""
import logging
import re

log = logging.getLogger("braind.significance")

# Minimum score to add to the brain
SIGNIFICANCE_THRESHOLD = 0.65

# Heuristic: minimum content length worth analyzing
MIN_CHARS = 80

# Patterns that indicate low-significance agent output
LOW_SIGNIFICANCE_PATTERNS = [
    r"^(ok|done|completed|finished|success|error|failed|yes|no|thanks?)[\.\!]?$",
    r"^\[ok\]",
    r"^\[error\]",
    r"^\[denied\]",
    r"^task (completed|failed|running|queued)",
    r"^workflow (started|completed|failed)",
    r"^\d+ (files?|items?) (processed|found|deleted|moved)",
    r"^(approve|deny|skip|cancel)",
    r"approval (required|granted|denied)",
    r"written \d+ chars",
    r"(screenshot|file) saved",
]

_LOW_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in LOW_SIGNIFICANCE_PATTERNS]

# Patterns that indicate HIGH significance — always add
HIGH_SIGNIFICANCE_PATTERNS = [
    r"(discovered|found|learned|identified|realized|insight|important|key fact)",
    r"(definition|concept|principle|theory|framework|pattern)",
    r"(research|analysis|summary|report|findings)",
    r"(relationship between|connected to|depends on|caused by|results in)",
    r"(architecture|design|decision|trade-off|approach)",
]

_HIGH_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in HIGH_SIGNIFICANCE_PATTERNS]


def is_significant(text: str, context: dict | None = None) -> tuple[bool, float, str]:
    """
    Determine if text is worth adding to the Kizuna.
    Returns (should_add: bool, score: float, reason: str)
    """
    if not text or len(text.strip()) < MIN_CHARS:
        return False, 0.0, "too short"

    text_stripped = text.strip()

    # Fast reject: obvious low-significance patterns
    for pattern in _LOW_PATTERNS_COMPILED:
        if pattern.match(text_stripped):
            return False, 0.1, f"low-significance pattern: {pattern.pattern[:30]}"

    # Fast accept: obvious high-significance patterns
    high_count = sum(1 for p in _HIGH_PATTERNS_COMPILED if p.search(text_stripped))
    if high_count >= 2:
        return True, 0.9, f"high-significance patterns detected ({high_count})"

    # Word count heuristic — longer structured output more likely significant
    words = len(text_stripped.split())
    if words > 200:
        # Long structured text — try LLM scoring
        score = _llm_score(text_stripped, context)
        if score >= SIGNIFICANCE_THRESHOLD:
            return True, score, "LLM score above threshold"
        return False, score, f"LLM score {score:.2f} below threshold {SIGNIFICANCE_THRESHOLD}"

    elif words > 50:
        # Medium text — heuristic only
        score = _heuristic_score(text_stripped)
        if score >= SIGNIFICANCE_THRESHOLD:
            return True, score, "heuristic score above threshold"
        return False, score, f"heuristic score {score:.2f}"

    return False, 0.3, "too short for meaningful extraction"


def _heuristic_score(text: str) -> float:
    """Score text 0.0–1.0 based on structural indicators of knowledge density."""
    score = 0.3  # baseline

    # Has multiple sentences → more likely meaningful
    sentences = len(re.findall(r'[.!?]+', text))
    if sentences >= 3:
        score += 0.1
    if sentences >= 6:
        score += 0.1

    # Has named entities (capitalized words that aren't sentence starts)
    entities = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
    if len(entities) >= 3:
        score += 0.1

    # Contains technical terms, URLs, or code references
    if re.search(r'(https?://|`\w+`|\bAPI\b|\bSQL\b|\bJSON\b|function|class|method)', text):
        score += 0.1

    # Has structure (bullet points, numbered lists, headers)
    if re.search(r'(^[-*•]\s|\d+\.\s|^#{1,3}\s)', text, re.MULTILINE):
        score += 0.1

    # High-significance keywords
    for p in _HIGH_PATTERNS_COMPILED:
        if p.search(text):
            score += 0.05

    return min(score, 1.0)


def _llm_score(text: str, context: dict | None = None) -> float:
    """
    Use the local LLM to score significance.
    Falls back to heuristic if LLM unavailable.
    Returns 0.0–1.0.
    """
    try:
        import requests
        from clawos_core.config import get

        model = get("model.chat", "qwen2.5:7b")
        host = get("model.host", "http://localhost:11434")

        prompt = (
            f"Rate how worth remembering this text is on a scale of 0.0 to 1.0.\n"
            f"High score (>0.7): new facts, insights, concepts, analysis, research findings.\n"
            f"Low score (<0.4): task confirmations, status updates, file paths, numbers only.\n\n"
            f"Text:\n{text[:800]}\n\n"
            f"Respond with ONLY a number between 0.0 and 1.0. Nothing else."
        )

        response = requests.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": 8}},
            timeout=10,
        )
        if response.status_code == 200:
            raw = response.json().get("response", "0.5").strip()
            # Extract first number from response
            match = re.search(r'\d+\.?\d*', raw)
            if match:
                score = float(match.group())
                return min(max(score, 0.0), 1.0)
    except Exception as e:
        log.debug(f"LLM significance score failed: {e}")

    return _heuristic_score(text)


def filter_for_brain(items: list[dict]) -> list[dict]:
    """
    Filter a list of {content, source, ...} dicts.
    Returns only items that pass the significance threshold.
    """
    significant = []
    for item in items:
        content = item.get("content", item.get("text", ""))
        should_add, score, reason = is_significant(content)
        if should_add:
            item["_significance_score"] = score
            item["_significance_reason"] = reason
            significant.append(item)
        else:
            log.debug(f"Filtered out: score={score:.2f} reason={reason} text={content[:50]}")
    return significant
