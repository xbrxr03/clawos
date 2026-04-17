# SPDX-License-Identifier: AGPL-3.0-or-later
"""
intent_classifier — 7 intent types, pure regex, zero LLM calls.

Routes queries to the right memory backend:
  FACTUAL     → Temporal Knowledge Graph
  RECENT      → Archive FTS (last N days)
  TECHNICAL   → Vector store (semantic similarity)
  EXPLORATORY → Vector store (broad)
  TIMELINE    → Archive session catalog / history
  PREFERENCE  → KG preference triples
  IDENTITY    → KG is_a / has triples
"""
from __future__ import annotations

import re
from enum import Enum


class QueryIntent(str, Enum):
    FACTUAL = "factual"
    RECENT = "recent"
    TECHNICAL = "technical"
    EXPLORATORY = "exploratory"
    TIMELINE = "timeline"
    PREFERENCE = "preference"
    IDENTITY = "identity"


# Pattern sets — more specific patterns first
_PATTERNS: list[tuple[QueryIntent, list[re.Pattern]]] = [
    (QueryIntent.RECENT, [
        re.compile(r'\b(yesterday|today|last night|this morning|this week|recently|just now|earlier)\b', re.I),
        re.compile(r'\b(what (was|were|did) (i|we|nexus))\b', re.I),
        re.compile(r'\blast\s+(few\s+)?(hour|day|week|session|conversation)\b', re.I),
        re.compile(r'\b(previous|prior)\s+(session|conversation|chat|task)\b', re.I),
    ]),
    (QueryIntent.TIMELINE, [
        re.compile(r'\b(when (did|was|were|have))\b', re.I),
        re.compile(r'\b(history|timeline|log|audit|track)\b', re.I),
        re.compile(r'\b(first time|last time|how long ago)\b', re.I),
    ]),
    (QueryIntent.PREFERENCE, [
        re.compile(r'\b(prefer|like|dislike|favorite|favourite|want|hate)\b', re.I),
        re.compile(r'\b(my (setting|preference|option|choice|default))\b', re.I),
    ]),
    (QueryIntent.IDENTITY, [
        re.compile(r'\b(who (is|am|are)|what (is|are) (my|the|your))\b', re.I),
        re.compile(r'\b(identity|persona|role|type|kind of)\b', re.I),
    ]),
    (QueryIntent.TECHNICAL, [
        re.compile(r'\b(how (to|do|does|can)|implement|configure|setup|install|debug|error|fix|code)\b', re.I),
        re.compile(r'\b(function|method|class|module|api|endpoint|command|syntax)\b', re.I),
        re.compile(r'\b(what (does|is the|are the).*(do|mean|return|accept))\b', re.I),
    ]),
    (QueryIntent.FACTUAL, [
        re.compile(r'\b(what is|what are|who is|where is|which)\b', re.I),
        re.compile(r'\b(tell me about|explain|describe|define)\b', re.I),
    ]),
]

_DEFAULT_INTENT = QueryIntent.EXPLORATORY


def classify_intent(query: str) -> QueryIntent:
    """
    Classify a retrieval query into one of 7 intent types.
    Pure regex — zero LLM calls. O(N) where N = total pattern count (~20).
    """
    q = query.strip()
    for intent, patterns in _PATTERNS:
        if any(p.search(q) for p in patterns):
            return intent
    return _DEFAULT_INTENT


def route_to_backends(intent: QueryIntent) -> list[str]:
    """
    Return the ordered list of backend names to query for a given intent.
    Backends: 'kg', 'archive', 'vector'
    """
    return {
        QueryIntent.FACTUAL:     ["kg", "vector"],
        QueryIntent.RECENT:      ["archive", "kg"],
        QueryIntent.TECHNICAL:   ["vector", "archive"],
        QueryIntent.EXPLORATORY: ["vector", "kg", "archive"],
        QueryIntent.TIMELINE:    ["archive"],
        QueryIntent.PREFERENCE:  ["kg"],
        QueryIntent.IDENTITY:    ["kg"],
    }[intent]
