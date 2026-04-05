from __future__ import annotations

import os
from collections import deque
from pathlib import Path
from typing import Iterable


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in TRUE_VALUES


def format_bytes(size: int | float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(max(size, 0))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024
    return "0B"


def tail_lines(path: Path, count: int) -> list[str]:
    maxlen = max(1, count)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n") for line in deque(handle, maxlen=maxlen)]


def iter_files(root: Path, skip_dirs: set[str] | None = None, max_files: int | None = None) -> Iterable[Path]:
    skip_dirs = skip_dirs or set()
    seen = 0
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames
            if name not in skip_dirs and not name.startswith(".")
        ]
        for filename in filenames:
            path = Path(current_root) / filename
            try:
                if path.is_symlink() or not path.is_file():
                    continue
            except OSError:
                continue
            yield path
            seen += 1
            if max_files is not None and seen >= max_files:
                return
