# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
"""Screen 8 — Policy / permission mode."""


def run(state) -> bool:
    print("\n  ── Permission Model ────────────────────────────")
    print()
    print("  How should Nexus handle sensitive actions?")
    print()
    print("  [1] Recommended  ← safe default")
    print("      · High-risk actions (delete, shell) pause for your approval")
    print("      · Approve from terminal, dashboard, or WhatsApp reply")
    print("      · Full Merkle-chained audit log")
    print()
    print("  [2] Developer")
    print("      · Shell commands and API calls granted automatically")
    print("      · Still audited — no action is invisible")
    print("      · Good if you're building on top of ClawOS")
    print()

    choice = input("  Choose [1/2] or Enter for Recommended: ").strip()
    state.policy_mode = "developer" if choice == "2" else "recommended"

    from bootstrap.permissions_init import write as write_policy
    write_policy(state.policy_mode, state.workspace_id)
    print(f"\n  Policy: {state.policy_mode}")

    state.mark_done("policy_setup")
    return True
