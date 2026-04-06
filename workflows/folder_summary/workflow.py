# SPDX-License-Identifier: AGPL-3.0-or-later
"""folder-summary — generate markdown summary of folder contents."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "folder-summary",
    name        = "Folder Summary",
    category    = "files",
    description = "Generate a markdown summary of folder contents, sizes, and modification dates",
    tags        = ["files", "summary", "markdown"],
    requires    = [],
    destructive = False,
    timeout_s   = 60,
)


async def run(args: dict, agent) -> WorkflowResult:
    target = args.get("dir") or "."
    path   = Path(target).expanduser().resolve()

    prompt = (
        f"Generate a markdown summary of the folder: {path}\n\n"
        "1. Use fs.list and shell.run (ls -lh) to get file list with sizes and dates.\n"
        "2. Write a markdown report:\n\n"
        "# Folder Summary: <folder name>\n"
        "**Path:** <full path>\n"
        "**Total files:** N  |  **Total size:** XMB  |  **Last modified:** <date>\n\n"
        "## Contents\n"
        "| Name | Type | Size | Modified |\n"
        "|------|------|------|----------|\n"
        "<rows>\n\n"
        "## File Types\n"
        "<breakdown by extension>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"directory": str(path)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
