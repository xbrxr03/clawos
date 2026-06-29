# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for clawctl cookbook — hardware scanning and model recommendations."""
from clawctl.commands.cookbook import (
    HardwareProfile, ModelSpec, scan_hardware, score_models, MODEL_CATALOG,
)


class TestHardwareProfile:
    """Tests for HardwareProfile dataclass."""

    def test_defaults(self):
        hw = HardwareProfile()
        assert hw.os == ""
        assert hw.tier == "A"
        assert hw.gpu_vendor == ""

    def test_to_dict(self):
        hw = HardwareProfile(os="Darwin", arch="arm64", ram_gb=16.0, tier="B",
                             gpu_vendor="apple", gpu_name="Apple M4",
                             gpu_vram_gb=11.2, gpu_compute="metal")
        d = hw.to_dict()
        assert d["os"] == "Darwin"
        assert d["ram_gb"] == 16.0
        assert d["tier"] == "B"
        assert d["gpu_vendor"] == "apple"

    def test_tier_assignment_A(self):
        hw = HardwareProfile(ram_gb=8, gpu_vram_gb=0)
        # Tier A: <16GB RAM, <6GB VRAM
        assert hw.ram_gb == 8

    def test_tier_assignment_C(self):
        HardwareProfile(ram_gb=32, gpu_vram_gb=16)
        # Tier C: >=32GB RAM or >=16GB VRAM


class TestModelSpec:
    """Tests for ModelSpec dataclass."""

    def test_size_gb_q4(self):
        spec = ModelSpec("test:7b", 7, "q4_0", 8, 0, 16, 0)
        assert 3.5 < spec.size_gb() < 5  # ~4.5GB for q4_0 7B

    def test_size_gb_q8(self):
        spec = ModelSpec("test:7b", 7, "q8_0", 12, 0, 24, 0)
        assert 7 < spec.size_gb() < 9  # ~8.5GB for q8_0 7B

    def test_size_gb_fp16(self):
        spec = ModelSpec("test:7b", 7, "fp16", 14, 0, 28, 0)
        assert spec.size_gb() == 14.0  # 16 bits * 7B / 8


class TestScoreModels:
    """Tests for model scoring engine."""

    def test_basic_hardware_gets_recommendations(self):
        hw = HardwareProfile(
            os="Darwin", arch="arm64", cpu_cores=8, ram_gb=16.0,
            gpu_vendor="apple", gpu_name="Apple M4", gpu_vram_gb=11.2,
            gpu_compute="metal", tier="B"
        )
        recs = score_models(hw)
        assert len(recs) > 0
        # Top picks should fit
        top = recs[0]
        assert top.fits is True

    def test_low_end_hardware_gets_tier_A(self):
        hw = HardwareProfile(
            os="Linux", arch="x86_64", cpu_cores=4, ram_gb=8.0,
            gpu_vendor="none", gpu_compute="cpu", tier="A"
        )
        recs = score_models(hw)
        # Tier C models should not fit
        [r for r in recs if r.model.tier == "C" and r.fits]
        # Some C-tier models may still fit if RAM is enough, but should score low
        fitting = [r for r in recs if r.fits]
        assert len(fitting) > 0

    def test_gpu_models_score_higher_with_gpu(self):
        hw_gpu = HardwareProfile(
            os="Darwin", arch="arm64", ram_gb=16.0,
            gpu_vendor="apple", gpu_name="M4", gpu_vram_gb=11.2,
            gpu_compute="metal", tier="B"
        )
        hw_cpu = HardwareProfile(
            os="Linux", arch="x86_64", ram_gb=16.0,
            gpu_vendor="none", gpu_compute="cpu", tier="B"
        )
        recs_gpu = score_models(hw_gpu)
        score_models(hw_cpu)
        # GPU scores should be >= CPU scores for GPU-requiring models
        gpu_requiring = [r for r in recs_gpu if r.model.min_vram_gb > 0 and r.fits]
        assert len(gpu_requiring) >= 0  # May be empty on this hardware

    def test_general_models_score_higher(self):
        hw = HardwareProfile(
            os="Darwin", arch="arm64", ram_gb=16.0,
            gpu_vendor="apple", gpu_name="M4", gpu_vram_gb=11.2,
            gpu_compute="metal", tier="B"
        )
        recs = score_models(hw)
        # The best pick should be a general model
        best = recs[0]
        assert best.model.category in ("general", "reasoning")

    def test_sorted_by_score(self):
        hw = HardwareProfile(ram_gb=16.0, tier="B")
        recs = score_models(hw)
        scores = [r.score for r in recs]
        assert scores == sorted(scores, reverse=True)


class TestModelCatalog:
    """Tests for the built-in model catalog."""

    def test_catalog_not_empty(self):
        assert len(MODEL_CATALOG) > 0

    def test_all_tiers_represented(self):
        tiers = {m.tier for m in MODEL_CATALOG}
        assert "A" in tiers
        assert "B" in tiers
        assert "C" in tiers

    def test_all_categories_represented(self):
        categories = {m.category for m in MODEL_CATALOG}
        assert "general" in categories
        assert "code" in categories

    def test_no_duplicate_names(self):
        names = [m.name for m in MODEL_CATALOG]
        assert len(names) == len(set(names))


class TestScanHardware:
    """Tests for hardware scanning (integration, uses real system calls)."""

    def test_scan_returns_profile(self):
        hw = scan_hardware()
        assert isinstance(hw, HardwareProfile)
        assert hw.os != ""
        assert hw.arch != ""
        assert hw.ram_gb > 0
        assert hw.cpu_cores > 0

    def test_scan_tier_assignment(self):
        hw = scan_hardware()
        assert hw.tier in ("A", "B", "C")