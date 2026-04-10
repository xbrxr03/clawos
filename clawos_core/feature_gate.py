# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Feature Gate — open-core tier enforcement.

The @require_premium decorator is published open-source (AGPL is fine for this).
The license server (Supabase) is a SaaS component — no AGPL requirement there.

Usage:
    from clawos_core.feature_gate import FeatureGate, require_premium

    # Check programmatically
    gate = FeatureGate()
    if gate.is_premium():
        ...

    # Decorator on functions
    @require_premium
    def use_elevenlabs():
        ...

    # Decorator on async functions
    @require_premium_async
    async def use_nexus_brain():
        ...

Free tier: core agent, Ollama, basic workflows, Piper TTS, basic RAG, WhatsApp
Premium ($10 once): all workflows, cloud models, ElevenLabs, Nexus Brain,
                    A2A, skill publishing, browser control, proactive intelligence
"""
import functools
import logging
from typing import Any, Callable, TypeVar

log = logging.getLogger("feature_gate")

F = TypeVar("F", bound=Callable[..., Any])


class FeatureGate:
    """
    Checks tier and feature availability.
    Caches license state — does not call Supabase on every check.
    """

    def __init__(self):
        self._tier: str | None = None
        self._last_check: float = 0.0
        # Cache tier for 5 minutes
        self._cache_ttl = 300

    def _refresh_tier(self) -> str:
        import time
        now = time.time()
        if self._tier is None or (now - self._last_check) > self._cache_ttl:
            try:
                from clawos_core.license import get_license_manager, PREMIUM_FEATURES, PRO_FEATURES
                mgr = get_license_manager()
                self._tier = mgr.get_tier()
            except Exception:
                self._tier = "free"
            self._last_check = now
        return self._tier

    def get_tier(self) -> str:
        """Return 'free' | 'premium' | 'pro'."""
        return self._refresh_tier()

    def is_free(self) -> bool:
        return True  # Free tier always available

    def is_premium(self) -> bool:
        return self._refresh_tier() in ("premium", "pro")

    def is_pro(self) -> bool:
        return self._refresh_tier() == "pro"

    def has_feature(self, feature: str) -> bool:
        """Check if a specific feature is available in the current tier."""
        try:
            from clawos_core.license import FREE_FEATURES, PREMIUM_FEATURES, PRO_FEATURES
            tier = self._refresh_tier()
            if tier == "pro":
                return feature in PRO_FEATURES
            elif tier == "premium":
                return feature in PREMIUM_FEATURES
            return feature in FREE_FEATURES
        except Exception:
            return False

    def require(self, feature: str) -> None:
        """Raise FeatureNotAvailable if feature not in current tier."""
        if not self.has_feature(feature):
            tier = self._refresh_tier()
            raise FeatureNotAvailable(
                feature=feature,
                current_tier=tier,
                message=_upgrade_message(feature, tier),
            )

    def upgrade_url(self) -> str:
        return "https://clawos.dev/#premium"


class FeatureNotAvailable(Exception):
    """Raised when a premium/pro feature is accessed without the right tier."""
    def __init__(self, feature: str, current_tier: str, message: str = ""):
        self.feature = feature
        self.current_tier = current_tier
        super().__init__(message or f"Feature '{feature}' requires Premium. "
                                     f"Current tier: {current_tier}. "
                                     f"Upgrade at https://clawos.dev/#premium")


def _upgrade_message(feature: str, tier: str) -> str:
    feature_labels = {
        "all_workflows":           "All 29 workflows",
        "cloud_models":            "Cloud AI models (OpenRouter, kimi-k2)",
        "voice_elevenlabs":        "ElevenLabs premium TTS",
        "nexus_brain":             "Nexus 3D knowledge brain",
        "browser_control":         "Browser control",
        "proactive_intelligence":  "Proactive ambient intelligence",
        "a2a_federation":          "A2A multi-agent federation",
        "skill_publishing":        "Publish skills to ClawHub",
        "rag_advanced":            "Advanced RAG + GraphRAG",
    }
    label = feature_labels.get(feature, feature)
    return (
        f"'{label}' is a Premium feature. You're on the {tier} tier.\n"
        f"  Upgrade at https://clawos.dev/#premium ($10 once, yours forever)"
    )


# ── Decorators ─────────────────────────────────────────────────────────────────

def require_premium(fn: F) -> F:
    """
    Decorator: raises FeatureNotAvailable if caller is not on premium/pro tier.
    Works on sync functions.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        gate = FeatureGate()
        if not gate.is_premium():
            raise FeatureNotAvailable(
                feature=fn.__name__,
                current_tier=gate.get_tier(),
                message=f"'{fn.__name__}' requires Premium tier. "
                        f"Upgrade at https://clawos.dev/#premium"
            )
        return fn(*args, **kwargs)
    return wrapper  # type: ignore


def require_premium_async(fn: F) -> F:
    """
    Decorator: raises FeatureNotAvailable if caller is not on premium/pro tier.
    Works on async functions.
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        gate = FeatureGate()
        if not gate.is_premium():
            raise FeatureNotAvailable(
                feature=fn.__name__,
                current_tier=gate.get_tier(),
                message=f"'{fn.__name__}' requires Premium tier. "
                        f"Upgrade at https://clawos.dev/#premium"
            )
        return await fn(*args, **kwargs)
    return wrapper  # type: ignore


def gate_feature(feature_name: str):
    """
    Decorator factory: gate a specific named feature.
    Usage:
        @gate_feature("nexus_brain")
        def build_brain():
            ...
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            FeatureGate().require(feature_name)
            return fn(*args, **kwargs)
        return wrapper  # type: ignore
    return decorator


# ── Singleton ──────────────────────────────────────────────────────────────────
_gate: FeatureGate | None = None


def get_gate() -> FeatureGate:
    global _gate
    if _gate is None:
        _gate = FeatureGate()
    return _gate


def is_premium() -> bool:
    """Quick check — no class needed."""
    return get_gate().is_premium()


def is_pro() -> bool:
    """Quick check."""
    return get_gate().is_pro()
