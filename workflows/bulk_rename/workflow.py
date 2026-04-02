"""bulk-rename — rename files via natural language pattern."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "bulk-rename",
    name        = "Bulk Rename",
    category    = "files",
    description = "Rename files in a folder using a natural language pattern",
    tags        = ["files", "rename"],
    requires    = [],
    destructive = True,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    target  = args.get("dir") or "."
    pattern = args.get("pattern") or args.get("rule") or "add date prefix"
    dry_run = args.get("dry_run", True)

    prompt = (
        f"Rename files in: {target}\n"
        f"Rule: {pattern}\n\n"
        "1. Use fs.list to list all files.\n"
        "2. Apply the rename rule to generate new filenames.\n"
        "3. " + ("Show what the renames WOULD be (dry run — do not rename).\n" if dry_run else
                  "Rename each file using shell.run or fs operations.\n") +
        "4. List: old name → new name for each file.\n"
        "End with: Renamed N files."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
