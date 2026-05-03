# SPDX-License-Identifier: AGPL-3.0-or-later
"""
File tools — read, write, list, open. Workspace-scoped via ctx['ws_root'].

Open delegates to xdg-open / open(macOS) for files and URLs.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from clawos_core.platform import is_linux, is_macos

log = logging.getLogger("agent.tools.files")


def _resolve(args_path: str, ws_root: Path) -> Path:
    p = Path(args_path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (ws_root / p).resolve()


# ── read / write / list ──────────────────────────────────────────────────────

async def read_file(args: dict, ctx: dict) -> str:
    ws_root: Path = ctx.get("ws_root") or Path.cwd()
    p = _resolve(args.get("path", ""), ws_root)
    if not p.exists():
        return f"[ERROR] not found: {p}"
    if not p.is_file():
        return f"[ERROR] not a file: {p}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError) as e:
        return f"[ERROR] {e}"
    if len(text) > 8000:
        text = text[:8000] + f"\n…[truncated; {len(text)} total chars]"
    return text


async def write_file(args: dict, ctx: dict) -> str:
    """Sensitive — policy queues for approval. By the time we run, approved."""
    ws_root: Path = ctx.get("ws_root") or Path.cwd()
    p = _resolve(args.get("path", ""), ws_root)
    content = str(args.get("content", ""))
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except (OSError, PermissionError) as e:
        return f"[ERROR] {e}"
    return f"[OK] wrote {len(content)} chars to {p}"


async def list_files(args: dict, ctx: dict) -> str:
    ws_root: Path = ctx.get("ws_root") or Path.cwd()
    target = (args.get("path") or "").strip()
    p = ws_root if target in ("", ".", "./") else _resolve(target, ws_root)
    if not p.exists():
        return f"[ERROR] not found: {p}"
    if not p.is_dir():
        return f"[ERROR] not a directory: {p}"
    try:
        entries = sorted(p.iterdir())[:50]
    except (OSError, PermissionError) as e:
        return f"[ERROR] {e}"
    lines = [
        ("/" if e.is_dir() else "") + e.name + (f" ({e.stat().st_size}B)" if e.is_file() else "")
        for e in entries
    ]
    return "\n".join(lines) if lines else "(empty)"


# ── open ─────────────────────────────────────────────────────────────────────

async def _open_path(target: str) -> str:
    loop = asyncio.get_running_loop()
    if is_linux() and shutil.which("xdg-open"):
        def _go():
            subprocess.Popen(
                ["xdg-open", target],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        await loop.run_in_executor(None, _go)
        return f"[OK] opened {target}"
    if is_macos():
        def _go():
            subprocess.Popen(
                ["open", target],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        await loop.run_in_executor(None, _go)
        return f"[OK] opened {target}"
    return "[ERROR] no open backend"


async def open_file(args: dict, ctx: dict) -> str:
    ws_root: Path = ctx.get("ws_root") or Path.cwd()
    p = _resolve(args.get("path", ""), ws_root)
    if not p.exists():
        return f"[ERROR] not found: {p}"
    return await _open_path(str(p))


async def open_url(args: dict, ctx: dict) -> str:
    url = (args.get("url") or "").strip()
    if not url:
        return "[ERROR] url required"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "[ERROR] only http/https URLs allowed"
    # webbrowser.open handles all platforms cleanly
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(None, lambda: webbrowser.open(url, new=2))
    return f"[OK] opened {url}" if ok else "[ERROR] failed to open browser"
