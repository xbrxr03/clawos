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
        files = sorted(
            [path for path in target.iterdir() if path.is_file()],
            key=lambda item: item.name.lower(),
        )
        if not files:
            return WorkflowResult(
                status=WorkflowStatus.OK,
                output=f"No loose files found in {target}; nothing to organize.",
                metadata={"target": str(target), "files_moved": 0, "folders_created": 0, "dry_run": dry_run},
            )

        await emit_workflow_progress(
            f"Classifying {len(files)} files into tidy folders",
            phase="plan",
            progress=46,
        )
        planned_moves: list[tuple[Path, Path, str, int]] = []
        folders_created: set[str] = set()
        shadow_destinations: set[Path] = set()
        category_counts: dict[str, int] = {}
        category_bytes: dict[str, int] = {}
        total_bytes = 0

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
            category_counts[category] = category_counts.get(category, 0) + 1
            category_bytes[category] = category_bytes.get(category, 0) + size_bytes
            total_bytes += size_bytes

        if not dry_run:
            await emit_workflow_progress(
                "Moving files into their new folders",
                phase="apply",
                progress=72,
            )
            halfway = max(1, len(planned_moves) // 2)
            for index, (source, destination, _category, _size_bytes) in enumerate(planned_moves, start=1):
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.rename(destination)
                if index == halfway and len(planned_moves) > 2:
                    await emit_workflow_progress(
                        "Halfway through the file moves",
                        phase="apply",
                        progress=84,
                    )

        await emit_workflow_progress(
            "Building the organization summary",
            phase="summary",
            progress=92,
        )

        ordered_categories = _sorted_categories(category_counts)
        category_lines = [
            f"- {category}: {category_counts[category]} files • {format_bytes(category_bytes.get(category, 0))}"
            for category in ordered_categories
        ]
        largest_moves = sorted(planned_moves, key=lambda item: (-item[3], item[0].name.lower()))[:5]
        sample_moves = planned_moves[:8]

        lines = [
            "**Downloads Command Center**",
            f"- Target: {target}",
            f"- Mode: {'preview only (dry run)' if dry_run else 'applied live'}",
            f"- Outcome: {len(planned_moves)} files across {len(folders_created)} folders • {format_bytes(total_bytes)} total",
            "",
            "**Category breakdown:**",
        ]
        lines.extend(category_lines)
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
        lines.extend(
            f"- {source.name} -> {category}/{destination.name}"
            for source, destination, category, _size_bytes in sample_moves
        )
        if len(planned_moves) > len(sample_moves):
            lines.append(f"- ... and {len(planned_moves) - len(sample_moves)} more")
        lines.extend(
            [
                "",
                (
                    "**Next step:** Review the preview, then rerun with dry run off to apply it."
                    if dry_run
                    else "**Next step:** Open the folders above to confirm everything landed where you expect."
                ),
            ]
        )

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "target": str(target),
                "files_moved": len(planned_moves),
                "folders_created": len(folders_created),
                "dry_run": dry_run,
                "total_bytes": total_bytes,
                "category_counts": category_counts,
                "category_bytes": category_bytes,
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
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
