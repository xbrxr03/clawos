# SPDX-License-Identifier: AGPL-3.0-or-later
import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest


_AUTO_TEMP_ROOT = "CLAWOS_TEST_TEMP_ROOT" not in os.environ
TEMP_ROOT = Path(os.environ.get("CLAWOS_TEST_TEMP_ROOT", tempfile.mkdtemp(prefix="clawos-tests-"))).resolve()
TEMP_ROOT.mkdir(parents=True, exist_ok=True)

if _AUTO_TEMP_ROOT:
    atexit.register(lambda: shutil.rmtree(TEMP_ROOT, ignore_errors=True))

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


def pytest_configure(config):
    if not getattr(config.option, "basetemp", None):
        basetemp = TEMP_ROOT / "pytest"
        basetemp.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(basetemp)


@pytest.fixture
def workspace_tmp_dir():
    root = TEMP_ROOT / "workspace-tests"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="workspace-", dir=str(root)))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
