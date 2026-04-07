# SPDX-License-Identifier: AGPL-3.0-or-later
"""write-readme - generate README content from repository metadata."""

from __future__ import annotations

import json
from pathlib import Path

from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus
from workflows.helpers import SUPPORTED_PLATFORMS, iter_files, normalize_text

META = WorkflowMeta(
    id="write-readme",
    name="Write README",
    category="developer",
    description="Generate README content from project files, metadata, and common entrypoints",
    tags=["developer", "docs", "readme", "git"],
    requires=[],
    destructive=False,
    platforms=SUPPORTED_PLATFORMS,
    needs_agent=False,
    timeout_s=120,
)


def _detect_name(path: Path) -> str:
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("name ="):
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    package_json = path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            if payload.get("name"):
                return str(payload["name"])
        except Exception:
            pass
    return path.name


def _detect_description(path: Path, project_name: str) -> str:
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(encoding="utf-8", errors="replace").splitlines():
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
        except Exception:
            pass
    return f"{project_name} project"


def _requirements(path: Path) -> list[str]:
    lines: list[str] = []
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        python_line = next((line for line in text.splitlines() if "requires-python" in line), "")
        if python_line:
            lines.append("Python " + python_line.split("=", 1)[1].strip().strip('"').strip("'"))
        else:
            lines.append("Python environment")
    if (path / "package.json").exists():
        lines.append("Node.js and npm")
    if not lines:
        suffixes = {file_path.suffix.lower() for file_path in iter_files(path, skip_dirs={".git"}, max_files=120)}
        if ".py" in suffixes:
            lines.append("Python environment")
        if ".js" in suffixes or ".ts" in suffixes:
            lines.append("JavaScript runtime")
    return lines or ["See project files for runtime requirements."]


def _usage_command(path: Path) -> str:
    if (path / "clawctl" / "main.py").exists():
        return "python -m clawctl.main --help"
    package_json = path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = payload.get("scripts") or {}
            if "dev" in scripts:
                return "npm run dev"
            if "start" in scripts:
                return "npm run start"
        except Exception:
            pass
    return "python main.py"


def _project_layout(path: Path) -> list[str]:
    lines: list[str] = []
    for entry in sorted(path.iterdir(), key=lambda item: item.name.lower()):
        if entry.name.startswith(".") or entry.name == ".git":
            continue
        if entry.is_dir():
            lines.append(f"- `{entry.name}/`")
        elif entry.is_file() and entry.name in {"README.md", "pyproject.toml", "package.json", "Makefile"}:
            lines.append(f"- `{entry.name}`")
        if len(lines) >= 8:
            break
    return lines


async def run(args: dict, agent) -> WorkflowResult:
    try:
        path = Path(args.get("dir") or ".").expanduser().resolve()
        if not path.exists():
            return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=f"Directory not found: {path}")

        project_name = _detect_name(path)
        description = normalize_text(_detect_description(path, project_name))
        requirements = _requirements(path)
        layout = _project_layout(path)
        usage = _usage_command(path)

        readme = "\n".join(
            [
                f"# {project_name}",
                "",
                description,
                "",
                "## What it does",
                description,
                "",
                "## Requirements",
                *[f"- {item}" for item in requirements],
                "",
                "## Installation",
                "```bash",
                "pip install -e .",
                "```",
                "",
                "## Usage",
                "```bash",
                usage,
                "```",
                "",
                "## Project Layout",
                *(layout or ["- Review the repository root for the main project modules."]),
                "",
                "## License",
                "AGPL-3.0-or-later",
            ]
        ).strip()

        return WorkflowResult(
            status=WorkflowStatus.OK,
            output=readme,
            metadata={
                "directory": str(path),
                "project_name": project_name,
                "requirements": len(requirements),
                "layout_entries": len(layout),
            },
        )
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
