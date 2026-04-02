"""clean-empty-dirs — recursively find and remove empty directories."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "clean-empty-dirs",
    name        = "Clean Empty Dirs",
    category    = "files",
    description = "Recursively find and remove empty directories",
    tags        = ["files", "cleanup"],
    requires    = [],
    destructive = True,
    timeout_s   = 60,
)


async def run(args: dict, agent) -> WorkflowResult:
    target  = args.get("dir") or str(Path.home())
    dry_run = args.get("dry_run", False)

    prompt = (
        f"Find and remove empty directories under: {target}\n\n"
        "1. Use shell.run: find {target} -type d -empty 2>/dev/null | head -50\n"
        "2. List the empty directories found.\n"
        + ("3. Remove them using: find {target} -type d -empty -delete 2>/dev/null\n"
           if not dry_run else
           "3. Do NOT delete — just report what would be removed.\n") +
        "End with: Found N empty directories."
        + (" Removed N." if not dry_run else "")
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
