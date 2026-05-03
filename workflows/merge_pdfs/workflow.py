# SPDX-License-Identifier: AGPL-3.0-or-later
"""merge-pdfs - merge multiple PDFs into one file."""

from __future__ import annotations

import shlex
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import format_bytes

META = WorkflowMeta(
    id="merge-pdfs",
    name="Merge PDFs",
    category="documents",
    description="Merge multiple PDFs into one in specified order",
    tags=["pdf", "merge", "documents"],
    requires=[],
    destructive=True,
    platforms=["linux", "macos", "windows"],
    needs_agent=False,
    timeout_s=90,
)


def _parse_files(raw) -> list[Path]:
    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw]
    else:
        parts = shlex.split(str(raw))
    return [Path(part).expanduser().resolve() for part in parts if part]


async def run(args: dict, agent) -> WorkflowResult:
    try:
        from pypdf import PdfReader, PdfWriter

        files = args.get("files") or ""
        output = args.get("output") or "merged.pdf"
        input_paths = _parse_files(files)
        if not input_paths:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                output="",
                error="No files specified. Usage: nexus workflow run merge-pdfs files='a.pdf b.pdf' output=merged.pdf",
            )

        for input_path in input_paths:
            if not input_path.exists():
                return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Missing PDF: {input_path}")

        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        writer = PdfWriter()
        try:
            for input_path in input_paths:
                reader = PdfReader(str(input_path))
                for page in reader.pages:
                    writer.add_page(page)
            with output_path.open("wb") as handle:
                writer.write(handle)
        finally:
            writer.close()

        size = output_path.stat().st_size
        output_text = f"Merged {len(input_paths)} files into {output_path} ({format_bytes(size)})."
        return WorkflowResult(
            status=WorkflowStatus.OK,
            output=output_text,
            metadata={"output": str(output_path), "files": len(input_paths), "size_bytes": size},
        )
    except (OSError, PermissionError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
