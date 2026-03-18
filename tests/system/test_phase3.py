"""
ClawOS Session 3 Test Suite
============================
Tests OpenClaw integration layer — config gen, installer checks,
auth fix, model detection, clawctl openclaw commands.

Usage:
  python3 tests/system/test_phase3.py
  python3 tests/system/test_phase3.py --e2e   (needs OpenClaw installed)
"""
import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

E2E    = "--e2e" in sys.argv
passed = failed = 0


def ok(name):
    global passed; passed += 1
    print(f"  ✓  {name}")


def fail(name, reason=""):
    global failed; failed += 1
    print(f"  ✗  {name}" + (f" — {reason}" if reason else ""))


def section(title):
    print(f"\n  ── {title}")


# ── 1. Config generation ──────────────────────────────────────────────────────
section("1. OpenClaw config generation")

try:
    from openclaw_integration.config_gen import gen_config, GOOD_MODELS
    cfg = gen_config("qwen2.5:7b")

    # Correct API format
    provider = cfg["models"]["providers"]["ollama"]
    assert provider["api"] == "openai-completions", \
        f"Wrong api: {provider['api']} (must be openai-completions)"
    assert "/v1" in provider["baseUrl"], "baseUrl must include /v1"
    assert provider["apiKey"] == "ollama-local"
    ok("api=openai-completions, baseUrl includes /v1, apiKey=ollama-local")
except Exception as e:
    fail("config API format", str(e))

try:
    from openclaw_integration.config_gen import gen_config
    cfg = gen_config("qwen2.5:7b")
    assert cfg["cloud"]["enabled"] is False
    assert cfg["network"]["mode"] == "offline"
    assert cfg["network"]["allow_internet"] is False
    ok("cloud disabled, network offline, no internet")
except Exception as e:
    fail("config offline mode", str(e))

try:
    from openclaw_integration.config_gen import gen_config
    cfg = gen_config("qwen3:8b")
    model = cfg["models"]["providers"]["ollama"]["models"][0]
    assert model["id"] == "qwen3:8b"
    assert model["contextWindow"] == 131072
    assert model["inputCostPer1M"] == 0
    assert cfg["agents"]["defaults"]["model"]["primary"] == "ollama/qwen3:8b"
    ok("qwen3:8b config — ctx=131072, cost=0, primary set correctly")
except Exception as e:
    fail("config model fields", str(e))

try:
    from openclaw_integration.config_gen import GOOD_MODELS
    assert "gemma3:4b" not in GOOD_MODELS, "gemma3:4b must NOT be in GOOD_MODELS"
    assert "qwen2.5:7b" in GOOD_MODELS
    assert "qwen3:8b" in GOOD_MODELS
    ok("GOOD_MODELS excludes gemma3:4b, includes qwen2.5:7b and qwen3:8b")
except Exception as e:
    fail("GOOD_MODELS contents", str(e))


# ── 2. Auth fix ───────────────────────────────────────────────────────────────
section("2. Linux auth fix (issue #22055)")

try:
    from openclaw_integration.config_gen import apply_auth_fix
    with tempfile.TemporaryDirectory() as td:
        import openclaw_integration.config_gen as cg
        orig = cg.AUTH_FIX_PATH
        cg.AUTH_FIX_PATH = Path(td) / "agents" / "main" / "agent" / "auth-profiles.json"
        path = apply_auth_fix()
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["ollama:local"]["token"] == "ollama-local"
        assert data["ollama:local"]["provider"] == "ollama"
        assert data["lastGood"]["ollama"] == "ollama:local"
        cg.AUTH_FIX_PATH = orig
    ok("auth-profiles.json written with correct ollama-local token")
except Exception as e:
    fail("auth fix", str(e))


# ── 3. Config write ───────────────────────────────────────────────────────────
section("3. Config write to disk")

try:
    from openclaw_integration.config_gen import write_config
    with tempfile.TemporaryDirectory() as td:
        import openclaw_integration.config_gen as cg
        orig_dir  = cg.OPENCLAW_DIR
        orig_path = cg.CONFIG_PATH
        cg.OPENCLAW_DIR = Path(td)
        cg.CONFIG_PATH  = Path(td) / "openclaw.json"
        path = write_config("qwen2.5:7b")
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["cloud"]["enabled"] is False
        cg.OPENCLAW_DIR = orig_dir
        cg.CONFIG_PATH  = orig_path
    ok("write_config() creates valid openclaw.json")
except Exception as e:
    fail("write_config", str(e))


# ── 4. System check ───────────────────────────────────────────────────────────
section("4. Installer system check")

try:
    from openclaw_integration.installer import system_check
    c = system_check()
    assert "node" in c
    assert "npm" in c
    assert "openclaw" in c
    assert "ollama" in c
    assert "ram_gb" in c
    assert "ram_ok" in c
    assert "node_version" in c
    assert isinstance(c["ram_gb"], float)
    ok(f"system_check() — ram={c['ram_gb']}GB node_v={c['node_version']} ollama={c['ollama']}")
except Exception as e:
    fail("system_check", str(e))

try:
    from openclaw_integration.installer import MIN_RAM_GB, NODE_MIN_VER
    assert MIN_RAM_GB == 14
    assert NODE_MIN_VER == 22
    ok(f"constants: MIN_RAM_GB={MIN_RAM_GB}, NODE_MIN_VER={NODE_MIN_VER}")
except Exception as e:
    fail("installer constants", str(e))


# ── 5. model detection ────────────────────────────────────────────────────────
section("5. Model detection")

try:
    from openclaw_integration.config_gen import detect_best_model
    model = detect_best_model()
    assert isinstance(model, str)
    assert ":" in model
    ok(f"detect_best_model() returns: {model}")
except Exception as e:
    fail("detect_best_model", str(e))


# ── 6. clawctl openclaw commands ─────────────────────────────────────────────
section("6. clawctl openclaw commands")

try:
    from clawctl.commands.openclaw import (
        run_status, run_install, run_start, run_stop,
        run_restart, run_whatsapp, run_config, run_onboard
    )
    for fn in [run_status, run_install, run_start, run_stop,
               run_restart, run_whatsapp, run_config, run_onboard]:
        assert callable(fn)
    ok("all 8 openclaw commands importable")
except Exception as e:
    fail("openclaw commands import", str(e))


# ── 7. ISO build files ────────────────────────────────────────────────────────
section("7. ISO build infrastructure")

try:
    iso_dir = ROOT / "packaging" / "iso"
    for f in ["build_iso.sh", "chroot_install.sh", "firstboot.sh", "preseed.cfg"]:
        assert (iso_dir / f).exists(), f"missing: {f}"
    build = (iso_dir / "build_iso.sh").read_text()
    assert "xorriso" in build
    assert "mksquashfs" in build
    assert "ClawOS" in build
    ok("All ISO build files exist with correct content")
except Exception as e:
    fail("ISO build files", str(e))

try:
    chroot = (ROOT / "packaging" / "iso" / "chroot_install.sh").read_text()
    assert "openclaw@latest" in chroot
    assert "auth-profiles.json" in chroot
    assert "ollama-local" in chroot
    assert "openai-completions" in chroot or "openclaw.json" in chroot
    ok("chroot_install.sh bakes OpenClaw + auth fix + offline config")
except Exception as e:
    fail("chroot_install.sh content", str(e))


# ── 8. README ─────────────────────────────────────────────────────────────────
section("8. README (launch weapon check)")

try:
    readme = (ROOT / "README.md").read_text()
    checks = [
        ("dd if=clawos.iso",    "has dd flash command"),
        ("No API keys",          "mentions no API keys"),
        ("No monthly bill",      "mentions no monthly bill"),
        ("Bootable ISO",         "has comparison table"),
        ("clawctl openclaw",     "shows openclaw commands"),
        ("OpenClaw ecosystem",   "mentions OpenClaw ecosystem"),
    ]
    for snippet, desc in checks:
        assert snippet in readme, f"missing: {snippet}"
    ok(f"README has all {len(checks)} launch-critical elements")
except Exception as e:
    fail("README content", str(e))


# ── 9. E2E ────────────────────────────────────────────────────────────────────
if E2E:
    section("9. E2E — live OpenClaw")

    try:
        import shutil
        assert shutil.which("openclaw"), "openclaw not in PATH"
        ok("openclaw binary found")
    except Exception as e:
        fail("openclaw binary", str(e))

    try:
        import subprocess
        r = subprocess.run(["openclaw", "--version"],
                           capture_output=True, text=True, timeout=5)
        assert r.returncode == 0
        ok(f"openclaw version: {r.stdout.strip()}")
    except Exception as e:
        fail("openclaw --version", str(e))

    try:
        from openclaw_integration.installer import gateway_status
        status = gateway_status()
        ok(f"gateway_status(): {status[:60]}")
    except Exception as e:
        fail("gateway_status", str(e))
else:
    print("\n  (skip e2e — run with --e2e when OpenClaw is installed)")


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
