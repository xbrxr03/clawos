"""fs.write — write or append to a file within the workspace."""
from pathlib import Path


def run(target: str, content: str, workspace_root: Path, append: bool = False) -> str:
    path = _resolve(target, workspace_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        path.write_text(content) if not append else path.open("a").write(content)
        action = "Appended to" if append else "Written"
        return f"[OK] {action} {target} ({len(content)} chars)"
    except Exception as e:
        return f"[ERROR] Could not write {target}: {e}"


def _resolve(target: str, workspace_root: Path) -> Path:
    p = Path(target)
    if p.is_absolute():
        return p
    return (workspace_root / target).resolve()
