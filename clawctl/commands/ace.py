# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl ace commands — ACE self-improving loop (LEARNED.md) management."""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ACE_PAUSED_FLAG = Path.home() / ".claw" / "ace_paused"


def _learned_path(workspace: str) -> Path:
    return Path.home() / ".claw" / "workspaces" / workspace / "LEARNED.md"


def _pause_flag(workspace: str) -> Path:
    return Path.home() / ".claw" / "workspaces" / workspace / ".ace_paused"


def run_status(workspace: str) -> None:
    learned = _learned_path(workspace)
    paused = _pause_flag(workspace).exists()

    print(f"\n  ACE Status  (workspace: {workspace})\n")
    if not learned.exists():
        print("  LEARNED.md  not found — no entries written yet")
    else:
        size = learned.stat().st_size
        mtime = learned.stat().st_mtime
        lines = learned.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        entries = [l for l in lines if l.startswith("[")]
        print(f"  File:      {learned}")
        print(f"  Size:      {size:,} bytes")
        print(f"  Entries:   {len(entries)}")
        print(f"  Last write: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))}")

    print(f"  ACE writes: {'PAUSED ⏸' if paused else 'ACTIVE ▶'}")
    print()


def run_show(workspace: str) -> None:
    learned = _learned_path(workspace)
    if not learned.exists():
        print("(LEARNED.md is empty — no entries written yet)")
        return
    content = learned.read_text(encoding="utf-8", errors="ignore")
    print(content if content.strip() else "(empty)")


def run_clear(workspace: str, confirm: bool = True) -> None:
    learned = _learned_path(workspace)
    if not learned.exists():
        print("LEARNED.md is already empty.")
        return
    if confirm:
        try:
            import click
            if not click.confirm(f"Clear LEARNED.md for workspace '{workspace}'? This cannot be undone."):
                print("Aborted.")
                return
        except ImportError:
            ans = input("Clear LEARNED.md? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                return
    # Write the template header back
    learned.write_text(
        "# LEARNED.md — ACE Self-Improving Loop\n"
        "# Nexus writes learnings here after completing tasks.\n"
        "# These are injected into every conversation turn.\n"
        "# Max 2KB (4KB on Tier D). Oldest entries pruned automatically.\n",
        encoding="utf-8",
    )
    print("✓ LEARNED.md cleared")


def run_pause(workspace: str) -> None:
    flag = _pause_flag(workspace)
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
    print(f"⏸ ACE writes paused for workspace '{workspace}'")
    print("  Resume with: clawctl ace resume")


def run_resume(workspace: str) -> None:
    flag = _pause_flag(workspace)
    if flag.exists():
        flag.unlink()
    print(f"▶ ACE writes resumed for workspace '{workspace}'")
