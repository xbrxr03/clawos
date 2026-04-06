# SPDX-License-Identifier: AGPL-3.0-or-later
"""csv-to-report — convert CSV into a markdown report."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "csv-to-report",
    name        = "CSV to Report",
    category    = "data",
    description = "Convert a CSV into a markdown/PDF report with auto-generated chart descriptions",
    tags        = ["csv", "data", "report", "markdown"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run csv-to-report file=/path/to/data.csv")

    path    = Path(filepath).expanduser().resolve()
    out     = path.with_suffix(".md")

    prompt = (
        f"Convert {path} into a structured markdown report.\n\n"
        "1. Read the CSV and understand its structure.\n"
        "2. Write a report:\n\n"
        f"# Report: {path.stem}\n"
        f"*Generated from {path.name}*\n\n"
        "## Overview\n"
        "<total rows, columns, date range if applicable>\n\n"
        "## Key Findings\n"
        "<3-5 insights derived from the data>\n\n"
        "## Data Summary\n"
        "<table with key stats per column>\n\n"
        "## Trends\n"
        "<describe any notable patterns>\n\n"
        f"3. Save the report to: {out}\n"
        "End with: Report saved to <path>."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path), "output": str(out)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
