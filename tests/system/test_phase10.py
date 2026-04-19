# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Phase 10 tests — Key Vault, Runtime Selector, OpenRouter config, Dashboard runtime status.
All tests run without a live LLM, live API keys, or live OpenClaw instance.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure repo root is on path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# test_key_registry_structure
# ─────────────────────────────────────────────────────────────────────────────

def test_key_registry_structure():
    """All KEY_REGISTRY entries have required fields with correct types."""
    from clawos_core.key_registry import KEY_REGISTRY

    required_fields = {"id", "label", "description", "url", "required_for", "optional_for", "placements", "tier_shown"}
    placement_types = {"env", "json_key", "secretd"}

    for entry in KEY_REGISTRY:
        missing = required_fields - set(entry.keys())
        assert not missing, f"Entry {entry.get('id')} missing fields: {missing}"

        assert isinstance(entry["id"], str) and entry["id"].isupper(), \
            f"Key ID should be uppercase string: {entry['id']}"
        assert isinstance(entry["placements"], list) and entry["placements"], \
            f"Placements must be non-empty list: {entry['id']}"
        assert isinstance(entry["tier_shown"], list), \
            f"tier_shown must be list: {entry['id']}"

        for p in entry["placements"]:
            assert "type" in p, f"Placement missing 'type' in {entry['id']}"
            assert p["type"] in placement_types, \
                f"Unknown placement type {p['type']} in {entry['id']}"


# ─────────────────────────────────────────────────────────────────────────────
# test_place_env_idempotent
# ─────────────────────────────────────────────────────────────────────────────

def test_place_env_idempotent():
    """Placing the same env key twice doesn't duplicate lines."""
    from services.secretd.placer import _place_env

    with tempfile.NamedTemporaryFile(mode='w', suffix='.bashrc', delete=False) as f:
        f.write('# ClawOS test bashrc\nexport PATH="$PATH:/usr/local/bin"\n')
        tmpfile = f.name

    try:
        _place_env("TEST_KEY", "value1", tmpfile, "TEST_KEY")
        _place_env("TEST_KEY", "value2", tmpfile, "TEST_KEY")  # update

        content = Path(tmpfile).read_text()
        occurrences = content.count('export TEST_KEY=')
        assert occurrences == 1, f"Expected 1 export line, found {occurrences}"
        assert 'value2' in content, "Second placement should have updated the value"
        assert 'value1' not in content, "First value should be replaced"
    finally:
        Path(tmpfile).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# test_place_json_creates_nested_path
# ─────────────────────────────────────────────────────────────────────────────

def test_place_json_creates_nested_path():
    """Deep JSON paths are created correctly by the placement engine."""
    from services.secretd.placer import _place_json

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"models": {}}, f)
        tmpfile = f.name

    try:
        _place_json("sk-test-key", tmpfile, ["models", "providers", "openrouter", "apiKey"])
        data = json.loads(Path(tmpfile).read_text())
        assert data["models"]["providers"]["openrouter"]["apiKey"] == "sk-test-key"
    finally:
        Path(tmpfile).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# test_wizard_state_runtimes
# ─────────────────────────────────────────────────────────────────────────────

def test_wizard_state_runtimes():
    """WizardState serializes/deserializes runtimes list correctly."""
    from setup.first_run.state import WizardState
    import dataclasses

    state = WizardState()
    state.runtimes = ["nexus", "picoclaw", "openclaw"]
    state.hardware_tier = "C"
    state.api_keys_configured = ["OPENROUTER_API_KEY", "OPENAI_API_KEY"]

    d = dataclasses.asdict(state)
    assert d["runtimes"] == ["nexus", "picoclaw", "openclaw"]
    assert d["hardware_tier"] == "C"
    assert d["api_keys_configured"] == ["OPENROUTER_API_KEY", "OPENAI_API_KEY"]

    # Round-trip through JSON
    serialized = json.dumps(d)
    restored = json.loads(serialized)
    state2 = WizardState(**{k: v for k, v in restored.items() if k in WizardState.__dataclass_fields__})
    assert state2.runtimes == ["nexus", "picoclaw", "openclaw"]
    assert state2.hardware_tier == "C"
    assert state2.api_keys_configured == ["OPENROUTER_API_KEY", "OPENAI_API_KEY"]


# ─────────────────────────────────────────────────────────────────────────────
# test_runtime_choice_screen_tiers
# ─────────────────────────────────────────────────────────────────────────────

def test_runtime_choice_screen_tiers():
    """Tier A shows Nexus+PicoClaw default; Tier C shows all three."""
    from bootstrap.profile_selector import recommended_runtimes

    tier_a = recommended_runtimes("A")
    assert "nexus" in tier_a
    assert "picoclaw" in tier_a
    assert "openclaw" not in tier_a

    tier_c = recommended_runtimes("C")
    assert "nexus" in tier_c
    assert "picoclaw" in tier_c
    assert "openclaw" in tier_c


# ─────────────────────────────────────────────────────────────────────────────
# test_secretd_export_to_env
# ─────────────────────────────────────────────────────────────────────────────

def test_secretd_export_to_env():
    """Stored keys appear in os.environ after export_to_env()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the secrets dir
        with patch("services.secretd.service.SECRETS_DIR", Path(tmpdir)), \
             patch("services.secretd.service.SECRETS_FILE", Path(tmpdir) / "secrets.enc"), \
             patch("services.secretd.service.KEY_FILE", Path(tmpdir) / "secrets.key"):
            from services.secretd.service import SecretsStore
            store = SecretsStore()
            store.set("test_export_key_xyz", "test_value_123")

            # Remove from env first if set
            os.environ.pop("TEST_EXPORT_KEY_XYZ", None)

            store.export_to_env()
            assert os.environ.get("TEST_EXPORT_KEY_XYZ") == "test_value_123"

            # Cleanup
            os.environ.pop("TEST_EXPORT_KEY_XYZ", None)


# ─────────────────────────────────────────────────────────────────────────────
# test_openclaw_config_openrouter
# ─────────────────────────────────────────────────────────────────────────────

def test_openclaw_config_openrouter():
    """Generated config contains openrouter provider with Kimi k2.5."""
    from openclaw_integration.config_gen import gen_config

    # Without key — openrouter provider still present (for placer.py to fill in)
    cfg_no_key = gen_config("qwen2.5:7b", openrouter_key="")
    assert "openrouter" in cfg_no_key["models"]["providers"]

    # With key — openrouter provider has the key and cloud models
    cfg_with_key = gen_config("qwen2.5:7b", openrouter_key="sk-or-test-key")
    openrouter = cfg_with_key["models"]["providers"]["openrouter"]
    assert openrouter["apiKey"] == "sk-or-test-key"
    model_ids = [m["id"] for m in openrouter["models"]]
    assert "moonshotai/kimi-k2" in model_ids

    # With key — default agent model should be Kimi via openrouter
    primary = cfg_with_key["agents"]["defaults"]["model"]["primary"]
    assert "openrouter" in primary
    assert "kimi" in primary.lower()

    # Without key — default should fall back to local ollama
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OPENROUTER_API_KEY", None)
        cfg_local = gen_config("qwen2.5:7b", openrouter_key="")
        primary_local = cfg_local["agents"]["defaults"]["model"]["primary"]
        assert "ollama" in primary_local
