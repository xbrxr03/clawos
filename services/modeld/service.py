"""modeld — model routing + profile management."""
import logging
from clawos_core.constants import MODEL_PROFILES, DEFAULT_MODEL
from clawos_core.config.loader import get
from services.modeld.ollama_client import is_running, list_models, model_exists

log = logging.getLogger("modeld")



# ── Task-aware routing ────────────────────────────────────────────────────────
TASK_ROUTING = {
    # basic tier — fast, no tools needed
    "greeting":    "qwen2.5:1.5b",
    "simple_qa":   "qwen2.5:1.5b",
    "acknowledge": "qwen2.5:1.5b",
    # standard tier — writing quality matters, no heavy tool use
    "write":       "qwen2.5:3b",
    "summarize":   "qwen2.5:3b",
    "draft":       "qwen2.5:3b",
    "explain":     "qwen2.5:3b",
    # full tier — default for everything with tools
    "chat":        "qwen2.5:7b",
    "code":        "qwen2.5:7b",
    "rag":         "qwen2.5:7b",
    "plan":        "qwen2.5:7b",
    "shell":       "qwen2.5:7b",
    "voice":       "qwen2.5:7b",
    # openclaw tier — only when OpenClaw gateway is routing
    "openclaw":    "kimi-k2.5:cloud",
}


def classify_task(user_input: str) -> str:
    """Classify task type for model routing. No LLM call — keyword heuristics only."""
    text = user_input.lower().strip()
    n = len(text.split())

    # Greetings / acks — never need a big model
    if n <= 5 and any(text.startswith(w) for w in
                      ("hi", "hello", "hey", "ok", "okay", "thanks",
                       "sure", "yes", "no", "got it", "understood")):
        return "greeting"

    # Writing / summarization triggers
    if any(w in text for w in ("write", "draft", "compose", "summarize",
                                "summarise", "rephrase", "explain", "describe")):
        return "write"
    if any(w in text for w in ("summary", "tldr", "brief", "overview", "condense")):
        return "summarize"

    # Everything else → full tier (tools, code, files, shell)
    return "chat"

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


    def route(self, task_type: str = "chat") -> str:
        """Pick the best available model for this task type."""
        preferred = TASK_ROUTING.get(task_type, "qwen2.5:7b")
        try:
            available = [m.get("name", "") for m in list_models()]
        except Exception:
            available = []
        if preferred in available:
            return preferred
        # Fallback chain: go up one tier if preferred not available
        fallback_chain = ["qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b"]
        for model in fallback_chain:
            if model in available:
                return model
        return self.model  # last resort: current default


_svc: ModelService = None

def get_service() -> ModelService:
    global _svc
    if _svc is None:
        _svc = ModelService()
    return _svc
