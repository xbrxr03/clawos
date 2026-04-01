"""system.info — return disk usage, RAM free, CPU load, GPU VRAM as JSON."""
import json
import shutil
import subprocess


def run(target: str = "") -> str:
    """target is ignored — returns full system snapshot."""
    info: dict = {}

    # Disk
    try:
        usage = shutil.disk_usage("/")
        info["disk"] = {
            "total_gb":  round(usage.total / 1e9, 1),
            "used_gb":   round(usage.used  / 1e9, 1),
            "free_gb":   round(usage.free  / 1e9, 1),
            "used_pct":  round(usage.used / usage.total * 100, 1),
        }
    except Exception as e:
        info["disk"] = {"error": str(e)}

    # RAM
    try:
        with open("/proc/meminfo") as f:
            lines = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        total = lines.get("MemTotal", 0)
        avail = lines.get("MemAvailable", 0)
        info["ram"] = {
            "total_gb": round(total / 1e6, 1),
            "free_gb":  round(avail / 1e6, 1),
            "used_pct": round((total - avail) / total * 100, 1) if total else 0,
        }
    except Exception as e:
        info["ram"] = {"error": str(e)}

    # CPU load
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        info["cpu"] = {"load_1m": float(parts[0]), "load_5m": float(parts[1])}
    except Exception as e:
        info["cpu"] = {"error": str(e)}

    # GPU VRAM (nvidia-smi)
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0:
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            info["gpu"] = {
                "name":       parts[0],
                "vram_total": round(int(parts[1]) / 1024, 1),
                "vram_free":  round(int(parts[2]) / 1024, 1),
            }
    except Exception:
        info["gpu"] = {"available": False}

    return json.dumps(info, indent=2)
