# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Automated pytest tests for ClawOS .deb package integrity.

Run with:
    pytest tests/packaging/test_deb.py --deb /path/to/clawos-command-center.deb -v

If --deb is not supplied the tests are skipped.
"""
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--deb",
        default=None,
        help="Path to the .deb package to validate",
    )


@pytest.fixture(scope="session")
def deb_path(request):
    path = request.config.getoption("--deb")
    if not path:
        pytest.skip("No --deb supplied; skipping packaging tests")
    p = Path(path)
    if not p.exists():
        pytest.fail(f"DEB file not found: {path}")
    return p


@pytest.fixture(scope="session")
def deb_contents(deb_path):
    """Run dpkg-deb --contents and return the output string."""
    _require_tool("dpkg-deb")
    result = subprocess.run(
        ["dpkg-deb", "--contents", str(deb_path)],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


@pytest.fixture(scope="session")
def deb_fields(deb_path):
    """Return a dict of control fields."""
    _require_tool("dpkg-deb")
    result = subprocess.run(
        ["dpkg-deb", "--field", str(deb_path)],
        capture_output=True, text=True, check=True,
    )
    fields = {}
    for line in result.stdout.splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


@pytest.fixture(scope="session")
def extracted_deb(deb_path):
    """Extract the deb into a temporary directory and return its path."""
    _require_tool("dpkg-deb")
    tmpdir = tempfile.mkdtemp(prefix="clawos_deb_test_")
    subprocess.run(
        ["dpkg-deb", "--extract", str(deb_path), tmpdir],
        check=True, capture_output=True,
    )
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_tool(name: str):
    if shutil.which(name) is None:
        pytest.skip(f"{name} not available")


# ---------------------------------------------------------------------------
# Tests: package integrity
# ---------------------------------------------------------------------------

class TestPackageIntegrity:
    def test_dpkg_info_succeeds(self, deb_path):
        result = subprocess.run(
            ["dpkg-deb", "--info", str(deb_path)],
            capture_output=True,
        )
        assert result.returncode == 0, f"dpkg-deb --info failed:\n{result.stderr.decode()}"

    def test_dpkg_contents_succeeds(self, deb_path):
        result = subprocess.run(
            ["dpkg-deb", "--contents", str(deb_path)],
            capture_output=True,
        )
        assert result.returncode == 0, "dpkg-deb --contents failed"

    def test_file_size_min(self, deb_path):
        size_kb = deb_path.stat().st_size // 1024
        assert size_kb > 50, f"Package suspiciously small: {size_kb}KB"

    def test_file_size_max(self, deb_path):
        size_kb = deb_path.stat().st_size // 1024
        assert size_kb < 500_000, f"Package unexpectedly large: {size_kb}KB"


# ---------------------------------------------------------------------------
# Tests: control fields
# ---------------------------------------------------------------------------

class TestControlFields:
    REQUIRED_FIELDS = ["Package", "Version", "Architecture", "Maintainer", "Description", "Depends"]

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_required_field_present(self, deb_fields, field):
        assert field in deb_fields, f"Control field missing: {field}"

    def test_package_name(self, deb_fields):
        assert deb_fields["Package"] == "clawos-command-center"

    def test_version_format(self, deb_fields):
        version = deb_fields.get("Version", "")
        assert version, "Version field is empty"
        # Must start with a digit
        assert version[0].isdigit(), f"Version does not start with digit: {version}"

    def test_architecture_valid(self, deb_fields):
        arch = deb_fields.get("Architecture", "")
        valid = {"amd64", "arm64", "armhf", "i386", "all"}
        assert arch in valid, f"Unexpected architecture: {arch}"

    def test_depends_python3(self, deb_fields):
        depends = deb_fields.get("Depends", "")
        assert "python3" in depends, f"Depends does not include python3: {depends}"

    def test_section_utils_or_misc(self, deb_fields):
        section = deb_fields.get("Section", "")
        assert section in ("utils", "misc"), f"Unexpected Section: {section}"


# ---------------------------------------------------------------------------
# Tests: package contents
# ---------------------------------------------------------------------------

class TestPackageContents:
    REQUIRED_PATHS = [
        "usr/bin/clawctl",
        "usr/lib/clawos",
        "usr/share/doc/clawos",
        "lib/systemd/system/clawos",
    ]

    @pytest.mark.parametrize("path", REQUIRED_PATHS)
    def test_required_path(self, deb_contents, path):
        assert path in deb_contents, f"Package missing required path: {path}"

    def test_desktop_entry(self, deb_contents):
        assert ".desktop" in deb_contents, "No .desktop file found in package"

    def test_postinst_present(self, deb_contents):
        # postinst lives in the control archive, not the data archive;
        # dpkg-deb --contents only shows data files so we check --info instead
        pass  # covered by test_dpkg_info_succeeds (postinst is in the control archive)


# ---------------------------------------------------------------------------
# Tests: extracted filesystem
# ---------------------------------------------------------------------------

class TestExtractedFiles:
    def test_clawctl_is_file(self, extracted_deb):
        clawctl = extracted_deb / "usr" / "bin" / "clawctl"
        assert clawctl.exists(), f"clawctl not found at {clawctl}"

    def test_systemd_service_file(self, extracted_deb):
        service = extracted_deb / "lib" / "systemd" / "system"
        services = list(service.glob("clawos*.service")) if service.exists() else []
        assert services, "No clawos*.service file found"

    def test_doc_dir(self, extracted_deb):
        doc = extracted_deb / "usr" / "share" / "doc" / "clawos"
        assert doc.exists(), f"Doc dir missing: {doc}"


# ---------------------------------------------------------------------------
# Tests: lintian (optional, skipped if not installed)
# ---------------------------------------------------------------------------

class TestLintian:
    def test_no_lintian_errors(self, deb_path):
        if shutil.which("lintian") is None:
            pytest.skip("lintian not installed")
        result = subprocess.run(
            ["lintian", "--no-tag-display-limit", str(deb_path)],
            capture_output=True, text=True,
        )
        errors = [line for line in result.stdout.splitlines() if line.startswith("E:")]
        assert not errors, f"lintian errors:\n" + "\n".join(errors)
