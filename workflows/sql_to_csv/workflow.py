"""sql-to-csv — run SQL query against local SQLite database, export to CSV."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "sql-to-csv",
    name        = "SQL to CSV",
    category    = "data",
    description = "Run a SQL query against a local SQLite database and export results to CSV",
    tags        = ["sql", "sqlite", "csv", "data", "developer"],
    requires    = [],
    destructive = False,
    timeout_s   = 60,
)


async def run(args: dict, agent) -> WorkflowResult:
    db_path = args.get("db") or args.get("database")
    query   = args.get("query") or args.get("sql") or "SELECT * FROM sqlite_master LIMIT 20"
    output  = args.get("output") or "query_result.csv"

    if not db_path:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No database specified. Usage: nexus workflow run sql-to-csv db=/path/to/db.sqlite query='SELECT ...' output=result.csv")

    path = Path(db_path).expanduser().resolve()

    prompt = (
        f"Run a SQL query against: {path}\n"
        f"Query: {query}\n"
        f"Output CSV: {output}\n\n"
        "1. Use Python to execute the query:\n"
        "```python\n"
        "import sqlite3, csv\n"
        f"conn = sqlite3.connect('{path}')\n"
        "cursor = conn.execute('''<query>''')\n"
        "rows = cursor.fetchall()\n"
        "headers = [d[0] for d in cursor.description]\n"
        "```\n"
        f"2. Write the results to {output} as CSV with headers.\n"
        "3. Report: N rows exported, columns: <list>.\n"
        f"End with: Exported N rows to {output}."
    )

    try:
        output_text = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output_text, metadata={"db": str(path), "output": output})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
