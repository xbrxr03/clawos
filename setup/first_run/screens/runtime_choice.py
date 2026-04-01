import sys
"""Screen 3 — Runtime choice: Nexus / OpenClaw / Both / PicoClaw / A2A Federation."""
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
        print(f"  [2] OpenClaw   ← not recommended ({state.ram_gb}GB RAM, needs 14GB+)")
        print()

    is_arm = False
    try:
        import platform
        is_arm = platform.machine().lower().startswith(("arm", "aarch64"))
    except Exception:
        pass

    if is_arm or state.ram_gb <= 10:
        print("  [4] PicoClaw   (Tier A edge runtime — ARM/low-RAM)")
        print("      · Lightweight Go binary, <10MB RAM, <1s boot")
        print("      · Runs qwen2.5:1.5b on CPU — no GPU needed")
        print("      · WhatsApp + Telegram via gatewayd bridge")
        print()

    print("  [5] A2A Federation  (this node + connect to other ClawOS nodes)")
    print("      · Enables Agent-to-Agent protocol (a2ad service)")
    print("      · Other ClawOS boxes on your LAN discover this node")
    print("      · Delegate tasks between nodes via clawctl a2a delegate")
    print("      · Combine with any of the above runtimes")
    print()

    valid = ["1", "2", "3", "5"]
    if is_arm or state.ram_gb <= 10:
        valid.append("4")
    default_hint = "2" if oc_ok else "1"
    choice = input(f"  Choose [{chr(47).join(valid)}] or Enter for {'OpenClaw' if oc_ok else 'Nexus'}: ").strip()

    # A2A is an add-on — check if combined choice e.g. "3+5" or "35"
    enable_a2a = "5" in choice
    base = choice.replace("5", "").replace("+", "").strip() or default_hint

    if base == "2" and oc_ok:
        state.runtime = "openclaw"
        from bootstrap.profile_selector import recommended_openclaw_model
        from bootstrap.hardware_probe import HardwareProfile
        hw = HardwareProfile(ram_gb=state.ram_gb, gpu_vram_gb=state.gpu_vram_gb)
        state.openclaw_model = recommended_openclaw_model(hw)
        print(f"\n  Runtime: OpenClaw (model: {state.openclaw_model})")
    elif base == "3" and oc_ok:
        state.runtime = "both"
        print("\n  Runtime: Both (Nexus default, OpenClaw available)")
    elif base == "4" and "4" in valid:
        state.runtime = "picoclaw"
        state.model = "qwen2.5:1.5b"
        print("\n  Runtime: PicoClaw (Tier A edge runtime)")
    elif base == "" and oc_ok:
        state.runtime = "openclaw"
        from bootstrap.profile_selector import recommended_openclaw_model
        from bootstrap.hardware_probe import HardwareProfile
        hw = HardwareProfile(ram_gb=state.ram_gb, gpu_vram_gb=state.gpu_vram_gb)
        state.openclaw_model = recommended_openclaw_model(hw)
        print(f"\n  Runtime: OpenClaw (model: {state.openclaw_model})")
    else:
        state.runtime = "core"
        print("\n  Runtime: Nexus")

    if enable_a2a:
        state.enable_a2a = True
        print("  + A2A Federation enabled — a2ad will start with ClawOS")
    else:
        state.enable_a2a = False

    state.mark_done("runtime_choice")
    return True
