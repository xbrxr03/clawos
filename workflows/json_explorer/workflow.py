# SPDX-License-Identifier: AGPL-3.0-or-later
"""json-explorer — pretty-print and summarize structure of a JSON file."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "json-explorer",
    name        = "JSON Explorer",
    category    = "data",
    description = "Pretty-print and summarize the structure of a JSON file",
    tags        = ["json", "data", "developer"],
    requires    = [],
    destructive = False,
    timeout_s   = 60,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run json-explorer file=/path/to/data.json")

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"File not found: {path}")

    prompt = (
        f"Explore and summarize the JSON file: {path}\n\n"
        "1. Read the file.\n"
        "2. Report:\n"
        "   - Top-level type (object/array)\n"
        "   - If array: length and item structure\n"
        "   - If object: all keys and their value types\n"
        "   - Nested depth\n"
        "   - Total key count\n"
        "3. Show a pretty-printed preview (first 30 lines).\n"
        "4. If it looks like a config, API response, or dataset — say so.\n\n"
        "Format as a clean markdown summary."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path)})
    except (OSError, ValueError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
