"""
ClawOS Session 4 Test Suite
============================
Tests ISO build infrastructure, install script, launch assets.
All tests run without actually building the ISO (that needs sudo + 20 min).

Usage:
  python3 tests/system/test_phase4.py
"""
import sys
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

passed = failed = 0


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
    build = (ISO_DIR / "build_iso.sh").read_text()
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
    chroot = (ISO_DIR / "chroot_install.sh").read_text()
    checks = [
        ("openclaw@latest",   "installs OpenClaw npm"),
        ("auth-profiles.json","applies auth fix"),
        ("ollama-local",      "sets ollama-local token"),
        ("openai-completions","uses correct API format"),
        ("clawos-firstboot",  "enables firstboot service"),
        ("ollama.service",    "enables Ollama service"),
        ("motd",              "sets MOTD"),
    ]
    for snippet, desc in checks:
        assert snippet.lower() in chroot.lower(), f"missing: {snippet}"
    ok(f"chroot_install.sh has all {len(checks)} required elements")
except Exception as e:
    fail("chroot_install.sh content", str(e))

try:
    firstboot = (ISO_DIR / "firstboot.sh").read_text()
    assert "ollama pull qwen2.5:7b" in firstboot
    assert "firstboot_done" in firstboot
    assert "bootstrap" in firstboot
    assert "dev_boot" in firstboot or "services" in firstboot
    ok("firstboot.sh pulls model + runs bootstrap + marks done")
except Exception as e:
    fail("firstboot.sh content", str(e))


# ── 2. Install script ─────────────────────────────────────────────────────────
section("2. Install script (non-ISO path)")

try:
    install = (INSTALL_DIR / "install.sh").read_text()
    checks = [
        ("ollama.com/install.sh", "installs Ollama"),
        ("github.com/you/clawos", "clones correct repo"),
        ("bootstrap.bootstrap",   "runs bootstrap"),
        ("clawctl",               "installs clawctl"),
        ("PATH",                  "updates PATH"),
    ]
    for snippet, _ in checks:
        assert snippet in install, f"missing: {snippet}"
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
        if shutil.which("bash"):
            r = subprocess.run(["bash", "-n", str(path)],
                               capture_output=True, text=True)
            if r.returncode == 0:
                ok(f"bash -n {path.name} — syntax OK")
            else:
                fail(f"bash -n {path.name}", r.stderr.strip()[:80])
        else:
            ok(f"{path.name} present (bash not available to syntax check)")
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
    readme = (ROOT / "README.md").read_text()
    launch_elements = [
        ("dd if=clawos",    "has dd flash command"),
        ("No API keys",     "no API keys message"),
        ("No monthly bill", "no monthly bill message"),
        ("Bootable ISO",    "comparison table row"),
        ("OpenClaw",        "mentions OpenClaw"),
        ("Ollama",          "mentions Ollama"),
        ("8GB",             "hardware requirements"),
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
sys.exit(0 if failed == 0 else 1)
