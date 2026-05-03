# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Desktop tools — clipboard, paste, type, screenshot, hotkeys.

Wraps services/desktopd's HTTP API (PORT_DESKTOPD) so we don't reimplement
cross-platform input. Falls back to direct subprocess calls on Linux when
desktopd isn't reachable, so simple operations still work in CLI-only setups.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import shutil
import subprocess
from pathlib import Path

import httpx

from clawos_core.constants import PORT_DESKTOPD
from clawos_core.platform import is_linux, is_macos
from runtimes.agent.tools.system import _run  # type: ignore

log = logging.getLogger("agent.tools.desktop")

DESKTOPD_URL = f"http://127.0.0.1:{PORT_DESKTOPD}"


# ── desktopd HTTP helper ─────────────────────────────────────────────────────

async def _desktopd_action(payload: dict, timeout: float = 5.0) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(f"{DESKTOPD_URL}/api/v1/action", json=payload)
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, OSError, ConnectionError) as e:
        log.debug(f"desktopd unreachable, will fall back: {e}")
        return None


# ── clipboard ────────────────────────────────────────────────────────────────

async def set_clipboard(args: dict, ctx: dict) -> str:
    text = str(args.get("text", ""))
    # Try desktopd first
    r = await _desktopd_action({"type": "clipboard_set", "text": text})
    if r and r.get("success"):
        return f"[OK] clipboard set ({len(text)} chars)"
    # Fallback: pyperclip → xclip / wl-copy / pbcopy
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"[OK] clipboard set ({len(text)} chars)"
    except (ImportError, OSError):
        log.debug("pyperclip copy failed, trying CLI fallback")
        pass
    if is_linux():
        if shutil.which("wl-copy"):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(["wl-copy"], input=text.encode(), timeout=5),
            )
            return f"[OK] clipboard set ({len(text)} chars)"
        if shutil.which("xclip"):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(), timeout=5,
                ),
            )
            return f"[OK] clipboard set ({len(text)} chars)"
    if is_macos():
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(["pbcopy"], input=text.encode(), timeout=5),
        )
        return f"[OK] clipboard set ({len(text)} chars)"
    return "[ERROR] no clipboard backend (install pyperclip, xclip, wl-copy, or pbcopy)"


async def get_clipboard(args: dict, ctx: dict) -> str:
    r = await _desktopd_action({"type": "clipboard_get"})
    if r and r.get("success"):
        return r.get("content", "") or "(empty)"
    try:
        import pyperclip
        text = pyperclip.paste()
        return text or "(empty)"
    except (ImportError, OSError):
        log.debug("pyperclip paste failed, trying CLI fallback")
        pass
    if is_linux():
        if shutil.which("wl-paste"):
            rc, out, _ = await _run(["wl-paste"])
            if rc == 0:
                return out or "(empty)"
        if shutil.which("xclip"):
            rc, out, _ = await _run(["xclip", "-selection", "clipboard", "-o"])
            if rc == 0:
                return out or "(empty)"
    if is_macos():
        rc, out, _ = await _run(["pbpaste"])
        if rc == 0:
            return out or "(empty)"
    return "[ERROR] no clipboard backend"


# ── paste / type into focused app ────────────────────────────────────────────

async def paste_to_app(args: dict, ctx: dict) -> str:
    """
    Send Ctrl/Cmd-V to the focused app. If args['app'] is given, focus that
    app first.
    """
    app = (args.get("app") or "").strip()
    if app:
        from runtimes.agent.tools.system import focus_window
        focus = await focus_window({"name": app}, ctx)
        if focus.startswith("[ERROR]"):
            return focus
        # Tiny wait to give the WM time to actually focus
        await asyncio.sleep(0.25)

    modifier = "cmd" if is_macos() else "ctrl"
    r = await _desktopd_action({"type": "hotkey", "keys": [modifier, "v"]})
    if r and r.get("success"):
        return f"[OK] pasted into {app or 'focused app'}"

    # Fallback: xdotool / wtype on Linux
    if is_linux():
        if shutil.which("xdotool"):
            rc, _, err = await _run(["xdotool", "key", "ctrl+v"])
            if rc == 0:
                return f"[OK] pasted into {app or 'focused app'}"
        if shutil.which("wtype"):
            rc, _, _ = await _run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"])
            if rc == 0:
                return f"[OK] pasted into {app or 'focused app'}"
    return "[ERROR] no input backend (need desktopd, xdotool, or wtype)"


async def type_in_app(args: dict, ctx: dict) -> str:
    text = str(args.get("text", ""))
    if not text:
        return "[ERROR] text required"
    r = await _desktopd_action({"type": "type", "text": text}, timeout=15.0)
    if r and r.get("success"):
        return f"[OK] typed {len(text)} chars"
    if is_linux():
        if shutil.which("xdotool"):
            rc, _, _ = await _run(["xdotool", "type", "--delay", "10", text])
            if rc == 0:
                return f"[OK] typed {len(text)} chars"
        if shutil.which("wtype"):
            rc, _, _ = await _run(["wtype", text])
            if rc == 0:
                return f"[OK] typed {len(text)} chars"
    return "[ERROR] no input backend"


# ── screenshot ───────────────────────────────────────────────────────────────

async def screenshot(args: dict, ctx: dict) -> str:
    """Save a screenshot under the workspace's screenshots/ dir; return path."""
    ws_root: Path = ctx.get("ws_root") or Path.home() / "clawos" / "workspace" / "default"
    out_dir = ws_root / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    from clawos_core.util.time import now_stamp
    out_path = out_dir / f"shot-{now_stamp()}.png"

    # Try desktopd
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{DESKTOPD_URL}/api/v1/screenshot")
            if r.status_code == 200 and r.content:
                out_path.write_bytes(r.content)
                return f"[OK] screenshot saved: {out_path}"
    except (httpx.HTTPError, OSError, ConnectionError):
        log.debug("desktopd screenshot failed, trying fallback")
        pass

    # Linux fallbacks
    if is_linux():
        if shutil.which("grim"):  # Wayland
            rc, _, _ = await _run(["grim", str(out_path)])
            if rc == 0: return f"[OK] screenshot saved: {out_path}"
        if shutil.which("gnome-screenshot"):
            rc, _, _ = await _run(["gnome-screenshot", "-f", str(out_path)])
            if rc == 0: return f"[OK] screenshot saved: {out_path}"
        if shutil.which("scrot"):
            rc, _, _ = await _run(["scrot", str(out_path)])
            if rc == 0: return f"[OK] screenshot saved: {out_path}"
    if is_macos():
        rc, _, _ = await _run(["screencapture", "-x", str(out_path)])
        if rc == 0: return f"[OK] screenshot saved: {out_path}"

    return "[ERROR] no screenshot backend"
