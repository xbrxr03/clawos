"""Enable and start ClawOS systemd user services."""
import subprocess
import shutil
from pathlib import Path

SYSTEMD_DIR = Path(__file__).parent.parent / "packaging" / "systemd"
USER_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"

SERVICES = [
    "clawos-policyd",
    "clawos-memd",
    "clawos-modeld",
    "clawos-toolbridge",
    "clawos-agentd",
    "clawos-clawd",
    "clawos-dashd",
]


def _run(cmd: list) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def install_units(project_root: Path = None) -> bool:
    """Copy systemd unit files to ~/.config/systemd/user/"""
    if not shutil.which("systemctl"):
        return False
    USER_UNIT_DIR.mkdir(parents=True, exist_ok=True)
    for svc in SERVICES:
        src = SYSTEMD_DIR / f"{svc}.service"
        if src.exists():
            dst = USER_UNIT_DIR / f"{svc}.service"
            # Patch ExecStart path if project_root given
            text = src.read_text()
            if project_root:
                text = text.replace("/opt/clawos", str(project_root))
            dst.write_text(text)
    _run(["systemctl", "--user", "daemon-reload"])
    return True


def enable_all() -> dict:
    results = {}
    for svc in SERVICES:
        ok = _run(["systemctl", "--user", "enable", f"{svc}.service"])
        results[svc] = "enabled" if ok else "skip"
    return results


def start_all() -> dict:
    results = {}
    for svc in SERVICES:
        ok = _run(["systemctl", "--user", "start", f"{svc}.service"])
        results[svc] = "started" if ok else "skip"
    return results


def status_all() -> dict:
    results = {}
    for svc in SERVICES:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", f"{svc}.service"],
            capture_output=True, text=True
        )
        results[svc] = r.stdout.strip()
    return results
