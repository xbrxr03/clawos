"""port-scan — list all open ports on local machine."""
import subprocess
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "port-scan",
    name        = "Port Scan",
    category    = "system",
    description = "List all open ports on the local machine and their owning processes",
    tags        = ["system", "network", "ports", "security"],
    requires    = [],
    destructive = False,
    timeout_s   = 60,
)


def _run(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return f"(error: {e})"


async def run(args: dict, agent) -> WorkflowResult:
    # Gather real port data
    tcp_out = _run("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
    udp_out = _run("ss -ulnp 2>/dev/null")

    prompt = (
        "You have real network port data below. Write a clean port report.\n\n"
        f"=== TCP listening ports (ss -tlnp) ===\n{tcp_out}\n\n"
        f"=== UDP listening ports (ss -ulnp) ===\n{udp_out}\n\n"
        "Write the report in this format:\n\n"
        "## Open Ports\n\n"
        "### TCP\n"
        "| Port | State | Process | PID |\n"
        "|------|-------|---------|-----|\n\n"
        "### UDP\n"
        "| Port | Process |\n"
        "|------|--------|\n\n"
        "### Notable Services\n"
        "<identify well-known services by port number>\n\n"
        "### Security Notes\n"
        "<flag any unexpected or potentially risky open ports, or 'No concerns.'>"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
