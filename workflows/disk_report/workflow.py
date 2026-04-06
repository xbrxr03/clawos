"""disk-report - analyze disk usage and suggest cleanups."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import format_bytes

META = WorkflowMeta(
    id="disk-report",
    name="Disk Report",
    category="system",
    description="Analyze disk usage, find largest files/dirs, generate cleanup recommendations",
    tags=["disk", "system", "cleanup", "beginner"],
    requires=[],
    destructive=False,
    platforms=["linux", "macos", "windows"],
    needs_agent=False,
    timeout_s=90,
)


def _entry_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        if not path.is_dir():
            return 0
    except OSError:
        return 0

    total = 0
    for root, _, files in os.walk(path):
        for filename in files:
            file_path = Path(root) / filename
            try:
                if file_path.is_symlink():
                    continue
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def _top_entries(target: Path, limit: int = 5) -> list[tuple[int, Path]]:
    entries: list[tuple[int, Path]] = []
    for entry in target.iterdir():
        if entry.name.startswith("."):
            continue
        entries.append((_entry_size(entry), entry))
    entries.sort(key=lambda item: item[0], reverse=True)
    return entries[:limit]


def _large_files(target: Path, threshold_bytes: int, limit: int = 10) -> list[tuple[int, Path]]:
    matches: list[tuple[int, Path]] = []
    for root, _, files in os.walk(target):
        for filename in files:
            file_path = Path(root) / filename
            try:
                if file_path.is_symlink():
                    continue
                size = file_path.stat().st_size
            except OSError:
                continue
            if size >= threshold_bytes:
                matches.append((size, file_path))
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[:limit]


async def run(args: dict, agent) -> WorkflowResult:
    try:
        target = Path(args.get("dir") or Path.home()).expanduser().resolve()
        if not target.exists():
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                output="",
                error=f"Directory not found: {target}",
            )

        usage = shutil.disk_usage(target)
        threshold_mb = int(args.get("large_file_mb") or 50)
        threshold_bytes = threshold_mb * 1024 * 1024
        top_entries = _top_entries(target)
        large_files = _large_files(target, threshold_bytes)
        reclaimable = sum(size for size, _ in large_files)

        recommendations: list[str] = []
        if usage.total and (usage.used / usage.total) >= 0.85:
            recommendations.append("Disk usage is above 85%; clear caches and downloads soon.")
        if large_files:
            recommendations.append(f"Review the {len(large_files)} files above {threshold_mb}MB first.")
        if any(path.name.lower() in {"downloads", "desktop"} for _, path in top_entries):
            recommendations.append("Your top-level personal folders are large; archive older files there.")
        if not recommendations:
            recommendations.append("No urgent cleanup signal found; keep an eye on the largest top-level folders.")
        recommendations.append("Delete or archive files only after confirming they are not active project data.")

        lines = [
            "**Disk Usage Report**",
            f"- Target: {target}",
            f"- Total / Used / Free: {format_bytes(usage.total)} / {format_bytes(usage.used)} / {format_bytes(usage.free)}",
            f"- Usage: {round((usage.used / usage.total) * 100, 1) if usage.total else 0.0}%",
            "",
            "**Top 5 largest entries:**",
        ]
        if top_entries:
            lines.extend(f"- {format_bytes(size)}  {path}" for size, path in top_entries)
        else:
            lines.append("- No visible entries found.")

        lines.extend(["", f"**Large files (>{threshold_mb}MB):**"])
        if large_files:
            lines.extend(f"- {format_bytes(size)}  {path}" for size, path in large_files)
        else:
            lines.append("- None found.")

        lines.extend(["", "**Cleanup recommendations:**"])
        lines.extend(f"- {item}" for item in recommendations[:5])
        lines.extend(["", f"Total reclaimable: ~{format_bytes(reclaimable)}"])

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "target": str(target),
                "used_pct": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
                "reclaimable_bytes": reclaimable,
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
