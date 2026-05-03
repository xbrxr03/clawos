# SPDX-License-Identifier: AGPL-3.0-or-later
"""pdf-to-notes — convert PDF into structured markdown notes."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "pdf-to-notes",
    name        = "PDF to Notes",
    category    = "documents",
    description = "Convert PDF into structured markdown notes with headings and action items",
    tags        = ["pdf", "notes", "markdown", "documents"],
    requires    = [],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run pdf-to-notes file=/path/to/doc.pdf")

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"File not found: {path}")

    prompt = (
        f"Convert the document at {path} into structured markdown notes.\n\n"
        "Instructions:\n"
        "1. Read the document content.\n"
        "2. Extract the main sections and organize them into markdown headings.\n"
        "3. Under each heading, write concise bullet-point notes.\n"
        "4. At the end, add an '## Action Items' section with any tasks mentioned.\n"
        "5. Keep the notes under 500 words.\n\n"
        "Output format:\n"
        "# Notes: <Document Title>\n"
        "## <Section 1>\n"
        "- <note>\n"
        "## Action Items\n"
        "- [ ] <task>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path)})
    except (OSError, ValueError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
