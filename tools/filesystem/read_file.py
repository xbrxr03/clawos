# SPDX-License-Identifier: AGPL-3.0-or-later
"""fs.read — read a file within the workspace. Max 50KB."""
from pathlib import Path


MAX_BYTES = 50 * 1024


def run(target: str, workspace_root: Path) -> str:
    path = _resolve(target, workspace_root)
    if not path.exists():
        return f"[NOT FOUND] {target}"
    if not path.is_file():
        return f"[ERROR] {target} is not a file"
    size = path.stat().st_size
    if size > MAX_BYTES:
        return f"[ERROR] File too large ({size // 1024}KB). Max 50KB. Use fs.search to find specific content."
    try:
        return path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError) as e:
        return f"[ERROR] Could not read {target}: {e}"


def _resolve(target: str, workspace_root: Path) -> Path:
    p = Path(target)
    if p.is_absolute():
        return p
    return (workspace_root / target).resolve()
