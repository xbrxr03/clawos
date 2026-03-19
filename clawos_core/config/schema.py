"""Pydantic models for config validation."""
from typing import Optional
try:
    from pydantic import BaseModel
    class ModelConfig(BaseModel):
        provider: str = "ollama"
        chat: str = "qwen2.5:7b"
        embed: str = "nomic-embed-text"
        host: str = "http://localhost:11434"
        ctx_window: int = 4096
        temperature: float = 0.3
        max_loaded: int = 1
        keep_alive: str = "5m"

    class VoiceConfig(BaseModel):
        enabled: bool = False
        mode: str = "push_to_talk"
        stt_model: str = "base"
        record_rate: int = 44100
        silence_rms: int = 300
        silence_secs: float = 1.8

    class PolicyConfig(BaseModel):
        mode: str = "recommended"
        approval_timeout_s: int = 120
        default_grants: list = ["fs.read","fs.write","fs.list","web.search","memory.read","memory.write"]

    class ClawOSConfig(BaseModel):
        model: ModelConfig = ModelConfig()
        voice: VoiceConfig = VoiceConfig()
        policy: PolicyConfig = PolicyConfig()
        _profile: str = "balanced"

except ImportError:
    # pydantic not available — use plain dicts
    class ClawOSConfig:
        pass
