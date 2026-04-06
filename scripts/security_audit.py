# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Repeatable security audit entrypoint for ClawOS.

Runs:
1. Static pattern scans for risky execution primitives in repo code
2. `python -m pip check`
3. `pip-audit` against declared Python dependencies in pyproject.toml
4. `npm audit --omit=dev` for the command-center frontend
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
FRONTEND_DIR = ROOT / "dashboard" / "frontend"

STATIC_SCANS = (
    {
        "label": "no shell=True in product code",
        "pattern": re.compile(r"\bshell=True\b"),
        "include": {".py"},
        "exclude_parts": {"tests", "node_modules", ".git", "storybook-static", "playwright-report", "test-results"},
        "exclude_paths": {Path("scripts/security_audit.py")},
    },
    {
        "label": "no tempfile.mktemp in product code",
        "pattern": re.compile(r"\btempfile\.mktemp\("),
        "include": {".py"},
        "exclude_parts": {"tests", "node_modules", ".git"},
        "exclude_paths": set(),
    },
    {
        "label": "no exec(open(...)) shims in product code",
        "pattern": re.compile(r"exec\(open\("),
        "include": {".py"},
        "exclude_parts": {"tests", "node_modules", ".git"},
        "exclude_paths": {Path("scripts/security_audit.py")},
    },
    {
        "label": "no curl-pipe-shell installers in product code",
        "pattern": re.compile(r"curl[^\n|]*\|\s*(sh|bash)"),
        "include": {".py", ".sh"},
        "exclude_parts": {"tests", "node_modules", ".git", "README.md"},
        "exclude_paths": {
            Path("bootstrap/model_provision.py"),
            Path("clawctl/commands/model.py"),
            Path("setup/repair/doctor.py"),
            Path("tools/shell/do/safety.py"),
            Path("scripts/security_audit.py"),
        },
    },
)


def info(message: str):
    print(f"[security] {message}")


def fail(message: str):
    raise SystemExit(message)


def _iter_repo_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        yield path


def _scan_patterns():
    findings: list[str] = []
    for scan in STATIC_SCANS:
        matches: list[str] = []
        for path in _iter_repo_files():
            if path.suffix not in scan["include"]:
                continue
            if any(part in scan["exclude_parts"] for part in path.parts):
                continue
            if path.relative_to(ROOT) in scan["exclude_paths"]:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for index, line in enumerate(text.splitlines(), start=1):
                if scan["pattern"].search(line):
                    matches.append(f"{path.relative_to(ROOT)}:{index}")
        if matches:
            findings.extend([scan["label"], *matches])
        else:
            info(f"static scan passed: {scan['label']}")
    if findings:
        fail("[security] static scan failed:\n" + "\n".join(findings))


def _run(cmd: list[str], cwd: Path | None = None):
    info("running: " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd or ROOT), check=True)


def _pip_check():
    _run([sys.executable, "-m", "pip", "check"])


def _load_dependency_groups() -> dict[str, list[str]]:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    groups = {"base": list(project.get("dependencies", []))}
    optional = project.get("optional-dependencies", {})
    for name, deps in optional.items():
        if name == "full":
            continue
        groups[name] = list(deps)
    return groups


def _pip_audit_declared_dependencies():
    groups = _load_dependency_groups()
    for name, requirements in groups.items():
        if not requirements:
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write("\n".join(requirements) + "\n")
            req_path = Path(handle.name)
        try:
            _run([sys.executable, "-m", "pip_audit", "-r", str(req_path), "--progress-spinner", "off"])
            info(f"pip-audit passed for dependency group: {name}")
        finally:
            req_path.unlink(missing_ok=True)


def _npm_audit():
    package_lock = FRONTEND_DIR / "package-lock.json"
    if not package_lock.exists():
        info("dashboard/frontend/package-lock.json missing; skipping npm audit")
        return
    npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_bin:
        fail("[security] npm was not found on PATH")
    result = subprocess.run(
        [npm_bin, "audit", "--omit=dev", "--json"],
        cwd=str(FRONTEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        fail(f"[security] npm audit output was not valid JSON: {exc}")

    vulnerabilities = payload.get("metadata", {}).get("vulnerabilities", {})
    total = int(vulnerabilities.get("total", 0))
    if result.returncode not in (0, 1):
        fail(f"[security] npm audit failed to execute:\n{result.stderr}")
    if total:
        fail("[security] npm audit reported vulnerabilities:\n" + json.dumps(vulnerabilities, indent=2))
    info("npm audit passed for production frontend dependencies")


def main():
    _scan_patterns()
    _pip_check()
    _pip_audit_declared_dependencies()
    _npm_audit()
    info("security audit complete")


if __name__ == "__main__":
    main()
