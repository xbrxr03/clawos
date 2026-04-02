"""extract-tables — extract tables from PDF or Word doc as CSV."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "extract-tables",
    name        = "Extract Tables",
    category    = "documents",
    description = "Extract all tables from a PDF or Word doc and save as CSV",
    tags        = ["pdf", "tables", "csv", "documents"],
    requires    = [],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run extract-tables file=/path/to/doc.pdf")

    path      = Path(filepath).expanduser().resolve()
    out_dir   = path.parent
    prompt = (
        f"Extract all tables from the document: {path}\n\n"
        "1. Read the document content.\n"
        "2. Identify all tables (look for tabular data, columns, rows).\n"
        "3. For each table:\n"
        "   - Give it a name based on its content.\n"
        "   - Save it as a CSV file in {out_dir} named table_1.csv, table_2.csv, etc.\n"
        "4. Report how many tables were found and saved.\n"
        "End with: Extracted N tables to {out_dir}."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
