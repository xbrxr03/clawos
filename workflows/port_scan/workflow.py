"""port-scan — list all open ports on local machine."""
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


async def run(args: dict, agent) -> WorkflowResult:
    prompt = (
        "List all open ports on this machine and their owning processes.\n\n"
        "1. Use shell.run: ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null\n"
        "2. Use shell.run: ss -ulnp 2>/dev/null (UDP ports)\n"
        "3. Format the results:\n\n"
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
        "<flag any unexpected or potentially risky open ports>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
