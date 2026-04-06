#!/usr/bin/env python3
"""Run the repo's main verification surfaces in a repeatable order."""

from __future__ import annotations

import argparse
import os
import pathlib
import py_compile
import shutil
import subprocess
import sys
from typing import Iterable


ROOT = pathlib.Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "dashboard" / "frontend"
PHASE_GLOB = "tests/system/test_phase*.py"


def info(message: str) -> None:
    print(f"[verify] {message}", flush=True)


def resolve_executable(name: str) -> str:
    if os.path.isabs(name) or os.path.sep in name:
        return name

    resolved = shutil.which(name)
    if resolved:
        return resolved

    if os.name == "nt" and not pathlib.Path(name).suffix:
        for suffix in (".cmd", ".exe", ".bat"):
            resolved = shutil.which(f"{name}{suffix}")
            if resolved:
                return resolved

    return name


def tracked_python_files() -> list[pathlib.Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "*.py"],
            cwd=ROOT,
            text=True,
        )
        return [ROOT / line for line in output.splitlines() if line.strip()]
    except Exception:
        return [
            path
            for path in ROOT.rglob("*.py")
            if ".venv" not in path.parts and "node_modules" not in path.parts and "__pycache__" not in path.parts
        ]


def run(command: list[str], *, cwd: pathlib.Path = ROOT, env: dict[str, str] | None = None) -> None:
    resolved = [resolve_executable(command[0]), *command[1:]]
    info(f"running: {' '.join(resolved)}")
    subprocess.run(resolved, cwd=cwd, env=env, check=True)


def compile_python(files: Iterable[pathlib.Path]) -> None:
    count = 0
    for path in files:
        py_compile.compile(str(path), doraise=True)
        count += 1
    info(f"compiled {count} python files")


def run_phase_scripts(python_bin: str) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    for script in sorted(ROOT.glob(PHASE_GLOB)):
        run([python_bin, str(script)], env=env)


def ensure_frontend_deps(npm_bin: str) -> None:
    if (FRONTEND_DIR / "node_modules").exists():
        return
    info("frontend dependencies missing; running npm ci")
    run([npm_bin, "ci"], cwd=FRONTEND_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-bin", default=sys.executable, help="Python interpreter to use")
    parser.add_argument("--npm-bin", default="npm", help="npm executable to use for frontend checks")
    parser.add_argument("--skip-py-compile", action="store_true", help="Skip py_compile verification")
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest")
    parser.add_argument("--skip-phase-scripts", action="store_true", help="Skip direct test_phase*.py runs")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend verification")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    npm_bin = resolve_executable(args.npm_bin)

    if not args.skip_py_compile:
        compile_python(tracked_python_files())

    if not args.skip_pytest:
        run([args.python_bin, "-m", "pytest", "tests"])

    if not args.skip_phase_scripts:
        run_phase_scripts(args.python_bin)

    if not args.skip_frontend:
        if not FRONTEND_DIR.exists():
            info("frontend directory not found; skipping frontend verification")
        elif shutil.which(npm_bin) is None and not os.path.exists(npm_bin):
            raise SystemExit(f"npm executable not found: {args.npm_bin}")
        else:
            ensure_frontend_deps(npm_bin)
            run([npm_bin, "run", "ci"], cwd=FRONTEND_DIR)

    info("verification complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
