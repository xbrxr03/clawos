"""pr-review — review a git diff/patch file with structured feedback."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "pr-review",
    name        = "PR Review",
    category    = "developer",
    description = "Review a git diff or patch file with structured feedback: bugs, style, suggestions",
    tags        = ["git", "review", "developer"],
    requires    = ["git"],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("diff")
    branch   = args.get("branch")

    if filepath:
        path = Path(filepath).expanduser().resolve()
        source = f"the diff file at: {path}"
        read_step = f"1. Read the diff file: {path}\n"
    elif branch:
        source = f"the git diff for branch: {branch}"
        read_step = f"1. Use shell.run: git diff main...{branch}\n"
    else:
        source = "the current git staged changes"
        read_step = "1. Use shell.run: git diff --staged\n"

    prompt = (
        f"Review {source}\n\n"
        + read_step +
        "2. Analyze the changes for:\n"
        "   - Bugs or logic errors\n"
        "   - Security issues\n"
        "   - Code style / readability\n"
        "   - Missing tests\n"
        "   - Performance concerns\n"
        "3. Output structured review:\n\n"
        "## PR Review\n"
        "**Summary:** <what this change does>\n\n"
        "**🐛 Issues (must fix):**\n"
        "- <file:line — description>\n\n"
        "**⚠️ Suggestions:**\n"
        "- <recommendation>\n\n"
        "**✅ Looks good:**\n"
        "- <positive notes>\n\n"
        "**Verdict:** Approve / Request Changes / Needs Discussion"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
