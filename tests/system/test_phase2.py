"""
ClawOS Session 2 Test Suite
============================
Tests bootstrap, hardware probe, profile selector, wizard state,
workspace init, permissions, memory init, clawctl commands.

Usage:
  python3 tests/system/test_phase2.py
  python3 tests/system/test_phase2.py --e2e
"""
import sys
import asyncio
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

E2E = "--e2e" in sys.argv
passed = failed = 0


def ok(name):
    global passed; passed += 1
    print(f"  ✓  {name}")


def fail(name, reason=""):
    global failed; failed += 1
    print(f"  ✗  {name}" + (f" — {reason}" if reason else ""))


def section(title):
    print(f"\n  ── {title}")


# ── 1. Hardware probe ─────────────────────────────────────────────────────────
section("1. Hardware probe")

try:
    from bootstrap.hardware_probe import HardwareProfile, _ram_gb, _cpu_cores, _disk_free_gb
    ram = _ram_gb()
    assert ram > 0
    ok(f"_ram_gb() = {ram}GB")
except Exception as e:
    fail("_ram_gb", str(e))

try:
    from bootstrap.hardware_probe import _cpu_cores
    cores = _cpu_cores()
    assert cores >= 1
    ok(f"_cpu_cores() = {cores}")
except Exception as e:
    fail("_cpu_cores", str(e))

try:
    from bootstrap.hardware_probe import _disk_free_gb
    free = _disk_free_gb("/")
    assert free > 0
    ok(f"_disk_free_gb('/') = {free}GB")
except Exception as e:
    fail("_disk_free_gb", str(e))

try:
    from bootstrap.hardware_probe import probe
    hw = probe()
    assert hw.ram_gb > 0
    assert hw.cpu_cores >= 1
    assert hw.tier in ("A", "B", "C")
    assert hw.disk_free_gb > 0
    ok(f"probe() — tier={hw.tier} ram={hw.ram_gb}GB cpu={hw.cpu_cores}")
except Exception as e:
    fail("probe()", str(e))

try:
    from bootstrap.hardware_probe import probe_and_save, load_saved
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.HARDWARE_JSON = Path(td) / "hardware.json"
        hw1 = probe_and_save()
        hw2 = load_saved()
        assert hw1.ram_gb == hw2.ram_gb
        assert hw1.tier   == hw2.tier
    ok("probe_and_save() + load_saved() round-trip")
except Exception as e:
    fail("probe_and_save/load_saved", str(e))


# ── 2. Profile selector ───────────────────────────────────────────────────────
section("2. Profile selector")

try:
    from bootstrap.hardware_probe import HardwareProfile
    from bootstrap.profile_selector import select

    assert select(HardwareProfile(ram_gb=8,  tier="A")) == "lowram"
    assert select(HardwareProfile(ram_gb=16, tier="B")) == "balanced"
    assert select(HardwareProfile(ram_gb=32, tier="C")) == "performance"
    assert select(HardwareProfile(ram_gb=16, gpu_vram_gb=10, tier="B")) == "performance"
    ok("select() — lowram/balanced/performance/GPU override")
except Exception as e:
    fail("profile select()", str(e))

try:
    from bootstrap.profile_selector import openclaw_feasible, voice_feasible, recommended_model
    from bootstrap.hardware_probe import HardwareProfile
    assert openclaw_feasible(HardwareProfile(ram_gb=16)) is True
    assert openclaw_feasible(HardwareProfile(ram_gb=8))  is False
    assert voice_feasible(HardwareProfile(ram_gb=8, has_mic=True)) is True
    assert voice_feasible(HardwareProfile(ram_gb=8, has_mic=False)) is False
    assert recommended_model(HardwareProfile(ram_gb=8))  == "qwen2.5:3b",  "Tier A (<12GB) should use qwen2.5:3b to avoid OOM"
    assert recommended_model(HardwareProfile(ram_gb=16)) == "qwen2.5:7b",  "Tier B should use qwen2.5:7b"
    assert recommended_model(HardwareProfile(ram_gb=32)) == "qwen2.5:7b",  "Tier C should use qwen2.5:7b"
    ok("openclaw_feasible, voice_feasible, recommended_model — qwen2.5:3b Tier A, qwen2.5:7b Tier B/C")
except Exception as e:
    fail("profile helpers", str(e))

try:
    from bootstrap.profile_selector import summary
    from bootstrap.hardware_probe import HardwareProfile
    s = summary(HardwareProfile(ram_gb=16, cpu_cores=8, tier="B"))
    assert "16" in s and "balanced" in s
    ok("summary() returns formatted string")
except Exception as e:
    fail("profile summary", str(e))


# ── 3. Workspace init ─────────────────────────────────────────────────────────
section("3. Workspace init")

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        import clawos_core.util.paths as _paths
        constants.CLAWOS_DIR = Path(td)
        _paths.CLAWOS_DIR    = Path(td)
        # Patch module-level constants in paths
        import importlib
        from bootstrap.workspace_init import init_all_dirs, init_workspace
        init_all_dirs()
        for sub in ("config","logs","memory","workspace","voice"):
            assert (Path(td) / sub).exists(), f"missing {sub}/"
        ok("init_all_dirs() creates all required subdirs")
except Exception as e:
    fail("init_all_dirs", str(e))

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        import clawos_core.util.paths as _paths
        constants.CLAWOS_DIR = Path(td)
        _paths.CLAWOS_DIR    = Path(td)
        from bootstrap.workspace_init import init_all_dirs, init_workspace
        init_all_dirs()
        ws = init_workspace("test_ws")
        mem = Path(td) / "memory" / "test_ws"
        assert (mem / "SOUL.md").exists()
        assert (mem / "AGENTS.md").exists()
        assert (mem / "HEARTBEAT.md").exists()
        assert (mem / "PINNED.md").exists()
        ok("init_workspace() seeds SOUL/AGENTS/HEARTBEAT/PINNED")
except Exception as e:
    fail("init_workspace", str(e))


# ── 4. Memory init ────────────────────────────────────────────────────────────
section("4. Memory init")

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.MEMORY_FTS_DB = Path(td) / "fts.db"
        constants.MEMORY_DIR    = Path(td)
        from bootstrap.memory_init import init_fts
        ok_fts = init_fts()
        assert ok_fts
        import sqlite3
        db = sqlite3.connect(str(constants.MEMORY_FTS_DB))
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "memories_meta" in tables
        ok("init_fts() creates FTS5 tables")
except Exception as e:
    fail("init_fts", str(e))


# ── 5. Permissions init ───────────────────────────────────────────────────────
section("5. Permissions init")

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.CONFIG_DIR = Path(td)
        from bootstrap.permissions_init import write, load
        path = write("recommended", "test_ws")
        assert path.exists()
        policy = load()
        assert policy["mode"] == "recommended"
        assert "nexus_default" in policy["workspaces"] or "test_ws" in policy["workspaces"]
        ok("permissions_init — write() + load() round-trip")
except Exception as e:
    fail("permissions_init", str(e))

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.CONFIG_DIR = Path(td)
        from bootstrap.permissions_init import write, DEVELOPER_EXTRAS
        write("developer", "test_ws")
        from bootstrap.permissions_init import load
        policy = load()
        assert policy["mode"] == "developer"
        ok("permissions_init — developer mode written correctly")
except Exception as e:
    fail("permissions_init developer", str(e))


# ── 6. Wizard state ───────────────────────────────────────────────────────────
section("6. Wizard state")

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.CONFIG_DIR = Path(td)
        import setup.first_run.state as state_mod
        state_mod.STATE_FILE = Path(td) / "wizard_state.json"
        from setup.first_run.state import WizardState
        s = WizardState()
        s.profile  = "balanced"
        s.runtime  = "core"
        s.workspace_id = "my_ws"
        s.save()
        s2 = WizardState.load()
        assert s2.profile      == "balanced"
        assert s2.runtime      == "core"
        assert s2.workspace_id == "my_ws"
        ok("WizardState — save() + load() round-trip")
except Exception as e:
    fail("WizardState", str(e))

try:
    with tempfile.TemporaryDirectory() as td:
        import setup.first_run.state as state_mod
        state_mod.STATE_FILE = Path(td) / "wizard_state.json"
        from setup.first_run.state import WizardState
        s = WizardState()
        s.mark_done("welcome")
        s.mark_done("hardware_profile")
        assert "welcome"          in s.screens_done
        assert "hardware_profile" in s.screens_done
        assert len(s.screens_done) == 2
        # Idempotent
        s.mark_done("welcome")
        assert s.screens_done.count("welcome") == 1
        ok("WizardState — mark_done() idempotent")
except Exception as e:
    fail("WizardState mark_done", str(e))


# ── 7. clawctl commands ───────────────────────────────────────────────────────
section("7. clawctl commands")

try:
    from clawctl.ui.banner import status_icon, success, error, info, table
    assert status_icon("active")   == "✓"
    assert status_icon("failed")   == "✗"
    assert status_icon("inactive") == "○"
    ok("clawctl banner — status_icon(), helpers")
except Exception as e:
    fail("clawctl banner", str(e))

try:
    from clawctl.commands.model import run_list
    # Just ensure it's importable and callable
    assert callable(run_list)
    ok("clawctl model commands importable")
except Exception as e:
    fail("clawctl model import", str(e))

try:
    from clawctl.commands.workspace import run_list, run_create, run_delete
    assert callable(run_list) and callable(run_create) and callable(run_delete)
    ok("clawctl workspace commands importable")
except Exception as e:
    fail("clawctl workspace import", str(e))

try:
    from clawctl.commands.openclaw import run_status, run_install, run_start, run_stop
    assert callable(run_status)
    ok("clawctl openclaw commands importable")
except Exception as e:
    fail("clawctl openclaw import", str(e))

try:
    from clawctl.main import main
    assert callable(main)
    ok("clawctl main entry point importable")
except Exception as e:
    fail("clawctl main", str(e))


# ── 8. Config profiles ────────────────────────────────────────────────────────
section("8. Config profiles")

try:
    configs = ["defaults", "lowram", "balanced", "performance"]
    for name in configs:
        path = ROOT / "configs" / f"{name}.yaml"
        assert path.exists(), f"{name}.yaml missing"
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data is not None
    ok("All 4 config YAML files exist and parse cleanly")
except Exception as e:
    fail("config YAML files", str(e))

try:
    from clawos_core.config.loader import load
    for profile in ["lowram", "balanced", "performance"]:
        cfg = load(profile)
        assert cfg["model"]["chat"]
        assert cfg["_profile"] == profile
    ok("Config loader — all profiles load with model.chat set")
except Exception as e:
    fail("config loader profiles", str(e))


# ── 9. systemd unit files ─────────────────────────────────────────────────────
section("9. Systemd unit files")

try:
    units_dir = ROOT / "packaging" / "systemd"
    expected = [
        "clawos-policyd.service",
        "clawos-memd.service",
        "clawos-modeld.service",
        "clawos-toolbridge.service",
        "clawos-agentd.service",
        "clawos-voiced.service",
        "clawos-clawd.service",
        "clawos-dashd.service",
        "clawos-gatewayd.service",
    ]
    for unit in expected:
        path = units_dir / unit
        assert path.exists(), f"missing: {unit}"
        content = path.read_text()
        assert "ExecStart" in content
        assert "Restart"   in content
    ok(f"All 9 systemd unit files exist with ExecStart + Restart")
except Exception as e:
    fail("systemd units", str(e))


# ── 10. Project structure ─────────────────────────────────────────────────────
section("10. Project structure")

try:
    required_files = [
        "README.md", "pyproject.toml", "Makefile",
        "PROJECT_TRUTH.md",
        "scripts/dev_boot.sh",
        "scripts/seed_workspace.sh",
        "packaging/install/install.sh",
        "clients/dashboard/index.html",
    ]
    for f in required_files:
        assert (ROOT / f).exists(), f"missing: {f}"
    ok(f"All {len(required_files)} required project files exist")
except Exception as e:
    fail("project structure", str(e))

try:
    services = ["policyd","memd","modeld","toolbridge","agentd","voiced","clawd","dashd","gatewayd"]
    for svc in services:
        svc_dir = ROOT / "services" / svc
        assert (svc_dir / "service.py").exists() or (svc_dir / "api.py").exists(), \
            f"services/{svc}/service.py missing"
    ok("All 9 service directories have a service.py or api.py")
except Exception as e:
    fail("service files", str(e))


# ── 11. E2E (requires live Ollama) ────────────────────────────────────────────
if E2E:
    section("11. E2E — live Ollama + bootstrap")

    try:
        from bootstrap.model_provision import ollama_running
        assert ollama_running(), "Ollama not running"
        ok("Ollama running")
    except Exception as e:
        fail("Ollama running", str(e))

    try:
        with tempfile.TemporaryDirectory() as td:
            from clawos_core import constants
            constants.CLAWOS_DIR    = Path(td)
            constants.CONFIG_DIR    = Path(td) / "config"
            constants.MEMORY_DIR    = Path(td) / "memory"
            constants.HARDWARE_JSON = Path(td) / "config" / "hardware.json"
            constants.CLAWOS_CONFIG = Path(td) / "config" / "clawos.yaml"
            import clawos_core.util.paths as _p
            _p.CLAWOS_DIR = Path(td)
            from bootstrap.bootstrap import run as boot_run
            result = boot_run(profile="lowram", yes=True, workspace="e2e_test")
            assert result["profile"] == "lowram"
            assert result["workspace"] == "e2e_test"
            ok("bootstrap.run() completes end-to-end")
    except Exception as e:
        fail("bootstrap e2e", str(e))
else:
    print("\n  (skip e2e — run with --e2e for live Ollama tests)")


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
