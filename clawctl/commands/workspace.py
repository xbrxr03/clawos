"""clawctl workspace — manage workspaces."""
from clawos_core.constants import WORKSPACE_DIR, MEMORY_DIR
from clawctl.ui.banner import success, error, info, table


def run_list():
    print()
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    workspaces = [d.name for d in WORKSPACE_DIR.iterdir() if d.is_dir()]
    if not workspaces:
        info("No workspaces. Create one: clawctl workspace create <name>")
        return
    rows = []
    for ws in workspaces:
        mem_dir = MEMORY_DIR / ws
        mem_count = 0
        if mem_dir.exists():
            try:
                import sqlite3
                from clawos_core.constants import MEMORY_FTS_DB
                db = sqlite3.connect(str(MEMORY_FTS_DB))
                mem_count = db.execute(
                    "SELECT COUNT(*) FROM memories_meta WHERE workspace_id=?", (ws,)
                ).fetchone()[0]
                db.close()
            except Exception:
                pass
        pinned = (mem_dir / "PINNED.md").exists()
        rows.append((ws, str(mem_count) + " memories", "✓" if pinned else "○"))
    table(rows, headers=("workspace", "memory", "pinned"))
    print()


def run_create(name: str):
    print()
    from bootstrap.workspace_init import init_workspace
    ws = init_workspace(name)
    success(f"Created workspace '{name}' at {ws}")
    print()


def run_delete(name: str):
    print()
    if name == "nexus_default":
        error("Cannot delete the default workspace")
        return
    import shutil
    ws_path  = WORKSPACE_DIR / name
    mem_path = MEMORY_DIR / name
    if not ws_path.exists() and not mem_path.exists():
        error(f"Workspace '{name}' not found")
        return
    confirm = input(f"  Delete workspace '{name}' and all its memory? [y/N]: ").strip().lower()
    if confirm != "y":
        info("Cancelled")
        return
    if ws_path.exists():
        shutil.rmtree(ws_path)
    if mem_path.exists():
        shutil.rmtree(mem_path)
    success(f"Deleted workspace '{name}'")
    print()
