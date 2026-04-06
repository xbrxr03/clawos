# SPDX-License-Identifier: AGPL-3.0-or-later
"""repo-summary — plain-English summary of a git repo."""
import re
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "repo-summary",
    name        = "Repo Summary",
    category    = "developer",
    description = "Plain-English summary of a git repo: what it does, tech stack, recent changes",
    tags        = ["git", "developer", "readme"],
    requires    = ["git"],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    target_dir = args.get("dir") or args.get("directory") or "."
    path = Path(target_dir).expanduser().resolve()

    prompt = (
        f"Summarize the git repository at: {path}\n\n"
        "Instructions:\n"
        "1. Use fs.list and fs.read to inspect the repo structure.\n"
        "2. Read README.md if it exists.\n"
        f"3. Check the last 10 git commits (use shell.run: git -C {path} log --oneline -10).\n"
        "4. Identify the main language and frameworks used.\n"
        "5. Write a summary:\n\n"
        "**Repository:** <name>\n"
        "**What it does:** <1-2 sentences>\n"
        "**Tech stack:** <languages, frameworks, key dependencies>\n"
        "**Structure:** <main directories and their purpose>\n"
        "**Recent activity:** <what the last few commits changed>\n"
        "**Entry point:** <how to run or install it>\n"
    )

    try:
        output = await agent.chat(prompt)
        lines = [l for l in output.split("\n") if l.strip()]
        return WorkflowResult(
            status=WorkflowStatus.OK,
            output=output,
            metadata={"directory": str(path), "sections": len(lines)},
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
