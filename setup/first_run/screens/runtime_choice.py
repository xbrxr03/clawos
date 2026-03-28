import sys
"""Screen 3 — Runtime choice: Nexus / OpenClaw / Both."""


def run(state) -> bool:
    print("\n  ── Runtime Choice ──────────────────────────────")
    print()
    print("  ClawOS ships with two AI runtimes. Pick one to start with:")
    print()
    print("  [1] Nexus  (recommended)")
    print("      · Native Python agent, works on 8GB RAM")
    print(f"      · Uses {state.model} — already on your machine")
    print("      · Fast startup, full voice + WhatsApp support")
    print("      · Our custom secure runtime with policyd")
    print()

    oc_ok = state.ram_gb >= 14
    if oc_ok:
        print("  [2] OpenClaw   (full ecosystem)")
        print("      · 13,700+ community skills and integrations")
        print("      · Pre-configured for Ollama offline (no API keys)")
        print("      · Needs Node.js + qwen2.5:7b (tool-calling model)")
        print("      · Requires ~2GB extra disk + longer first setup")
        print()
        print("  [3] Both       (Nexus default + OpenClaw available)")
        print("      · Nexus handles everyday tasks")
        print("      · OpenClaw available via: clawctl openclaw start")
    else:
        print(f"  [2] OpenClaw   ← not recommended ({state.ram_gb}GB RAM, needs 14GB+)")
        print("      · Can still install later: clawctl openclaw install")

    print()
    valid = ["1", "2", "3"] if oc_ok else ["1", "2"]
    choice = input("  Choose [1/2/3] or Enter for Nexus: ").strip()

    if choice == "2":
        state.runtime = "openclaw"
        from bootstrap.profile_selector import recommended_openclaw_model
        from bootstrap.hardware_probe import HardwareProfile
        hw = HardwareProfile(ram_gb=state.ram_gb, gpu_vram_gb=state.gpu_vram_gb)
        state.openclaw_model = recommended_openclaw_model(hw)
        print(f"\n  Runtime: OpenClaw (model: {state.openclaw_model})")
        if not oc_ok:
            print("  ⚠ Low RAM — performance may be limited")
    elif choice == "3" and oc_ok:
        state.runtime = "both"
        print("\n  Runtime: Both (Nexus default, OpenClaw available)")
    else:
        state.runtime = "core"
        print("\n  Runtime: Nexus")

    state.mark_done("runtime_choice")
    return True
