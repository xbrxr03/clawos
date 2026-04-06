"""Enable and start ClawOS user services on Linux or macOS."""
import shutil
import subprocess
import sys
from pathlib import Path

from clawos_core.constants import DEFAULT_WORKSPACE
from clawos_core.service_manager import (
    install_launch_agents,
    is_active,
    service_hint,
    service_manager_name,
    start as start_service,
)

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


def _run(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).returncode == 0
    except Exception:
        return False


def install_units(project_root: Path = None) -> bool:
    project_root = project_root or Path(__file__).parent.parent
    manager = service_manager_name()

    if manager == "systemd":
        USER_UNIT_DIR.mkdir(parents=True, exist_ok=True)
        for svc in SERVICES:
            src = SYSTEMD_DIR / f"{svc}.service"
            if not src.exists():
                continue
            dst = USER_UNIT_DIR / f"{svc}.service"
            text = src.read_text(encoding="utf-8", errors="replace")
            text = text.replace("/opt/clawos", str(project_root))
            dst.write_text(text, encoding="utf-8")
        _run(["systemctl", "--user", "daemon-reload"])
        return True

    if manager == "launchd":
        install_launch_agents(
            project_root=project_root,
            workspace=DEFAULT_WORKSPACE,
            python_bin=sys.executable,
            ollama_bin=shutil.which("ollama") or "ollama",
        )
        return True

    return False


def enable_all() -> dict:
    manager = service_manager_name()
    if manager == "systemd":
        return {
            svc: ("enabled" if _run(["systemctl", "--user", "enable", f"{svc}.service"]) else "skip")
            for svc in SERVICES
        }
    if manager == "launchd":
        return {
            "clawos.service": "installed",
            "ollama.service": "installed",
        }
    return {}


def start_all() -> dict:
    manager = service_manager_name()
    if manager == "systemd":
        return {
            svc: ("started" if _run(["systemctl", "--user", "start", f"{svc}.service"]) else "skip")
            for svc in SERVICES
        }
    if manager == "launchd":
        results = {}
        for service_name in ("ollama.service", "clawos.service"):
            ok, _ = start_service(service_name)
            results[service_name] = "started" if ok else "skip"
        return results
    return {}


def status_all() -> dict:
    manager = service_manager_name()
    if manager == "systemd":
        results = {}
        for svc in SERVICES:
            try:
                proc = subprocess.run(
                    ["systemctl", "--user", "is-active", f"{svc}.service"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                results[svc] = proc.stdout.strip()
            except Exception:
                results[svc] = "unknown"
        return results
    if manager == "launchd":
        return {
            "clawos.service": "active" if is_active("clawos.service") else "inactive",
            "ollama.service": "active" if is_active("ollama.service") else "inactive",
        }
    return {"clawos.service": f"unmanaged ({service_hint('start', 'clawos.service')})"}
