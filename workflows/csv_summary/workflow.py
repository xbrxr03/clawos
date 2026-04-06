# SPDX-License-Identifier: AGPL-3.0-or-later
"""csv-summary — load CSV, generate stats."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "csv-summary",
    name        = "CSV Summary",
    category    = "data",
    description = "Load a CSV file and generate stats: row count, column types, nulls, min/max/mean",
    tags        = ["csv", "data", "stats"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run csv-summary file=/path/to/data.csv")

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"File not found: {path}")

    prompt = (
        f"Summarize the CSV file: {path}\n\n"
        "Use Python to analyze it:\n"
        "```python\n"
        "import csv\n"
        f"with open('{path}') as f:\n"
        "    reader = csv.DictReader(f)\n"
        "    rows = list(reader)\n"
        "```\n"
        "Report:\n"
        "- Total rows and columns\n"
        "- Column names and inferred types (numeric, text, date)\n"
        "- For numeric columns: min, max, mean\n"
        "- Null/empty value counts per column\n"
        "- First 3 rows as a preview\n\n"
        "Format as a clean markdown report."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
