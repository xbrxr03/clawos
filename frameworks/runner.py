# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Framework runner — start / stop / status for installed frameworks via systemd.
"""
from __future__ import annotations

import logging
import subprocess
import urllib.request
from typing import Optional

from frameworks.registry import AppState, get_registry

log = logging.getLogger("frameworkd.runner")


def _systemctl(args: list[str], user: bool = False) -> tuple[int, str]:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def _unit_name(framework_name: str) -> str:
    return f"clawos-fw-{framework_name}.service"


def _is_active(unit: str) -> bool:
    rc, _ = _systemctl(["is-active", unit])
    if rc == 0:
        return True
    rc, _ = _systemctl(["is-active", unit], user=True)
    return rc == 0


def _probe_http(port: int) -> bool:
    """Check if the framework's HTTP endpoint is up."""
    if not port:
        return False
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2) as r:
            return r.status < 500
    except Exception:
        try:
            # Try root path as fallback
            with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as r:
                return r.status < 500
        except Exception:
            return False


def start(name: str) -> bool:
    registry = get_registry()
    if not registry.is_installed(name):
        log.error(f"runner: {name} is not installed")
        return False

    unit = _unit_name(name)
    rc, out = _systemctl(["start", unit])
    if rc != 0:
        rc, out = _systemctl(["start", unit], user=True)
    if rc == 0:
        registry.set_state(name, AppState.RUNNING)
        log.info(f"runner: started {name}")
        return True
    log.error(f"runner: failed to start {name}: {out}")
    return False


def stop(name: str) -> bool:
    registry = get_registry()
    unit = _unit_name(name)
    rc, _ = _systemctl(["stop", unit])
    if rc != 0:
        rc, _ = _systemctl(["stop", unit], user=True)
    if rc == 0:
        registry.set_state(name, AppState.INSTALLED)
        log.info(f"runner: stopped {name}")
        return True
    return False


def status(name: str) -> dict:
    registry = get_registry()
    manifest = registry.get(name)
    if manifest is None:
        return {"name": name, "state": "unknown", "error": "Not in catalog"}

    unit = _unit_name(name)
    active = _is_active(unit)
    http_ok = _probe_http(manifest.port) if active else False

    if active:
        registry.set_state(name, AppState.RUNNING)
    elif registry.is_installed(name):
        registry.set_state(name, AppState.INSTALLED)

    return {
        "name":      name,
        "version":   manifest.version,
        "state":     registry.state(name).value,
        "systemd":   "active" if active else "inactive",
        "http_ok":   http_ok,
        "port":      manifest.port,
        "api_base":  manifest.api_base,
    }


def status_all() -> list[dict]:
    registry = get_registry()
    return [status(m.name) for m in registry.all()]
