"""batch-summarize — summarize all PDFs in a folder."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "batch-summarize",
    name        = "Batch Summarize",
    category    = "documents",
    description = "Summarize all PDFs in a folder, one markdown file per PDF",
    tags        = ["pdf", "summary", "batch", "documents"],
    requires    = [],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    target = args.get("dir") or "."
    path   = Path(target).expanduser().resolve()

    prompt = (
        f"Summarize all PDF files in the folder: {path}\n\n"
        "1. Use fs.list to find all .pdf files.\n"
        "2. For each PDF:\n"
        "   - Read its content.\n"
        "   - Write a 3-5 bullet point summary.\n"
        "   - Save the summary as <filename>_summary.md in the same folder.\n"
        "3. After processing all files, report how many were summarized.\n"
        "End with: Summarized N documents."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"directory": str(path)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
