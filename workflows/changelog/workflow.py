# SPDX-License-Identifier: AGPL-3.0-or-later
"""changelog - generate grouped release notes from git history."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import SUPPORTED_PLATFORMS, run_command

META = WorkflowMeta(
    id="changelog",
    name="Changelog",
    category="developer",
    description="Generate a grouped changelog from git history between two refs",
    tags=["git", "developer", "changelog", "docs"],
    requires=["git"],
    destructive=False,
    platforms=SUPPORTED_PLATFORMS,
    needs_agent=False,
    timeout_s=90,
)


def _categorize(message: str) -> str:
    lowered = message.lower()
    if "breaking" in lowered or "!" in message.split(":", 1)[0]:
        return "Breaking Changes"
    if lowered.startswith("feat") or any(token in lowered for token in (" add ", " added", " implement", " new ")):
        return "Features"
    if lowered.startswith("fix") or any(token in lowered for token in (" bug", " resolve", " patch")):
        return "Bug Fixes"
    return "Improvements"


async def run(args: dict, agent) -> WorkflowResult:
    try:
        from_ref = str(args.get("from") or args.get("from_tag") or "HEAD~20").strip()
        to_ref = str(args.get("to") or args.get("to_tag") or "HEAD").strip()
        repo_dir = Path(args.get("dir") or ".").expanduser().resolve()

        result = run_command(
            ["git", "-C", str(repo_dir), "log", f"{from_ref}..{to_ref}", "--oneline", "--no-merges"],
            timeout=20,
        )
        if result.returncode != 0:
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=result.stderr.strip() or "git log failed")

        commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        groups = {
            "Breaking Changes": [],
            "Features": [],
            "Bug Fixes": [],
            "Improvements": [],
        }
        for commit in commits:
            _sha, _sep, message = commit.partition(" ")
            groups[_categorize(message)].append(message or commit)

        lines = [f"## [{to_ref}] - {date.today().isoformat()}"]
        for title in ("Breaking Changes", "Features", "Bug Fixes", "Improvements"):
            lines.extend(["", f"### {title}"])
            items = groups[title]
            if items:
                lines.extend(f"- {item}" for item in items)
            else:
                lines.append("- None")

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "from": from_ref,
                "to": to_ref,
                "commits": len(commits),
                "categories": {key: len(value) for key, value in groups.items()},
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
