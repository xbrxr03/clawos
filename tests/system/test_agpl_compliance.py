# SPDX-License-Identifier: AGPL-3.0-or-later
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

SOURCE_EXTENSIONS = {".py", ".sh", ".ts", ".tsx", ".js", ".jsx", ".css"}
HEADER_TEXT = "SPDX-License-Identifier: AGPL-3.0-or-later"
SKIP_PREFIXES = (
    ".claude/",
    "dashboard/frontend/node_modules/",
    "services/dashd/static/assets/",
)
SKIP_FILES = {
    "services/dashd/static/index.html",
}


def _tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files"], cwd=str(ROOT), text=True)
    return [line.strip() for line in output.splitlines() if line.strip()]


def test_tracked_source_files_carry_agpl_headers():
    missing: list[str] = []
    for rel in _tracked_files():
        if rel in SKIP_FILES or rel.startswith(SKIP_PREFIXES):
            continue
        path = ROOT / rel
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        first_lines = "\n".join(text.splitlines()[:3])
        if HEADER_TEXT not in first_lines:
            missing.append(rel)

    assert missing == []


def test_license_file_contains_full_agpl_text():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "TERMS AND CONDITIONS" in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text
    assert len(license_text) > 30000


def test_readme_and_pyproject_reflect_agpl():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "AGPL" in readme
    assert "GNU Affero General Public License" in readme
    assert 'license = { text = "AGPL-3.0-or-later" }' in pyproject
    assert "GNU Affero General Public License v3 or later (AGPLv3+)" in pyproject
