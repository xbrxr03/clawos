"""
ClawOS hardware probe.
Detects RAM, GPU, CPU cores, audio devices, disk space.
Returns a HardwareProfile used by profile_selector.py.
"""
import json
import shutil
from dataclasses import dataclass, asdict

from clawos_core.platform import (
    audio_info,
    disk_snapshot_gb,
    gpu_info,
    ram_snapshot_gb,
)


@dataclass
class HardwareProfile:
    ram_gb:       float = 0.0
    cpu_cores:    int   = 0
    gpu_vram_gb:  float = 0.0
    gpu_name:     str   = "none"
    disk_free_gb: float = 0.0
    has_mic:      bool  = False
    audio_rate:   int   = 44100
    audio_device: int   = 0          # pipewire/alsa card index
    tier:         str   = "A"        # A=8GB B=16GB C=32GB+
    ollama_ok:    bool  = False
    node_ok:      bool  = False


def _ram_gb() -> float:
    return ram_snapshot_gb().get("total_gb", 0.0)


def _cpu_cores() -> int:
    try:
        import os
        return os.cpu_count() or 4
    except Exception:
        return 4


def _disk_free_gb(path: str = "/") -> float:
    try:
        return disk_snapshot_gb(path).get("free_gb", 0.0)
    except Exception:
        return 0.0


def _gpu_info() -> tuple[str, float]:
    return gpu_info()


def _audio_info() -> tuple[bool, int, int]:
    return audio_info()


def _check_ollama() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _check_node() -> bool:
    return shutil.which("node") is not None


def probe() -> HardwareProfile:
    ram   = _ram_gb()
    cores = _cpu_cores()
    disk  = _disk_free_gb()
    gpu_name, vram = _gpu_info()
    has_mic, rate, dev = _audio_info()

    # Tier D: GPU VRAM >= 10GB (gaming/workstation with big GPU)
    if vram >= 10.0:
        tier = "D"
    elif ram >= 30:
        tier = "C"
    elif ram >= 14:
        tier = "B"
    else:
        tier = "A"

    return HardwareProfile(
        ram_gb       = ram,
        cpu_cores    = cores,
        gpu_vram_gb  = vram,
        gpu_name     = gpu_name,
        disk_free_gb = disk,
        has_mic      = has_mic,
        audio_rate   = rate,
        audio_device = dev,
        tier         = tier,
        ollama_ok    = _check_ollama(),
        node_ok      = _check_node(),
    )


def probe_and_save() -> HardwareProfile:
    import os
    from clawos_core.constants import HARDWARE_JSON
    HARDWARE_JSON.parent.mkdir(parents=True, exist_ok=True)
    hw = probe()
    HARDWARE_JSON.write_text(json.dumps(asdict(hw), indent=2))
    # Export tier so wizard and install.sh can read it
    os.environ["CLAWOS_DETECTED_TIER"] = hw.tier
    return hw


def load_saved() -> HardwareProfile:
    from clawos_core.constants import HARDWARE_JSON
    if HARDWARE_JSON.exists():
        d = json.loads(HARDWARE_JSON.read_text())
        return HardwareProfile(**d)
    return probe()


def is_tier_d(hw: HardwareProfile = None) -> bool:
    """Tier D: GPU VRAM >= 10GB."""
    if hw is None:
        hw = load_saved()
    return hw.gpu_vram_gb >= 10.0


def get_tier(hw: HardwareProfile = None) -> str:
    if hw is None:
        hw = load_saved()
    if hw.gpu_vram_gb >= 10.0:
        return "D"
    if hw.ram_gb >= 30:
        return "C"
    if hw.ram_gb >= 14:
        return "B"
    return "A"
