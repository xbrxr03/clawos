# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Idempotent setup-time provisioning helpers owned by setupd.
"""
from __future__ import annotations

import json
import os
import platform as py_platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from clawos_core.constants import PICOCLAW_GITHUB, PICOCLAW_HTTP_TIMEOUT, PICOCLAW_VERSION


def install_openclaw() -> tuple[bool, str]:
    """Delegate to the canonical frameworkd install path."""
    if sys.platform == "win32":
        return False, "OpenClaw install is skipped on Windows"
    from services.frameworkd.service import install_framework
    result = install_framework("openclaw")
    return result["ok"], result["message"]


def install_openclaude() -> tuple[bool, str]:
    if sys.platform == "win32":
        return False, "OpenClaude install is skipped on Windows during setup"

    npm = shutil.which("npm")
    if not npm:
        return False, "npm not found - skipping OpenClaude"

    try:
        subprocess.run(
            [npm, "install", "-g", "@gitlawb/openclaude"],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        return False, f"OpenClaude install failed: {detail}"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"OpenClaude install failed: {exc}"

    env_path = Path.home() / ".clawos_dev_env"
    env_path.write_text(
        "\n".join(
            [
                "# OpenClaude - open-source Claude Code, powered by local Ollama",
                "export CLAUDE_CODE_USE_OPENAI=1",
                "export OPENAI_BASE_URL=http://localhost:11434/v1",
                "export OPENAI_MODEL=qwen2.5-coder:7b",
                "",
            ]
        ),
        encoding="utf-8",
    )

    source_line = 'source "$HOME/.clawos_dev_env" 2>/dev/null'
    for rc_name in (".bashrc", ".zshrc"):
        rc_path = Path.home() / rc_name
        try:
            existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
        except OSError:
            existing = ""
        if source_line in existing:
            continue
        prefix = "\n" if existing and not existing.endswith("\n") else ""
        rc_path.write_text(existing + prefix + source_line + "\n", encoding="utf-8")

    return True, "OpenClaude installed - run: openclaude"


def install_picoclaw() -> tuple[bool, str]:
    if sys.platform == "win32":
        return False, "PicoClaw install is skipped on Windows during setup"
    if sys.platform == "darwin":
        return False, "PicoClaw install is skipped on macOS - only Linux release binaries are published today"
    if shutil.which("picoclaw"):
        _write_picoclaw_config()
        return True, "PicoClaw already installed and configured"

    arch = _picoclaw_arch(py_platform.machine())
    url = (
        f"https://github.com/{PICOCLAW_GITHUB}/releases/download/"
        f"{PICOCLAW_VERSION}/picoclaw_Linux_{arch}.tar.gz"
    )

    try:
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            with urllib.request.urlopen(url, timeout=PICOCLAW_HTTP_TIMEOUT) as response:
                shutil.copyfileobj(response, tmp)
            archive_path = Path(tmp.name)

        install_dir = Path.home() / ".local" / "bin"
        install_dir.mkdir(parents=True, exist_ok=True)
        destination = install_dir / "picoclaw"

        with tarfile.open(archive_path, "r:gz") as archive:
            member = next((item for item in archive.getmembers() if item.name.endswith("picoclaw")), None)
            if member is None:
                return False, "PicoClaw archive did not contain the picoclaw binary"
            with archive.extractfile(member) as source, destination.open("wb") as target:
                if source is None:
                    return False, "PicoClaw archive could not be extracted"
                shutil.copyfileobj(source, target)
        destination.chmod(0o755)
    except (OSError, ConnectionRefusedError, TimeoutError) as exc:
        return False, f"PicoClaw download failed: {exc}"
    finally:
        try:
            archive_path.unlink(missing_ok=True)  # type: ignore[name-defined]
        except (OSError, ValueError):
            pass

    _write_picoclaw_config()
    return True, f"PicoClaw installed to {destination}"


def _write_picoclaw_config():
    config_dir = Path.home() / ".picoclaw"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "ollama",
                "endpoint": "http://localhost:11434",
                "model": "qwen2.5:3b",
                "timeout": 300,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _ensure_local_bin_export():
    line = 'export PATH="$HOME/.local/bin:$PATH"'
    for rc_name in (".bashrc", ".zshrc", ".profile", ".zprofile"):
        rc_path = Path.home() / rc_name
        try:
            existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
        except OSError:
            existing = ""
        if line in existing:
            continue
        prefix = "\n" if existing and not existing.endswith("\n") else ""
        rc_path.write_text(existing + prefix + line + "\n", encoding="utf-8")


def _picoclaw_arch(machine: str) -> str:
    value = (machine or "").lower()
    if value in {"armv7l", "armv8l", "armhf"}:
        return "armv7"
    if value in {"aarch64", "arm64"}:
        return "arm64"
    if value == "riscv64":
        return "riscv64"
    return "x86_64"
