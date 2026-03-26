"""Screen 2 — Hardware detection + profile selection."""


def run(state) -> bool:
    print("\n  ── Hardware Detection ──────────────────────────")
    print("  Scanning your machine ...\n")

    from bootstrap.hardware_probe import probe_and_save
    from bootstrap.profile_selector import select, summary, openclaw_feasible, voice_feasible
    hw = probe_and_save()

    print(summary(hw))
    print()

    auto = select(hw)
    print(f"  Recommended profile: {auto}")
    print()
    print("  Profiles:")
    print("    [1] Low RAM      — <12GB,  qwen2.5:3b, voice off")
    print("    [2] Balanced     — 12-32GB, qwen2.5:7b, voice optional  ← recommended for you")
    print("    [3] Performance  — 32GB+,   qwen2.5:7b, voice on, GPU acceleration")
    print()

    choice = input("  Choose profile [1/2/3] or Enter for recommended: ").strip()
    mapping = {"1": "lowram", "2": "balanced", "3": "performance", "": auto}
    profile = mapping.get(choice, auto)

    state.profile        = profile
    state.hw_tier        = hw.tier
    state.ram_gb         = hw.ram_gb
    state.gpu_vram_gb    = hw.gpu_vram_gb
    state.has_mic        = hw.has_mic
    state.voice_enabled  = voice_feasible(hw)

    from bootstrap.profile_selector import recommended_model
    state.model = recommended_model(hw)

    print(f"\n  Profile set: {profile}  →  model: {state.model}")
    state.mark_done("hardware_profile")
    return True
