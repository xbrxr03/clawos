"""Screen — API Keys.
Runs after runtime_choice. Shows all keys from the registry filtered to the user's tier.
Masks input. Runs place_all() with everything provided.
"""

import getpass
import sys

try:
    C = sys.stdout.isatty()
except Exception:
    C = False

R = "\033[0m"          if C else ""
B = "\033[1m"          if C else ""
D = "\033[2m\033[38;5;245m" if C else ""
G = "\033[38;5;84m"    if C else ""
Y = "\033[38;5;220m"   if C else ""


def run(state) -> bool:
    print(f"\n  {B}── API Keys ────────────────────────────────────{R}")
    print()
    print(f"  {D}ClawOS will place each key everywhere it needs to go automatically.{R}")
    print(f"  {D}Press Enter to skip any key. OpenRouter is recommended if you selected OpenClaw.{R}")
    print()

    tier = getattr(state, "hardware_tier", "B")
    runtimes = getattr(state, "runtimes", ["nexus", "picoclaw"])
    openclaw_selected = "openclaw" in runtimes

    # Skip entirely if no OpenClaw and Tier A (pure offline)
    if not openclaw_selected and tier == "A":
        print(f"  {D}Offline-only setup — skipping API keys.{R}")
        state.mark_done("api_keys")
        return True

    try:
        from clawos_core.key_registry import KEY_REGISTRY
        from services.secretd.placer import place_all, get_existing_keys
    except ImportError as e:
        print(f"  {D}Warning: key registry unavailable ({e}) — skipping.{R}")
        state.mark_done("api_keys")
        return True

    existing = get_existing_keys()
    collected = {}

    for entry in KEY_REGISTRY:
        show = (
            any(r in runtimes for r in entry.get("required_for", [])) or
            tier in entry.get("tier_shown", [])
        )
        if not show:
            continue

        is_recommended = (entry["id"] == "OPENROUTER_API_KEY")
        tag = f"{Y}recommended{R}" if is_recommended else f"{D}optional{R}"

        existing_val = existing.get(entry["id"], "")

        print(f"  {B}{entry['label']}{R}  [{tag}]")
        print(f"  {D}{entry['description']}{R}")
        print(f"  {D}Get yours: {entry['url']}{R}")
        if existing_val:
            masked = existing_val[:4] + "****" + existing_val[-4:] if len(existing_val) > 8 else "****"
            print(f"  {D}(already set: {masked} — press Enter to keep){R}")

        try:
            val = getpass.getpass("  Key: ")
        except (EOFError, KeyboardInterrupt):
            val = ""

        if not val.strip() and existing_val:
            collected[entry["id"]] = existing_val
        elif val.strip():
            collected[entry["id"]] = val.strip()

        print()

    provided  = {k: v for k, v in collected.items() if v}
    new_keys  = {k: v for k, v in collected.items() if v and k not in existing}
    kept_keys = {k: v for k, v in collected.items() if v and k in existing}

    if not provided:
        print(f"  {D}No keys provided — using local models only.{R}")
        print(f"  {D}To add keys later: nexus setup --from api_keys{R}")
        state.api_keys_configured = []
        state.mark_done("api_keys")
        return True

    if new_keys:
        print(f"  {D}Placing keys...{R}")
        results = place_all(new_keys)
        total_placements = sum(len(locs) for locs in results.values())
        print(f"  {G}✓{R}  {len(new_keys)} key(s) saved and placed in {total_placements} location(s)")
    if kept_keys:
        print(f"  {D}Kept {len(kept_keys)} existing key(s) unchanged.{R}")
    print()

    state.api_keys_configured = list(provided.keys())
    state.mark_done("api_keys")
    return True
