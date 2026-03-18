"""clawctl stop — stop ClawOS services."""
import subprocess
import shutil
from clawctl.ui.banner import success, error


def run(service: str = None):
    print()
    if not shutil.which("systemctl"):
        # Kill by process name in dev mode
        import subprocess as sp
        targets = [service] if service else [
            "policyd.main","memd.main","modeld.main",
            "agentd.main","dashd.main","clawd.service"
        ]
        sp.run(["pkill", "-f", f"clawos"], capture_output=True)
        success("Stopped ClawOS processes")
        return

    svcs = [f"clawos-{service}"] if service else [
        f"clawos-{s}" for s in
        ["dashd","clawd","agentd","toolbridge","modeld","memd","policyd"]
    ]
    for svc in svcs:
        r = subprocess.run(["systemctl","--user","stop",f"{svc}.service"],
                           capture_output=True)
        if r.returncode == 0:
            success(f"Stopped {svc}")
        else:
            error(f"Could not stop {svc}")
    print()
