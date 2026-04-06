"""
Desktop integration helpers for ClawOS Command Center.
"""
from __future__ import annotations

import os
import plistlib
from pathlib import Path
from typing import Any

from clawos_core.constants import CLAWOS_DIR, CONFIG_DIR, LOGS_DIR, SUPPORT_DIR, WORKSPACE_DIR
from clawos_core.platform import is_linux, is_macos, launch_agents_dir, platform_key, preferred_shell_path_entries

COMMAND_CENTER_LABEL = "io.clawos.command-center"
COMMAND_CENTER_DESKTOP_FILE = "clawos-command-center.desktop"


def linux_autostart_dir() -> Path:
    return Path.home() / ".config" / "autostart"


def command_center_command() -> str:
    return os.environ.get("CLAWOS_COMMAND_CENTER_CMD", "clawos-command-center").strip() or "clawos-command-center"


def desktop_paths() -> dict[str, str]:
    return {
        "clawos": str(CLAWOS_DIR),
        "config": str(CONFIG_DIR),
        "logs": str(LOGS_DIR),
        "support": str(SUPPORT_DIR),
        "workspace": str(WORKSPACE_DIR),
    }


def autostart_supported() -> bool:
    return is_linux() or is_macos()


def autostart_kind() -> str:
    if is_macos():
        return "launchagent"
    if is_linux():
        return "autostart-desktop"
    return "unsupported"


def launch_on_login_path() -> Path:
    if is_macos():
        return launch_agents_dir() / f"{COMMAND_CENTER_LABEL}.plist"
    return linux_autostart_dir() / COMMAND_CENTER_DESKTOP_FILE


def launch_on_login_enabled() -> bool:
    return launch_on_login_path().exists()


def _linux_desktop_entry(exec_command: str) -> str:
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Version=1.0",
            "Name=ClawOS Command Center",
            "Comment=Open the ClawOS command center at login",
            f"Exec={exec_command}",
            "Terminal=false",
            "X-GNOME-Autostart-enabled=true",
            "StartupNotify=true",
        ]
    ) + "\n"


def enable_launch_on_login(exec_command: str | None = None) -> Path:
    if not autostart_supported():
        raise RuntimeError(f"launch on login is not supported on {platform_key()}")

    exec_command = (exec_command or command_center_command()).strip()
    path = launch_on_login_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if is_macos():
        env = {
            "PATH": ":".join(preferred_shell_path_entries()),
            "CLAWOS_DIR": str(CLAWOS_DIR),
        }
        plist = {
            "Label": COMMAND_CENTER_LABEL,
            "ProgramArguments": ["/bin/sh", "-lc", exec_command],
            "EnvironmentVariables": env,
            "RunAtLoad": True,
            "KeepAlive": False,
            "LimitLoadToSessionType": ["Aqua"],
        }
        with open(path, "wb") as handle:
            plistlib.dump(plist, handle, sort_keys=False)
        return path

    path.write_text(_linux_desktop_entry(exec_command), encoding="utf-8")
    return path


def disable_launch_on_login() -> bool:
    path = launch_on_login_path()
    if not path.exists():
        return False
    path.unlink()
    return True


def desktop_posture() -> dict[str, Any]:
    path = launch_on_login_path()
    return {
        "platform": platform_key(),
        "autostart_kind": autostart_kind(),
        "launch_on_login_supported": autostart_supported(),
        "launch_on_login_enabled": path.exists(),
        "launch_on_login_path": str(path),
        "command_center_command": command_center_command(),
        "paths": desktop_paths(),
    }
