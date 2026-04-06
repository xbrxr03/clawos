# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl start — start ClawOS services."""
import subprocess
import sys
from pathlib import Path

from clawctl.ui.banner import error, info, success
from clawos_core.service_manager import service_hint, service_manager_name, start as start_service

ROOT = Path(__file__).parent.parent.parent

# All core services run in-process inside clawos.service.
DAEMON_UNIT = "clawos.service"


def _start_dev(service: str = None):
    """Start in dev mode when no user service manager is available."""
    if service:
        module_map = {
            "policyd": "services.policyd.main",
            "memd": "services.memd.main",
            "modeld": "services.modeld.main",
            "agentd": "services.agentd.main",
            "toolbridge": "services.toolbridge.service",
            "dashd": "services.dashd.main",
            "clawd": "services.clawd.service",
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
        return

    subprocess.Popen(["bash", "scripts/dev_boot.sh"], cwd=str(ROOT))
    info("Starting all services — dashboard at http://localhost:7070")


def _start_managed(service: str = None):
    ok, detail = start_service(DAEMON_UNIT)
    if ok:
        if service:
            success(f"{DAEMON_UNIT} started ({service} runs in-process)")
        else:
            success(f"{DAEMON_UNIT} started")
        return

    if "launch agent not installed" in detail.lower():
        info("Autostart is not installed yet — starting directly in dev mode.")
        _start_dev(service)
        return

    error(f"Failed to start {DAEMON_UNIT}: {detail or service_hint('start', DAEMON_UNIT)}")


def run(service: str = None, dev: bool = False):
    print()
    manager = service_manager_name()
    if not dev and manager != "none":
        _start_managed(service)
    else:
        _start_dev(service)
    print()
