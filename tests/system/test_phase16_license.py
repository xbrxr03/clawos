# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Phase 16 — Monetisation / License tests.
Tests LicenseManager, FeatureGate, @require_premium decorator.
All tests run offline (no Supabase connection).
"""
import json
import os
import tempfile
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── 1. LicenseManager — module loads ─────────────────────────────────────────

def test_license_module_imports():
    from clawos_core import license as lic
    assert hasattr(lic, "LicenseManager")
    assert hasattr(lic, "get_license_manager")
    assert hasattr(lic, "FREE_FEATURES")
    assert hasattr(lic, "PREMIUM_FEATURES")


def test_free_features_are_subset_of_premium():
    from clawos_core.license import FREE_FEATURES, PREMIUM_FEATURES
    assert FREE_FEATURES.issubset(PREMIUM_FEATURES)


def test_premium_features_are_subset_of_pro():
    from clawos_core.license import PREMIUM_FEATURES, PRO_FEATURES
    assert PREMIUM_FEATURES.issubset(PRO_FEATURES)


# ── 2. Machine ID ─────────────────────────────────────────────────────────────

def test_get_machine_id_returns_string():
    from clawos_core.license import _get_machine_id
    mid = _get_machine_id()
    assert isinstance(mid, str)
    assert len(mid) == 32  # SHA-256 truncated to 32 hex chars


def test_get_machine_id_is_deterministic():
    from clawos_core.license import _get_machine_id
    id1 = _get_machine_id()
    id2 = _get_machine_id()
    assert id1 == id2


# ── 3. LicenseManager — activate (mocked Supabase) ───────────────────────────

def test_license_activate_invalid_key_format():
    """Activation rejects keys not starting with CLAW-."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    result = mgr.activate("NOT-A-VALID-KEY")
    assert result["ok"] is False
    assert "CLAW-" in result["error"]


def test_license_activate_key_not_found():
    """Activation returns error when key not in Supabase."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    with patch("clawos_core.license._supabase_get", return_value=[]):
        result = mgr.activate("CLAW-AAAA-BBBB-CCCC-DDDD")
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_license_activate_offline():
    """Activation returns error when Supabase unreachable."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    with patch("clawos_core.license._supabase_get", return_value=None):
        result = mgr.activate("CLAW-AAAA-BBBB-CCCC-DDDD")
    assert result["ok"] is False
    assert "internet" in result["error"].lower() or "license server" in result["error"].lower()


def test_license_activate_success():
    """Activation succeeds with valid Supabase response."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    fake_row = [{"key": "CLAW-AAAA-BBBB-CCCC-DDDD", "tier": "premium",
                 "machine_id": None, "is_active": True, "email": "user@example.com"}]

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "license.json"
        with patch("clawos_core.license._supabase_get", return_value=fake_row):
            with patch("clawos_core.license._supabase_patch", return_value=True):
                with patch("clawos_core.license.LICENSE_CACHE_FILE", cache_file):
                    result = mgr.activate("CLAW-AAAA-BBBB-CCCC-DDDD")

    assert result["ok"] is True
    assert result["tier"] == "premium"
    assert result["email"] == "user@example.com"


def test_license_activate_machine_conflict():
    """Activation fails if key is bound to a different machine."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    mgr._machine_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # 32 chars
    fake_row = [{"key": "CLAW-XXXX-XXXX-XXXX-XXXX", "tier": "premium",
                 "machine_id": "different_machine_id_here_32char",
                 "is_active": True, "email": ""}]
    with patch("clawos_core.license._supabase_get", return_value=fake_row):
        result = mgr.activate("CLAW-XXXX-XXXX-XXXX-XXXX")
    assert result["ok"] is False
    assert "different machine" in result["error"].lower()


# ── 4. LicenseManager — validate (cache) ─────────────────────────────────────

def test_license_validate_no_cache_returns_free():
    """validate() returns free tier when no license is cached."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    with patch("clawos_core.license._load_cache", return_value={}):
        result = mgr.validate()
    assert result["valid"] is False
    assert result["tier"] == "free"


def test_license_validate_fresh_cache_skips_network():
    """validate() uses cache when validated_at is recent (< 1h)."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    mgr._last_online_check = time.time()  # mark as just checked
    cache = {
        "key": "CLAW-AAAA-BBBB-CCCC-DDDD",
        "tier": "premium",
        "validated_at": time.time() - 60,  # 1 minute ago
        "is_active": True,
    }
    with patch("clawos_core.license._load_cache", return_value=cache):
        result = mgr.validate()
    assert result["valid"] is True
    assert result["tier"] == "premium"
    assert result["source"] == "cache"


def test_license_validate_expired_cache_returns_free():
    """validate() falls back to free when cache is older than 72h."""
    from clawos_core.license import LicenseManager
    mgr = LicenseManager()
    mgr._last_online_check = time.time() - 7200  # 2h ago — triggers online check
    cache = {
        "key": "CLAW-AAAA-BBBB-CCCC-DDDD",
        "tier": "premium",
        "validated_at": time.time() - (73 * 3600),  # 73h old
        "is_active": True,
    }
    with patch("clawos_core.license._load_cache", return_value=cache):
        with patch("clawos_core.license._supabase_get", return_value=None):  # offline
            result = mgr.validate()
    assert result["valid"] is False
    assert result["tier"] == "free"
    assert "expired" in result["source"]


# ── 5. FeatureGate ────────────────────────────────────────────────────────────

def test_feature_gate_imports():
    from clawos_core import feature_gate
    assert hasattr(feature_gate, "FeatureGate")
    assert hasattr(feature_gate, "require_premium")
    assert hasattr(feature_gate, "FeatureNotAvailable")


def test_feature_gate_free_tier():
    """FeatureGate on free tier returns is_premium=False."""
    from clawos_core.feature_gate import FeatureGate
    gate = FeatureGate()
    with patch.object(gate, "_refresh_tier", return_value="free"):
        assert gate.is_free() is True
        assert gate.is_premium() is False
        assert gate.is_pro() is False


def test_feature_gate_premium_tier():
    """FeatureGate on premium tier returns is_premium=True."""
    from clawos_core.feature_gate import FeatureGate
    gate = FeatureGate()
    with patch.object(gate, "_refresh_tier", return_value="premium"):
        assert gate.is_premium() is True
        assert gate.is_pro() is False


def test_feature_gate_has_feature_free():
    """Free users have core_agent but not elevenlabs."""
    from clawos_core.feature_gate import FeatureGate
    gate = FeatureGate()
    with patch.object(gate, "_refresh_tier", return_value="free"):
        assert gate.has_feature("core_agent") is True
        assert gate.has_feature("voice_elevenlabs") is False
        assert gate.has_feature("nexus_brain") is False


def test_feature_gate_has_feature_premium():
    """Premium users have elevenlabs and nexus_brain."""
    from clawos_core.feature_gate import FeatureGate
    gate = FeatureGate()
    with patch.object(gate, "_refresh_tier", return_value="premium"):
        assert gate.has_feature("voice_elevenlabs") is True
        assert gate.has_feature("nexus_brain") is True
        assert gate.has_feature("browser_control") is True


# ── 6. @require_premium decorator ────────────────────────────────────────────

def test_require_premium_allows_premium():
    """@require_premium passes when tier is premium."""
    from clawos_core.feature_gate import require_premium, FeatureGate

    @require_premium
    def premium_fn():
        return "premium_result"

    with patch("clawos_core.feature_gate.FeatureGate.is_premium", return_value=True):
        assert premium_fn() == "premium_result"


def test_require_premium_blocks_free():
    """@require_premium raises FeatureNotAvailable on free tier."""
    from clawos_core.feature_gate import require_premium, FeatureNotAvailable, FeatureGate

    @require_premium
    def premium_fn():
        return "should_not_reach"

    with patch("clawos_core.feature_gate.FeatureGate.is_premium", return_value=False):
        with patch("clawos_core.feature_gate.FeatureGate.get_tier", return_value="free"):
            with pytest.raises(FeatureNotAvailable):
                premium_fn()


def test_feature_not_available_has_attributes():
    """FeatureNotAvailable has feature and current_tier attributes."""
    from clawos_core.feature_gate import FeatureNotAvailable
    exc = FeatureNotAvailable("nexus_brain", "free")
    assert exc.feature == "nexus_brain"
    assert exc.current_tier == "free"
    assert "upgrade" in str(exc).lower() or "premium" in str(exc).lower()
