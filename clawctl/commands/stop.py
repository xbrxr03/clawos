"""clawctl stop — stop ClawOS services."""
import subprocess
import shutil
from clawctl.ui.banner import success, error

# All core services run in-process inside clawos.service.
DAEMON_UNIT = "clawos.service"


def run(service: str = None):
    print()
    if not shutil.which("systemctl"):
        # Dev mode — kill the daemon process
        import subprocess as sp
        sp.run(["pkill", "-f", "clients/daemon/daemon.py"], capture_output=True)
        success("Stopped ClawOS daemon")
        return

    # All services run inside the single daemon — stop the whole thing.
    r = subprocess.run(
        ["systemctl", "--user", "stop", DAEMON_UNIT],
        capture_output=True,
    )
    if r.returncode == 0:
        if service:
            success(f"clawos.service stopped ({service} ran in-process)")
        else:
            success("clawos.service stopped")
    else:
        error(f"Could not stop clawos.service: {r.stderr.decode().strip()}")
    print()
