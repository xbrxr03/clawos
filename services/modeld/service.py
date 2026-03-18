"""modeld — model routing + profile management."""
import logging
from clawos_core.constants import MODEL_PROFILES, DEFAULT_MODEL
from clawos_core.config.loader import get
from services.modeld.ollama_client import is_running, list_models, model_exists

log = logging.getLogger("modeld")


class ModelService:
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
        return self.model

    def set_model(self, name: str):
        self.model = name
        log.info(f"Model set to {name}")

    def ctx_window(self) -> int:
        return get("model.ctx_window", self.cfg.get("ctx", 4096))


_svc: ModelService = None

def get_service() -> ModelService:
    global _svc
    if _svc is None:
        _svc = ModelService()
    return _svc
