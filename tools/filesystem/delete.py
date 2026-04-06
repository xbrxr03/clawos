# SPDX-License-Identifier: AGPL-3.0-or-later
"""fs.delete — delete a file or empty directory. Requires policyd score 70+."""
from pathlib import Path


def run(target: str, workspace_root: Path) -> str:
    path = _resolve(target, workspace_root)
    if not path.exists():
        return f"[NOT FOUND] {target}"
    try:
        if path.is_file():
            path.unlink()
            return f"[OK] Deleted file: {target}"
        elif path.is_dir():
            path.rmdir()   # only succeeds if empty
            return f"[OK] Deleted directory: {target}"
        return f"[ERROR] Unknown file type: {target}"
    except OSError as e:
        return f"[ERROR] {e}"


def _resolve(target: str, workspace_root: Path) -> Path:
    p = Path(target)
    if p.is_absolute():
        return p
    return (workspace_root / target).resolve()
