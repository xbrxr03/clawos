# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
"""Screen 6 — Model provisioning."""


def run(state) -> bool:
    print("\n  ── Model Setup ─────────────────────────────────")
    print()
    print(f"  Profile: {state.profile}  →  model: {state.model}")
    if state.runtime in ("openclaw", "both"):
        print(f"  OpenClaw model: {state.openclaw_model}")
    print()

    from bootstrap.model_provision import ollama_running, model_present, ensure_model

    if not ollama_running():
        print("  Ollama is not running.")
        print("  Start it now: ollama serve")
        ans = input("  Try to start Ollama automatically? [Y/n]: ").strip().lower()
        if ans != "n":
            from bootstrap.model_provision import ensure_model as em
            em(state.model)
        else:
            print(f"\n  Run manually later:")
            print(f"    ollama serve && ollama pull {state.model}")
            state.model_pulled = False
            state.mark_done("model_setup")
            return True

    # Pull Claw Core model
    if model_present(state.model):
        print(f"  ✓ {state.model} already present")
        state.model_pulled = True
    else:
        print(f"  Pulling {state.model} ...")
        from bootstrap.model_provision import pull
        ok = pull(state.model)
        state.model_pulled = ok

    # Pull OpenClaw model if needed
    if state.runtime in ("openclaw", "both") and state.openclaw_model != state.model:
        if model_present(state.openclaw_model):
            print(f"  ✓ {state.openclaw_model} already present")
        else:
            print(f"\n  OpenClaw needs {state.openclaw_model} for tool calling.")
            ans = input(f"  Pull {state.openclaw_model} now? (~5GB) [Y/n]: ").strip().lower()
            if ans != "n":
                from bootstrap.model_provision import pull
                pull(state.openclaw_model)

    state.mark_done("model_setup")
    return True
