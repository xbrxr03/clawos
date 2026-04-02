"""find-todos — scan codebase for TODO/FIXME/HACK, output prioritized list."""
import re
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "find-todos",
    name        = "Find TODOs",
    category    = "developer",
    description = "Scan codebase for TODO/FIXME/HACK comments, output prioritized list",
    tags        = ["developer", "code", "todos", "review"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    target_dir = args.get("dir") or args.get("directory") or "."
    path = Path(target_dir).expanduser().resolve()

    prompt = (
        f"Scan the codebase at {path} for TODO, FIXME, HACK, and NOTE comments.\n\n"
        "Instructions:\n"
        "1. Use shell.run: grep -rn --include='*.py' --include='*.js' --include='*.ts' "
        f"--include='*.jsx' --include='*.tsx' -E '(TODO|FIXME|HACK|NOTE):?' {path} 2>/dev/null | head -50\n"
        "2. Group results by severity:\n"
        "   - FIXME / BUG: must fix before shipping\n"
        "   - TODO: planned work\n"
        "   - HACK: technical debt\n"
        "   - NOTE: informational\n"
        "3. Output:\n\n"
        "**TODO Report**\n"
        "Found N items across M files.\n\n"
        "**Must Fix (FIXME/BUG):**\n"
        "<file:line — description>\n\n"
        "**Planned (TODO):**\n"
        "<file:line — description>\n\n"
        "**Tech Debt (HACK):**\n"
        "<file:line — description>\n\n"
        "**Top priority to address:** <your recommendation>\n"
    )

    try:
        output = await agent.chat(prompt)
        counts = re.findall(r"\b(TODO|FIXME|HACK|NOTE)\b", output)
        meta = {
            "total": len(counts),
            "fixme": counts.count("FIXME"),
            "todo":  counts.count("TODO"),
            "hack":  counts.count("HACK"),
        }
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata=meta)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
