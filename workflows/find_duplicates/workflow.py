"""find-duplicates — find duplicate files via content hash."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "find-duplicates",
    name        = "Find Duplicates",
    category    = "files",
    description = "Find duplicate files via content hash, output report, optionally delete",
    tags        = ["files", "cleanup", "duplicates"],
    requires    = [],
    destructive = True,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    target = args.get("dir") or str(Path.home())
    delete = args.get("delete", False)

    prompt = (
        f"Find duplicate files in: {target}\n\n"
        "1. Use shell.run: find {target} -type f | xargs md5sum 2>/dev/null | sort | "
        "awk 'BEGIN{{p=\"\"}} {{if($1==p)print; p=$1}}' | head -40\n"
        "2. Group files by hash to identify duplicates.\n"
        "3. Report: total duplicates found, total space wasted.\n"
        + ("4. Delete the duplicate copies (keep the first occurrence).\n" if delete else
           "4. List which files could be deleted to free space (do NOT delete yet).\n") +
        "End with: Found N duplicate groups, ~XMB reclaimable."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
