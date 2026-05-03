# SPDX-License-Identifier: AGPL-3.0-or-later
"""
User service-manager helpers for ClawOS.
Supports systemd user services on Linux and launchd LaunchAgents on macOS.
"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from clawos_core.constants import DEFAULT_WORKSPACE, LOGS_DIR
from clawos_core.platform import is_macos, launch_agents_dir, preferred_shell_path_entries

SERVICE_LABELS = {
    "clawos.service": "io.clawos.daemon",
    "ollama.service": "io.clawos.ollama",
    "openclaw-gateway.service": "io.clawos.openclaw-gateway",
}


def _run(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def service_manager_name() -> str:
    if shutil.which("systemctl"):
        try:
            result = _run(["systemctl", "--user", "show-environment"], timeout=5)
            if result.returncode == 0:
                return "systemd"
        except Exception:  # broad catch — cannot narrow automatically
            pass
    if is_macos() and shutil.which("launchctl"):
        return "launchd"
    return "none"


def launch_agent_label(service_name: str) -> str:
    service = service_name if service_name.endswith(".service") else f"{service_name}.service"
    return SERVICE_LABELS.get(service, f"io.clawos.{service.replace('.service', '')}")


def launch_agent_path(service_name: str) -> Path:
    return launch_agents_dir() / f"{launch_agent_label(service_name)}.plist"


def user_domain_target() -> str:
    return f"gui/{os.getuid()}"


def service_hint(action: str, service_name: str = "clawos.service") -> str:
    manager = service_manager_name()
    if manager == "systemd":
        return f"systemctl --user {action} {service_name}"
    if manager == "launchd":
        label = launch_agent_label(service_name)
        plist = launch_agent_path(service_name)
        plist_display = plist.as_posix()
        if action == "start":
            return f"launchctl bootstrap {user_domain_target()} {plist_display}"
        if action == "stop":
            return f"launchctl bootout {user_domain_target()} {plist_display}"
        if action == "restart":
            return f"launchctl kickstart -k {user_domain_target()}/{label}"
        if action == "status":
            return f"launchctl print {user_domain_target()}/{label}"
    return f"python {Path('clients/daemon/daemon.py')}"


def install_launch_agents(
    project_root: Path,
    workspace: str = DEFAULT_WORKSPACE,
    python_bin: str | None = None,
    ollama_bin: str | None = None,
) -> list[Path]:
    python_bin = python_bin or sys.executable
    ollama_bin = ollama_bin or shutil.which("ollama") or "ollama"

    launch_agents_dir().mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    path_env = ":".join(preferred_shell_path_entries())
    env = {
        "HOME": str(Path.home()),
        "PATH": path_env,
        "PYTHONPATH": str(project_root),
        "CLAWOS_DIR": os.environ.get("CLAWOS_DIR", str(Path.home() / "clawos")),
    }

    created = []
    created.append(_write_launch_agent(
        "clawos.service",
        [python_bin, str(project_root / "clients" / "daemon" / "daemon.py"), workspace],
        project_root,
        env,
        LOGS_DIR / "clawos.stdout.log",
        LOGS_DIR / "clawos.stderr.log",
    ))
    created.append(_write_launch_agent(
        "ollama.service",
        [ollama_bin, "serve"],
        project_root,
        {"HOME": str(Path.home()), "PATH": path_env},
        LOGS_DIR / "ollama.stdout.log",
        LOGS_DIR / "ollama.stderr.log",
    ))
    return created


def _write_launch_agent(
    service_name: str,
    argv: list[str],
    workdir: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> Path:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": launch_agent_label(service_name),
        "ProgramArguments": argv,
        "WorkingDirectory": str(workdir),
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
    }
    path = launch_agent_path(service_name)
    with open(path, "wb") as handle:
        plistlib.dump(plist, handle, sort_keys=False)
    return path


def start(service_name: str) -> tuple[bool, str]:
    manager = service_manager_name()
    if manager == "systemd":
        result = _run(["systemctl", "--user", "start", service_name])
        return result.returncode == 0, (result.stderr or result.stdout).strip()
    if manager == "launchd":
        plist = launch_agent_path(service_name)
        if not plist.exists():
            return False, f"launch agent not installed: {plist}"
        _run(["launchctl", "bootout", user_domain_target(), str(plist)], timeout=10)
        bootstrap = _run(["launchctl", "bootstrap", user_domain_target(), str(plist)], timeout=10)
        kickstart = _run(["launchctl", "kickstart", "-k", f"{user_domain_target()}/{launch_agent_label(service_name)}"], timeout=10)
        ok = bootstrap.returncode == 0 and kickstart.returncode == 0
        detail = (kickstart.stderr or bootstrap.stderr or kickstart.stdout or bootstrap.stdout).strip()
        return ok, detail
    return False, "no supported user service manager found"


def stop(service_name: str) -> tuple[bool, str]:
    manager = service_manager_name()
    if manager == "systemd":
        result = _run(["systemctl", "--user", "stop", service_name])
        return result.returncode == 0, (result.stderr or result.stdout).strip()
    if manager == "launchd":
        plist = launch_agent_path(service_name)
        if not plist.exists():
            return False, f"launch agent not installed: {plist}"
        result = _run(["launchctl", "bootout", user_domain_target(), str(plist)], timeout=10)
        ok = result.returncode == 0 or "No such process" in (result.stderr or "")
        return ok, (result.stderr or result.stdout).strip()
    return False, "no supported user service manager found"


def restart(service_name: str) -> tuple[bool, str]:
    manager = service_manager_name()
    if manager == "systemd":
        result = _run(["systemctl", "--user", "restart", service_name])
        return result.returncode == 0, (result.stderr or result.stdout).strip()
    if manager == "launchd":
        label = launch_agent_label(service_name)
        result = _run(["launchctl", "kickstart", "-k", f"{user_domain_target()}/{label}"], timeout=10)
        if result.returncode == 0:
            return True, (result.stderr or result.stdout).strip()
        return start(service_name)
    return False, "no supported user service manager found"


def is_active(service_name: str) -> bool:
    manager = service_manager_name()
    if manager == "systemd":
        try:
            result = _run(["systemctl", "--user", "is-active", service_name], timeout=5)
            return result.stdout.strip() == "active"
        except (OSError, RuntimeError, AttributeError):
            return False
    if manager == "launchd":
        label = launch_agent_label(service_name)
        try:
            result = _run(["launchctl", "print", f"{user_domain_target()}/{label}"], timeout=5)
            return result.returncode == 0
        except (OSError, RuntimeError):
            return False
    return False


def log_files_for(service_name: str | None = None) -> list[Path]:
    manager = service_manager_name()
    if manager == "launchd":
        if not service_name or service_name in ("clawos", "clawos.service"):
            return [LOGS_DIR / "clawos.stdout.log", LOGS_DIR / "clawos.stderr.log"]
        if service_name in ("ollama", "ollama.service"):
            return [LOGS_DIR / "ollama.stdout.log", LOGS_DIR / "ollama.stderr.log"]
    if service_name:
        service = service_name.removesuffix(".service")
        return [LOGS_DIR / f"{service}.log"]
    return [LOGS_DIR / "audit.jsonl"]
