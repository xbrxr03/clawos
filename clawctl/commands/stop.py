"""clawctl stop — stop ClawOS services."""
import subprocess

from clawctl.ui.banner import error, success
from clawos_core.service_manager import service_manager_name, stop as stop_service

DAEMON_UNIT = "clawos.service"


def run(service: str = None):
    print()
    if service_manager_name() == "none":
        subprocess.run(["pkill", "-f", "clients/daemon/daemon.py"], capture_output=True)
        success("Stopped ClawOS daemon")
        return

    ok, detail = stop_service(DAEMON_UNIT)
    if ok:
        if service:
            success(f"{DAEMON_UNIT} stopped ({service} ran in-process)")
        else:
            success(f"{DAEMON_UNIT} stopped")
    else:
        error(f"Could not stop {DAEMON_UNIT}: {detail}")
    print()
