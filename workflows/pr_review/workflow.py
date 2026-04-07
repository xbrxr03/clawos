# SPDX-License-Identifier: AGPL-3.0-or-later
"""pr-review - inspect a diff and produce a deterministic review summary."""

from __future__ import annotations

from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import SUPPORTED_PLATFORMS, run_command

META = WorkflowMeta(
    id="pr-review",
    name="PR Review",
    category="developer",
    description="Review a git diff or patch with deterministic checks for bugs, risk, and missing tests",
    tags=["git", "review", "developer"],
    requires=["git"],
    destructive=False,
    platforms=SUPPORTED_PLATFORMS,
    needs_agent=False,
    timeout_s=120,
)

HIGH_RISK_PATTERNS = {
    "shell=True": "Shell execution with shell=True increases command injection risk.",
    "verify=False": "TLS verification is disabled.",
    "exec(": "Dynamic code execution was introduced.",
    "eval(": "Dynamic evaluation was introduced.",
    "password": "A password-related change needs careful handling and tests.",
    "secret": "A secret-related change appears in the diff.",
    "token=": "A token assignment appears in the diff.",
}
DEBUG_PATTERNS = ("print(", "console.log(", "debugger")


def _load_diff(filepath: str = "", branch: str = "") -> tuple[str, str]:
    if filepath:
        path = Path(filepath).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Diff file not found: {path}")
        return path.read_text(encoding="utf-8", errors="replace"), str(path)
    if branch:
        result = run_command(["git", "diff", f"main...{branch}"], timeout=20)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git diff failed")
        return result.stdout, f"branch {branch}"
    result = run_command(["git", "diff", "--staged"], timeout=20)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --staged failed")
    return result.stdout, "staged changes"


def _parse_diff(diff_text: str) -> tuple[list[str], list[str]]:
    files: list[str] = []
    added_lines: list[str] = []
    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git "):
            parts = raw_line.split()
            if len(parts) >= 4:
                files.append(parts[3].replace("b/", "", 1))
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            added_lines.append(raw_line[1:])
    return files, added_lines


async def run(args: dict, agent) -> WorkflowResult:
    try:
        diff_text, source = _load_diff(
            filepath=str(args.get("file") or args.get("diff") or "").strip(),
            branch=str(args.get("branch") or "").strip(),
        )
        if not diff_text.strip():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error="No diff content was found to review.")

        files, added_lines = _parse_diff(diff_text)
        issues: list[str] = []
        suggestions: list[str] = []
        positives: list[str] = []

        lowered_lines = [line.lower() for line in added_lines]
        for pattern, message in HIGH_RISK_PATTERNS.items():
            if any(pattern.lower() in line for line in lowered_lines):
                issues.append(message)

        if any(pattern.lower() in line for pattern in DEBUG_PATTERNS for line in lowered_lines):
            suggestions.append("Remove debug-only logging before merging.")

        test_files = [path for path in files if "test" in path.lower() or path.startswith("tests/")]
        product_files = [path for path in files if path not in test_files]
        if product_files and not test_files:
            suggestions.append("Add or update regression coverage for the changed product files.")
        if len(files) > 12:
            suggestions.append("This diff touches many files; consider splitting it into smaller reviewable slices.")

        if test_files:
            positives.append("The change includes test updates.")
        if any(path.endswith((".md", ".rst")) for path in files):
            positives.append("Documentation changed alongside code.")
        if not issues:
            positives.append("No obvious high-risk security patterns were introduced by the added lines.")

        verdict = "Approve"
        if issues:
            verdict = "Request Changes"
        elif suggestions:
            verdict = "Needs Discussion"

        lines = [
            "## PR Review",
            f"**Summary:** Reviewed {len(files)} changed file(s) from {source}.",
            "",
            "**Issues (must fix):**",
        ]
        lines.extend(f"- {item}" for item in issues) if issues else lines.append("- None found.")
        lines.extend(["", "**Suggestions:**"])
        lines.extend(f"- {item}" for item in suggestions) if suggestions else lines.append("- None.")
        lines.extend(["", "**Looks good:**"])
        lines.extend(f"- {item}" for item in positives) if positives else lines.append("- No explicit positives identified.")
        lines.extend(["", f"**Verdict:** {verdict}"])

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "files_changed": len(files),
                "issues": len(issues),
                "suggestions": len(suggestions),
                "verdict": verdict,
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
