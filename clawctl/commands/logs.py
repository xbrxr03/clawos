"""clawctl logs — tail ClawOS logs."""
import subprocess
from pathlib import Path

from clawos_core.constants import LOGS_DIR
from clawos_core.service_manager import log_files_for, service_manager_name


def run(service: str = None, follow: bool = False, lines: int = 40):
    print()
    if service_manager_name() == "systemd":
        unit = f"clawos-{service}.service" if service else None
        cmd = ["journalctl", "--user", "-n", str(lines)]
        if unit:
            cmd += ["-u", unit]
        if follow:
            cmd.append("-f")
        try:
            subprocess.run(cmd)
            return
        except KeyboardInterrupt:
            return

    files = [path for path in log_files_for(service) if path.exists()]
    if not files:
        print(f"  No logs found in {LOGS_DIR}")
    else:
        for log_file in files:
            _tail(log_file, lines, follow)
    print()


def _tail(path: Path, n: int, follow: bool):
    if follow:
        try:
            subprocess.run(["tail", "-f", "-n", str(n), str(path)])
        except KeyboardInterrupt:
            pass
        return

    text = path.read_text(encoding="utf-8", errors="replace").strip()
    for line in text.split("\n")[-n:]:
        if line:
            print(f"  {line}")
