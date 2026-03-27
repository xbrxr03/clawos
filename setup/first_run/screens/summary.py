"""Screen 9 — Summary and launch.
Fixes:
  - Saves active workspace to clawos.yaml so repl picks it up on next start
  - Overrides sys.argv before launching repl so --reset never leaks as workspace name
  - Port-in-use guard: skips dashd if :7070 already bound
"""
import subprocess
import sys
import time
from pathlib import Path


def run(state) -> bool:
    runtime_label = {
        "core":     "Nexus (native Python agent)",
        "openclaw": "OpenClaw (full ecosystem, Ollama offline)",
        "both":     "Both (Nexus default + OpenClaw available)",
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
    print("  Start Nexus:")
    print()
    print(f"    nexus                                — start Nexus")
    print(f"    http://localhost:7070                — dashboard")
    if state.whatsapp_enabled:
        print("    Message yourself on WhatsApp         — voice/text to Nexus")
    if state.runtime in ("openclaw", "both"):
        print("    clawctl openclaw start               — start OpenClaw gateway")
    print()
    print("  Useful commands:")
    print("    clawctl status                       — service health")
    print("    clawctl doctor                       — diagnose issues")
    print("    clawctl model pull <name>         — pull more models")
    print("    python3 -m setup.first_run.wizard    — re-run this wizard")
    print()

    # Persist active workspace + model to clawos.yaml
    _save_active_workspace(state)

    ans = input("  Launch Nexus now? [Y/n]: ").strip().lower()
    state.completed = True
    state.mark_done("summary")

    if ans != "n":
        print()
        print("  Starting Claw Core ...")
        clawos_dir = Path(__file__).parent.parent.parent.parent
        _start_services(clawos_dir)
        time.sleep(2)
        print("  Dashboard: http://localhost:7070")
        print()
        # Launch repl with correct workspace — reset sys.argv so --reset never leaks in
        try:
            old_argv = sys.argv[:]
            sys.argv = ["repl", state.workspace_id]
            try:
                import importlib
                from clients.cli import repl as repl_mod
                importlib.reload(repl_mod)
                repl_mod.main()
            finally:
                sys.argv = old_argv
        except KeyboardInterrupt:
            pass
        except Exception:
            print(f"  Could not auto-launch — start manually: clawos")

    return True


def _save_active_workspace(state):
    """Write active workspace and model into clawos.yaml."""
    try:
        from clawos_core.constants import CLAWOS_CONFIG, CONFIG_DIR
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            import yaml
            existing = {}
            if CLAWOS_CONFIG.exists():
                with open(CLAWOS_CONFIG) as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("workspace", {})["default"] = state.workspace_id
            existing.setdefault("model", {})["chat"] = state.model
            existing["_profile"] = state.profile
            with open(CLAWOS_CONFIG, "w") as f:
                yaml.dump(existing, f)
        except ImportError:
            CLAWOS_CONFIG.write_text(
                f"_profile: {state.profile}\n"
                f"workspace:\n  default: {state.workspace_id}\n"
                f"model:\n  chat: {state.model}\n"
            )
    except Exception:
        pass  # non-fatal — repl falls back to jarvis_default


def _start_services(clawos_dir: Path):
    """Start ClawOS background services. Skip dashd if :7070 already bound."""
    import socket, os

    def port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0

    env = {**os.environ, "PYTHONPATH": str(clawos_dir)}

    for module in [
        "services.policyd.main",
        "services.memd.main",
        "services.modeld.main",
        "services.agentd.main",
    ]:
        try:
            subprocess.Popen(
                [sys.executable, "-m", module],
                cwd=str(clawos_dir), env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    if not port_in_use(7070):
        try:
            subprocess.Popen(
                [sys.executable, "-m", "services.dashd.main"],
                cwd=str(clawos_dir), env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    else:
        print("  Dashboard already running on :7070 — skipping dashd start")
