"""find-todos - scan code for TODO/FIXME/HACK comments."""

from __future__ import annotations

import re
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import iter_files

META = WorkflowMeta(
    id="find-todos",
    name="Find TODOs",
    category="developer",
    description="Scan codebase for TODO/FIXME/HACK comments, output prioritized list",
    tags=["developer", "code", "todos", "review"],
    requires=[],
    destructive=False,
    platforms=["linux", "macos", "windows"],
    needs_agent=False,
    timeout_s=90,
)

MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|NOTE|BUG)\b[:\s-]*(.*)", re.IGNORECASE)
SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".sh",
    ".yaml", ".yml", ".md", ".c", ".cpp", ".h", ".hpp",
}


async def run(args: dict, agent) -> WorkflowResult:
    try:
        target_dir = args.get("dir") or args.get("directory") or "."
        path = Path(target_dir).expanduser().resolve()
        max_files = max(1, int(args.get("max_files") or 5000))

        if not path.exists():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Directory not found: {path}")

        buckets = {
            "must_fix": [],
            "todo": [],
            "hack": [],
            "note": [],
        }
        files_with_hits: set[Path] = set()

        for file_path in iter_files(path, skip_dirs={"node_modules", "__pycache__", ".git", ".venv", "venv", "dist", "build"}, max_files=max_files):
            if file_path.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_no, raw in enumerate(lines, start=1):
                match = MARKER_RE.search(raw)
                if not match:
                    continue
                marker = match.group(1).upper()
                text = (match.group(2) or raw).strip()
                record = f"{file_path}:{line_no} - {text}"
                files_with_hits.add(file_path)
                if marker in {"FIXME", "BUG"}:
                    buckets["must_fix"].append(record)
                elif marker == "TODO":
                    buckets["todo"].append(record)
                elif marker == "HACK":
                    buckets["hack"].append(record)
                else:
                    buckets["note"].append(record)

        total = sum(len(items) for items in buckets.values())
        top_priority = (
            buckets["must_fix"][0] if buckets["must_fix"]
            else buckets["todo"][0] if buckets["todo"]
            else buckets["hack"][0] if buckets["hack"]
            else "No follow-up needed."
        )

        lines = [
            "**TODO Report**",
            f"Found {total} items across {len(files_with_hits)} files.",
            "",
            "**Must Fix (FIXME/BUG):**",
        ]
        lines.extend(f"- {item}" for item in (buckets["must_fix"][:20] or ["None found."]))
        lines.extend(["", "**Planned (TODO):**"])
        lines.extend(f"- {item}" for item in (buckets["todo"][:20] or ["None found."]))
        lines.extend(["", "**Tech Debt (HACK):**"])
        lines.extend(f"- {item}" for item in (buckets["hack"][:20] or ["None found."]))
        lines.extend(["", "**Notes:**"])
        lines.extend(f"- {item}" for item in (buckets["note"][:10] or ["None found."]))
        if total:
            lines.extend(["", f"**Top priority to address:** {top_priority}"])

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "total": total,
                "fixme": len(buckets["must_fix"]),
                "todo": len(buckets["todo"]),
                "hack": len(buckets["hack"]),
                "note": len(buckets["note"]),
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
