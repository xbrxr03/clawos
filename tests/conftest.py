# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import shutil
import tempfile
from pathlib import Path

import pytest


TEMP_ROOT = Path(__file__).resolve().parent.parent / ".pytest_tmp"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("TMP", str(TEMP_ROOT))
os.environ.setdefault("TEMP", str(TEMP_ROOT))
os.environ.setdefault("TMPDIR", str(TEMP_ROOT))
tempfile.tempdir = str(TEMP_ROOT)


def pytest_addoption(parser):
    parser.addoption(
        "--deb",
        default=None,
        help="Path to the .deb package to validate",
    )


@pytest.fixture
def workspace_tmp_dir():
    root = TEMP_ROOT / "workspace-tests"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=str(root)))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
