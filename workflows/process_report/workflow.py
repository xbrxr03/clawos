# SPDX-License-Identifier: AGPL-3.0-or-later
"""process-report — snapshot running processes, CPU/mem usage, flag anomalies."""
import subprocess
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


def _run(argv: list[str]) -> str:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or r.stderr.strip()
    except FileNotFoundError:
        return "(command unavailable)"
    except Exception as e:
        return f"(error: {e})"


async def run(args: dict, agent) -> WorkflowResult:
    # Gather real data first
    ps_out     = _run(["ps", "aux", "--sort=-%cpu"])
    if ps_out and not ps_out.startswith("(error:") and not ps_out.startswith("(command unavailable)"):
        ps_out = "\n".join(ps_out.splitlines()[:20])
    mem_out    = _run(["free", "-h"])
    uptime_out = _run(["uptime"])

    prompt = (
        "You have real system data below. Write a clean process report.\n\n"
        f"=== uptime ===\n{uptime_out}\n\n"
        f"=== free -h ===\n{mem_out}\n\n"
        f"=== ps aux --sort=-%cpu | head -20 ===\n{ps_out}\n\n"
        "Write the report in this format:\n\n"
        "## Process Report\n"
        "**Uptime:** <value>  **Load:** <1m/5m/15m>\n"
        "**Memory:** <used>/<total> (<percentage>%)\n\n"
        "### Top Processes (CPU)\n"
        "| PID | Name | CPU% | MEM% |\n"
        "|-----|------|------|------|\n\n"
        "### Anomalies\n"
        "<any processes using >20% CPU, >1GB RAM, or zombie processes, or 'None detected'>\n\n"
        "### System Health\n"
        "<1-2 sentences on overall system health based on the data>"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output,
                              metadata={"uptime": uptime_out})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
