"""merge-pdfs — merge multiple PDFs into one."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "merge-pdfs",
    name        = "Merge PDFs",
    category    = "documents",
    description = "Merge multiple PDFs into one in specified order",
    tags        = ["pdf", "merge", "documents"],
    requires    = [],
    destructive = True,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    files  = args.get("files") or ""
    output = args.get("output") or "merged.pdf"

    if not files:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No files specified. Usage: nexus workflow run merge-pdfs files='a.pdf b.pdf' output=merged.pdf")

    prompt = (
        f"Merge these PDF files into one: {files}\n"
        f"Output file: {output}\n\n"
        "Use one of these methods (try in order):\n"
        f"1. shell.run: pdfunite {files} {output}\n"
        f"2. shell.run: gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile={output} {files}\n"
        "3. Python: use PyPDF2 or pypdf to merge the files.\n\n"
        "After merging, confirm the output file exists and report its size.\n"
        f"End with: Merged N files into {output} (XMB)."
    )

    try:
        output_text = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output_text, metadata={"output": output})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
