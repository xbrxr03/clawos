"""clawctl start — start ClawOS services."""
import subprocess
import sys
from pathlib import Path
from clawctl.ui.banner import success, error, info

ROOT = Path(__file__).parent.parent.parent


def _start_dev(service: str = None):
    """Start in dev mode (no systemd)."""
    if service:
        module_map = {
            "policyd":    "services.policyd.main",
            "memd":       "services.memd.main",
            "modeld":     "services.modeld.main",
            "agentd":     "services.agentd.main",
            "toolbridge": "services.toolbridge.service",
            "dashd":      "services.dashd.main",
            "clawd":      "services.clawd.service",
        }
        mod = module_map.get(service)
        if not mod:
            error(f"Unknown service: {service}")
            return
        subprocess.Popen(
            [sys.executable, "-m", mod],
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
            cwd=str(ROOT),
        )
        success(f"Started {service}")
    else:
        subprocess.Popen(["bash", "scripts/dev_boot.sh"], cwd=str(ROOT))
        info("Starting all services — dashboard at http://localhost:7070")


def _start_systemd(service: str = None):
    svcs = [f"clawos-{service}"] if service else [
        f"clawos-{s}" for s in
        ["policyd","memd","modeld","toolbridge","agentd","clawd","dashd"]
    ]
    for svc in svcs:
        r = subprocess.run(["systemctl","--user","start",f"{svc}.service"],
                           capture_output=True)
        if r.returncode == 0:
            success(f"Started {svc}")
        else:
            error(f"Failed to start {svc}")


def run(service: str = None, dev: bool = False):
    print()
    use_systemd = not dev and __import__("shutil").which("systemctl")
    if use_systemd:
        _start_systemd(service)
    else:
        _start_dev(service)
    print()
