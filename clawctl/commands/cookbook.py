# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl cookbook — hardware-aware model recommendations.

Commands:
  clawctl cookbook scan       — scan hardware, show detected specs
  clawctl cookbook recommend  — scan + score models, show ranked list
  clawctl cookbook serve     — pick top recommendation, pull + serve
"""
import json
import multiprocessing
import platform
import subprocess
from dataclasses import dataclass, field

# ── Hardware detection ────────────────────────────────────────────────────────

@dataclass
class HardwareProfile:
    """Detected hardware capabilities."""
    os: str = ""
    arch: str = ""
    cpu_cores: int = 0
    cpu_freq_mhz: float = 0.0
    ram_gb: float = 0.0
    gpu_vendor: str = ""         # nvidia, apple, amd, intel, none
    gpu_name: str = ""
    gpu_vram_gb: float = 0.0
    gpu_compute: str = ""        # cuda, metal, rocm, none
    tier: str = "A"              # A=basic, B=full, C=power

    def to_dict(self) -> dict:
        return {
            "os": self.os, "arch": self.arch,
            "cpu_cores": self.cpu_cores, "cpu_freq_mhz": round(self.cpu_freq_mhz, 0),
            "ram_gb": round(self.ram_gb, 1),
            "gpu_vendor": self.gpu_vendor, "gpu_name": self.gpu_name,
            "gpu_vram_gb": round(self.gpu_vram_gb, 1),
            "gpu_compute": self.gpu_compute, "tier": self.tier,
        }


def scan_hardware() -> HardwareProfile:
    """Detect system hardware for model fitting."""
    hw = HardwareProfile()
    hw.os = platform.system()
    hw.arch = platform.machine()

    # CPU cores
    try:
        hw.cpu_cores = multiprocessing.cpu_count() if "multiprocessing" in dir() else 0
    except Exception:
        pass
    try:
        import os
        hw.cpu_cores = os.cpu_count() or 0
    except Exception:
        pass

    # RAM
    try:
        if hw.os == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            hw.ram_gb = int(out.stdout.strip()) / (1024 ** 3)
        elif hw.os == "Linux":
            out = subprocess.run(["free", "-g"], capture_output=True, text=True, timeout=5)
            for line in out.stdout.splitlines():
                if line.startswith("Mem:"):
                    hw.ram_gb = float(line.split()[1])
                    break
    except Exception:
        pass

    # GPU detection — Apple Silicon
    if hw.os == "Darwin" and hw.arch == "arm64":
        hw.gpu_vendor = "apple"
        hw.gpu_compute = "metal"
        try:
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5)
            hw.gpu_name = out.stdout.strip() or "Apple Silicon"
        except Exception:
            hw.gpu_name = "Apple Silicon"
        # Unified memory — GPU shares RAM
        hw.gpu_vram_gb = hw.ram_gb * 0.7  # Approx 70% for GPU on unified

    # GPU detection — NVIDIA
    if hw.gpu_vendor == "":
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,compute_cap",
                                  "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5)
            if out.returncode == 0 and out.stdout.strip():
                parts = out.stdout.strip().split(", ")
                hw.gpu_name = parts[0].strip()
                hw.gpu_vram_gb = float(parts[1].strip()) / 1024  # MiB → GiB
                hw.gpu_vendor = "nvidia"
                hw.gpu_compute = "cuda"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # GPU detection — AMD
    if hw.gpu_vendor == "":
        try:
            out = subprocess.run(["rocm-smi", "--showproductname"],
                                 capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                hw.gpu_vendor = "amd"
                hw.gpu_compute = "rocm"
                hw.gpu_name = out.stdout.strip().split("\n")[0] if out.stdout.strip() else "AMD GPU"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if hw.gpu_vendor == "":
        hw.gpu_vendor = "none"
        hw.gpu_compute = "cpu"

    # Tier assignment
    if hw.gpu_vram_gb >= 16 or hw.ram_gb >= 32:
        hw.tier = "C"
    elif hw.gpu_vram_gb >= 6 or hw.ram_gb >= 16:
        hw.tier = "B"
    else:
        hw.tier = "A"

    return hw


# ── Model registry ────────────────────────────────────────────────────────────

@dataclass
class ModelSpec:
    """A model's hardware requirements and metadata."""
    name: str
    params_b: float              # billions of parameters
    quant: str                   # q4_0, q5_0, q8_0, fp16
    min_ram_gb: float
    min_vram_gb: float           # 0 = CPU only
    recommended_ram_gb: float
    recommended_vram_gb: float
    category: str = "general"    # general, code, vision, embedding
    description: str = ""
    tier: str = "A"              # minimum tier to run comfortably
    tags: list = field(default_factory=list)

    def size_gb(self) -> float:
        """Approximate download size in GiB."""
        bits_per_param = {"q4_0": 4.5, "q4_1": 5, "q5_0": 5.5, "q5_1": 6,
                          "q6_0": 6.5, "q8_0": 8.5, "fp16": 16}.get(self.quant, 5)
        return round(self.params_b * bits_per_param / 8, 1)


# Known models — curated for quality and variety
MODEL_CATALOG: list[ModelSpec] = [
    # Tier A (8 GB RAM, no GPU)
    ModelSpec("gemma3:1b", 1, "q4_0", 2, 0, 4, 0, "general", "Ultra-light chat", "A", ["fast", "tiny"]),
    ModelSpec("tinyllama:1.1b", 1.1, "q4_0", 2, 0, 4, 0, "general", "Tiny but capable", "A", ["fast"]),
    ModelSpec("phi3:3.8b", 3.8, "q4_0", 4, 0, 8, 0, "general", "Microsoft's small model", "A", ["reasoning"]),
    ModelSpec("qwen3:4b", 4, "q4_0", 4, 0, 8, 0, "general", "Qwen 3 small — great all-rounder", "A", ["balanced"]),
    ModelSpec("gemma3:4b", 4, "q4_0", 4, 0, 8, 0, "general", "Google Gemma 3 — solid small model", "A", ["balanced"]),
    ModelSpec("llama3.2:3b", 3, "q4_0", 4, 0, 8, 0, "general", "Llama 3.2 lightweight", "A", ["balanced"]),
    ModelSpec("deepseek-r1:1.5b", 1.5, "q4_0", 3, 0, 6, 0, "reasoning", "DeepSeek R1 tiny — chain of thought", "A", ["reasoning", "cot"]),

    # Tier B (16 GB RAM, optional GPU)
    ModelSpec("qwen3:8b", 8, "q4_0", 8, 0, 16, 0, "general", "Qwen 3 — excellent all-rounder", "B", ["balanced"]),
    ModelSpec("llama3.1:8b", 8, "q4_0", 8, 0, 16, 0, "general", "Llama 3.1 — Meta's flagship small", "B", ["balanced"]),
    ModelSpec("mistral:7b", 7, "q4_0", 8, 0, 16, 0, "general", "Mistral 7B — fast & good", "B", ["fast"]),
    ModelSpec("deepseek-r1:8b", 8, "q4_0", 8, 0, 16, 0, "reasoning", "DeepSeek R1 — chain of thought", "B", ["reasoning", "cot"]),
    ModelSpec("qwen2.5-coder:7b", 7, "q4_0", 8, 0, 16, 0, "code", "Qwen Coder — great for programming", "B", ["code"]),
    ModelSpec("gemma3:12b", 12, "q4_0", 10, 0, 20, 4, "general", "Gemma 3 medium — built-in vision, needs GPU for speed", "B", ["quality", "vision", "multimodal"]),

    # Tier B with GPU
    ModelSpec("phi4:14b", 14, "q4_0", 12, 4, 24, 6, "general", "Phi-4 — strong reasoning in 14B", "B", ["reasoning", "quality"]),
    ModelSpec("codellama:13b", 13, "q4_0", 12, 4, 24, 6, "code", "Code Llama 13B — code specialist", "B", ["code"]),

    # Tier C (32 GB RAM, GPU 8GB+)
    ModelSpec("qwen3:14b", 14, "q4_0", 12, 4, 28, 8, "general", "Qwen 3 medium — very strong", "C", ["quality"]),
    ModelSpec("llama3.1:70b", 70, "q4_0", 40, 16, 64, 24, "general", "Llama 3.1 70B — powerhouse", "C", ["flagship"]),
    ModelSpec("deepseek-r1:14b", 14, "q4_0", 12, 4, 28, 8, "reasoning", "DeepSeek R1 14B — strong CoT", "C", ["reasoning", "cot"]),
    ModelSpec("qwen2.5-coder:32b", 32, "q4_0", 24, 8, 48, 16, "code", "Qwen Coder 32B — SOTA code", "C", ["code", "flagship"]),
    ModelSpec("gemma3:27b", 27, "q4_0", 20, 8, 40, 12, "general", "Gemma 3 large — top quality", "C", ["quality"]),
    ModelSpec("deepseek-r1:32b", 32, "q4_0", 24, 8, 48, 16, "reasoning", "DeepSeek R1 32B — deep reasoning", "C", ["reasoning", "cot", "flagship"]),

    # Vision models
    ModelSpec("llama3.2-vision:11b", 11, "q4_0", 10, 4, 20, 6, "vision", "Llama 3.2 Vision — see + chat", "B", ["vision"]),
    ModelSpec("minicpm-v:8b", 8, "q4_0", 8, 2, 16, 4, "vision", "MiniCPM-V — efficient vision+chat", "B", ["vision", "multimodal"]),

    # Embedding
    ModelSpec("nomic-embed-text", 0.3, "fp16", 1, 0, 2, 0, "embedding", "Nomic text embeddings", "A", ["embedding"]),
    ModelSpec("mxbai-embed-large", 0.3, "fp16", 1, 0, 2, 0, "embedding", "MixedBread large embeddings", "A", ["embedding"]),
]


# ── Fit scoring ──────────────────────────────────────────────────────────────

@dataclass
class ModelRecommendation:
    """A model scored for specific hardware."""
    model: ModelSpec
    score: float          # 0-100
    fits: bool            # can it run at all?
    comfortable: bool      # can it run with headroom?
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.model.name,
            "score": round(self.score, 1),
            "fits": self.fits,
            "comfortable": self.comfortable,
            "size_gb": self.model.size_gb(),
            "category": self.model.category,
            "description": self.model.description,
            "tier": self.model.tier,
            "tags": self.model.tags,
            "reasons": self.reasons,
        }


def score_models(hw: HardwareProfile) -> list[ModelRecommendation]:
    """Score all catalog models against detected hardware."""
    recs = []
    tier_order = {"A": 0, "B": 1, "C": 2}

    for model in MODEL_CATALOG:
        reasons = []
        score = 50.0  # base

        # Can it fit at all?
        fits = hw.ram_gb >= model.min_ram_gb
        if model.min_vram_gb > 0 and hw.gpu_vram_gb < model.min_vram_gb:
            # Can spill to RAM but very slow
            fits = hw.ram_gb >= model.min_ram_gb + model.min_vram_gb
            if fits:
                reasons.append("GPU VRAM low — will spill to RAM (slow)")

        # Can it run comfortably?
        comfortable = hw.ram_gb >= model.recommended_ram_gb
        if model.recommended_vram_gb > 0:
            comfortable = comfortable and hw.gpu_vram_gb >= model.recommended_vram_gb

        if not fits:
            score = 0
            reasons.append(f"Needs {model.recommended_ram_gb}GB RAM, you have {round(hw.ram_gb, 1)}GB")
            if model.min_vram_gb > 0:
                reasons.append(f"Needs {model.min_vram_gb}GB VRAM, you have {round(hw.gpu_vram_gb, 1)}GB")
        else:
            # Score adjustments
            if comfortable:
                score += 20
            else:
                score -= 10
                reasons.append("Tight fit — may be slow")

            # Tier match bonus
            hw_tier_idx = tier_order.get(hw.tier, 0)
            model_tier_idx = tier_order.get(model.tier, 0)
            if model_tier_idx == hw_tier_idx:
                score += 15  # Perfect match
                reasons.append(f"Perfect for your {hw.tier}-tier hardware")
            elif model_tier_idx < hw_tier_idx:
                score += 5   # Under-utilizing, but fine
            else:
                score -= 30  # Over-reaching
                reasons.append("May be slow on your hardware")

            # GPU bonus
            if hw.gpu_compute != "cpu" and model.min_vram_gb > 0:
                score += 10
                reasons.append(f"GPU accelerated ({hw.gpu_compute})")

            # Apple Silicon unified memory bonus
            if hw.gpu_vendor == "apple" and model.min_vram_gb > 0:
                score += 5
                reasons.append("Apple unified memory = efficient GPU sharing")

            # Category bonuses based on general usefulness
            if model.category == "general":
                score += 15
            elif model.category == "code":
                score += 6
            elif model.category == "reasoning":
                score += 8
            elif model.category == "vision":
                score += 2

        score = max(0, min(100, score))
        recs.append(ModelRecommendation(model=model, score=score, fits=fits,
                                         comfortable=comfortable, reasons=reasons))

    # Sort by score descending
    recs.sort(key=lambda r: r.score, reverse=True)
    return recs


# ── CLI output ────────────────────────────────────────────────────────────────

def run_scan():
    """Scan and display hardware profile."""
    hw = scan_hardware()
    from clawctl.ui.banner import info, success

    print()
    success(f"Hardware detected — Tier {hw.tier}")
    print()
    print(f"  OS:           {hw.os} ({hw.arch})")
    print(f"  CPU cores:    {hw.cpu_cores}")
    print(f"  RAM:          {round(hw.ram_gb, 1)} GB")
    if hw.gpu_vendor != "none":
        print(f"  GPU:          {hw.gpu_name}")
        print(f"  GPU VRAM:     {round(hw.gpu_vram_gb, 1)} GB")
        print(f"  GPU compute:  {hw.gpu_compute}")
    else:
        print("  GPU:          none detected (CPU-only mode)")
    print()
    info(f"Tier {hw.tier}: {'Basic — small models (1-4B)' if hw.tier == 'A' else 'Full — medium models (7-14B)' if hw.tier == 'B' else 'Power — large models (14B+)'}")
    print()
    print("  Run 'clawctl cookbook recommend' to see model suggestions")
    print()


def run_recommend():
    """Scan hardware and show model recommendations."""
    hw = scan_hardware()
    recs = score_models(hw)

    from clawctl.ui.banner import info, success, error

    # Filter to fitting models only
    fitting = [r for r in recs if r.fits]
    top = fitting[:10]

    print()
    success(f"Top recommendations for your Tier {hw.tier} hardware")
    print(f"  {hw.gpu_name or 'CPU-only'} · {round(hw.ram_gb, 1)}GB RAM · {round(hw.gpu_vram_gb, 1)}GB VRAM")
    print()

    if not top:
        error("No models fit your hardware. Consider upgrading RAM.")
        print()
        return

    # Table header
    fmt = "  {:<28} {:>6} {:>8} {:>8}  {}"
    print(fmt.format("MODEL", "SCORE", "SIZE", "TIER", "NOTES"))
    print("  " + "─" * 80)

    for r in top:
        emoji = "🟢" if r.comfortable else "🟡"
        note = r.reasons[0] if r.reasons else ""
        print(fmt.format(
            f"{emoji} {r.model.name}",
            f"{r.score:.0f}",
            f"{r.model.size_gb():.1f}G",
            r.model.tier,
            note[:45]
        ))

    print()
    best = top[0]
    info(f"Best pick: {best.model.name} — {best.model.description}")
    print(f"  Install: clawctl model pull {best.model.name}")
    print("  Or run:  clawctl cookbook serve")
    print()


def run_serve():
    """Auto-select best model, pull it, and start serving."""
    hw = scan_hardware()
    recs = score_models(hw)
    fitting = [r for r in recs if r.fits and r.comfortable]

    if not fitting:
        fitting = [r for r in recs if r.fits]

    if not fitting:
        from clawctl.ui.banner import error
        error("No models fit your hardware.")
        return

    best = fitting[0]
    from clawctl.ui.banner import info, success

    print()
    info(f"Auto-selecting {best.model.name} for your Tier {hw.tier} hardware")
    print(f"  Score: {best.score:.0f}/100 — {best.model.description}")
    if best.reasons:
        for reason in best.reasons[:3]:
            print(f"  · {reason}")
    print()

    # Pull the model
    info(f"Pulling {best.model.name} ({best.model.size_gb():.1f} GB)...")
    try:
        r = subprocess.run(["ollama", "pull", best.model.name], timeout=600)
        if r.returncode == 0:
            success(f"{best.model.name} installed and ready")
        else:
            print(f"  Pull failed — try manually: ollama pull {best.model.name}")
    except FileNotFoundError:
        print("  Ollama not found — install: curl -fsSL https://ollama.com/install.sh | sh")
    except subprocess.TimeoutExpired:
        print("  Pull timed out — model may be large. Try: ollama pull " + best.model.name)
    print()


def run_json():
    """Output hardware + recommendations as JSON (for dashboard API)."""
    hw = scan_hardware()
    recs = score_models(hw)
    output = {
        "hardware": hw.to_dict(),
        "recommendations": [r.to_dict() for r in recs if r.fits][:15],
    }
    print(json.dumps(output, indent=2))