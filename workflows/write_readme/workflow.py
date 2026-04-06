# SPDX-License-Identifier: AGPL-3.0-or-later
"""write-readme — auto-generate README.md from codebase."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "write-readme",
    name        = "Write README",
    category    = "developer",
    description = "Auto-generate README.md from codebase: description, install, usage, examples",
    tags        = ["developer", "docs", "readme", "git"],
    requires    = [],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    target_dir = args.get("dir") or "."
    path = Path(target_dir).expanduser().resolve()

    prompt = (
        f"Generate a README.md for the project at: {path}\n\n"
        "1. Inspect the project structure with fs.list.\n"
        "2. Read key files: existing README, package.json, pyproject.toml, setup.py, main files.\n"
        "3. Write a complete README.md:\n\n"
        "# <Project Name>\n"
        "<one-line description>\n\n"
        "## What it does\n"
        "<2-3 sentences>\n\n"
        "## Requirements\n"
        "<OS, Python/Node version, dependencies>\n\n"
        "## Installation\n"
        "```bash\n<install commands>\n```\n\n"
        "## Usage\n"
        "```bash\n<usage examples>\n```\n\n"
        "## Configuration\n"
        "<key config options if any>\n\n"
        "## License\n"
        "<license>\n\n"
        f"Save the README.md to: {path / 'README.md'}"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"directory": str(path)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
