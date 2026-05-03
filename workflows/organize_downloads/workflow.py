# SPDX-License-Identifier: AGPL-3.0-or-later
"""organize-downloads - sort a directory into predictable content folders."""

from __future__ import annotations

from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus, emit_workflow_progress
from workflows.helpers import SUPPORTED_PLATFORMS, format_bytes, parse_bool

CATEGORY_RULES: list[tuple[str, set[str]]] = [
    ("Images", {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".svg"}),
    ("Documents", {".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".csv", ".pptx"}),
    ("Archives", {".zip", ".tar", ".gz", ".7z", ".rar", ".bz2"}),
    ("Code", {".py", ".js", ".ts", ".tsx", ".sh", ".json", ".yaml", ".yml", ".html", ".css"}),
    ("Videos", {".mp4", ".mov", ".avi", ".mkv", ".wmv"}),
    ("Audio", {".mp3", ".wav", ".flac", ".m4a", ".ogg"}),
]
NOISY_FILENAMES = {".ds_store", ".localized", "desktop.ini", "thumbs.db"}

META = WorkflowMeta(
    id="organize-downloads",
    name="Organize Downloads",
    category="files",
    description="Sort a Downloads folder into Images, Documents, Archives, Code, Video, Audio, and Other",
    tags=["files", "cleanup", "beginner"],
    requires=[],
    destructive=False,
    platforms=SUPPORTED_PLATFORMS,
    needs_agent=False,
    timeout_s=120,
)


def _category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    for name, extensions in CATEGORY_RULES:
        if suffix in extensions:
            return name
    return "Other"


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _sorted_categories(counts: dict[str, int]) -> list[str]:
    ordered = [name for name, _extensions in CATEGORY_RULES] + ["Other"]
    return [name for name in ordered if counts.get(name, 0)]


def _skip_reason(path: Path) -> str | None:
    lowered = path.name.lower()
    if lowered in NOISY_FILENAMES:
        return "system"
    if path.name.startswith("."):
        return "hidden"
    try:
        if path.is_symlink():
            return "symlink"
    except OSError:
        return "unreadable"
    return None


def _category_totals(moves: list[tuple[Path, Path, str, int]]) -> tuple[dict[str, int], dict[str, int], int]:
    counts: dict[str, int] = {}
    sizes: dict[str, int] = {}
    total_bytes = 0
    for _source, _destination, category, size_bytes in moves:
        counts[category] = counts.get(category, 0) + 1
        sizes[category] = sizes.get(category, 0) + size_bytes
        total_bytes += size_bytes
    return counts, sizes, total_bytes


def _move_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)


async def run(args: dict, agent) -> WorkflowResult:
    try:
        await emit_workflow_progress(
            "Checking the target folder",
            phase="validate",
            progress=8,
        )
        target = Path(args.get("target_dir") or Path.home() / "Downloads").expanduser().resolve()
        dry_run = parse_bool(args.get("dry_run"))

        if not target.exists():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Directory not found: {target}")
        if not target.is_dir():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Not a directory: {target}")

        await emit_workflow_progress(
            "Scanning loose files in Downloads",
            phase="scan",
            progress=24,
        )
        files: list[Path] = []
        skipped_files: list[dict[str, str]] = []
        for path in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            reason = _skip_reason(path)
            if reason:
                skipped_files.append({"name": path.name, "reason": reason})
                continue
            try:
                if not path.is_file():
                    continue
            except OSError:
                skipped_files.append({"name": path.name, "reason": "unreadable"})
                continue
            files.append(path)

        if not files:
            skipped_suffix = ""
            if skipped_files:
                skipped_suffix = f" Ignored {len(skipped_files)} hidden/system/symlink files."
            return WorkflowResult(
                status=WorkflowStatus.OK,
                output=f"No eligible loose files found in {target}; nothing to organize.{skipped_suffix}",
                metadata={
                    "target": str(target),
                    "files_moved": 0,
                    "files_planned": 0,
                    "files_failed": 0,
                    "files_skipped": len(skipped_files),
                    "folders_created": 0,
                    "dry_run": dry_run,
                    "skipped_files": skipped_files,
                },
            )

        await emit_workflow_progress(
            f"Classifying {len(files)} files into tidy folders",
            phase="plan",
            progress=46,
        )
        planned_moves: list[tuple[Path, Path, str, int]] = []
        folders_created: set[str] = set()
        shadow_destinations: set[Path] = set()

        for source in files:
            category = _category_for(source)
            destination_dir = target / category
            destination = _unique_destination(destination_dir / source.name)
            while destination in shadow_destinations:
                destination = _unique_destination(destination.with_name(f"{destination.stem}-copy{destination.suffix}"))
            try:
                size_bytes = max(0, source.stat().st_size)
            except OSError:
                size_bytes = 0
            planned_moves.append((source, destination, category, size_bytes))
            folders_created.add(category)
            shadow_destinations.add(destination)

        planned_category_counts, planned_category_bytes, planned_total_bytes = _category_totals(planned_moves)
        completed_moves: list[tuple[Path, Path, str, int]] = []
        failed_moves: list[dict[str, str | int]] = []

        if not dry_run:
            await emit_workflow_progress(
                "Moving files into their new folders",
                phase="apply",
                progress=72,
            )
            halfway = max(1, len(planned_moves) // 2)
            for index, (source, destination, category, size_bytes) in enumerate(planned_moves, start=1):
                try:
                    _move_file(source, destination)
                    completed_moves.append((source, destination, category, size_bytes))
                except OSError as exc:
                    failed_moves.append(
                        {
                            "name": source.name,
                            "category": category,
                            "destination": f"{category}/{destination.name}",
                            "error": str(exc),
                            "size_bytes": size_bytes,
                        }
                    )
                if index == halfway and len(planned_moves) > 2:
                    await emit_workflow_progress(
                        "Halfway through the file moves",
                        phase="apply",
                        progress=84,
                    )
        else:
            completed_moves = list(planned_moves)

        await emit_workflow_progress(
            "Building the organization summary",
            phase="summary",
            progress=92,
        )

        category_counts, category_bytes, total_bytes = _category_totals(completed_moves)
        ordered_categories = _sorted_categories(category_counts)
        category_lines = [
            f"- {category}: {category_counts[category]} files | {format_bytes(category_bytes.get(category, 0))}"
            for category in ordered_categories
        ]
        largest_moves = sorted(completed_moves, key=lambda item: (-item[3], item[0].name.lower()))[:5]
        sample_moves = completed_moves[:8]
        files_planned = len(planned_moves)
        files_moved = len(completed_moves)
        files_failed = len(failed_moves)
        status = WorkflowStatus.OK if files_failed == 0 else WorkflowStatus.FAILED

        if dry_run:
            outcome = (
                f"- Outcome: {files_planned} files across {len(folders_created)} folders"
                f" | {format_bytes(total_bytes)} total"
            )
        else:
            outcome = (
                f"- Outcome: moved {files_moved} of {files_planned} eligible files"
                f" into {len(folders_created)} folders | {format_bytes(total_bytes)} moved"
            )

        lines = [
            "**Downloads Command Center**",
            f"- Target: {target}",
            f"- Mode: {'preview only (dry run)' if dry_run else 'applied live'}",
            outcome,
            f"- Ignored before planning: {len(skipped_files)} files",
            f"- Files that could not move: {files_failed if not dry_run else 0}",
            "",
            "**Category breakdown:**",
        ]
        if category_lines:
            lines.extend(category_lines)
        else:
            lines.append("- No files were moved into category folders.")
        lines.extend(
            [
                "",
                "**Largest items:**",
            ]
        )
        if largest_moves:
            lines.extend(
                f"- {source.name} -> {category}/{destination.name} ({format_bytes(size_bytes)})"
                for source, destination, category, size_bytes in largest_moves
            )
        else:
            lines.append("- No file sizes were available.")
        lines.extend(
            [
                "",
                "**Move preview:**" if dry_run else "**Completed moves:**",
            ]
        )
        if sample_moves:
            lines.extend(
                f"- {source.name} -> {category}/{destination.name}"
                for source, destination, category, _size_bytes in sample_moves
            )
            if len(completed_moves) > len(sample_moves):
                lines.append(f"- ... and {len(completed_moves) - len(sample_moves)} more")
        else:
            lines.append("- No files were moved.")
        if failed_moves:
            lines.extend(
                [
                    "",
                    "**Failed moves:**",
                ]
            )
            lines.extend(
                f"- {item['name']} -> {item['destination']} ({item['error']})"
                for item in failed_moves[:8]
            )
            if len(failed_moves) > 8:
                lines.append(f"- ... and {len(failed_moves) - 8} more")
        if skipped_files:
            lines.extend(
                [
                    "",
                    "**Ignored files:**",
                ]
            )
            lines.extend(
                f"- {item['name']} ({item['reason']})"
                for item in skipped_files[:8]
            )
            if len(skipped_files) > 8:
                lines.append(f"- ... and {len(skipped_files) - 8} more")
        lines.extend(
            [
                "",
                (
                    "**Next step:** Review the preview, then rerun with dry run off to apply it."
                    if dry_run
                    else (
                        "**Next step:** Rerun after closing or unlocking the failed files."
                        if failed_moves
                        else "**Next step:** Open the folders above to confirm everything landed where you expect."
                    )
                ),
            ]
        )

        return WorkflowResult(
            status=status,
            output="\n".join(lines),
            metadata={
                "target": str(target),
                "files_moved": files_moved,
                "files_planned": files_planned,
                "files_failed": files_failed,
                "files_skipped": len(skipped_files),
                "folders_created": len(folders_created),
                "dry_run": dry_run,
                "total_bytes": total_bytes,
                "category_counts": category_counts,
                "category_bytes": category_bytes,
                "planned_total_bytes": planned_total_bytes,
                "planned_category_counts": planned_category_counts,
                "planned_category_bytes": planned_category_bytes,
                "largest_moves": [
                    {
                        "name": source.name,
                        "category": category,
                        "destination": f"{category}/{destination.name}",
                        "size_bytes": size_bytes,
                    }
                    for source, destination, category, size_bytes in largest_moves
                ],
                "sample_moves": [
                    {
                        "name": source.name,
                        "category": category,
                        "destination": f"{category}/{destination.name}",
                    }
                    for source, destination, category, _size_bytes in sample_moves
                ],
                "failed_moves": failed_moves,
                "skipped_files": skipped_files,
            },
            error=(
                None
                if files_failed == 0
                else f"{files_failed} file move{'s' if files_failed != 1 else ''} failed during organization."
            ),
        )
    except (RuntimeError, OSError, TypeError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
