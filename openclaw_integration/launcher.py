# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Start / stop / status OpenClaw gateway.
Replaces ad-hoc shell calls with a proper managed launcher.
"""
import os
import logging
import shutil
import subprocess
import time
from pathlib import Path
from clawos_core.constants import PORT_GATEWAYD

log = logging.getLogger("openclaw.launcher")

_GATEWAY_PID_FILE = Path.home() / ".openclaw" / "gateway.pid"


def is_installed() -> bool:
    return shutil.which("openclaw") is not None


def is_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"http://localhost:{PORT_GATEWAYD}/health", timeout=2)
        return True
    except Exception:
        pass
    # Check via PID file
    if _GATEWAY_PID_FILE.exists():
        pid = int(_GATEWAY_PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            _GATEWAY_PID_FILE.unlink(missing_ok=True)
    return False


def start(allow_unconfigured: bool = True) -> bool:
    """Start OpenClaw gateway in background. Returns True if started."""
    if not is_installed():
        log.warning("openclaw not installed")
        return False
    if is_running():
        log.info("openclaw gateway already running")
        return True

    # Kill any stale gateway processes
    subprocess.run(["pkill", "-f", "openclaw-gateway"], capture_output=True)
    time.sleep(0.5)

    cmd = ["openclaw", "gateway"]
    if allow_unconfigured:
        cmd.append("--allow-unconfigured")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _GATEWAY_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _GATEWAY_PID_FILE.write_text(str(proc.pid))
    log.info(f"openclaw gateway started (pid={proc.pid})")
    time.sleep(2)
    return True


def stop() -> bool:
    """Stop OpenClaw gateway."""
    subprocess.run(["openclaw", "gateway", "stop"], capture_output=True, timeout=10)
    subprocess.run(["pkill", "-f", "openclaw-gateway"], capture_output=True)
    _GATEWAY_PID_FILE.unlink(missing_ok=True)
    log.info("openclaw gateway stopped")
    return True


def status() -> dict:
    return {
        "installed": is_installed(),
        "running":   is_running(),
        "port":      PORT_GATEWAYD,
    }
