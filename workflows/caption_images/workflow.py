# SPDX-License-Identifier: AGPL-3.0-or-later
"""caption-images — generate captions for images in a folder."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "caption-images",
    name        = "Caption Images",
    category    = "content",
    description = "Generate captions for images in a folder using filename inference",
    tags        = ["images", "content", "captions"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    target = args.get("dir") or "."
    style  = args.get("style") or "descriptive"
    path   = Path(target).expanduser().resolve()

    prompt = (
        f"Generate {style} captions for images in: {path}\n\n"
        "1. Use fs.list to find all image files (.jpg, .jpeg, .png, .gif, .webp).\n"
        "2. For each image, infer a caption from:\n"
        "   - The filename (clean it up: replace _ and - with spaces, remove extensions)\n"
        "   - The folder name for context\n"
        "3. Write a caption for each image:\n\n"
        "| Filename | Caption |\n"
        "|----------|--------|\n"
        "| <name> | <caption> |\n\n"
        "Keep captions under 15 words each.\n"
        "End with: Generated N captions."
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"directory": str(path)})
    except (OSError, ValueError) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
