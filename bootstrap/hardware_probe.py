# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS hardware probe.
Detects RAM, GPU, CPU, NPU, audio, disk.

Provides:
  - HardwareProfile — legacy ClawOS dataclass (tier A/B/C/D)
  - profile_id      — taOS-style tier string (arm-npu-16gb, x86-cuda-12gb, …)
  - detect_*        — fine-grained sub-detectors (NPU, GPU, CPU, disk, OS)

Hardware detection logic for GPU/NPU/ARM adapted from tinyagentos/hardware.py
(AGPL-3.0, https://github.com/jaylfc/tinyagentos).
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from clawos_core.platform import (
    audio_info,
    disk_snapshot_gb,
    gpu_info,
    ram_snapshot_gb,
)


# ── Legacy ClawOS HardwareProfile (unchanged API) ──────────────────────────────

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

    # ── taOS-style fields (added) ─────────────────────────────────────────────
    cpu_arch:     str   = ""         # aarch64 | x86_64 | arm64 | …
    cpu_soc:      str   = ""         # rk3588 | bcm2711 | m4 | …
    npu_type:     str   = "none"     # rknpu | hailo | coral | hailo10h | axera | none
    npu_tops:     int   = 0
    npu_cores:    int   = 0
    gpu_type:     str   = "none"     # nvidia | amd | mali | apple | none
    gpu_cuda:     bool  = False
    gpu_rocm:     bool  = False
    disk_total_gb: float = 0.0
    disk_type:    str   = ""         # nvme | emmc | ssd | hdd | sd
    os_distro:    str   = ""
    os_version:   str   = ""
    is_arm:       bool  = False

    @property
    def profile_id(self) -> str:
        """taOS-style tier identifier: {arch}-{accel}-{ram}gb.

        Examples: arm-npu-16gb, x86-cuda-12gb, arm-cpu-8gb, x86-cpu-32gb
        """
        arch = "arm" if self.is_arm else "x86"
        if self.npu_type != "none":
            accel = "npu"
        elif self.gpu_cuda:
            accel = "cuda"
        elif self.gpu_rocm:
            accel = "rocm"
        elif self.gpu_type == "apple":
            # Apple Silicon: unified memory — use total RAM as VRAM
            accel = "apple"
        else:
            accel = "cpu"
        ram_gb = max(1, int(self.ram_gb))
        return f"{arch}-{accel}-{ram_gb}gb"


# ── taOS-pattern sub-detectors ─────────────────────────────────────────────────

def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def _path_exists_safe(p: Path) -> bool:
    """Path.exists() can raise PermissionError on /sys/kernel/debug paths
    when running unprivileged. Treat denied as 'not present'."""
    try:
        return p.exists()
    except (PermissionError, OSError):
        return False


def _detect_cpu_arch() -> tuple[str, str, bool]:
    """Returns (arch, soc, is_arm)."""
    arch = platform.machine()
    is_arm = arch in ("aarch64", "armv7l", "arm64")
    soc = ""
    try:
        dt_model = Path("/proc/device-tree/model")
        if dt_model.exists():
            soc_str = dt_model.read_text(errors="replace").strip("\x00").lower()
            for name in ("rk3588", "rk3576", "rk3568", "bcm2712", "bcm2711"):
                if name in soc_str:
                    soc = name
                    break
    except OSError:
        pass
    # Apple Silicon
    if platform.system() == "Darwin" and arch == "arm64":
        try:
            chip = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            for m in ("m5", "m4", "m3", "m2", "m1"):
                if m in chip.lower():
                    soc = m
                    break
            if not soc:
                soc = "apple-silicon"
        except Exception:
            pass
    return arch, soc, is_arm


def _detect_npu() -> tuple[str, int, int]:
    """Returns (npu_type, tops, cores). npu_type='none' if nothing found."""
    # Rockchip RKNPU
    rknpu_paths = [
        Path("/dev/rknpu"),
        Path("/sys/kernel/debug/rknpu/load"),
        Path("/sys/class/devfreq/fdab0000.npu"),
    ]
    if any(_path_exists_safe(p) for p in rknpu_paths):
        try:
            model = Path("/proc/device-tree/model").read_text(errors="replace").lower()
            if "rk3588" in model:
                return "rknpu", 6, 3
            if "rk3576" in model:
                return "rknpu", 6, 1
            if "rk3568" in model:
                return "rknpu", 1, 1
        except OSError:
            pass
        # Parse core count from NPU load file
        cores = 1
        try:
            import re
            load_text = Path("/sys/kernel/debug/rknpu/load").read_text()
            core_matches = re.findall(r"Core(\d+):", load_text)
            if core_matches:
                cores = len(core_matches)
        except (OSError, PermissionError):
            pass
        tops = 6 if cores >= 3 else 1
        return "rknpu", tops, cores

    # Hailo — distinguish 10H (40 TOPS, LLM capable) from 8L (13 TOPS)
    for p in Path("/dev").glob("hailo*"):
        hailo_info = _run(["lspci", "-d", "1e60:"])
        if "10h" in hailo_info.lower() or "hailo-10" in hailo_info.lower():
            return "hailo10h", 40, 1
        return "hailo", 13, 1

    # Axera AX8850
    axera_info = _run(["lspci"])
    if "axera" in axera_info.lower() or "ax8850" in axera_info.lower():
        return "axera", 24, 1

    # Google Coral
    for _ in Path("/dev").glob("apex_*"):
        return "coral", 4, 1

    return "none", 0, 0


# NVIDIA VRAM lookup (taOS pattern — used when nvidia-smi unavailable)
_NVIDIA_VRAM_MB: list[tuple[str, int]] = [
    # RTX 50 series
    ("rtx 5090", 32768), ("rtx 5080", 16384), ("rtx 5070 ti", 16384),
    ("rtx 5070", 12288), ("rtx 5060 ti", 8192), ("rtx 5060", 8192),
    # RTX 40 series
    ("rtx 4090", 24576), ("rtx 4080 super", 16384), ("rtx 4080", 16384),
    ("rtx 4070 ti super", 16384), ("rtx 4070 super", 12288), ("rtx 4070 ti", 12288),
    ("rtx 4070", 12288), ("rtx 4060 ti", 8192), ("rtx 4060", 8192),
    # RTX 30 series
    ("rtx 3090 ti", 24576), ("rtx 3090", 24576), ("rtx 3080 ti", 12288),
    ("rtx 3080", 10240), ("rtx 3070 ti", 8192), ("rtx 3070", 8192),
    ("rtx 3060 ti", 8192), ("rtx 3060", 12288), ("rtx 3050", 8192),
    # RTX 20 series
    ("rtx 2080 ti", 11264), ("rtx 2080 super", 8192), ("rtx 2080", 8192),
    ("rtx 2070 super", 8192), ("rtx 2070", 8192), ("rtx 2060 super", 8192),
    ("rtx 2060", 6144),
    # GTX 16/10
    ("gtx 1660 ti", 6144), ("gtx 1660 super", 6144), ("gtx 1660", 6144),
    ("gtx 1650", 4096), ("gtx 1080 ti", 11264), ("gtx 1080", 8192),
    ("gtx 1070 ti", 8192), ("gtx 1070", 8192), ("gtx 1060", 6144),
    # Datacenter
    ("h100", 81920), ("a100 80", 81920), ("a100", 40960), ("l40s", 49152),
    ("l40", 49152), ("l4", 24576), ("a40", 49152), ("a30", 24576),
    ("a10", 24576), ("a6000", 49152), ("a5000", 24576), ("a4000", 16384),
    ("tesla v100 32", 32768), ("tesla v100", 16384), ("tesla t4", 16384),
]


def _nvidia_vram_for_model(model: str) -> int:
    needle = model.lower()
    for key, mb in _NVIDIA_VRAM_MB:
        if key in needle:
            return mb
    return 0


def _detect_gpu_extended() -> tuple[str, str, float, bool, bool]:
    """Returns (gpu_type, gpu_name, vram_gb, cuda, rocm).
    Falls back to clawos_core.platform.gpu_info() for basic detection.
    """
    # Apple Silicon
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            mem_bytes = int(subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip())
            vram_gb = mem_bytes / (1024 ** 3)
        except Exception:
            vram_gb = 0.0
        return "apple", "Apple Silicon (unified memory)", vram_gb, False, False

    # NVIDIA — /proc/driver/nvidia first (works without nvidia-smi userspace)
    info_root = Path("/proc/driver/nvidia/gpus")
    if _path_exists_safe(info_root):
        try:
            for gpu_dir in info_root.iterdir():
                info_file = gpu_dir / "information"
                if not _path_exists_safe(info_file):
                    continue
                for line in info_file.read_text(errors="replace").splitlines():
                    if line.lower().startswith("model:"):
                        model_name = line.split(":", 1)[1].strip()
                        vram_mb = _nvidia_vram_for_model(model_name)
                        return "nvidia", model_name, vram_mb / 1024, True, False
        except (PermissionError, OSError):
            pass

    lspci = _run(["lspci"])
    if "NVIDIA" in lspci.upper():
        for line in lspci.split("\n"):
            if "NVIDIA" in line.upper() and ("VGA" in line or "3D" in line):
                model_name = line.split(":")[-1].strip()
                cuda = shutil.which("nvidia-smi") is not None
                vram_mb = _nvidia_vram_for_model(model_name)
                return "nvidia", model_name, vram_mb / 1024, cuda, False
    elif "AMD" in lspci.upper() and "VGA" in lspci.upper():
        for line in lspci.split("\n"):
            if "AMD" in line.upper() and "VGA" in line:
                model_name = line.split(":")[-1].strip()
                rocm = Path("/opt/rocm").exists()
                return "amd", model_name, 0.0, False, rocm

    # Mali (ARM integrated)
    if Path("/sys/class/misc/mali0").exists():
        return "mali", "Mali (integrated)", 0.0, False, False

    # Fall back to clawos_core detection for VRAM number
    try:
        legacy_name, legacy_vram = gpu_info()
        if legacy_vram > 0:
            gpu_type = "nvidia" if "nvidia" in legacy_name.lower() else "unknown"
            return gpu_type, legacy_name, legacy_vram, gpu_type == "nvidia", False
    except Exception:
        pass

    return "none", "none", 0.0, False, False


def _detect_disk_type() -> tuple[float, str]:
    """Returns (total_gb, disk_type). disk_type in nvme|emmc|ssd|hdd|sd."""
    dtype = ""
    lsblk = _run(["lsblk", "-dno", "NAME,ROTA,TRAN"])
    for line in lsblk.split("\n"):
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0]
        if any(name.startswith(skip) for skip in ("zram", "loop", "mtdblock", "ram")):
            continue
        rota = parts[1] if len(parts) > 1 else "1"
        tran = parts[2] if len(parts) > 2 else ""
        if "nvme" in tran or "nvme" in name:
            dtype = "nvme"; break
        elif "mmc" in name:
            dtype = "emmc" if "mmcblk" in name else "sd"; break
        elif rota == "0":
            dtype = "ssd"; break
        elif rota == "1":
            dtype = "hdd"; break
    try:
        import shutil as sh
        usage = sh.disk_usage("/")
        return usage.total / (1024 ** 3), dtype
    except OSError:
        return 0.0, dtype


def _detect_os() -> tuple[str, str]:
    distro, version = "", ""
    try:
        for line in Path("/etc/os-release").read_text().split("\n"):
            if line.startswith("ID="):
                distro = line.split("=", 1)[1].strip('"')
            elif line.startswith("VERSION_ID="):
                version = line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    if "TERMUX_VERSION" in os.environ or "com.termux" in str(Path.home()):
        distro = "android-termux"
    return distro, version


# ── ClawOS legacy helpers (preserved) ─────────────────────────────────────────

def _ram_gb() -> float:
    return ram_snapshot_gb().get("total_gb", 0.0)


def _cpu_cores() -> int:
    try:
        return os.cpu_count() or 4
    except Exception:
        return 4


def _disk_free_gb(path: str = "/") -> float:
    try:
        return disk_snapshot_gb(path).get("free_gb", 0.0)
    except Exception:
        return 0.0


def _check_ollama() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _check_node() -> bool:
    return shutil.which("node") is not None


# ── Main probe function ────────────────────────────────────────────────────────

def probe() -> HardwareProfile:
    """Full hardware probe. Returns HardwareProfile with both legacy and taOS fields."""
    ram   = _ram_gb()
    cores = _cpu_cores()
    disk_free = _disk_free_gb()
    has_mic, rate, dev = audio_info()

    cpu_arch, cpu_soc, is_arm = _detect_cpu_arch()
    npu_type, npu_tops, npu_cores = _detect_npu()
    gpu_type, gpu_name_ext, gpu_vram_ext, gpu_cuda, gpu_rocm = _detect_gpu_extended()
    disk_total, disk_type = _detect_disk_type()
    os_distro, os_version = _detect_os()

    # Prefer extended VRAM detection; fall back to clawos_core
    vram = gpu_vram_ext if gpu_vram_ext > 0 else 0.0
    gpu_name = gpu_name_ext if gpu_name_ext != "none" else "none"

    # ClawOS tier (legacy A/B/C/D)
    if vram >= 10.0:
        tier = "D"
    elif ram >= 30:
        tier = "C"
    elif ram >= 14:
        tier = "B"
    else:
        tier = "A"

    return HardwareProfile(
        # Legacy fields
        ram_gb       = ram,
        cpu_cores    = cores,
        gpu_vram_gb  = vram,
        gpu_name     = gpu_name,
        disk_free_gb = disk_free,
        has_mic      = has_mic,
        audio_rate   = rate,
        audio_device = dev,
        tier         = tier,
        ollama_ok    = _check_ollama(),
        node_ok      = _check_node(),
        # taOS-style fields
        cpu_arch     = cpu_arch,
        cpu_soc      = cpu_soc,
        is_arm       = is_arm,
        npu_type     = npu_type,
        npu_tops     = npu_tops,
        npu_cores    = npu_cores,
        gpu_type     = gpu_type,
        gpu_cuda     = gpu_cuda,
        gpu_rocm     = gpu_rocm,
        disk_total_gb = disk_total,
        disk_type    = disk_type,
        os_distro    = os_distro,
        os_version   = os_version,
    )


_CACHE_TTL = 86400  # 24 hours — re-detect if user adds accelerator card


def probe_and_save() -> HardwareProfile:
    from clawos_core.constants import HARDWARE_JSON
    HARDWARE_JSON.parent.mkdir(parents=True, exist_ok=True)
    hw = probe()
    data = asdict(hw)
    data["profile_id"] = hw.profile_id   # persist computed property
    HARDWARE_JSON.write_text(json.dumps(data, indent=2))
    os.environ["CLAWOS_DETECTED_TIER"] = hw.tier
    os.environ["CLAWOS_PROFILE_ID"] = hw.profile_id
    return hw


def load_saved() -> HardwareProfile:
    from clawos_core.constants import HARDWARE_JSON
    if HARDWARE_JSON.exists():
        # Re-probe if cache is stale
        age = time.time() - HARDWARE_JSON.stat().st_mtime
        if age < _CACHE_TTL:
            d = json.loads(HARDWARE_JSON.read_text())
            d.pop("profile_id", None)  # computed property, not a field
            # Gracefully handle missing taOS fields in older saved files
            known = {f.name for f in HardwareProfile.__dataclass_fields__.values()}
            d = {k: v for k, v in d.items() if k in known}
            return HardwareProfile(**d)
    return probe_and_save()


def is_tier_d(hw: HardwareProfile | None = None) -> bool:
    if hw is None:
        hw = load_saved()
    return hw.gpu_vram_gb >= 10.0


def get_tier(hw: HardwareProfile | None = None) -> str:
    if hw is None:
        hw = load_saved()
    if hw.gpu_vram_gb >= 10.0:
        return "D"
    if hw.ram_gb >= 30:
        return "C"
    if hw.ram_gb >= 14:
        return "B"
    return "A"
