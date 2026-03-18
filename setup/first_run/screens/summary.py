"""Screen 9 — Summary and launch."""


def run(state) -> bool:
    runtime_label = {
        "core":     "Claw Core (native Python agent)",
        "openclaw": "OpenClaw (full ecosystem, Ollama offline)",
        "both":     "Both (Claw Core default + OpenClaw available)",
    }.get(state.runtime, state.runtime)

    print("\n  ── Setup Complete ──────────────────────────────")
    print()
    print(f"  Profile:    {state.profile} (Tier {state.hw_tier}, {state.ram_gb}GB RAM)")
    print(f"  Runtime:    {runtime_label}")
    print(f"  Model:      {state.model}")
    print(f"  Workspace:  {state.workspace_id}")
    print(f"  Voice:      {state.voice_mode}")
    print(f"  WhatsApp:   {'linked (' + state.whatsapp_number + ')' if state.whatsapp_enabled else 'not linked'}")
    print(f"  Policy:     {state.policy_mode}")
    print()
    print("  ─────────────────────────────────────────────")
    print()
    print("  Start Jarvis:")
    print()
    print("    python3 -m clients.cli.repl          — text chat")
    print("    bash scripts/dev_boot.sh             — all services + dashboard")
    print("    http://localhost:7070                — dashboard")
    if state.whatsapp_enabled:
        print("    Message yourself on WhatsApp         — voice/text to Jarvis")
    if state.runtime in ("openclaw", "both"):
        print("    clawctl openclaw start               — start OpenClaw gateway")
    print()
    print("  Useful commands:")
    print("    clawctl status                       — service health")
    print("    clawctl doctor                       — diagnose issues")
    print("    clawctl model pull <name>            — pull more models")
    print()

    ans = input("  Launch Jarvis now? [Y/n]: ").strip().lower()
    state.completed = True
    state.mark_done("summary")

    if ans != "n":
        print()
        print("  Starting Claw Core ...")
        try:
            import subprocess, sys
            subprocess.Popen(["bash", "scripts/dev_boot.sh"],
                             cwd=str(__import__('pathlib').Path(__file__).parent.parent.parent.parent))
            import time; time.sleep(2)
            print("  Dashboard: http://localhost:7070")
            print()
            from clients.cli.repl import main
            main()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"  Start manually: python3 -m clients.cli.repl")

    return True
