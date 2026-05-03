# SPDX-License-Identifier: AGPL-3.0-or-later
"""rewrite — rewrite text in a different tone."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "rewrite",
    name        = "Rewrite",
    category    = "content",
    description = "Rewrite a text file in a different tone: formal, casual, shorter, bullet points",
    tags        = ["writing", "content", "edit"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    tone     = args.get("tone") or "clearer and more concise"

    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run rewrite file=/path/to/text.txt tone=formal")

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"File not found: {path}")

    prompt = (
        f"Rewrite the text in {path} to be: {tone}\n\n"
        "1. Read the file content.\n"
        "2. Rewrite it in the requested tone while preserving the meaning.\n"
        "3. Output the rewritten version only — no commentary.\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path), "tone": tone})
    except (OSError, ValueError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
