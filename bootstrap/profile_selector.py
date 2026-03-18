"""
Auto-select ClawOS profile from hardware tier.
Can be overridden by user during first-run wizard.
"""
from bootstrap.hardware_probe import HardwareProfile


def select(hw: HardwareProfile) -> str:
    """Return profile name: lowram | balanced | performance."""
    if hw.ram_gb >= 32 or hw.gpu_vram_gb >= 8:
        return "performance"
    elif hw.ram_gb >= 14:
        return "balanced"
    else:
        return "lowram"


def openclaw_feasible(hw: HardwareProfile) -> bool:
    """OpenClaw needs Node.js + enough RAM for model + Node overhead."""
    return hw.ram_gb >= 14


def voice_feasible(hw: HardwareProfile) -> bool:
    return hw.has_mic and hw.ram_gb >= 8


def recommended_model(hw: HardwareProfile) -> str:
    if hw.ram_gb >= 32 or hw.gpu_vram_gb >= 8:
        return "gemma3:12b"
    return "gemma3:4b"


def recommended_openclaw_model(hw: HardwareProfile) -> str:
    """OpenClaw needs tool-calling models — gemma3 doesn't work."""
    if hw.ram_gb >= 32:
        return "qwen2.5:14b"
    return "qwen2.5:7b"


def summary(hw: HardwareProfile) -> str:
    profile = select(hw)
    lines = [
        f"  RAM:    {hw.ram_gb}GB → profile: {profile}",
        f"  CPU:    {hw.cpu_cores} cores",
        f"  GPU:    {hw.gpu_name} ({hw.gpu_vram_gb}GB VRAM)" if hw.gpu_vram_gb > 0
               else f"  GPU:    none (CPU inference)",
        f"  Disk:   {hw.disk_free_gb}GB free",
        f"  Audio:  {'mic detected' if hw.has_mic else 'no mic'}",
        f"  Ollama: {'running' if hw.ollama_ok else 'not running'}",
        f"  Tier:   {hw.tier}",
    ]
    return "\n".join(lines)
