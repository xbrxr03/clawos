# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Download PicoClaw binary for this architecture from GitHub releases.
Only runs on ARM hardware (Tier A detection).
"""
import json
import logging
import os
import platform
import stat
import urllib.request
from pathlib import Path

from clawos_core.constants import PICOCLAW_GITHUB, PICOCLAW_VERSION

log = logging.getLogger("picoclawd")

INSTALL_PATH = Path("/usr/local/bin/picoclaw")
CONFIG_PATH  = Path.home() / ".picoclaw" / "config.json"


def _arch_suffix() -> str:
    """Map platform.machine() to PicoClaw release asset name suffix."""
    m = platform.machine().lower()
    if m in ("aarch64", "arm64"):
        return "arm64"
    if m.startswith("armv7") or m == "armhf":
        return "arm32"
    if "riscv" in m:
        return "riscv64"
    # Fallback to x86_64 for testing
    return "amd64"


def _release_url() -> str:
    arch = _arch_suffix()
    return (
        f"https://github.com/{PICOCLAW_GITHUB}/releases/download/"
        f"{PICOCLAW_VERSION}/picoclaw-linux-{arch}"
    )


def is_installed() -> bool:
    return INSTALL_PATH.exists() and os.access(str(INSTALL_PATH), os.X_OK)


def install(ollama_host: str = "http://localhost:11434",
            timeout: int = 300) -> bool:
    """Download PicoClaw binary and write config. Returns True on success."""
    url = _release_url()
    log.info(f"Downloading PicoClaw from {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClawOS/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        INSTALL_PATH.write_bytes(data)
        INSTALL_PATH.chmod(INSTALL_PATH.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        log.info(f"PicoClaw installed to {INSTALL_PATH}")
        _write_config(ollama_host, timeout)
        return True
    except Exception as e:
        log.error(f"PicoClaw install failed: {e}")
        return False


def _write_config(ollama_host: str, timeout: int):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "provider": "ollama",
        "endpoint": ollama_host,
        "model":    "qwen2.5:1.5b",
        "timeout":  timeout,
        "workspace": str(Path.home() / "clawos" / "workspace" / "nexus_default"),
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    log.info(f"PicoClaw config written to {CONFIG_PATH}")
