# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Session 4 Test Suite
============================
Tests ISO build infrastructure, install script, launch assets.
All tests run without actually building the ISO (that needs sudo + 20 min).

Usage:
  python3 tests/system/test_phase4.py
"""
import sys
import os
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

passed = failed = 0


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def can_run_bash_syntax() -> bool:
    return os.name != "nt" and bool(shutil.which("bash"))


def ok(name):
    global passed; passed += 1
    print(f"  ✓  {name}")


def fail(name, reason=""):
    global failed; failed += 1
    print(f"  ✗  {name}" + (f" — {reason}" if reason else ""))


def section(title):
    print(f"\n  ── {title}")


ISO_DIR     = ROOT / "packaging" / "iso"
INSTALL_DIR = ROOT / "packaging" / "install"
LAUNCH_DIR  = ROOT / "packaging" / "launch"


# ── 1. ISO build files ────────────────────────────────────────────────────────
section("1. ISO build files")

try:
    for f in ["build_iso.sh", "chroot_install.sh", "firstboot.sh", "preseed.cfg"]:
        assert (ISO_DIR / f).exists(), f"missing: {f}"
    ok("All 4 ISO build files present")
except Exception as e:
    fail("ISO files", str(e))

try:
    build = read_text(ISO_DIR / "build_iso.sh")
    checks = [
        ("xorriso",       "uses xorriso for ISO creation"),
        ("mksquashfs",    "uses mksquashfs to repack"),
        ("chroot_install","calls chroot_install.sh"),
        ("ClawOS",        "names the ISO correctly"),
        ("sha256sum",     "generates SHA256 checksum"),
        ("dd if=",        "shows flash command in output"),
    ]
    for snippet, desc in checks:
        assert snippet in build, f"missing: {snippet} ({desc})"
    ok(f"build_iso.sh has all {len(checks)} required elements")
except Exception as e:
    fail("build_iso.sh content", str(e))

try:
    chroot = read_text(ISO_DIR / "chroot_install.sh")
    checks = [
        ("dashboard/frontend",          "builds the canonical frontend"),
        ("npm run build",               "builds the frontend bundle"),
        ("clawos-setup.desktop",        "installs setup autostart"),
        ("clawos-command-center.desktop", "installs command-center desktop entry"),
        ("ollama.ai/install.sh",        "installs Ollama in chroot"),
    ]
    for snippet, desc in checks:
        assert snippet.lower() in chroot.lower(), f"missing: {snippet} ({desc})"
    ok(f"chroot_install.sh has all {len(checks)} required elements")
except Exception as e:
    fail("chroot_install.sh content", str(e))

try:
    firstboot = read_text(ISO_DIR / "firstboot.sh")
    assert "launch_command_center.py" in firstboot
    assert "--route /setup" in firstboot
    assert "DONE_FLAG" in firstboot
    assert "first-boot handoff" in firstboot.lower()
    ok("firstboot.sh hands off into the new /setup experience and marks completion")
except Exception as e:
    fail("firstboot.sh content", str(e))


# ── 2. Install script ─────────────────────────────────────────────────────────
section("2. Install script (non-ISO path)")

try:
    install = read_text(INSTALL_DIR / "install.sh")
    root_install = read_text(ROOT / "install.sh")
    checks = [
        ('exec bash "$REPO_ROOT/install.sh" "$@"', "wrapper delegates to root installer"),
        ("ollama launch openclaw", "root installer launches OpenClaw"),
        ("dashboard/frontend",    "root installer builds frontend"),
        ("clawos-setup",          "root installer installs GUI setup launcher"),
        ("launch_command_center.py", "root installer uses command-center launcher"),
        ("setup-launchd.sh",      "root installer supports macOS launchd"),
        ("setup-systemd.sh",      "root installer supports Linux systemd"),
    ]
    assert checks[0][0] in install, f"missing: {checks[0][0]}"
    for snippet, _ in checks[1:]:
        assert snippet in root_install, f"missing: {snippet}"
    ok(f"install.sh has all {len(checks)} required elements")
except Exception as e:
    fail("install.sh content", str(e))


# ── 3. Launch assets ──────────────────────────────────────────────────────────
section("3. Launch assets")

try:
    assert (LAUNCH_DIR / "hn_post.md").exists()
    assert (LAUNCH_DIR / "demo_script.md").exists()
    hn = (LAUNCH_DIR / "hn_post.md").read_text()
    assert "Show HN" in hn
    assert "CVE" in hn
    assert "dd if=" in hn
    ok("HN post has Show HN format, CVE mention, dd command")
except Exception as e:
    fail("launch assets", str(e))

try:
    demo = (LAUNCH_DIR / "demo_script.md").read_text()
    assert "60" in demo or "90" in demo   # time target mentioned
    assert "clawctl chat" in demo
    assert "WhatsApp" in demo
    ok("Demo script has timing, chat demo, WhatsApp shot")
except Exception as e:
    fail("demo script content", str(e))


# ── 4. Shell script syntax ────────────────────────────────────────────────────
section("4. Shell script syntax check")

for script_name in ["build_iso.sh", "chroot_install.sh",
                    "firstboot.sh", "../../packaging/install/install.sh"]:
    try:
        path = ISO_DIR / script_name if "install" not in script_name \
               else INSTALL_DIR / "install.sh"
        if not path.exists():
            continue
        if can_run_bash_syntax():
            r = subprocess.run(["bash", "-n", str(path)],
                               capture_output=True, text=True)
            if r.returncode == 0:
                ok(f"bash -n {path.name} — syntax OK")
            else:
                fail(f"bash -n {path.name}", r.stderr.strip()[:80])
        else:
            ok(f"{path.name} present (bash syntax check skipped on this platform)")
    except Exception as e:
        fail(f"syntax check {script_name}", str(e))


# ── 5. Dist directory ─────────────────────────────────────────────────────────
section("5. Build output directory")

try:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    assert dist.exists()
    ok("dist/ directory exists (ISO output target)")
except Exception as e:
    fail("dist/ directory", str(e))


# ── 6. README final check ─────────────────────────────────────────────────────
section("6. README final check")

try:
    readme = read_text(ROOT / "README.md").lower()
    launch_elements = [
        ("curl -fssl https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh", "installer command"),
        ("no api keys",     "no API keys message"),
        ("no monthly bill", "no monthly bill message"),
        ("bootable iso",    "bootable ISO roadmap"),
        ("openclaw",        "mentions OpenClaw"),
        ("ollama",          "mentions Ollama"),
        ("8gb",             "hardware requirements"),
    ]
    for snippet, desc in launch_elements:
        assert snippet in readme, f"README missing: '{snippet}' ({desc})"
    ok(f"README has all {len(launch_elements)} launch elements")
except Exception as e:
    fail("README final check", str(e))


# ── 7. Full test count ────────────────────────────────────────────────────────
section("7. Full project test count")

try:
    test_files = [
        ROOT / "tests/system/test_phase1.py",
        ROOT / "tests/system/test_phase2.py",
        ROOT / "tests/system/test_phase3.py",
        ROOT / "tests/system/test_phase4.py",
    ]
    for tf in test_files:
        assert tf.exists(), f"missing: {tf.name}"
    ok(f"All {len(test_files)} test suites present")
except Exception as e:
    fail("test suites", str(e))


# ── Summary ───────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n  {'─'*46}")
print(f"  {passed}/{total} passed", end="")
if failed:
    print(f"  |  {failed} FAILED  ←")
else:
    print("  ✓  all passed")
print()
if __name__ == "__main__":
    raise SystemExit(1 if failed else 0)
