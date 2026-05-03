# SPDX-License-Identifier: AGPL-3.0-or-later
"""clean-empty-dirs - recursively find and optionally remove empty directories."""

from __future__ import annotations

import os
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import parse_bool

META = WorkflowMeta(
    id="clean-empty-dirs",
    name="Clean Empty Dirs",
    category="files",
    description="Recursively find and remove empty directories",
    tags=["files", "cleanup"],
    requires=[],
    destructive=True,
    platforms=["linux", "macos", "windows"],
    needs_agent=False,
    timeout_s=60,
)


async def run(args: dict, agent) -> WorkflowResult:
    try:
        target = Path(args.get("dir") or Path.home()).expanduser().resolve()
        dry_run = parse_bool(args.get("dry_run"))

        if not target.exists():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Directory not found: {target}")

        empty_dirs: list[Path] = []
        removed = 0
        for root, dirnames, _ in os.walk(target, topdown=False):
            for dirname in dirnames:
                candidate = Path(root) / dirname
                try:
                    if any(candidate.iterdir()):
                        continue
                except (OSError, PermissionError):
                    continue
                empty_dirs.append(candidate)
                if not dry_run:
                    try:
                        candidate.rmdir()
                        removed += 1
                    except OSError:
                        continue

        empty_dirs.sort(key=lambda item: str(item))
        lines = [
            "**Empty Directory Report**",
            f"- Target: {target}",
            f"- Found: {len(empty_dirs)}",
        ]
        if dry_run:
            lines.append("- Mode: dry run")
        else:
            lines.append(f"- Removed: {removed}")

        if empty_dirs:
            lines.extend(["", "**Directories:**"])
            lines.extend(f"- {path}" for path in empty_dirs[:25])
            if len(empty_dirs) > 25:
                lines.append(f"- ... and {len(empty_dirs) - 25} more")
        else:
            lines.extend(["", "No empty directories found."])

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={"found": len(empty_dirs), "removed": removed, "dry_run": dry_run},
        )
    except (RuntimeError, OSError, TypeError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
