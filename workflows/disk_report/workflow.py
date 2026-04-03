"""disk-report — analyze disk usage, find largest files/dirs."""
import re
import subprocess
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


def _run(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return f"(error: {e})"


async def run(args: dict, agent) -> WorkflowResult:
    target = args.get("dir") or "/"

    # Gather real disk data first
    df_out   = _run("df -h /")
    du_top   = _run("du -sh /* 2>/dev/null | sort -rh | head -15")
    du_home  = _run("du -sh ~/.* ~/* 2>/dev/null | sort -rh | head -10")
    big_files = _run("find /home -type f -size +50M 2>/dev/null | head -10 | xargs -I{} du -sh {} 2>/dev/null | sort -rh")

    prompt = (
        f"You have real disk usage data below. Write a clean disk report.\n\n"
        f"=== df -h / ===\n{df_out}\n\n"
        f"=== Largest top-level dirs (du -sh /*) ===\n{du_top}\n\n"
        f"=== Home directory sizes ===\n{du_home}\n\n"
        f"=== Large files (>50MB) in /home ===\n{big_files or 'none found'}\n\n"
        "Write the report in this exact format:\n\n"
        "**Disk Usage Report**\n"
        "• Total / Used / Free: <from df>\n"
        "• Usage: <percentage>%\n\n"
        "**Top 5 largest directories:**\n"
        "<list with size and path>\n\n"
        "**Large files (>50MB):**\n"
        "<list or 'None found'>\n\n"
        "**Cleanup recommendations:**\n"
        "<3-5 specific, actionable suggestions based on the actual data>\n\n"
        "End with: Total reclaimable: ~XGB"
    )

    try:
        output = await agent.chat(prompt)
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:GB|MB)\s*reclaimable", output, re.IGNORECASE)
        meta = {
            "reclaimable": m.group(0) if m else "unknown",
            "df": df_out.splitlines()[1] if "\n" in df_out else df_out,
        }
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata=meta)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
