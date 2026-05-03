# SPDX-License-Identifier: AGPL-3.0-or-later
"""system.info — return disk usage, RAM free, CPU load, GPU VRAM as JSON."""
import json

from clawos_core.platform import disk_snapshot_gb, gpu_info, load_snapshot, ram_snapshot_gb


def run(target: str = "") -> str:
    """target is ignored — returns full system snapshot."""
    info: dict = {}

    # Disk
    try:
        info["disk"] = disk_snapshot_gb("/")
    except (OSError, ValueError) as e:
        info["disk"] = {"error": str(e)}

    # RAM
    try:
        snap = ram_snapshot_gb()
        total = snap.get("total_gb", 0.0)
        free = snap.get("free_gb", 0.0)
        info["ram"] = {
            "total_gb": total,
            "free_gb": free,
            "used_pct": round(((total - free) / total) * 100, 1) if total else 0,
        }
    except (OSError, RuntimeError, AttributeError) as e:
        info["ram"] = {"error": str(e)}

    # CPU load
    try:
        info["cpu"] = load_snapshot() or {"error": "unavailable"}
    except Exception as e:  # broad catch — cannot narrow automatically
        info["cpu"] = {"error": str(e)}

    # GPU VRAM
    try:
        name, vram = gpu_info()
        info["gpu"] = {"name": name, "vram_total": vram, "available": name != "none"}
    except Exception:  # broad catch — cannot narrow automatically
        info["gpu"] = {"available": False}

    return json.dumps(info, indent=2)
