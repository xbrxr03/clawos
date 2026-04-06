# SPDX-License-Identifier: AGPL-3.0-or-later
"""summarize-pdf — summarize any PDF in 3-5 bullet points using local LLM."""
import re
from pathlib import Path
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "summarize-pdf",
    name        = "Summarize PDF",
    category    = "documents",
    description = "Summarize any PDF in 3–5 bullet points using local qwen2.5:7b — fully offline",
    tags        = ["pdf", "summary", "beginner", "documents"],
    requires    = [],
    destructive = False,
    timeout_s   = 120,
)


async def run(args: dict, agent) -> WorkflowResult:
    filepath = args.get("file") or args.get("filepath")
    if not filepath:
        return WorkflowResult(
            status=WorkflowStatus.FAILED,
            output="",
            error="No file specified. Usage: nexus workflow run summarize-pdf file=/path/to/doc.pdf",
        )

    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return WorkflowResult(
            status=WorkflowStatus.FAILED,
            output="",
            error=f"File not found: {path}",
        )

    prompt = (
        f"Summarize the document at: {path}\n\n"
        "Instructions:\n"
        "1. Use the project RAG system or fs.read to read the document content.\n"
        "2. Identify the main topic, key points, and conclusions.\n"
        "3. Write a summary with:\n"
        "   - One sentence describing what the document is about.\n"
        "   - 3 to 5 bullet points covering the most important information.\n"
        "   - One sentence on the main takeaway or conclusion.\n"
        "4. Keep it concise — under 200 words total.\n\n"
        "Format your response as:\n"
        "**Document:** <title or filename>\n"
        "**About:** <one sentence>\n"
        "• <key point 1>\n"
        "• <key point 2>\n"
        "• <key point 3>\n"
        "**Takeaway:** <conclusion>\n"
    )

    try:
        output = await agent.chat(prompt)
        word_count = len(output.split())
        return WorkflowResult(
            status=WorkflowStatus.OK,
            output=output,
            metadata={"file": str(path), "word_count": word_count},
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
