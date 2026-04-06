# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
"""Screen 4 — Workspace setup."""
from clawos_core.constants import CLAWOS_DIR


def run(state) -> bool:
    print("\n  ── Workspace Setup ─────────────────────────────")
    print()
    print(f"  All data stays on this machine at: {CLAWOS_DIR}")
    print()
    print(f"  Default workspace name: nexus_default")
    name = input("  Workspace name [Enter for default]: ").strip()
    if not name:
        name = "nexus_default"

    # Sanitise
    name = name.lower().replace(" ", "_").replace("-", "_")
    name = "".join(c for c in name if c.isalnum() or c == "_")[:32]
    if not name:
        name = "nexus_default"

    state.workspace_id = name

    from bootstrap.workspace_init import init_all_dirs, init_workspace
    init_all_dirs()
    ws = init_workspace(name)
    print(f"\n  Workspace '{name}' created at {ws}")

    # Optional: user name for PINNED.md
    user_name = input("  Your name (for Nexus to remember) [Enter to skip]: ").strip()
    if user_name:
        from clawos_core.util.paths import pinned_path
        p = pinned_path(name)
        current = p.read_text() if p.exists() else ""
        p.write_text(current + f"\n- My name is {user_name}.")
        print(f"  Pinned: 'My name is {user_name}.'")

    state.mark_done("workspace_setup")
    return True
