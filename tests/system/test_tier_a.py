"""
ClawOS Tier A System Tests
===========================
Tests PicoClaw installer detection and service structure.
Runs without live hardware — validates code paths only.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

passed = 0
failed = 0


def ok(label):
    global passed; passed += 1
    print(f"  ✓  {label}")

def fail(label, reason=""):
    global failed; failed += 1
    msg = f"  ✗  {label}"
    if reason: msg += f"  [{reason}]"
    print(msg)


def test_picoclawd_service_importable():
    try:
        from services.picoclawd.service import PicoClawd, get_picoclawd
        ok("picoclawd service importable")
    except Exception as e:
        fail("picoclawd service importable", str(e))


def test_picoclawd_installer_importable():
    try:
        from services.picoclawd.installer import is_installed, _arch_suffix
        suffix = _arch_suffix()
        assert suffix in ("arm64", "arm32", "riscv64", "amd64"), f"unknown arch: {suffix}"
        ok(f"picoclawd installer importable (arch={suffix})")
    except Exception as e:
        fail("picoclawd installer importable", str(e))


def test_picoclawd_bridge_importable():
    try:
        from services.picoclawd.bridge import send
        ok("picoclawd bridge importable")
    except Exception as e:
        fail("picoclawd bridge importable", str(e))


def test_is_tier_a_logic():
    try:
        from services.picoclawd.service import is_arm
        # On CI/x86 this should return False — that's expected
        result = is_arm()
        ok(f"is_arm() callable → {result}")
    except Exception as e:
        fail("is_arm() callable", str(e))


def test_picoclaw_config_path():
    try:
        from services.picoclawd.installer import CONFIG_PATH, INSTALL_PATH
        assert "picoclaw" in str(CONFIG_PATH).lower() or ".picoclaw" in str(CONFIG_PATH)
        ok(f"picoclaw paths correct ({CONFIG_PATH})")
    except Exception as e:
        fail("picoclaw paths", str(e))


if __name__ == "__main__":
    print("\n  ClawOS — Tier A Tests\n  " + "─" * 40)
    test_picoclawd_service_importable()
    test_picoclawd_installer_importable()
    test_picoclawd_bridge_importable()
    test_is_tier_a_logic()
    test_picoclaw_config_path()
    print(f"\n  {passed} passed  {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)
