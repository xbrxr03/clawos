# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl license — ClawOS license management.

  clawctl license activate CLAW-XXXX-XXXX-XXXX-XXXX
  clawctl license status
  clawctl license deactivate
"""
import sys


def run_activate(key: str):
    """Activate a ClawOS license key on this machine."""
    key = key.strip().upper()
    print(f"🔑 Activating license key...")

    try:
        from clawos_core.license import get_license_manager
        mgr = get_license_manager()
        result = mgr.activate(key)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Activation error: {e}", file=sys.stderr)
        return

    if result["ok"]:
        tier = result["tier"]
        email = result.get("email", "")
        tier_label = {"premium": "Premium ⭐", "pro": "Pro 🚀"}.get(tier, tier)
        print(f"\n  ✓ License activated!")
        print(f"    Tier:  {tier_label}")
        if email:
            print(f"    Email: {email}")
        print(f"\n  All {tier} features are now unlocked.")
        print(f"  Run 'clawctl license status' to see what's available.")
    else:
        print(f"\n  ✗ Activation failed: {result['error']}", file=sys.stderr)
        print(f"  Get a key at: https://clawos.dev/#premium")
        sys.exit(1)


def run_status():
    """Show current license status."""
    try:
        from clawos_core.license import get_license_manager, FREE_FEATURES, PREMIUM_FEATURES
        mgr = get_license_manager()
        status = mgr.get_status()
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Status error: {e}", file=sys.stderr)
        return

    tier = status["tier"]
    valid = status["valid"]

    tier_icons = {"free": "○", "premium": "⭐", "pro": "🚀"}
    icon = tier_icons.get(tier, "?")

    print(f"\n  ClawOS License Status")
    print(f"  ─────────────────────")
    print(f"  Tier:   {icon}  {tier.upper()}")
    print(f"  Valid:  {'✓ Yes' if valid else '✗ No'}")

    if status.get("key_prefix"):
        print(f"  Key:    {status['key_prefix']}")
    if status.get("email"):
        print(f"  Email:  {status['email']}")
    if status.get("grace_remaining_hours"):
        print(f"  Grace:  {status['grace_remaining_hours']}h remaining (offline)")
    if status.get("error"):
        print(f"  Note:   {status['error']}")

    print(f"  Machine: {status.get('machine_id', '?')}")

    if tier == "free":
        print(f"\n  Free tier unlocks: core agent, Ollama, basic workflows, Piper TTS")
        print(f"  Premium unlocks: all workflows, cloud models, ElevenLabs, Nexus Brain,")
        print(f"                   browser control, A2A, proactive intelligence + more")
        print(f"\n  Upgrade: https://clawos.dev/#premium  ($10 once, yours forever)")
    elif tier in ("premium", "pro"):
        print(f"\n  Premium features active:")
        from clawos_core.license import PREMIUM_FEATURES
        feature_labels = [
            "✓ All 29 workflows",
            "✓ Cloud AI models (OpenRouter + kimi-k2)",
            "✓ ElevenLabs premium voice",
            "✓ Nexus 3D knowledge brain",
            "✓ Browser control (Playwright)",
            "✓ Proactive ambient intelligence",
            "✓ A2A multi-agent federation",
            "✓ Advanced RAG + GraphRAG",
        ]
        for f in feature_labels:
            print(f"    {f}")


def run_deactivate():
    """Deactivate license on this machine (frees the key for another machine)."""
    print("  Deactivating license on this machine...")
    try:
        from clawos_core.license import get_license_manager
        mgr = get_license_manager()
        result = mgr.deactivate()
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Error: {e}", file=sys.stderr)
        return

    if result["ok"]:
        print("  ✓ License deactivated. Your key can now be activated on another machine.")
        print("  You are now on the free tier.")
    else:
        print(f"  ✗ {result['error']}", file=sys.stderr)
