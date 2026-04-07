# SPDX-License-Identifier: AGPL-3.0-or-later
"""log-summarize - summarize a log file and flag anomalies."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from clawos_core.platform import platform_key
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import tail_lines

META = WorkflowMeta(
    id="log-summarize",
    name="Log Summarize",
    category="system",
    description="Summarize a log file (syslog/nginx/app logs), flag errors and anomalies",
    tags=["system", "logs", "monitoring"],
    requires=[],
    destructive=False,
    platforms=["linux", "macos", "windows"],
    needs_agent=False,
    timeout_s=90,
)


def _default_log_path() -> Path | None:
    candidates = {
        "linux": [Path("/var/log/syslog"), Path("/var/log/messages")],
        "darwin": [Path("/var/log/system.log")],
        "windows": [],
    }
    for candidate in candidates.get(platform_key(), []):
        if candidate.exists():
            return candidate
    return None


async def run(args: dict, agent) -> WorkflowResult:
    try:
        filepath = args.get("file")
        path = Path(filepath).expanduser().resolve() if filepath else _default_log_path()
        if path is None or not path.exists():
            return WorkflowResult(
                status=WorkflowStatus.FAILED,
                output="",
                error="No default log file was found for this platform. Pass file=/path/to/log.",
            )

        line_count = max(1, int(args.get("lines") or 200))
        tail = tail_lines(path, line_count)
        error_counter = Counter()
        warning_counter = Counter()
        notable: list[str] = []

        for raw in tail:
            lowered = raw.lower()
            normalized = " ".join(raw.split())
            if any(token in lowered for token in ("error", "critical", "fatal", "panic")):
                error_counter[normalized] += 1
                notable.append(raw)
            elif "warn" in lowered:
                warning_counter[normalized] += 1
                notable.append(raw)
            elif any(token in lowered for token in ("restart", "started", "stopped", "failed")):
                notable.append(raw)

        verdict = "healthy"
        if error_counter:
            verdict = "critical" if sum(error_counter.values()) >= 5 else "needs attention"
        elif warning_counter:
            verdict = "needs attention"

        lines = [
            "## Log Summary",
            f"**File:** {path}",
            f"**Lines analyzed:** {len(tail)}",
            "",
            "### Errors Found",
        ]
        if error_counter:
            lines.extend(f"- {message}  ({count}x)" for message, count in error_counter.most_common(8))
        else:
            lines.append("- No error-level entries found.")

        lines.extend(["", "### Warnings"])
        if warning_counter:
            lines.extend(f"- {message}  ({count}x)" for message, count in warning_counter.most_common(8))
        else:
            lines.append("- No warning patterns found.")

        lines.extend(["", "### Timeline"])
        if notable:
            lines.extend(f"- {entry}" for entry in notable[-10:])
        else:
            lines.append("- No notable service changes found in the sampled lines.")

        lines.extend(["", "### Verdict", verdict])

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "file": str(path),
                "errors": sum(error_counter.values()),
                "warnings": sum(warning_counter.values()),
                "verdict": verdict,
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
