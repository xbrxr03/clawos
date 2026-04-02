"""disk-report — analyze disk usage, find largest files/dirs."""
import re
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "disk-report",
    name        = "Disk Report",
    category    = "system",
    description = "Analyze disk usage, find largest files/dirs, generate cleanup recommendations",
    tags        = ["disk", "system", "cleanup", "beginner"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    target = args.get("dir") or "/"

    prompt = (
        f"Generate a disk usage report for: {target}\n\n"
        "Instructions:\n"
        "1. Use system.disk_info to get overall disk usage.\n"
        "2. Use shell.run with: du -sh /* 2>/dev/null | sort -rh | head -20\n"
        "   to find the largest top-level directories.\n"
        "3. Use shell.run with: find /home -type f -size +100M 2>/dev/null | head -10\n"
        "   to find large files in home directories.\n"
        "4. Write a report:\n\n"
        "**Disk Usage Report**\n"
        "• Total / Used / Free: <values>\n"
        "• Usage: <percentage>%\n\n"
        "**Top 5 largest directories:**\n"
        "<table with size and path>\n\n"
        "**Large files (>100MB):**\n"
        "<list>\n\n"
        "**Cleanup recommendations:**\n"
        "<3-5 specific suggestions based on what you found>\n\n"
        "End with: Total reclaimable: ~XGB\n"
    )

    try:
        output = await agent.chat(prompt)
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:GB|MB)\s*reclaimable", output, re.IGNORECASE)
        meta = {"reclaimable": m.group(0) if m else "unknown"}
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata=meta)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
