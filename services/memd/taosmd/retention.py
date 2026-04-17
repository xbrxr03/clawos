# SPDX-License-Identifier: AGPL-3.0-or-later
"""
retention — Ebbinghaus decay scoring for memory entries.

Pure math, zero external dependencies.
Tiers: HOT ≥ 0.7, WARM ≥ 0.4, COLD ≥ 0.15, EVICTABLE < 0.15
"""
from __future__ import annotations

import math
import time
from enum import Enum
from typing import Sequence


class RetentionTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    EVICTABLE = "evictable"


# Stability factor — how many days until retention halves without re-access
_BASE_STABILITY_DAYS = 1.0


def retention_score(
    created_at: float,
    access_times: Sequence[float],
    salience: float = 0.5,
    now: float | None = None,
) -> float:
    """
    Compute Ebbinghaus-inspired retention score in [0.0, 1.0].

    Args:
        created_at:   Unix timestamp of first write.
        access_times: Sequence of Unix timestamps of subsequent recalls.
        salience:     0.0–1.0 importance hint (higher = decays slower).
        now:          Override for current time (useful in tests).

    Returns:
        Retention score in [0.0, 1.0].
    """
    if now is None:
        now = time.time()

    # Stability grows with each access (spaced repetition effect)
    stability = _BASE_STABILITY_DAYS * (1.0 + salience)
    for t in sorted(access_times):
        interval_days = max(0.0, (t - created_at) / 86400.0)
        # Stability increases proportionally to the retrieval interval
        stability = stability + interval_days * 0.1 + 0.5

    # Elapsed since last access (or creation if never accessed)
    last_access = max(access_times, default=created_at)
    elapsed_days = max(0.0, (now - last_access) / 86400.0)

    # Ebbinghaus: R = e^(-elapsed / stability)
    score = math.exp(-elapsed_days / max(stability, 0.001))
    return max(0.0, min(1.0, score))


def retention_tier(score: float) -> RetentionTier:
    if score >= 0.7:
        return RetentionTier.HOT
    elif score >= 0.4:
        return RetentionTier.WARM
    elif score >= 0.15:
        return RetentionTier.COLD
    else:
        return RetentionTier.EVICTABLE


def should_evict(
    created_at: float,
    access_times: Sequence[float],
    salience: float = 0.5,
) -> bool:
    score = retention_score(created_at, access_times, salience)
    return retention_tier(score) == RetentionTier.EVICTABLE
