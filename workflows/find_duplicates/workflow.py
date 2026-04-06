# SPDX-License-Identifier: AGPL-3.0-or-later
"""find-duplicates - find duplicate files via content hash."""

from __future__ import annotations

import hashlib
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import format_bytes, iter_files, parse_bool

META = WorkflowMeta(
    id="find-duplicates",
    name="Find Duplicates",
    category="files",
    description="Find duplicate files via content hash, output report, optionally delete",
    tags=["files", "cleanup", "duplicates"],
    requires=[],
    destructive=True,
    platforms=["linux", "macos", "windows"],
    needs_agent=False,
    timeout_s=120,
)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


async def run(args: dict, agent) -> WorkflowResult:
    try:
        target = Path(args.get("dir") or Path.home()).expanduser().resolve()
        delete = parse_bool(args.get("delete"))
        max_files = max(1, int(args.get("max_files") or 10000))

        if not target.exists():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Directory not found: {target}")

        size_groups: dict[int, list[Path]] = {}
        file_count = 0
        for file_path in iter_files(target, skip_dirs={"node_modules", "__pycache__", ".git", ".venv", "venv"}, max_files=max_files):
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            size_groups.setdefault(size, []).append(file_path)
            file_count += 1

        hash_groups: dict[str, list[Path]] = {}
        for size, files in size_groups.items():
            if len(files) < 2:
                continue
            for file_path in files:
                try:
                    digest = _hash_file(file_path)
                except OSError:
                    continue
                hash_groups.setdefault(f"{size}:{digest}", []).append(file_path)

        duplicates = []
        for key, files in hash_groups.items():
            if len(files) < 2:
                continue
            size = int(key.split(":", 1)[0])
            duplicates.append((size, sorted(files, key=lambda item: str(item))))
        duplicates.sort(key=lambda item: item[0] * (len(item[1]) - 1), reverse=True)

        reclaimed = 0
        removed: list[Path] = []
        removal_errors: list[str] = []
        if delete:
            for size, files in duplicates:
                for duplicate in files[1:]:
                    try:
                        duplicate.unlink()
                        reclaimed += size
                        removed.append(duplicate)
                    except OSError as exc:
                        removal_errors.append(f"{duplicate}: {exc}")
        else:
            reclaimed = sum(size * (len(files) - 1) for size, files in duplicates)

        lines = [
            "**Duplicate File Report**",
            f"- Target: {target}",
            f"- Files scanned: {file_count}",
            f"- Duplicate groups: {len(duplicates)}",
            "",
        ]
        if duplicates:
            lines.append("**Top duplicate groups:**")
            for size, files in duplicates[:10]:
                lines.append(f"- {format_bytes(size)} each  ({len(files)} copies)")
                lines.extend(f"  {path}" for path in files[:6])
                if len(files) > 6:
                    lines.append(f"  ... and {len(files) - 6} more")
        else:
            lines.append("No duplicate groups found.")

        lines.extend(["", "**Action:**"])
        if delete:
            lines.append(f"- Removed {len(removed)} duplicate files.")
        else:
            lines.append("- Dry run only; no files were deleted.")
        if removal_errors:
            lines.append(f"- {len(removal_errors)} deletions failed.")
        if file_count >= max_files:
            lines.append(f"- Scan capped at {max_files} files; rerun with max_files=... for a deeper pass.")
        lines.extend(["", f"Found {len(duplicates)} duplicate groups, ~{format_bytes(reclaimed)} reclaimable."])

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "groups": len(duplicates),
                "files_scanned": file_count,
                "reclaimable_bytes": reclaimed,
                "deleted": len(removed),
                "deletion_errors": len(removal_errors),
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
