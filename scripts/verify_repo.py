# SPDX-License-Identifier: AGPL-3.0-or-later
#!/usr/bin/env python3
"""Run the repo's main verification surfaces in a repeatable order."""

from __future__ import annotations

import argparse
import os
import pathlib
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable

SCRIPT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from clawos_core.util.git import git_check_output


ROOT = SCRIPT_ROOT
FRONTEND_DIR = ROOT / "dashboard" / "frontend"
PHASE_GLOB = "tests/system/test_phase*.py"
FALLBACK_EXCLUDE_PARTS = {
    ".claude",
    ".git",
    ".pytest_cache",
    ".pytest_tmp",
    "__pycache__",
    "node_modules",
    "playwright-report",
    "site-packages",
    "storybook-static",
    "test-results",
    "venv",
}


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
        output = git_check_output(["ls-files", "*.py"], repo=ROOT, cwd=ROOT)
        return [ROOT / line for line in output.splitlines() if line.strip()]
    except Exception:
        return [
            path
            for path in ROOT.rglob("*.py")
            if ".venv" not in path.parts and not any(part in FALLBACK_EXCLUDE_PARTS for part in path.parts)
        ]


def required_node_major() -> int | None:
    node_version_file = ROOT / ".nvmrc"
    if not node_version_file.exists():
        return None
    match = re.search(r"\d+", node_version_file.read_text(encoding="utf-8"))
    return int(match.group(0)) if match else None


def current_node_version() -> str | None:
    try:
        return subprocess.check_output([resolve_executable("node"), "-v"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def ensure_supported_node() -> None:
    required_major = required_node_major()
    if required_major is None:
        return
    version = current_node_version()
    if not version:
        raise SystemExit(f"Node {required_major} is required for frontend verification, but `node` was not found on PATH.")
    match = re.search(r"(\d+)", version)
    current_major = int(match.group(1)) if match else None
    if current_major != required_major:
        raise SystemExit(
            f"Frontend verification requires Node {required_major} from .nvmrc, but current node is {version}. "
            f"Run `nvm use` or pass a Node-{required_major} npm via --npm-bin."
        )


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


def build_test_env(temp_root: pathlib.Path) -> dict[str, str]:
    test_root = temp_root / "test-env"
    test_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMP"] = str(test_root)
    env["TEMP"] = str(test_root)
    env["TMPDIR"] = str(test_root)
    env["CLAWOS_TEST_TEMP_ROOT"] = str(test_root)
    env["PYTHONUTF8"] = "1"
    return env


def run_phase_scripts(python_bin: str, *, env: dict[str, str]) -> None:
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
    verify_temp_root = pathlib.Path(tempfile.mkdtemp(prefix="clawos-verify-")).resolve()
    test_env = build_test_env(verify_temp_root)

    if not args.skip_py_compile:
        compile_python(tracked_python_files())

    if not args.skip_pytest:
        pytest_basetemp = verify_temp_root / "pytest"
        pytest_cache = verify_temp_root / "pytest-cache"
        pytest_basetemp.mkdir(parents=True, exist_ok=True)
        pytest_cache.mkdir(parents=True, exist_ok=True)
        run(
            [
                args.python_bin,
                "-m",
                "pytest",
                "tests",
                f"--basetemp={pytest_basetemp}",
                "-o",
                f"cache_dir={pytest_cache}",
            ],
            env=test_env,
        )

    if not args.skip_phase_scripts:
        run_phase_scripts(args.python_bin, env=test_env)

    if not args.skip_frontend:
        if not FRONTEND_DIR.exists():
            info("frontend directory not found; skipping frontend verification")
        elif shutil.which(npm_bin) is None and not os.path.exists(npm_bin):
            raise SystemExit(f"npm executable not found: {args.npm_bin}")
        else:
            ensure_supported_node()
            ensure_frontend_deps(npm_bin)
            run([npm_bin, "run", "ci"], cwd=FRONTEND_DIR)

    info("verification complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
