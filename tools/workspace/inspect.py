# SPDX-License-Identifier: AGPL-3.0-or-later
"""
memory.read / memory.write — read and write workspace memory layers.
workspace.inspect — inspect workspace contents.
"""
from pathlib import Path
from clawos_core.util.paths import pinned_path, workflow_path


def memory_read(target: str, workspace_id: str) -> str:
    """Read PINNED.md, WORKFLOW.md, or LEARNED.md for the workspace."""
    layer = target.strip().lower()
    if layer in ("pinned", "pinned.md"):
        p = pinned_path(workspace_id)
        return p.read_text() if p.exists() else "[EMPTY] PINNED.md is empty"
    if layer in ("workflow", "workflow.md"):
        from clawos_core.util.paths import workflow_path
        p = workflow_path(workspace_id)
        return p.read_text() if p.exists() else "[EMPTY] WORKFLOW.md is empty"
    if layer in ("learned", "learned.md"):
        from clawos_core.constants import WORKSPACE_DIR
        p = WORKSPACE_DIR / workspace_id / "LEARNED.md"
        return p.read_text() if p.exists() else "[EMPTY] LEARNED.md is empty"
    # Generic memory search falls through to memd
    return f"[INFO] Use memory.read with: pinned | workflow | learned"


def memory_write(content: str, workspace_id: str) -> str:
    """Append a fact to PINNED.md for permanent memory."""
    p = pinned_path(workspace_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        from clawos_core.util.time import now_stamp
        f.write(f"\n- [{now_stamp()}] {content.strip()}")
    return f"[OK] Remembered: {content[:80]}"


def workspace_inspect(workspace_id: str) -> str:
    """List workspace files and memory layer sizes."""
    from clawos_core.constants import WORKSPACE_DIR
    ws = WORKSPACE_DIR / workspace_id
    if not ws.exists():
        return f"[NOT FOUND] Workspace: {workspace_id}"

    lines = [f"Workspace: {workspace_id}", ""]
    # Files
    files = [f for f in ws.iterdir() if f.is_file()]
    lines.append(f"Files ({len(files)}):")
    for f in sorted(files):
        lines.append(f"  {f.name}  ({f.stat().st_size} bytes)")

    # Memory layers
    lines.append("")
    for name, filename in [("PINNED.md", "PINNED.md"), ("WORKFLOW.md", "WORKFLOW.md"),
                            ("LEARNED.md", "LEARNED.md"), ("HISTORY.md", "HISTORY.md")]:
        p = ws / filename
        if p.exists():
            lines.append(f"  {name}: {p.stat().st_size} bytes")
        else:
            lines.append(f"  {name}: (empty)")

    return "\n".join(lines)
