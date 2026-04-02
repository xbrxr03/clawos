"""log-summarize — summarize a log file, flag errors and anomalies."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "log-summarize",
    name        = "Log Summarize",
    category    = "system",
    description = "Summarize a log file (syslog/nginx/app logs), flag errors and anomalies",
    tags        = ["system", "logs", "monitoring"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or "/var/log/syslog"
    lines    = args.get("lines") or "200"
    path     = Path(filepath).expanduser().resolve()

    prompt = (
        f"Summarize the log file: {path}\n\n"
        f"1. Use shell.run: tail -n {lines} {path} 2>/dev/null\n"
        "2. Identify:\n"
        "   - ERROR and CRITICAL messages\n"
        "   - Repeated warnings\n"
        "   - Unusual patterns or spikes\n"
        "   - Service restarts or failures\n"
        "3. Write a summary:\n\n"
        "## Log Summary\n"
        f"**File:** {path}  **Lines analyzed:** {lines}\n\n"
        "### Errors Found\n"
        "- <error message — count occurrences>\n\n"
        "### Warnings\n"
        "- <warning pattern>\n\n"
        "### Timeline\n"
        "<notable events in time order>\n\n"
        "### Verdict\n"
        "<healthy / needs attention / critical>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
