# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS picoclawd — PicoClaw Management Service (Tier A only)
=============================================================
Responsible for:
  - Detecting Tier A ARM hardware at boot
  - Downloading correct PicoClaw binary for arch
  - Writing ~/.picoclaw/config.json with Ollama endpoint + timeout patch
  - Starting/stopping PicoClaw process, health monitoring
  - Bridging gatewayd inbound messages to PicoClaw HTTP API

Only activates on ARM architecture with <= 8GB RAM.
On x86 hardware, this service does nothing.
"""
import asyncio
import logging
import platform
import subprocess
from pathlib import Path
from clawos_core.constants import OLLAMA_HOST, PICOCLAW_HTTP_TIMEOUT

log = logging.getLogger("picoclawd")

_process: subprocess.Popen = None


def is_arm() -> bool:
    m = platform.machine().lower()
    return m.startswith("arm") or m in ("aarch64", "arm64") or "riscv" in m


def is_tier_a() -> bool:
    """Tier A: ARM arch with <= 8GB RAM."""
    if not is_arm():
        return False
    try:
        from bootstrap.hardware_probe import load_saved
        hw = load_saved()
        return hw.ram_gb <= 10.0
    except Exception:
        return is_arm()   # fallback: trust ARM arch


class PicoClawd:
    def __init__(self):
        self._running = False
        self._active  = is_tier_a()

    async def start(self):
        if not self._active:
            log.debug("picoclawd: not Tier A — service inactive")
            return
        self._running = True
        log.info("picoclawd: Tier A detected — managing PicoClaw runtime")
        await self._ensure_installed()
        await self._start_process()

    async def stop(self):
        self._running = False
        if _process:
            try:
                _process.terminate()
                _process.wait(timeout=5)
            except Exception:
                pass

    async def _ensure_installed(self):
        from services.picoclawd.installer import is_installed, install
        if not is_installed():
            log.info("picoclawd: downloading PicoClaw binary...")
            ok = install(ollama_host=OLLAMA_HOST, timeout=PICOCLAW_HTTP_TIMEOUT)
            if not ok:
                log.error("picoclawd: PicoClaw install failed")
        else:
            log.info("picoclawd: PicoClaw already installed")

    async def _start_process(self):
        global _process
        from services.picoclawd.installer import INSTALL_PATH
        if not INSTALL_PATH.exists():
            log.warning("picoclawd: binary not found — PicoClaw not started")
            return
        try:
            _process = subprocess.Popen(
                [str(INSTALL_PATH), "--port", "18800"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log.info(f"picoclawd: PicoClaw started (pid={_process.pid})")
        except Exception as e:
            log.error(f"picoclawd: failed to start PicoClaw: {e}")


_service: PicoClawd = None


def get_picoclawd() -> PicoClawd:
    global _service
    if _service is None:
        _service = PicoClawd()
    return _service
