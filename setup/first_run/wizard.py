# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS First-Run Wizard
========================
10-screen terminal wizard. Idempotent — skips completed screens.
Usage: python3 -m setup.first_run.wizard [--reset] [--from <screen>]
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from setup.first_run.state import WizardState

SCREENS = [
    ("welcome",          "setup.first_run.screens.welcome"),
    ("hardware_profile", "setup.first_run.screens.hardware_profile"),
    ("runtime_choice",   "setup.first_run.screens.runtime_choice"),
    ("api_keys",         "setup.first_run.screens.api_keys"),        # NEW
    ("workspace_setup",  "setup.first_run.screens.workspace_setup"),
    ("user_profile",     "setup.first_run.screens.user_profile"),
    ("voice_setup",      "setup.first_run.screens.voice_setup"),
    ("model_setup",      "setup.first_run.screens.model_setup"),
    ("whatsapp_setup",   "setup.first_run.screens.whatsapp_setup"),
    ("policy_setup",     "setup.first_run.screens.policy_setup"),
    ("summary",          "setup.first_run.screens.summary"),
]


def run(reset: bool = False, from_screen: str = None):
    state = WizardState()
    if reset:
        state = WizardState()
        state.save()

    start_idx = 0
    if from_screen:
        names = [s[0] for s in SCREENS]
        if from_screen in names:
            start_idx = names.index(from_screen)

    for name, module_path in SCREENS[start_idx:]:
        if name in state.screens_done and not reset and name != "summary":
            print(f"  (skipping {name} — already done)")
            continue
        try:
            import importlib
            mod    = importlib.import_module(module_path)
            result = mod.run(state)
            if result is False:
                print("\n  Wizard cancelled. Run again: python3 -m setup.first_run.wizard")
                sys.exit(0)
        except KeyboardInterrupt:
            print(f"\n\n  Interrupted at '{name}'. Resume: python3 -m setup.first_run.wizard")
            state.save()
            sys.exit(0)
        except Exception as e:
            print(f"\n  [ERROR] Screen '{name}' failed: {e}")
            print("  Continuing to next screen ...")
            state.mark_done(name)

    print("\n  ClawOS is ready. Enjoy your private AI.\n")


def main():
    import sys
    if not sys.stdin.isatty():
        print("  Non-interactive install detected — skipping wizard.")
        print("  Run manually: nexus setup")
        return
    parser = argparse.ArgumentParser(description="ClawOS First-Run Wizard")
    parser.add_argument("--reset",      action="store_true",  help="Start from scratch")
    parser.add_argument("--from",       dest="from_screen",   help="Start from specific screen")
    args = parser.parse_args()
    run(reset=args.reset, from_screen=args.from_screen)


if __name__ == "__main__":
    main()
