# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Phase 15 — Skill Marketplace tests.
Tests ClawHub wrapper, Ed25519 verification, sandbox escape prevention.
Network-dependent tests skip gracefully when offline.
"""
import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── 1. Registry module loads ──────────────────────────────────────────────────

def test_registry_imports():
    from skills.marketplace import registry
    assert hasattr(registry, "search_skills")
    assert hasattr(registry, "get_skill_detail")
    assert hasattr(registry, "get_installed_skills")


def test_registry_search_offline_graceful():
    """search_skills() returns error dict (not raises) when ClawHub unreachable."""
    from skills.marketplace.registry import search_skills
    with patch("skills.marketplace.registry._http_get", return_value=None):
        result = search_skills("weather")
    assert "results" in result
    assert result["results"] == []
    assert "error" in result


def test_registry_search_normalizes_response():
    """search_skills() normalizes ClawHub response to ClawOS format."""
    from skills.marketplace.registry import search_skills
    fake_response = {
        "skills": [
            {"id": "weather-brief", "name": "Weather Brief",
             "description": "Get current weather", "author": "alice",
             "version": "1.2.0", "downloads": 5000, "tags": ["weather"]},
        ],
        "total": 1,
    }
    with patch("skills.marketplace.registry._http_get", return_value=fake_response):
        with patch("skills.marketplace.registry._load_sig_index", return_value={}):
            with patch("skills.marketplace.registry._is_installed", return_value=False):
                result = search_skills("weather")
    assert len(result["results"]) == 1
    skill = result["results"][0]
    assert skill["id"] == "weather-brief"
    assert skill["trust_tier"] == "community"  # not in sig index
    assert "name" in skill
    assert "description" in skill


def test_registry_verified_tier_when_in_sig_index():
    """Skills in signature index get trust_tier=clawos_verified."""
    from skills.marketplace.registry import search_skills
    fake_response = {
        "skills": [{"id": "verified-skill", "name": "Verified Skill",
                    "description": "A verified skill", "author": "clawos",
                    "version": "1.0.0"}],
        "total": 1,
    }
    with patch("skills.marketplace.registry._http_get", return_value=fake_response):
        with patch("skills.marketplace.registry._load_sig_index",
                   return_value={"verified-skill": {"signature": "abc123"}}):
            with patch("skills.marketplace.registry._is_installed", return_value=False):
                result = search_skills("verified")
    assert result["results"][0]["trust_tier"] == "clawos_verified"


# ── 2. Verifier — Ed25519 ─────────────────────────────────────────────────────

def test_verifier_imports():
    from skills.marketplace import verifier
    assert hasattr(verifier, "verify_skill_yaml")
    assert hasattr(verifier, "compute_skill_hash")
    assert hasattr(verifier, "verify_signature")


def test_verify_skill_yaml_valid():
    """verify_skill_yaml() returns valid for well-formed skill."""
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "skill.yaml").write_text(
            "name: test-skill\nversion: 1.0.0\nauthor: alice\n"
            "description: A test skill\nentry: entry.py\npermissions: []\n"
        )
        (d / "entry.py").write_text("def run(input, context): return 'ok'")
        from skills.marketplace.verifier import verify_skill_yaml
        valid, reason, meta = verify_skill_yaml(d)
    assert valid is True
    assert meta["name"] == "test-skill"


def test_verify_skill_yaml_missing_name():
    """verify_skill_yaml() fails when name is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "skill.yaml").write_text(
            "version: 1.0.0\nauthor: alice\ndescription: test\nentry: entry.py\n"
        )
        (d / "entry.py").write_text("def run(i, c): return 'ok'")
        from skills.marketplace.verifier import verify_skill_yaml
        valid, reason, _ = verify_skill_yaml(d)
    assert valid is False
    assert "name" in reason.lower()


def test_compute_skill_hash_deterministic():
    """Same files → same hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "skill.yaml").write_text("name: x\nversion: 1.0\nauthor: a\ndescription: x\nentry: entry.py\n")
        (d / "entry.py").write_text("def run(i, c): return 'hello'")
        from skills.marketplace.verifier import compute_skill_hash
        h1 = compute_skill_hash(d)
        h2 = compute_skill_hash(d)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_skill_hash_changes_on_edit():
    """Modifying entry.py changes the hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "skill.yaml").write_text("name: x\nversion: 1.0\nauthor: a\ndescription: x\nentry: entry.py\n")
        (d / "entry.py").write_text("def run(i, c): return 'hello'")
        from skills.marketplace.verifier import compute_skill_hash
        h1 = compute_skill_hash(d)
        (d / "entry.py").write_text("def run(i, c): return 'injected_code'")
        h2 = compute_skill_hash(d)
    assert h1 != h2


# ── 3. Sandbox — blocked imports ─────────────────────────────────────────────

def test_sandbox_blocks_os_import():
    """Sandbox blocks 'import os' in skill code."""
    from skills.marketplace.sandbox import SkillSandbox
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "skill.yaml").write_text("name: evil\nversion: 1.0\nauthor: x\ndescription: x\nentry: entry.py\npermissions: []\n")
        (d / "entry.py").write_text("import os\ndef run(i, c): return os.getcwd()")
        sb = SkillSandbox(d, "ws_test", "evil", [])
        result = sb.run({})
    assert result["ok"] is False
    assert "os" in result["error"].lower() or "blocked" in result["error"].lower()


def test_sandbox_blocks_subprocess():
    """Sandbox blocks subprocess import."""
    from skills.marketplace.sandbox import SkillSandbox
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "skill.yaml").write_text("name: evil2\nversion: 1.0\nauthor: x\ndescription: x\nentry: entry.py\npermissions: []\n")
        (d / "entry.py").write_text("import subprocess\ndef run(i, c): return subprocess.check_output(['id'])")
        sb = SkillSandbox(d, "ws_test", "evil2", [])
        result = sb.run({})
    assert result["ok"] is False


def test_sandbox_allows_safe_skill():
    """Sandbox allows a skill that uses only whitelisted builtins."""
    from skills.marketplace.sandbox import SkillSandbox
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "skill.yaml").write_text("name: safe\nversion: 1.0\nauthor: x\ndescription: x\nentry: entry.py\npermissions: []\n")
        (d / "entry.py").write_text(
            "def run(input_data, context):\n"
            "    result = [str(x) for x in range(5)]\n"
            "    context.log('Skill ran OK')\n"
            "    return ', '.join(result)\n"
        )
        sb = SkillSandbox(d, "ws_test", "safe", [])
        result = sb.run({"query": "test"})
    assert result["ok"] is True
    assert result["output"] == "0, 1, 2, 3, 4"


def test_sandbox_permission_check():
    """SkillContext raises PermissionError for undeclared permissions."""
    from skills.marketplace.sandbox import SkillContext
    ctx = SkillContext("ws_test", "my-skill", permissions=[])
    with pytest.raises(PermissionError):
        ctx.read_file("some_file.txt")


# ── 4. AST scan in installer ─────────────────────────────────────────────────

def test_installer_smoke_test_catches_blocked_import():
    """_sandbox_smoke_test flags skills with blocked imports."""
    from skills.marketplace.installer import _sandbox_smoke_test
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "entry.py").write_text("import subprocess\nimport os\ndef run(i,c): pass")
        result = _sandbox_smoke_test(d, {"entry": "entry.py"})
    assert result["ok"] is False
    assert "subprocess" in result["error"] or "os" in result["error"]


def test_installer_smoke_test_passes_safe_skill():
    """_sandbox_smoke_test passes safe skills."""
    from skills.marketplace.installer import _sandbox_smoke_test
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        (d / "entry.py").write_text("import json\ndef run(i, c): return json.dumps(i)")
        result = _sandbox_smoke_test(d, {"entry": "entry.py"})
    assert result["ok"] is True


# ── 5. Registry DB operations ─────────────────────────────────────────────────

def test_registry_install_uninstall_cycle():
    """register_installed / unregister_installed round-trip works."""
    from skills.marketplace.registry import (
        register_installed, unregister_installed, _is_installed
    )
    with patch("skills.marketplace.registry.INSTALLED_DB") as mock_db:
        # Use a temp file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = Path(f.name)
        tmp.write_text("{}")

        import skills.marketplace.registry as reg
        orig_db = reg.INSTALLED_DB
        reg.INSTALLED_DB = tmp
        try:
            register_installed("test-skill-xyz", "Test Skill", "1.0", "community", "/tmp/test")
            assert _is_installed("test-skill-xyz") is True
            unregister_installed("test-skill-xyz")
            assert _is_installed("test-skill-xyz") is False
        finally:
            reg.INSTALLED_DB = orig_db
            tmp.unlink(missing_ok=True)
