"""clawctl logs — tail ClawOS logs."""
import subprocess
import shutil
from pathlib import Path
from clawos_core.constants import LOGS_DIR


def run(service: str = None, follow: bool = False, lines: int = 40):
    print()
    # Try systemd journal first
    if shutil.which("journalctl"):
        unit = f"clawos-{service}.service" if service else None
        cmd  = ["journalctl", "--user", "-n", str(lines)]
        if unit:
            cmd += ["-u", unit]
        if follow:
            cmd.append("-f")
        try:
            subprocess.run(cmd)
            return
        except KeyboardInterrupt:
            return

    # Fallback: file logs
    if service:
        log_file = LOGS_DIR / f"{service}.log"
        if log_file.exists():
            _tail(log_file, lines, follow)
        else:
            print(f"  No log file for {service} at {log_file}")
    else:
        # Show audit log
        audit = LOGS_DIR / "audit.jsonl"
        if audit.exists():
            _tail(audit, lines, follow)
        else:
            print(f"  No logs found in {LOGS_DIR}")
    print()


def _tail(path: Path, n: int, follow: bool):
    if follow:
        try:
            subprocess.run(["tail", "-f", "-n", str(n), str(path)])
        except KeyboardInterrupt:
            pass
    else:
        lines = path.read_text().strip().split("\n")
        for line in lines[-n:]:
            print(f"  {line}")
