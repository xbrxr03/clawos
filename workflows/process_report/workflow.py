"""process-report — snapshot running processes, CPU/mem usage, flag anomalies."""
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "process-report",
    name        = "Process Report",
    category    = "system",
    description = "Snapshot running processes, CPU/memory usage, flag anomalies",
    tags        = ["system", "processes", "monitoring"],
    requires    = [],
    destructive = False,
    timeout_s   = 60,
)


async def run(args: dict, agent) -> WorkflowResult:
    prompt = (
        "Generate a process report for this machine.\n\n"
        "1. Use shell.run: ps aux --sort=-%cpu | head -20\n"
        "2. Use shell.run: free -h\n"
        "3. Use shell.run: uptime\n"
        "4. Identify any anomalies:\n"
        "   - Processes using >20% CPU\n"
        "   - Processes using >1GB RAM\n"
        "   - Zombie processes\n"
        "5. Write a report:\n\n"
        "## Process Report\n"
        "**Uptime:** <value>  **Load:** <1m/5m/15m>\n"
        "**Memory:** <used>/<total> (<percentage>%)\n\n"
        "### Top Processes (CPU)\n"
        "| PID | Name | CPU% | MEM% |\n"
        "|-----|------|------|------|\n\n"
        "### Anomalies\n"
        "<any unusual processes or high usage>\n\n"
        "### Recommendation\n"
        "<1-2 sentences on system health>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
