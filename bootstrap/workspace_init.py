# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Initialise a workspace — create dirs, seed SOUL/AGENTS/PINNED/HEARTBEAT.
Called once at bootstrap and optionally from wizard.
"""
from pathlib import Path
from clawos_core.constants import CLAWOS_DIR
from clawos_core.util.paths import (
    workspace_path, memory_path,
    pinned_path, soul_path, agents_path, heartbeat_path, identity_path
)

PRESETS = Path(__file__).parent.parent / "data" / "presets" / "workspaces" / "default"


def _copy_if_missing(src: Path, dst: Path):
    if not dst.exists() and src.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return True
    return False


def init_workspace(workspace_id: str = "nexus_default") -> Path:
    """Create workspace, seed template files. Idempotent."""
    ws   = workspace_path(workspace_id)
    mem  = memory_path(workspace_id)

    # Seed personality + instructions
    _copy_if_missing(PRESETS / "SOUL.md",      soul_path(workspace_id))
    _copy_if_missing(PRESETS / "AGENTS.md",    agents_path(workspace_id))
    _copy_if_missing(PRESETS / "HEARTBEAT.md", heartbeat_path(workspace_id))
    _copy_if_missing(PRESETS / "IDENTITY.md",  identity_path(workspace_id))

    # PINNED.md — blank if not present
    p = pinned_path(workspace_id)
    if not p.exists():
        p.write_text(
            "# Pinned Facts\n# Add permanent facts here - Nexus always reads this.\n",
            encoding="utf-8",
        )

    return ws


def init_all_dirs():
    """Create all ClawOS runtime directories."""
    dirs = [
        CLAWOS_DIR / "config",
        CLAWOS_DIR / "logs",
        CLAWOS_DIR / "memory",
        CLAWOS_DIR / "workspace",
        CLAWOS_DIR / "voice",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
