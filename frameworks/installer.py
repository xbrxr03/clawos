# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Framework installer — handles pip / npm / cargo / git / managed_by installs.

Each framework manifest specifies install_method.  This module translates
that into the correct subprocess call, generates a systemd unit, and registers
the result in the framework registry.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from frameworks.registry import (
    AppState,
    FrameworkManifest,
    get_registry,
)

log = logging.getLogger("frameworkd.installer")

SYSTEMD_UNIT_DIR  = Path("/etc/systemd/system")
USER_SYSTEMD_DIR  = Path.home() / ".config" / "systemd" / "user"
FRAMEWORKS_DIR    = Path.home() / ".claw" / "frameworks"
VENV_DIR          = FRAMEWORKS_DIR / "venvs"
TEMPLATES_DIR     = Path(__file__).parent / "templates"


# ── Systemd unit generation ────────────────────────────────────────────────────

_UNIT_TEMPLATE = """\
[Unit]
Description=ClawOS Framework: {name} v{version}
After=network.target clawos-llmd.service

[Service]
Type=simple
User={user}
Environment=OPENAI_API_KEY={api_key}
Environment=OPENAI_API_BASE={api_base}
WorkingDirectory={work_dir}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def _write_systemd_unit(manifest: FrameworkManifest, exec_start: str, work_dir: Path) -> Path:
    from services.llmd.service import get_virtual_key
    api_key = get_virtual_key(manifest.name) or "sk-clawos-local"

    content = _UNIT_TEMPLATE.format(
        name       = manifest.name,
        version    = manifest.version,
        user       = os.environ.get("USER", "clawos"),
        api_key    = api_key,
        api_base   = manifest.api_base,
        work_dir   = work_dir,
        exec_start = exec_start,
    )
    unit_name = f"clawos-fw-{manifest.name}.service"

    # Try system-level first, fall back to user-level
    for unit_dir in (SYSTEMD_UNIT_DIR, USER_SYSTEMD_DIR):
        try:
            unit_dir.mkdir(parents=True, exist_ok=True)
            unit_path = unit_dir / unit_name
            unit_path.write_text(content)
            log.info(f"installer: wrote systemd unit to {unit_path}")
            return unit_path
        except PermissionError:
            continue
    raise RuntimeError(f"Could not write systemd unit for {manifest.name}")


def _systemctl(args: list[str], user: bool = False) -> bool:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.debug(f"systemctl {' '.join(args)}: {result.stderr.strip()}")
    return result.returncode == 0


def _reload_systemd() -> None:
    _systemctl(["daemon-reload"]) or _systemctl(["daemon-reload"], user=True)


def _enable_and_start(unit_name: str) -> bool:
    ok = _systemctl(["enable", "--now", unit_name])
    if not ok:
        ok = _systemctl(["enable", "--now", unit_name], user=True)
    return ok


# ── Install methods ────────────────────────────────────────────────────────────

def _pip_install(manifest: FrameworkManifest, progress: Callable) -> Path:
    """Install via pip into an isolated venv."""
    venv_path = VENV_DIR / manifest.name
    venv_path.parent.mkdir(parents=True, exist_ok=True)

    progress(f"Creating Python venv for {manifest.name}…")
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

    pip = venv_path / "bin" / "pip"
    if not pip.exists():
        pip = venv_path / "Scripts" / "pip.exe"  # Windows

    progress(f"Installing {manifest.package}…")
    subprocess.run([str(pip), "install", "--quiet", manifest.package], check=True)

    return venv_path


def _npm_install(manifest: FrameworkManifest, progress: Callable) -> Path:
    """Install via npm globally or into a local prefix."""
    work_dir = FRAMEWORKS_DIR / manifest.name
    work_dir.mkdir(parents=True, exist_ok=True)
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm not found — install Node.js first")
    progress(f"npm install {manifest.package}…")
    subprocess.run([npm, "install", "-g", manifest.package], check=True, cwd=str(work_dir))
    return work_dir


def _cargo_install(manifest: FrameworkManifest, progress: Callable) -> Path:
    cargo = shutil.which("cargo")
    if not cargo:
        raise RuntimeError("cargo not found — install Rust/Cargo first")
    progress(f"cargo install {manifest.package}…")
    subprocess.run([cargo, "install", manifest.package], check=True)
    return Path.home() / ".cargo" / "bin"


def _git_install(manifest: FrameworkManifest, progress: Callable) -> Path:
    work_dir = FRAMEWORKS_DIR / manifest.name
    work_dir.parent.mkdir(parents=True, exist_ok=True)
    if not work_dir.exists():
        progress(f"git clone {manifest.repo}…")
        subprocess.run(["git", "clone", manifest.repo, str(work_dir)], check=True)
    else:
        progress("git pull…")
        subprocess.run(["git", "pull"], cwd=str(work_dir), check=True)

    # Install Python deps if requirements.txt or setup.py present
    venv_path = VENV_DIR / manifest.name
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    pip = venv_path / "bin" / "pip"
    if not pip.exists():
        pip = venv_path / "Scripts" / "pip.exe"
    for req in ("requirements.txt", "setup.py", "pyproject.toml"):
        if (work_dir / req).exists():
            progress(f"pip install from {req}…")
            subprocess.run([str(pip), "install", "-e", str(work_dir)], check=True)
            break
    return work_dir


# ── Public API ─────────────────────────────────────────────────────────────────

def install(
    name: str,
    progress: Callable[[str], None] | None = None,
) -> bool:
    """
    Install a framework by name.

    progress: optional callback(message) for UI updates.
    Returns True on success.
    """
    if progress is None:
        progress = lambda msg: log.info(f"installer: {msg}")

    registry = get_registry()
    manifest = registry.get(name)
    if manifest is None:
        log.error(f"installer: unknown framework '{name}'")
        return False

    registry.set_state(name, AppState.INSTALLING)
    try:
        method = manifest.install_method
        if method == "pip":
            work_dir = _pip_install(manifest, progress)
            venv_bin = work_dir / "bin"
            exec_bin = venv_bin / manifest.entry_point.split(".")[0]
            if not exec_bin.exists():
                # Fall back to python -m entry_point
                python = venv_bin / "python"
                exec_start = f"{python} -m {manifest.entry_point} --port {manifest.port}"
            else:
                exec_start = f"{exec_bin} --port {manifest.port}"
            _write_systemd_unit(manifest, exec_start, work_dir)

        elif method == "npm":
            work_dir = _npm_install(manifest, progress)
            if manifest.managed_by:
                # Managed externally — no systemd unit needed
                registry.set_state(name, AppState.INSTALLED)
                progress(f"{name} installed successfully (managed externally)")
                return True
            exec_bin = shutil.which(manifest.entry_point.split(".")[0]) or manifest.entry_point
            exec_start = f"{exec_bin} --port {manifest.port}"
            _write_systemd_unit(manifest, exec_start, work_dir)

        elif method == "cargo":
            bin_dir = _cargo_install(manifest, progress)
            exec_bin = bin_dir / manifest.entry_point
            exec_start = f"{exec_bin} --port {manifest.port}"
            _write_systemd_unit(manifest, exec_start, bin_dir)

        elif method == "git":
            work_dir = _git_install(manifest, progress)
            venv_bin = (VENV_DIR / name / "bin")
            python = venv_bin / "python"
            entry = manifest.entry_point
            if entry.endswith(".py"):
                exec_start = f"{python} {work_dir / entry} --port {manifest.port}"
            else:
                exec_start = f"{python} -m {entry} --port {manifest.port}"
            _write_systemd_unit(manifest, exec_start, work_dir)

        else:
            log.error(f"installer: unknown install_method '{method}' for {name}")
            registry.set_state(name, AppState.ERROR)
            return False

        _reload_systemd()
        registry.set_state(name, AppState.INSTALLED)
        progress(f"{name} installed successfully")
        return True

    except Exception as e:
        log.error(f"installer: failed to install {name}: {e}")
        registry.set_state(name, AppState.ERROR)
        return False


def remove(name: str, progress: Callable[[str], None] | None = None) -> bool:
    """Uninstall a framework and remove its systemd unit."""
    if progress is None:
        progress = lambda msg: log.info(f"installer: {msg}")

    registry = get_registry()
    manifest = registry.get(name)
    if manifest is None:
        return False

    registry.set_state(name, AppState.REMOVING)

    # Stop systemd service
    unit_name = f"clawos-fw-{name}.service"
    _systemctl(["disable", "--now", unit_name]) or \
    _systemctl(["disable", "--now", unit_name], user=True)

    # Remove systemd unit file
    for unit_dir in (SYSTEMD_UNIT_DIR, USER_SYSTEMD_DIR):
        unit_path = unit_dir / unit_name
        if unit_path.exists():
            unit_path.unlink(missing_ok=True)

    _reload_systemd()

    # Remove venv / install dir
    venv_path = VENV_DIR / name
    if venv_path.exists():
        import shutil as sh
        sh.rmtree(venv_path, ignore_errors=True)

    install_dir = FRAMEWORKS_DIR / name
    if install_dir.exists():
        import shutil as sh
        sh.rmtree(install_dir, ignore_errors=True)

    registry.set_state(name, AppState.AVAILABLE)
    progress(f"{name} removed")
    return True
