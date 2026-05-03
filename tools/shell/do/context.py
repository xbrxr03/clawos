# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS /do — Context collector
================================
Gathers shell context injected into every LLM prompt.
Keeps HOME-relative paths explicit so the model never hallucinates /clawos etc.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional


def _git_branch(cwd: Path) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(cwd), capture_output=True, text=True, timeout=2
        )
        branch = r.stdout.strip()
        return branch if branch and branch != "HEAD" else None
    except (subprocess.SubprocessError, OSError):
        return None


def _git_status_short(cwd: Path) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(cwd), capture_output=True, text=True, timeout=2
        )
        lines = r.stdout.strip().splitlines()
        if not lines:
            return "clean"
        return f"{len(lines)} changed file(s)"
    except (subprocess.SubprocessError, OSError):
        return None


def _recent_files(cwd: Path, limit: int = 5) -> list[str]:
    try:
        entries = sorted(
            [e for e in cwd.iterdir() if e.is_file()],
            key=lambda e: e.stat().st_mtime,
            reverse=True,
        )
        return [e.name for e in entries[:limit]]
    except (OSError, PermissionError):
        return []


def _bash_history(limit: int = 5) -> list[str]:
    """Return last N non-trivial shell commands, excluding claw-do invocations."""
    history_file = Path.home() / ".bash_history"
    if not history_file.exists():
        return []
    try:
        lines = history_file.read_text(errors="replace").splitlines()
        skip_prefixes = ("clawos", "claw", "/do", "python3 -m tools", "history", "clear", "exit")
        seen, result = set(), []
        for line in reversed(lines):
            line = line.strip()
            if not line or line in seen:
                continue
            if any(line.startswith(p) for p in skip_prefixes):
                continue
            seen.add(line)
            result.append(line)
            if len(result) >= limit:
                break
        return list(reversed(result))
    except (OSError, UnicodeDecodeError):
        return []


def _pinned_facts(workspace: str = "jarvis_default") -> str:
    """Read PINNED.md for the active workspace."""
    try:
        from clawos_core.constants import CLAWOS_DIR
        pinned = CLAWOS_DIR / "memory" / workspace / "PINNED.md"
        if pinned.exists():
            content = pinned.read_text().strip()
            # Strip comment lines, return first 300 chars
            lines = [l for l in content.splitlines() if not l.startswith("#")]
            return " | ".join(l.strip() for l in lines if l.strip())[:300]
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def collect_context(workspace: str = "jarvis_default") -> dict:
    """
    Collect all context for the current invocation.
    Returns a dict with string values safe to inject into the LLM prompt.
    """
    home = Path.home()
    cwd  = Path.cwd()

    # Make cwd home-relative if possible — so model uses ~/clawos not /home/user/clawos
    try:
        cwd_display = "~/" + str(cwd.relative_to(home))
    except ValueError:
        cwd_display = str(cwd)

    ctx = {
        "home":                str(home),
        "cwd":                 cwd_display,
        "cwd_absolute":        str(cwd),
        "os":                  "linux",
        "git_branch":          _git_branch(cwd),
        "git_status":          _git_status_short(cwd),
        "recent_files":        _recent_files(cwd),
        "recent_shell_history": _bash_history(),
        "pinned_facts":        _pinned_facts(workspace),
    }

    # Remove None values
    return {k: v for k, v in ctx.items() if v is not None and v != [] and v != ""}


def format_context(ctx: dict) -> str:
    """Format context dict into a readable string for the LLM user message."""
    lines = []
    if ctx.get("home"):
        lines.append(f"Home directory: {ctx['home']}")
    if ctx.get("cwd"):
        lines.append(f"Current directory: {ctx['cwd']}")
    if ctx.get("git_branch"):
        status = f" ({ctx['git_status']})" if ctx.get("git_status") else ""
        lines.append(f"Git: {ctx['git_branch']}{status}")
    if ctx.get("recent_files"):
        lines.append(f"Recent files: {', '.join(ctx['recent_files'][:5])}")
    if ctx.get("recent_shell_history"):
        lines.append(f"Recent commands: {'; '.join(ctx['recent_shell_history'])}")
    if ctx.get("pinned_facts"):
        lines.append(f"Workspace: {ctx['pinned_facts']}")
    return "\n".join(lines)
