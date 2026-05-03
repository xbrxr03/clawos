# SPDX-License-Identifier: AGPL-3.0-or-later
"""proofread — proofread document, return tracked changes as diff."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "proofread",
    name        = "Proofread",
    category    = "content",
    description = "Proofread a document, return tracked changes as a diff",
    tags        = ["writing", "content", "grammar", "edit"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run proofread file=/path/to/doc.txt")

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"File not found: {path}")

    prompt = (
        f"Proofread the document at: {path}\n\n"
        "1. Read the file.\n"
        "2. Identify: spelling errors, grammar issues, unclear sentences, awkward phrasing.\n"
        "3. Output your corrections as a list:\n\n"
        "## Proofreading Report\n\n"
        "### Corrections\n"
        "| Line | Original | Corrected | Issue |\n"
        "|------|----------|-----------|-------|\n"
        "| <n> | <original> | <corrected> | <spelling/grammar/clarity> |\n\n"
        "### Summary\n"
        "- N spelling errors\n"
        "- N grammar issues\n"
        "- N clarity improvements\n\n"
        "Overall quality: <score>/10\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path)})
    except (OSError, ValueError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
