"""changelog — human-readable changelog from git log between two tags."""
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "changelog",
    name        = "Changelog",
    category    = "developer",
    description = "Generate a human-readable changelog from git log between two tags or commits",
    tags        = ["git", "developer", "changelog", "docs"],
    requires    = ["git"],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    from_ref = args.get("from") or args.get("from_tag") or "HEAD~20"
    to_ref   = args.get("to")   or args.get("to_tag")   or "HEAD"
    target   = args.get("dir")  or "."

    prompt = (
        f"Generate a changelog for commits from {from_ref} to {to_ref} in: {target}\n\n"
        f"1. Use shell.run: git -C {target} log {from_ref}..{to_ref} --oneline --no-merges\n"
        "2. Group commits into categories:\n"
        "   - Features (feat:, add, implement)\n"
        "   - Bug Fixes (fix:, bug, resolve)\n"
        "   - Improvements (improve, update, refactor)\n"
        "   - Breaking Changes\n"
        "3. Write a CHANGELOG.md-style entry:\n\n"
        "## [Unreleased] — <date>\n\n"
        "### Features\n- <item>\n\n"
        "### Bug Fixes\n- <item>\n\n"
        "### Improvements\n- <item>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
