# SPDX-License-Identifier: AGPL-3.0-or-later
"""repo-summary - summarize a git repository without an LLM."""

from __future__ import annotations

import json
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import SUPPORTED_PLATFORMS, iter_files, normalize_text, run_command

META = WorkflowMeta(
    id="repo-summary",
    name="Repo Summary",
    category="developer",
    description="Summarize a git repository: purpose, tech stack, structure, and recent changes",
    tags=["git", "developer", "readme"],
    requires=["git"],
    destructive=False,
    platforms=SUPPORTED_PLATFORMS,
    needs_agent=False,
    timeout_s=120,
)

STRUCTURE_LABELS = {
    "src": "application source",
    "app": "application source",
    "dashboard": "dashboard and UI surfaces",
    "services": "backend services",
    "tests": "test coverage",
    "docs": "project documentation",
    "scripts": "helper scripts",
    "packaging": "packaging and release assets",
}


def _read_readme(path: Path) -> str:
    readme = path / "README.md"
    if not readme.exists():
        return ""
    return normalize_text(readme.read_text(encoding="utf-8", errors="replace"))


def _project_description(path: Path) -> str:
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("description ="):
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    package_json = path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            description = str(payload.get("description", "")).strip()
            if description:
                return description
        except (json.JSONDecodeError, ValueError):
            pass
            pass
    readme = _read_readme(path)
    if readme:
        return readme.split(". ", 1)[0].strip()
    return f"{path.name} repository"


def _detect_stack(path: Path) -> list[str]:
    stack: list[str] = []
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        stack.append("Python")
    if (path / "package.json").exists():
        stack.append("Node.js")
        package_text = (path / "package.json").read_text(encoding="utf-8", errors="replace").lower()
        if "\"react\"" in package_text:
            stack.append("React")
        if "\"typescript\"" in package_text:
            stack.append("TypeScript")
    if (path / "Cargo.toml").exists():
        stack.append("Rust")
    if (path / "go.mod").exists():
        stack.append("Go")
    if not stack:
        suffixes = {file_path.suffix.lower() for file_path in iter_files(path, skip_dirs={".git"}, max_files=200)}
        if ".py" in suffixes:
            stack.append("Python")
        if ".ts" in suffixes or ".tsx" in suffixes:
            stack.append("TypeScript")
        if ".js" in suffixes:
            stack.append("JavaScript")
    return stack or ["Unclear from repository files"]


def _structure_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for entry in sorted(path.iterdir(), key=lambda item: item.name.lower()):
        if entry.name.startswith(".") or entry.name == ".git":
            continue
        if entry.is_dir():
            description = STRUCTURE_LABELS.get(entry.name.lower(), "project directory")
            lines.append(f"- `{entry.name}/`: {description}")
        elif entry.is_file() and entry.name in {"README.md", "pyproject.toml", "package.json", "Makefile"}:
            lines.append(f"- `{entry.name}`: top-level project entry file")
        if len(lines) >= 8:
            break
    return lines


def _entry_point(path: Path) -> str:
    for candidate in ("clawctl/main.py", "src/main.py", "main.py", "app.py"):
        if (path / candidate).exists():
            return candidate
    package_json = path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = payload.get("scripts") or {}
            if "start" in scripts:
                return f"npm run start ({scripts['start']})"
            if "dev" in scripts:
                return f"npm run dev ({scripts['dev']})"
        except (json.JSONDecodeError, ValueError):
            pass
            pass
    return "See README or top-level scripts for the preferred entry path."


def _recent_activity(path: Path) -> list[str]:
    result = run_command(["git", "-C", str(path), "log", "--oneline", "-5"], timeout=20)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git log failed")
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return commits[:5]


async def run(args: dict, agent) -> WorkflowResult:
    try:
        path = Path(args.get("dir") or args.get("directory") or ".").expanduser().resolve()
        if not path.exists():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Directory not found: {path}")

        probe = run_command(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"])
        if probe.returncode != 0:
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Not a git repository: {path}")

        description = _project_description(path)
        stack = _detect_stack(path)
        structure = _structure_lines(path)
        activity = _recent_activity(path)
        entry_point = _entry_point(path)

        lines = [
            f"**Repository:** {path.name}",
            f"**What it does:** {description}",
            f"**Tech stack:** {', '.join(stack)}",
            "**Structure:**",
        ]
        lines.extend(structure or ["- No top-level structure summary available."])
        lines.append("**Recent activity:**")
        lines.extend(f"- {commit}" for commit in activity or ["No recent commits found."])
        lines.append(f"**Entry point:** {entry_point}")

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output="\n".join(lines),
            metadata={
                "directory": str(path),
                "stack": stack,
                "recent_commits": len(activity),
                "structure_entries": len(structure),
            },
        )
    except (OSError,) as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
