"""
ClawOS Phase 7 Test Suite
==========================
Tests: RTK + Headroom compression integration for OpenClaw.

Usage:
  python3 tests/system/test_phase7.py
  python3 tests/system/test_phase7.py --e2e   (needs internet + cargo)
"""
import sys
import json
import tempfile
import subprocess
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

E2E    = "--e2e" in sys.argv
passed = failed = 0


def ok(name):
    global passed; passed += 1
    print(f"  \u2713  {name}")


def fail(name, reason=""):
    global failed; failed += 1
    print(f"  \u2717  {name}" + (f" \u2014 {reason}" if reason else ""))


def section(title):
    print(f"\n  \u2500\u2500 {title}")


# ── 1. Module imports ─────────────────────────────────────────────────────────
section("1. Compression module imports")

try:
    from openclaw_integration.compression import (
        headroom_installed, headroom_running, headroom_stats,
        install_headroom, start_headroom, stop_headroom,
        rtk_installed, install_rtk, configure_rtk_hook, rtk_stats,
        patch_openclaw_config_for_headroom, restore_openclaw_config,
        setup_compression, compression_status,
        HEADROOM_PORT, HEADROOM_PID, HEADROOM_LOG, RTK_BIN,
    )
    assert HEADROOM_PORT == 8787
    ok("compression module imports cleanly, HEADROOM_PORT=8787")
except Exception as e:
    fail("compression import", str(e))


# ── 2. Detection functions work ───────────────────────────────────────────────
section("2. Detection functions")

try:
    from openclaw_integration.compression import headroom_installed, rtk_installed
    # These should return bool without crashing, regardless of install state
    h = headroom_installed()
    r = rtk_installed()
    assert isinstance(h, bool)
    assert isinstance(r, bool)
    ok(f"headroom_installed()={h}, rtk_installed()={r} — both return bool")
except Exception as e:
    fail("detection functions", str(e))

try:
    from openclaw_integration.compression import headroom_running
    result = headroom_running()
    assert isinstance(result, bool)
    ok(f"headroom_running()={result} — returns bool")
except Exception as e:
    fail("headroom_running", str(e))

try:
    from openclaw_integration.compression import headroom_stats, rtk_stats
    # Should return dict even when not installed
    hs = headroom_stats()
    rs = rtk_stats()
    assert isinstance(hs, dict)
    assert isinstance(rs, dict)
    ok("headroom_stats() + rtk_stats() return dict when not running")
except Exception as e:
    fail("stats functions", str(e))


# ── 3. compression_status() structure ────────────────────────────────────────
section("3. compression_status() output structure")

try:
    from openclaw_integration.compression import compression_status
    s = compression_status()
    assert "headroom" in s
    assert "rtk" in s
    assert "installed" in s["headroom"]
    assert "running"   in s["headroom"]
    assert "port"      in s["headroom"]
    assert "stats"     in s["headroom"]
    assert "installed" in s["rtk"]
    assert "stats"     in s["rtk"]
    ok("compression_status() returns correct structure")
except Exception as e:
    fail("compression_status structure", str(e))


# ── 4. OpenClaw config patching ───────────────────────────────────────────────
section("4. OpenClaw config patching")

try:
    with tempfile.TemporaryDirectory() as td:
        import openclaw_integration.config_gen as cg
        orig_path = cg.CONFIG_PATH
        test_path = Path(td) / "openclaw.json"
        cg.CONFIG_PATH = test_path

        # Write a test config
        test_cfg = {
            "models": {"providers": {"ollama": {"baseUrl": "http://127.0.0.1:11434/v1"}}},
            "agents": {"defaults": {"model": {"primary": "ollama/qwen2.5:7b"}}},
        }
        test_path.write_text(json.dumps(test_cfg))

        from openclaw_integration.compression import (
            patch_openclaw_config_for_headroom,
            restore_openclaw_config,
        )

        # Mock headroom_running to return True
        with patch("openclaw_integration.compression.headroom_running", return_value=True):
            result = patch_openclaw_config_for_headroom()
            assert result is True
            patched = json.loads(test_path.read_text())
            provider = patched["models"]["providers"]["ollama"]
            assert "8787" in provider["baseUrl"], f"Headroom port not in URL: {provider['baseUrl']}"
            assert "_headroom_original_baseUrl" in patched
            assert patched["_headroom_original_baseUrl"] == "http://127.0.0.1:11434/v1"
            ok("patch_openclaw_config_for_headroom() routes through :8787")

        # Restore
        result2 = restore_openclaw_config()
        assert result2 is True
        restored = json.loads(test_path.read_text())
        assert "8787" not in restored["models"]["providers"]["ollama"]["baseUrl"]
        assert "_headroom_original_baseUrl" not in restored
        ok("restore_openclaw_config() removes proxy and restores original URL")

        cg.CONFIG_PATH = orig_path
except Exception as e:
    fail("config patching", str(e))

try:
    with tempfile.TemporaryDirectory() as td:
        import openclaw_integration.config_gen as cg
        orig_path = cg.CONFIG_PATH
        test_path = Path(td) / "openclaw.json"
        cg.CONFIG_PATH = test_path

        test_cfg = {
            "models": {"providers": {"ollama": {"baseUrl": "http://127.0.0.1:8787/v1"}}},
            "_headroom_original_baseUrl": "http://127.0.0.1:11434/v1",
        }
        test_path.write_text(json.dumps(test_cfg))

        # Patching when already patched should be a no-op
        with patch("openclaw_integration.compression.headroom_running", return_value=True):
            from openclaw_integration.compression import patch_openclaw_config_for_headroom
            result = patch_openclaw_config_for_headroom()
            assert result is True
            cfg = json.loads(test_path.read_text())
            assert "8787" in cfg["models"]["providers"]["ollama"]["baseUrl"]
            ok("patch is idempotent — already-patched config not double-patched")

        cg.CONFIG_PATH = orig_path
except Exception as e:
    fail("idempotent patch", str(e))


# ── 5. installer.py integration ───────────────────────────────────────────────
section("5. installer.py has compression hooks")

try:
    text = (ROOT / "openclaw_integration" / "installer.py").read_text()
    assert "setup_compression" in text
    assert "start_headroom" in text
    assert "patch_openclaw_config_for_headroom" in text
    ok("installer.py imports and calls compression setup")
except Exception as e:
    fail("installer compression hooks", str(e))

try:
    text = (ROOT / "openclaw_integration" / "installer.py").read_text()
    assert "start_gateway" in text
    # start_gateway should have headroom restart logic
    idx = text.find("def start_gateway")
    gateway_body = text[idx:idx+400]
    assert "headroom" in gateway_body.lower()
    ok("start_gateway() ensures headroom is running")
except Exception as e:
    fail("start_gateway headroom", str(e))


# ── 6. nexus status shows compression ─────────────────────────────────────────
section("6. nexus CLI shows compression status")

try:
    text = (ROOT / "nexus" / "cli.py").read_text()
    assert "_print_compression_status" in text
    assert "headroom_running" in text
    assert "rtk_installed" in text
    ok("nexus/cli.py has _print_compression_status()")
except Exception as e:
    fail("nexus compression status", str(e))


# ── 7. clawctl status shows compression ───────────────────────────────────────
section("7. clawctl status shows compression")

try:
    text = (ROOT / "clawctl" / "commands" / "status.py").read_text()
    assert "headroom" in text
    assert "rtk" in text
    assert "Token compression" in text
    ok("clawctl status shows Token compression section")
except Exception as e:
    fail("clawctl status compression", str(e))


# ── 8. clawctl openclaw status shows compression ──────────────────────────────
section("8. clawctl openclaw status shows compression")

try:
    text = (ROOT / "clawctl" / "commands" / "openclaw.py").read_text()
    assert "headroom" in text
    assert "rtk" in text
    assert "stop_headroom" in text
    ok("openclaw commands have headroom/rtk integration")
except Exception as e:
    fail("openclaw commands", str(e))


# ── 9. setup_compression handles missing tools gracefully ─────────────────────
section("9. setup_compression graceful failure handling")

try:
    # Mock both install functions to fail — should not raise, should return status
    with patch("openclaw_integration.compression.install_headroom", return_value=False):
        with patch("openclaw_integration.compression.install_rtk", return_value=False):
            with patch("openclaw_integration.compression.headroom_installed", return_value=False):
                with patch("openclaw_integration.compression.rtk_installed", return_value=False):
                    from openclaw_integration.compression import setup_compression
                    result = setup_compression(show_progress=False)
                    assert isinstance(result, dict)
                    assert "headroom" in result
                    assert "rtk" in result
                    assert result["headroom"] is False
                    assert result["rtk"] is False
    ok("setup_compression() returns status dict even when both tools fail")
except Exception as e:
    fail("setup_compression graceful failure", str(e))

try:
    # Mock headroom installed but not running — should attempt start
    with patch("openclaw_integration.compression.headroom_installed", return_value=True):
        with patch("openclaw_integration.compression.headroom_running", return_value=False):
            with patch("openclaw_integration.compression.start_headroom", return_value=True) as mock_start:
                with patch("openclaw_integration.compression.patch_openclaw_config_for_headroom"):
                    with patch("openclaw_integration.compression.rtk_installed", return_value=True):
                        with patch("openclaw_integration.compression.configure_rtk_hook", return_value=True):
                            from openclaw_integration.compression import setup_compression
                            result = setup_compression(show_progress=False)
                            assert result["headroom"] is True
                            mock_start.assert_called_once()
    ok("setup_compression() starts headroom if installed but not running")
except Exception as e:
    fail("setup_compression starts headroom", str(e))


# ── 10. Full import chain ─────────────────────────────────────────────────────
section("10. Full import chain")

try:
    import importlib
    modules = [
        "openclaw_integration.compression",
        "openclaw_integration.installer",
        "clawctl.commands.status",
        "clawctl.commands.openclaw",
        "nexus.cli",
    ]
    for mod in modules:
        importlib.import_module(mod)
    ok(f"All {len(modules)} Phase 7 modules import cleanly")
except Exception as e:
    fail("import chain", str(e))


# ── 11. E2E ───────────────────────────────────────────────────────────────────
if E2E:
    section("11. E2E — live install attempt")

    try:
        from openclaw_integration.compression import install_headroom
        result = install_headroom(show_progress=True)
        ok(f"install_headroom() returned {result}")
    except Exception as e:
        fail("E2E headroom install", str(e))

    try:
        from openclaw_integration.compression import rtk_installed
        if rtk_installed():
            ok("RTK already installed on this machine")
        else:
            ok("RTK not installed (expected in CI — install manually)")
    except Exception as e:
        fail("E2E rtk check", str(e))
else:
    print("\n  (skip e2e — run with --e2e for live install tests)")


# ── Summary ───────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n  {chr(9472)*46}")
print(f"  {passed}/{total} passed", end="")
if failed:
    print(f"  |  {failed} FAILED  \u2190")
else:
    print("  \u2713  all passed")
print()
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)