# SPDX-License-Identifier: AGPL-3.0-or-later
"""Small git helpers for repo-aware commands."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


def _repo_path(repo: Path | str) -> Path:
    return Path(repo).resolve()


def safe_git_command(args: Sequence[str], *, repo: Path | str) -> list[str]:
    repo_path = _repo_path(repo)
    return ["git", "-c", f"safe.directory={repo_path.as_posix()}", *args]


def git_check_output(
    args: Sequence[str],
    *,
    repo: Path | str,
    cwd: Path | str | None = None,
    text: bool = True,
) -> str:
    repo_path = _repo_path(repo)
    run_cwd = Path(cwd).resolve() if cwd is not None else repo_path
    return subprocess.check_output(safe_git_command(args, repo=repo_path), cwd=str(run_cwd), text=text)
