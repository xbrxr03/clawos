"""fs.list — list directory contents within workspace."""
import json
from pathlib import Path


def run(target: str, workspace_root: Path) -> str:
    path = _resolve(target, workspace_root)
    if not path.exists():
        return f"[NOT FOUND] {target}"
    if not path.is_dir():
        return f"[ERROR] {target} is not a directory"
    try:
        entries = []
        for item in sorted(path.iterdir()):
            size = item.stat().st_size if item.is_file() else 0
            entries.append({
                "name": item.name,
                "type": "file" if item.is_file() else "dir",
                "size_bytes": size,
            })
        return json.dumps(entries, indent=2)
    except Exception as e:
        return f"[ERROR] Could not list {target}: {e}"


def _resolve(target: str, workspace_root: Path) -> Path:
    p = Path(target)
    if p.is_absolute():
        return p
    return (workspace_root / target).resolve()
