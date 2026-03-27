"""WizardState — persisted across all wizard screens."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from clawos_core.constants import CONFIG_DIR

STATE_FILE = CONFIG_DIR / "wizard_state.json"


@dataclass
class WizardState:
    # Hardware
    hw_tier:        str   = "B"
    ram_gb:         float = 16.0
    gpu_vram_gb:    float = 0.0
    has_mic:        bool  = True

    # Profile
    profile:        str   = "balanced"

    # Runtime choice
    runtime:        str   = "core"      # core | openclaw | both

    # Workspace
    workspace_id:   str   = "nexus_default"

    # Voice
    voice_enabled:  bool  = True
    voice_mode:     str   = "push_to_talk"

    # Model — qwen2.5:7b is the confirmed default (gemma3 removed)
    model:          str   = "qwen2.5:7b"
    openclaw_model: str   = "qwen2.5:7b"
    model_pulled:   bool  = False

    # WhatsApp
    whatsapp_enabled: bool = False
    whatsapp_number:  str  = ""

    # Policy
    policy_mode:    str   = "recommended"

    # Wizard progress
    completed:      bool  = False
    screens_done:   list  = field(default_factory=list)

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> "WizardState":
        if STATE_FILE.exists():
            try:
                d = json.loads(STATE_FILE.read_text())
                return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        return cls()

    def mark_done(self, screen: str):
        if screen not in self.screens_done:
            self.screens_done.append(screen)
        self.save()
