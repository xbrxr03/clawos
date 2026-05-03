# SPDX-License-Identifier: AGPL-3.0-or-later
"""backup-check — verify dirs have been recently backed up."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "backup-check",
    name        = "Backup Check",
    category    = "system",
    description = "Verify specified directories have been recently backed up, output status report",
    tags        = ["system", "backup", "monitoring"],
    requires    = [],
    destructive = False,
    timeout_s   = 60,
)


async def run(args: dict, agent) -> WorkflowResult:
    dirs = args.get("dirs") or str(Path.home())

    prompt = (
        f"Check backup status for: {dirs}\n\n"
        "1. Look for backup indicators:\n"
        "   - .backup, .bak, backup/ directories near the target\n"
        "   - Rsync log files in /var/log/ or ~/\n"
        "   - Time Machine, Duplicati, or Restic state files\n"
        "   - Git repos with recent pushes (git log --since='7 days ago')\n"
        "2. Check when the most recent backup-related file was modified.\n"
        "3. Report:\n\n"
        "## Backup Status Report\n\n"
        "| Directory | Last Backup | Method | Status |\n"
        "|-----------|-------------|--------|--------|\n\n"
        "### Recommendation\n"
        "<what to back up and suggested method>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except (OSError, ValueError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
