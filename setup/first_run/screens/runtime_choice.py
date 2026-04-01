"""Screen 3 — Runtime choice: Nexus / OpenClaw / Both + PicoClaw + A2A add-ons."""


def run(state) -> bool:
    print("\n  ── Runtime Choice ──────────────────────────────")
    print()
    print("  ClawOS ships with multiple AI runtimes. Pick your setup:")
    print()
    print("  [1] Nexus")
    print("      · Native Python agent, works on 8GB RAM")
    print(f"      · Uses {state.model} — already on your machine")
    print("      · Fast startup, full voice + WhatsApp support")
    print("      · Secure runtime with policyd + Merkle audit")
    print()

    oc_ok = state.ram_gb >= 14
    if oc_ok:
        print("  [2] OpenClaw   (recommended — full ecosystem)")
        print("      · 13,700+ community skills and integrations")
        print("      · Pre-configured for Ollama offline (no API keys)")
        print("      · Needs Node.js + qwen2.5:7b")
        print()
        print("  [3] Both       (Nexus + OpenClaw)")
        print("      · Nexus handles everyday tasks")
        print("      · OpenClaw available via: clawctl openclaw start")
        print()
    else:
        print(f"  [2] OpenClaw   not recommended ({state.ram_gb}GB RAM, needs 14GB+)")
        print()

    print("  Add-ons (combine with any runtime above e.g. '3+4+5' or '345'):")
    print()
    print("  [4] PicoClaw        (lightweight edge agent)")
    print("      · Go binary, <10MB RAM overhead, <1s boot")
    print("      · Runs qwen2.5:1.5b for fast simple tasks")
    print("      · Good for always-on background agent on same machine")
    print()
    print("  [5] A2A Federation  (connect to other ClawOS nodes on LAN)")
    print("      · Enables Agent-to-Agent protocol (a2ad service)")
    print("      · Other ClawOS boxes discover this node via mDNS")
    print("      · Delegate tasks: clawctl a2a delegate 'task' --peer <ip>")
    print()

    default = "2" if oc_ok else "1"
    default_label = "OpenClaw" if oc_ok else "Nexus"
    choice = input(f"  Choose [1/2/3/4/5] or combos e.g. 3+4+5, Enter for {default_label}: ").strip()

    # Normalise — strip + and spaces
    choice = choice.replace("+", "").replace(" ", "") or default

    enable_picoclaw = "4" in choice
    enable_a2a      = "5" in choice
    base            = choice.replace("4", "").replace("5", "").strip() or default

    if base == "2" and oc_ok:
        state.runtime = "openclaw"
        from bootstrap.profile_selector import recommended_openclaw_model
        from bootstrap.hardware_probe import HardwareProfile
        hw = HardwareProfile(ram_gb=state.ram_gb, gpu_vram_gb=state.gpu_vram_gb)
        state.openclaw_model = recommended_openclaw_model(hw)
        print(f"\n  Runtime: OpenClaw (model: {state.openclaw_model})")
    elif base == "3" and oc_ok:
        state.runtime = "both"
        from bootstrap.profile_selector import recommended_openclaw_model
        from bootstrap.hardware_probe import HardwareProfile
        hw = HardwareProfile(ram_gb=state.ram_gb, gpu_vram_gb=state.gpu_vram_gb)
        state.openclaw_model = recommended_openclaw_model(hw)
        print("\n  Runtime: Both (Nexus + OpenClaw)")
    else:
        state.runtime = "core"
        print("\n  Runtime: Nexus")

    if enable_picoclaw:
        state.enable_picoclaw = True
        print("  + PicoClaw enabled — lightweight edge agent alongside main runtime")
    else:
        state.enable_picoclaw = False

    if enable_a2a:
        state.enable_a2a = True
        print("  + A2A Federation enabled — a2ad will start with ClawOS")
    else:
        state.enable_a2a = False

    state.mark_done("runtime_choice")
    return True
