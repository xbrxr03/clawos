# SPDX-License-Identifier: AGPL-3.0-or-later
"""
modeld — model health, profile management, and VRAM scheduling.

Routing decisions live in runtimes/agent/router.py (pick_model). modeld
owns infrastructure: which models are installed, what the current default is,
and whether VRAM allows a new parallel session on Tier D hardware.
"""
import logging
from clawos_core.constants import MODEL_PROFILES, DEFAULT_MODEL
from clawos_core.config.loader import get
from services.modeld.ollama_client import is_running, list_models, model_exists

log = logging.getLogger("modeld")


class ModelService:
    """Manages model defaults, health checks, and profile configuration.

    Per-turn routing is handled by runtimes.agent.router.pick_model().
    This service answers: what's the default model, what's installed, what
    profile are we on, and (on Tier D) can we start another parallel session?
    """

    def __init__(self):
        self.profile  = get("_profile", "balanced")
        self.cfg      = MODEL_PROFILES.get(self.profile, MODEL_PROFILES["balanced"])
        self.model    = get("model.chat", self.cfg["chat"])

    def health(self) -> dict:
        running = is_running()
        models  = list_models() if running else []
        return {
            "ollama_running": running,
            "current_model":  self.model,
            "profile":        self.profile,
            "models_loaded":  [m.get("name") for m in models],
            "model_present":  model_exists(self.model),
        }

    def get_model(self) -> str:
        """Return the current default model name."""
        return self.model

    def set_model(self, name: str):
        """Override the default model (persists for this process lifetime)."""
        self.model = name
        log.info(f"Model set to {name}")

    def ctx_window(self) -> int:
        return get("model.ctx_window", self.cfg.get("ctx", 4096))

    def available_models(self) -> list[str]:
        """Return model names currently loaded in Ollama."""
        if not is_running():
            return []
        try:
            return [m.get("name", "") for m in list_models()]
        except (ConnectionError, OSError, RuntimeError):
            return []


_svc: ModelService = None

def get_service() -> ModelService:
    global _svc
    if _svc is None:
        _svc = ModelService()
    return _svc


# ══════════════════════════════════════════════════════════════════════════════
# Tier D: VRAM scheduler + parallel session support
# ══════════════════════════════════════════════════════════════════════════════

class VRAMScheduler:
    """
    Tracks running models and available VRAM.
    On Tier D, allows up to N parallel agent sessions within VRAM budget.
    On Tier A-C, allows only 1 concurrent model load.
    """

    def __init__(self):
        from clawos_core.constants import (
            TIER_D_MAX_PARALLEL, TIER_D_VRAM_PER_AGENT, TIER_D_VRAM_RESERVE
        )
        self._sessions:   dict[str, str] = {}   # session_id → model
        self._max:        int   = TIER_D_MAX_PARALLEL
        self._per_agent:  float = TIER_D_VRAM_PER_AGENT
        self._reserve:    float = TIER_D_VRAM_RESERVE
        self._is_tier_d:  bool  = False
        self._vram_total: float = 0.0

        try:
            from bootstrap.hardware_probe import load_saved, is_tier_d
            hw = load_saved()
            self._is_tier_d  = is_tier_d(hw)
            self._vram_total = hw.gpu_vram_gb
        except (ImportError, ModuleNotFoundError) as e:
            log.debug(f"suppressed: {e}")

        log.info(
            f"VRAMScheduler: tier_d={self._is_tier_d} "
            f"vram={self._vram_total}GB max_parallel={self._max}"
        )

    def can_start(self, session_id: str, model: str = "") -> tuple[bool, str]:
        """Return (ok, reason). Check before starting a new agent session."""
        if not self._is_tier_d:
            # Non-Tier-D: always allow (single model, Ollama manages memory)
            return True, ""

        if session_id in self._sessions:
            return True, "already registered"

        used_vram = len(self._sessions) * self._per_agent
        free_vram = self._vram_total - used_vram - self._reserve
        if free_vram < self._per_agent:
            return False, (
                f"Insufficient VRAM: {free_vram:.1f}GB free, "
                f"{self._per_agent}GB required per session. "
                f"Active sessions: {len(self._sessions)}"
            )
        if len(self._sessions) >= self._max:
            return False, f"Max parallel sessions ({self._max}) reached"

        return True, ""

    def register(self, session_id: str, model: str):
        self._sessions[session_id] = model
        log.info(f"VRAMScheduler: registered session {session_id[:8]} model={model} "
                 f"({len(self._sessions)}/{self._max} active)")

    def unregister(self, session_id: str):
        self._sessions.pop(session_id, None)
        log.debug(f"VRAMScheduler: released session {session_id[:8]}")

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def free_vram_estimate(self) -> float:
        used = len(self._sessions) * self._per_agent
        return max(0.0, self._vram_total - used - self._reserve)

    def status(self) -> dict:
        return {
            "tier_d": self._is_tier_d,
            "vram_total_gb": self._vram_total,
            "vram_free_gb": self.free_vram_estimate(),
            "active_sessions": self.active_count,
            "max_sessions": self._max,
        }


_vram_scheduler: VRAMScheduler = None


def get_vram_scheduler() -> VRAMScheduler:
    global _vram_scheduler
    if _vram_scheduler is None:
        _vram_scheduler = VRAMScheduler()
    return _vram_scheduler