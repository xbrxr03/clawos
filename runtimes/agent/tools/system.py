# SPDX-License-Identifier: AGPL-3.0-or-later
"""
System tools — open/focus/close apps, volume, system stats, shell.

Linux-first. macOS branches added in Phase 4. Windows in Phase 6.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from clawos_core.platform import is_linux, is_macos, is_windows

log = logging.getLogger("agent.tools.system")

# Shell allowlist mirrors toolbridge SHELL_ALLOWLIST — keep in sync.
_SHELL_ALLOW = [
    re.compile(p) for p in (
        r"^ls(\s|$)", r"^pwd$", r"^echo\s", r"^cat\s", r"^head\s", r"^tail\s",
        r"^wc\s", r"^find\s", r"^grep\s", r"^which\s", r"^whoami$", r"^date$",
        r"^df\s", r"^du\s", r"^uname", r"^hostname$", r"^ps\s",
        r"^python3?\s+[^-]", r"^pip\s", r"^git\s",
    )
]


# ── helpers ──────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    """Run a subprocess in the executor; return (rc, stdout, stderr)."""
    loop = asyncio.get_running_loop()
    def _sync():
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timed out after {timeout}s"
        except FileNotFoundError:
            return 127, "", f"not found: {cmd[0]}"
        except (OSError, subprocess.SubprocessError) as e:
            return 1, "", str(e)
    return await loop.run_in_executor(None, _sync)


def _which(name: str) -> str | None:
    return shutil.which(name)


# ── volume ───────────────────────────────────────────────────────────────────

async def set_volume(args: dict, ctx: dict) -> str:
    """Set output volume 0-100 across PulseAudio / PipeWire / macOS."""
    level = int(args.get("level", 50))
    level = max(0, min(100, level))

    if is_linux():
        # Try pactl (PulseAudio + PipeWire pipewire-pulse)
        if _which("pactl"):
            rc, _, err = await _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
            if rc == 0:
                return f"volume set to {level}%"
            log.debug(f"pactl failed: {err}")
        # Fallback: amixer (ALSA)
        if _which("amixer"):
            rc, _, err = await _run(["amixer", "-q", "sset", "Master", f"{level}%"])
            if rc == 0:
                return f"volume set to {level}%"
        return f"[ERROR] no volume backend (need pactl or amixer)"

    if is_macos():
        rc, _, err = await _run(["osascript", "-e", f"set volume output volume {level}"])
        return f"volume set to {level}%" if rc == 0 else f"[ERROR] {err}"

    if is_windows():
        # Phase 6: nircmd. For now, return a clear stub.
        return "[ERROR] Windows volume control pending Phase 6"

    return "[ERROR] unsupported platform"


async def get_volume(args: dict, ctx: dict) -> str:
    """Read current output volume as 'NN%'."""
    if is_linux():
        if _which("pactl"):
            rc, out, _ = await _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
            if rc == 0:
                # Output like: "Volume: front-left: 32768 /  50% / -18.06 dB,   ..."
                m = re.search(r"(\d{1,3})%", out)
                if m:
                    return f"{m.group(1)}%"
        if _which("amixer"):
            rc, out, _ = await _run(["amixer", "sget", "Master"])
            if rc == 0:
                m = re.search(r"\[(\d{1,3})%\]", out)
                if m:
                    return f"{m.group(1)}%"
        return "[ERROR] no volume backend"

    if is_macos():
        rc, out, _ = await _run(["osascript", "-e", "output volume of (get volume settings)"])
        if rc == 0 and out.isdigit():
            return f"{out}%"
        return "[ERROR] osascript failed"

    return "[ERROR] unsupported platform"


# ── apps ─────────────────────────────────────────────────────────────────────

# Common alias mapping for friendly names → executables
_APP_ALIASES_LINUX = {
    "firefox":     ["firefox", "firefox-esr"],
    "chrome":      ["google-chrome", "chromium", "chromium-browser"],
    "chromium":    ["chromium", "chromium-browser"],
    "vscode":      ["code", "codium", "vscodium"],
    "vs code":     ["code", "codium"],
    "spotify":     ["spotify", "spotify-launcher"],
    "text editor": ["gedit", "gnome-text-editor", "kate", "mousepad", "xed"],
    "notepad":     ["gedit", "gnome-text-editor", "kate", "mousepad", "xed"],
    "files":       ["nautilus", "dolphin", "thunar", "pcmanfm"],
    "file manager":["nautilus", "dolphin", "thunar", "pcmanfm"],
    "terminal":    ["gnome-terminal", "konsole", "xterm", "alacritty", "kitty"],
    "calculator":  ["gnome-calculator", "kcalc", "galculator"],
    "calendar":    ["gnome-calendar", "korganizer"],
}

_APP_ALIASES_MACOS = {
    "firefox":     "Firefox",
    "chrome":      "Google Chrome",
    "vscode":      "Visual Studio Code",
    "vs code":     "Visual Studio Code",
    "spotify":     "Spotify",
    "text editor": "TextEdit",
    "notepad":     "TextEdit",
    "files":       "Finder",
    "file manager":"Finder",
    "terminal":    "Terminal",
    "calculator":  "Calculator",
    "calendar":    "Calendar",
}


async def open_app(args: dict, ctx: dict) -> str:
    """Launch an installed application by name."""
    name = (args.get("name") or "").strip().lower()
    if not name:
        return "[ERROR] app name required"

    if is_linux():
        # Try aliases first, then the literal name
        candidates = _APP_ALIASES_LINUX.get(name, []) + [name, name.replace(" ", "-")]
        for c in candidates:
            bin_path = _which(c)
            if bin_path:
                # Detach so the agent doesn't block on the app's lifetime
                try:
                    subprocess.Popen(
                        [bin_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    return f"opened {c}"
                except (OSError, subprocess.SubprocessError) as e:
                    return f"[ERROR] launch {c}: {e}"
        # Last resort: gtk-launch with .desktop file
        if _which("gtk-launch"):
            for c in candidates:
                rc, _, _ = await _run(["gtk-launch", c])
                if rc == 0:
                    return f"opened {c}"
        return f"[ERROR] app not found: {name}"

    if is_macos():
        target = _APP_ALIASES_MACOS.get(name, name.title())
        rc, _, err = await _run(["open", "-a", target])
        return f"opened {target}" if rc == 0 else f"[ERROR] {err or target + ' not found'}"

    return "[ERROR] unsupported platform"


async def focus_window(args: dict, ctx: dict) -> str:
    """Bring an application's window to the foreground."""
    name = (args.get("name") or "").strip()
    if not name:
        return "[ERROR] app name required"

    if is_linux():
        # Wayland: try swaymsg first
        if os.environ.get("WAYLAND_DISPLAY") and _which("swaymsg"):
            rc, _, _ = await _run(["swaymsg", f'[title="{name}"] focus'])
            if rc == 0:
                return f"focused {name}"
        # X11: wmctrl preferred, xdotool fallback
        if _which("wmctrl"):
            rc, _, _ = await _run(["wmctrl", "-a", name])
            if rc == 0:
                return f"focused {name}"
        if _which("xdotool"):
            rc, _, _ = await _run(
                ["xdotool", "search", "--name", name, "windowactivate"]
            )
            if rc == 0:
                return f"focused {name}"
        return "[ERROR] no window manager helper (need wmctrl, xdotool, or swaymsg)"

    if is_macos():
        # AppleScript activate
        rc, _, err = await _run(["osascript", "-e", f'tell application "{name}" to activate'])
        return f"focused {name}" if rc == 0 else f"[ERROR] {err}"

    return "[ERROR] unsupported platform"


async def close_app(args: dict, ctx: dict) -> str:
    """Close a running application gracefully (SIGTERM)."""
    name = (args.get("name") or "").strip()
    if not name:
        return "[ERROR] app name required"

    if is_linux():
        if _which("pkill"):
            rc, _, _ = await _run(["pkill", "-TERM", "-f", name])
            return f"closed {name}" if rc == 0 else f"[ERROR] no matching process"
        return "[ERROR] pkill not available"

    if is_macos():
        rc, _, err = await _run(["osascript", "-e", f'tell application "{name}" to quit'])
        return f"closed {name}" if rc == 0 else f"[ERROR] {err}"

    return "[ERROR] unsupported platform"


# ── system stats ─────────────────────────────────────────────────────────────

async def system_stats(args: dict, ctx: dict) -> str:
    try:
        import psutil
    except ImportError:
        return "[ERROR] psutil not installed"

    loop = asyncio.get_running_loop()
    def _stats():
        cpu  = psutil.cpu_percent(interval=0.3)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu_pct":      cpu,
            "ram_pct":      ram.percent,
            "ram_used_gb":  round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "disk_pct":     disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
        }
    s = await loop.run_in_executor(None, _stats)
    return (
        f"CPU {s['cpu_pct']}% · "
        f"RAM {s['ram_used_gb']}/{s['ram_total_gb']} GB ({s['ram_pct']}%) · "
        f"Disk {s['disk_free_gb']} GB free ({s['disk_pct']}% used)"
    )


# ── shell ────────────────────────────────────────────────────────────────────

async def run_command(args: dict, ctx: dict) -> str:
    """
    Run an allowlisted shell command. Sensitive — policy queues for approval.
    By the time we get here, policy has already approved.
    """
    cmd = (args.get("command") or "").strip()
    if not cmd:
        return "[ERROR] command required"
    if not any(p.match(cmd) for p in _SHELL_ALLOW):
        return f"[DENIED] command not in allowlist: {cmd.split()[0] if cmd else '?'}"
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return f"[ERROR] parse failed: {e}"
    rc, out, err = await _run(argv, timeout=15.0)
    if rc != 0:
        tail = (err or out)[-400:]
        return f"[exit {rc}] {tail}"
    return out[:2000] if out else "[OK] (no output)"
