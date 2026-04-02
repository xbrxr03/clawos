import sys
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
    rec = {"lowram": "1", "balanced": "2", "performance": "3"}.get(auto, "2")
    print("  Profiles:")
    print("    [1] Low RAM      — <12GB,  qwen2.5:3b, voice off" + ("  ← recommended" if rec=="1" else ""))
    print("    [2] Balanced     — 12-32GB, qwen2.5:7b, voice optional" + ("  ← recommended" if rec=="2" else ""))
    print("    [3] Performance  — 32GB+,  qwen2.5:7b, GPU acceleration" + ("  ← recommended" if rec=="3" else ""))
    print()

    choice = input("  Choose profile [1/2/3] or Enter for recommended: ").strip()
    mapping = {"1": "lowram", "2": "balanced", "3": "performance", "": auto}
    profile = mapping.get(choice, auto)

    state.profile        = profile
    state.hw_tier        = hw.tier
    state.hardware_tier  = hw.tier  # sync both fields
    state.ram_gb         = hw.ram_gb
    state.gpu_vram_gb    = hw.gpu_vram_gb
    state.has_mic        = hw.has_mic
    state.voice_enabled  = voice_feasible(hw)

    from bootstrap.profile_selector import recommended_model
    state.model = recommended_model(hw)

    print(f"\n  Profile set: {profile}  →  model: {state.model}")
    state.mark_done("hardware_profile")
    return True
