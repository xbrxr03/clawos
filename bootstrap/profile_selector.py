# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Auto-select ClawOS profile from hardware tier.
Can be overridden by user during first-run wizard.
gemma3 models have been removed — qwen2.5:7b is the confirmed default.
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


def recommended_runtimes(tier: str) -> list[str]:
    """Return the recommended runtime list for a given hardware tier.
    Tier A keeps the lightweight stack (Nexus + PicoClaw); everything B+ gets
    the full stack including OpenClaw for its skill library.
    """
    if tier == "A":
        return ["nexus", "picoclaw"]
    return ["nexus", "picoclaw", "openclaw"]


def select_with_bundle(hw: HardwareProfile) -> dict:
    """
    Return {"profile": str, "runtimes": list, "tier": str}.
    Used by install.sh and the web setup flow.
    """
    profile = select(hw)
    tier    = hw.tier
    return {"profile": profile, "runtimes": recommended_runtimes(tier), "tier": tier}


def openclaw_feasible(hw: HardwareProfile) -> bool:
    """OpenClaw needs Node.js + enough RAM for model + Node overhead."""
    return hw.ram_gb >= 14


def voice_feasible(hw: HardwareProfile) -> bool:
    return hw.has_mic and hw.ram_gb >= 8


def recommended_model(hw: HardwareProfile) -> str:
    """
    qwen2.5:7b confirmed default across Tier B and C.
    Tier A (<12GB) gets qwen2.5:3b to avoid OOM.
    gemma3 models removed from project entirely.
    """
    if hw.ram_gb < 12:
        return "qwen2.5:3b"
    return "qwen2.5:7b"


def recommended_openclaw_model(hw: HardwareProfile) -> str:
    """OpenClaw needs tool-calling models — gemma3 doesn't support tool calls."""
    return "qwen2.5:7b"  # 7b is the default — upgrade to kimi-k2.5:cloud via ollama signin


def summary(hw: HardwareProfile) -> str:
    profile = select(hw)
    lines = [
        f"  RAM:    {hw.ram_gb}GB → profile: {profile}",
        f"  CPU:    {hw.cpu_cores} cores",
        (f"  GPU:    {hw.gpu_name} ({hw.gpu_vram_gb}GB VRAM)" if hw.gpu_vram_gb > 0
         else "  GPU:    none (CPU inference)"),
        f"  Disk:   {hw.disk_free_gb}GB free",
        f"  Audio:  {'mic detected' if hw.has_mic else 'no mic'}",
        f"  Ollama: {'running' if hw.ollama_ok else 'not running'}",
        f"  Tier:   {hw.tier}",
    ]
    return "\n".join(lines)
