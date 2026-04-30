# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Token-budgeted context assembly.

Trims memory / RAG / skills / learned-context blocks to fit a token budget
while preserving priority order:

  1. PINNED.md           (always; durable user facts)
  2. LEARNED.md          (ACE outputs; recent learnings)
  3. RAG documents
  4. Semantic recall
  5. Skills

Tokens are estimated at 4 chars/token — accurate enough for budgeting since
we leave a safety margin.
"""
from __future__ import annotations

# Total budget for all dynamic context blocks per turn (excludes system
# prompt and recent conversation, which the runtime budgets separately).
DEFAULT_BUDGET_TOKENS = 2000


def _est_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def fit_blocks(
    blocks: list[tuple[str, str]],
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> list[tuple[str, str]]:
    """
    Trim a priority-ordered list of (label, text) blocks to fit `budget_tokens`.
    Higher-priority blocks come first; lower-priority blocks may be truncated
    or dropped entirely to fit.
    """
    out: list[tuple[str, str]] = []
    remaining = budget_tokens
    for label, text in blocks:
        if not text:
            continue
        cost = _est_tokens(text)
        if cost <= remaining:
            out.append((label, text))
            remaining -= cost
            continue
        # Truncate to remaining budget, leave a small marker
        if remaining > 50:
            chars = max(0, (remaining - 10) * 4)
            truncated = text[:chars] + "\n…[trimmed]"
            out.append((label, truncated))
            remaining = 0
        else:
            # Out of budget — drop the rest
            break
    return out
