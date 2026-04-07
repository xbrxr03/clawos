# SPDX-License-Identifier: AGPL-3.0-or-later
"""summarize-pdf - extract and summarize PDF text deterministically."""

from __future__ import annotations

from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus, emit_workflow_progress
from workflows.helpers import (
    SUPPORTED_PLATFORMS,
    extract_pdf_text,
    keyword_terms,
    normalize_text,
    summarize_sentences,
)

META = WorkflowMeta(
    id="summarize-pdf",
    name="Summarize PDF",
    category="documents",
    description="Summarize a PDF in a deterministic offline format using extractable text",
    tags=["pdf", "summary", "beginner", "documents"],
    requires=[],
    destructive=False,
    platforms=SUPPORTED_PLATFORMS,
    needs_agent=False,
    timeout_s=120,
)


def _about_line(text: str) -> str:
    sentences = summarize_sentences(text, limit=1, min_words=5)
    if sentences:
        return sentences[0]
    words = normalize_text(text).split()
    return " ".join(words[:24]).strip()


def _takeaway_line(text: str) -> str:
    keywords = keyword_terms(text, limit=5)
    if keywords:
        return "Main themes: " + ", ".join(keywords) + "."
    sentences = summarize_sentences(text, limit=1, min_words=4)
    if sentences:
        return sentences[0]
    return "No clear takeaway could be extracted from the document text."


def _action_lines(text: str) -> list[str]:
    sentences = summarize_sentences(text, limit=2, min_words=8)
    if not sentences:
        return ["Review the original PDF for diagrams, tables, or appendix material that text extraction may miss."]
    return [
        f"Revisit this section: {sentence}"
        for sentence in sentences[:2]
    ]


async def run(args: dict, agent) -> WorkflowResult:
    try:
        await emit_workflow_progress(
            "Validating the PDF path",
            phase="validate",
            progress=10,
        )
        filepath = args.get("file") or args.get("filepath")
        if not filepath:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                output="",
                error="No file specified. Usage: clawctl workflow run summarize-pdf file=/path/to/doc.pdf",
            )

        path = Path(filepath).expanduser().resolve()
        if not path.exists():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"File not found: {path}")
        if path.suffix.lower() != ".pdf":
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Expected a .pdf file: {path}")

        await emit_workflow_progress(
            "Extracting text from the PDF",
            phase="extract",
            progress=34,
        )
        text, pages_used = extract_pdf_text(path)
        if not text:
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                output="",
                error="No extractable text was found in the PDF. It may be image-only or encrypted.",
            )

        await emit_workflow_progress(
            "Distilling the executive summary",
            phase="summarize",
            progress=68,
        )
        bullets = summarize_sentences(text, limit=4, min_words=5)
        about = _about_line(text)
        takeaway = _takeaway_line(text)
        keywords = keyword_terms(text, limit=6)
        follow_up = _action_lines(text)
        document_label = path.stem.replace("_", " ").replace("-", " ").strip() or path.name
        word_count = len(text.split())
        read_minutes = max(1, round(word_count / 180))

        await emit_workflow_progress(
            "Formatting the dashboard-ready summary",
            phase="format",
            progress=90,
        )

        lines = [
            f"**Document:** {document_label}",
            f"**Coverage:** {pages_used} text-rich pages • {word_count} words • {read_minutes} minute read",
            f"**Executive summary:** {about}",
            "",
            "**Key points:**",
        ]
        if bullets:
            lines.extend(f"- {item}" for item in bullets)
        else:
            lines.append("- No high-confidence summary bullets were extracted.")
        lines.extend(
            [
                "",
                f"**Why it matters:** {takeaway}",
                "",
                "**Key terms:**",
            ]
        )
        if keywords:
            lines.extend(f"- {term}" for term in keywords)
        else:
            lines.append("- No dominant terms stood out in the extracted text.")
        lines.extend(
            [
                "",
                "**Follow-up prompts:**",
            ]
        )
        lines.extend(f"- {item}" for item in follow_up)

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "file": str(path),
                "pages_used": pages_used,
                "bullet_count": len(bullets),
                "word_count": word_count,
                "read_minutes": read_minutes,
                "document_label": document_label,
                "about": about,
                "takeaway": takeaway,
                "keywords": keywords,
                "highlights": bullets,
                "follow_up": follow_up,
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
