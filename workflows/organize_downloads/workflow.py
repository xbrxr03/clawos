"""organize-downloads — sort ~/Downloads by file type into subfolders."""
import re
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "organize-downloads",
    name        = "Organize Downloads",
    category    = "files",
    description = "Sort ~/Downloads into subfolders by type (Images, Docs, Archives, etc.)",
    tags        = ["files", "cleanup", "beginner"],
    requires    = [],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    target  = args.get("target_dir") or str(Path.home() / "Downloads")
    dry_run = args.get("dry_run", False)

    prompt = (
        f"Organize the Downloads folder at: {target}\n\n"
        "Steps:\n"
        "1. Use fs.list to list all files in the folder.\n"
        "2. Group them into categories:\n"
        "   - Images: .jpg .jpeg .png .gif .webp .heic .svg\n"
        "   - Documents: .pdf .docx .doc .txt .md .xlsx .csv .pptx\n"
        "   - Archives: .zip .tar .gz .7z .rar .bz2\n"
        "   - Code: .py .js .ts .sh .json .yaml .yml .html .css\n"
        "   - Videos: .mp4 .mov .avi .mkv .wmv\n"
        "   - Audio: .mp3 .wav .flac .m4a .ogg\n"
        "   - Others: everything else\n"
        + (
            "3. Do NOT move files — describe what you WOULD do (dry run).\n"
            if dry_run else
            "3. Create the category subfolders if they do not exist, then move each file.\n"
        ) +
        "4. End your response with exactly this line:\n"
        "   Summary: Organized N files into M folders.\n\n"
        "Only move files, not existing subdirectories."
    )

    try:
        output = await agent.chat(prompt)
        m = re.search(r"Organized\s+(\d+)\s+files?\s+into\s+(\d+)\s+folders?", output, re.IGNORECASE)
        meta = {}
        if m:
            meta = {"files_moved": int(m.group(1)), "folders_created": int(m.group(2))}
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata=meta)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
