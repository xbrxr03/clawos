"""
ClawOS Bootstrap
================
One-time machine preparation. Run after git clone or first install.
Idempotent — safe to re-run.

Usage:
  python3 -m bootstrap.bootstrap
  python3 -m bootstrap.bootstrap --profile balanced
  python3 -m bootstrap.bootstrap --yes   (non-interactive)
"""
import sys
import argparse
from pathlib import Path


def _step(name: str):
    print(f"\n  [{name}]")


def run(profile: str = None, yes: bool = False, workspace: str = "nexus_default"):

    # Step 1: Hardware probe
    _step("1/6 Hardware detection")
    from bootstrap.hardware_probe import probe_and_save
    from bootstrap.profile_selector import select, summary
    hw = probe_and_save()
    print(summary(hw))

    # Step 2: Profile selection
    _step("2/6 Profile selection")
    if profile is None:
        profile = select(hw)
    print(f"  Profile: {profile}")

    # Save profile to config
    from clawos_core.constants import CONFIG_DIR, CLAWOS_CONFIG
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        existing = {}
        if CLAWOS_CONFIG.exists():
            with open(CLAWOS_CONFIG) as f:
                existing = yaml.safe_load(f) or {}
        existing["_profile"] = profile
        with open(CLAWOS_CONFIG, "w") as f:
            yaml.dump(existing, f)
    except ImportError:
        CLAWOS_CONFIG.write_text(f"_profile: {profile}\n")

    # Step 3: Create dirs + seed workspace
    _step("3/6 Workspace setup")
    from bootstrap.workspace_init import init_all_dirs, init_workspace
    init_all_dirs()
    ws_path = init_workspace(workspace)
    print(f"  Workspace '{workspace}' ready at {ws_path}")

    # Step 4: Memory backends
    _step("4/6 Memory initialisation")
    from bootstrap.memory_init import init_all
    mem = init_all()
    for backend, ok in mem.items():
        print(f"  {backend}: {'✓' if ok else '✗ (optional)'}")

    # Step 5: Policy config
    _step("5/6 Policy config")
    from bootstrap.permissions_init import write as write_policy
    path = write_policy("recommended", workspace)
    print(f"  Policy written: {path}")

    # Step 6: Model provisioning
    _step("6/6 Model provisioning")
    from bootstrap.profile_selector import recommended_model
    model = recommended_model(hw)
    if hw.ollama_ok:
        from bootstrap.model_provision import pull
        pull(model)
    else:
        print(f"  Ollama not running — skipping pull of {model}")
        print(f"  Start Ollama later: ollama serve && ollama pull {model}")

    # Done
    print("""
  ─────────────────────────────────────────────
  Bootstrap complete!

  Next steps:
    nexus                            — start chatting
    bash scripts/dev_boot.sh          — start all services
    http://localhost:7070             — dashboard (after dev_boot)

  Or run the first-run wizard:
    python3 -m setup.first_run.wizard
  ─────────────────────────────────────────────
    """)

    return {"profile": profile, "workspace": workspace, "hw_tier": hw.tier}


def main():
    parser = argparse.ArgumentParser(description="ClawOS Bootstrap")
    parser.add_argument("--profile", choices=["lowram","balanced","performance"],
                        help="Force a profile instead of auto-detecting")
    parser.add_argument("--workspace", default="nexus_default",
                        help="Workspace name to initialise")
    parser.add_argument("--yes", action="store_true",
                        help="Non-interactive mode")
    args = parser.parse_args()
    run(profile=args.profile, yes=args.yes, workspace=args.workspace)


if __name__ == "__main__":
    main()
