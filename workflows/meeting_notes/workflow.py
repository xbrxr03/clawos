"""meeting-notes — convert raw transcript to structured notes."""
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "meeting-notes",
    name        = "Meeting Notes",
    category    = "content",
    description = "Convert raw meeting transcript to structured notes: attendees, decisions, actions",
    tags        = ["meetings", "notes", "content", "writing"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="",
                              error="No file specified. Usage: nexus workflow run meeting-notes file=/path/to/transcript.txt")

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"File not found: {path}")

    prompt = (
        f"Convert the meeting transcript at {path} into structured notes.\n\n"
        "1. Read the transcript.\n"
        "2. Extract:\n"
        "   - Meeting date and participants\n"
        "   - Key discussion points\n"
        "   - Decisions made\n"
        "   - Action items (who, what, by when)\n"
        "3. Format as:\n\n"
        "# Meeting Notes\n"
        "**Date:** <date>  **Attendees:** <names>\n\n"
        "## Discussion\n- <point>\n\n"
        "## Decisions\n- <decision>\n\n"
        "## Action Items\n"
        "- [ ] <task> — **Owner:** <name> — **Due:** <date>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output, metadata={"file": str(path)})
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
