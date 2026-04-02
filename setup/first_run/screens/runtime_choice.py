"""Screen 3 — Runtime choice: multi-select for Nexus / PicoClaw / OpenClaw.
Shows detected hardware tier and pre-selects the recommended combination.
Saves selections to state.runtimes as a list.
"""

import sys
import platform

try:
    C = sys.stdout.isatty()
except Exception:
    C = False

R = "\033[0m"                 if C else ""
B = "\033[1m"                 if C else ""
D = "\033[2m\033[38;5;245m"   if C else ""
G = "\033[38;5;84m"           if C else ""
Y = "\033[38;5;220m"          if C else ""


def _tier_label(tier: str) -> str:
    return {
        "A": "Tier A — lightweight stack recommended",
        "B": "Tier B — full stack recommended",
        "C": "Tier C — full stack recommended",
        "D": "Tier C — full stack recommended",
    }.get(tier, "Tier B — full stack recommended")


def _recommended_runtimes(tier: str) -> list:
    if tier == "A":
        return ["nexus", "picoclaw"]
    return ["nexus", "picoclaw", "openclaw"]


def run(state) -> bool:
    tier     = getattr(state, "hardware_tier", "B")
    ram      = getattr(state, "ram_gb", 16.0)
    vram     = getattr(state, "gpu_vram_gb", 0.0)
    recommended = _recommended_runtimes(tier)

    arch    = platform.machine()
    gpu_str = f" · GPU {vram}GB VRAM" if vram > 0 else ""

    print(f"\n  {B}── Runtime Choice ──────────────────────────────{R}")
    print()
    print(f"  {D}Detected: {ram}GB RAM{gpu_str} · {arch}{R}")
    print(f"  {D}{_tier_label(tier)}{R}")
    print()
    print(f"  {B}Select your runtimes:{R}")
    print()

    runtimes_info = [
        {"id": "nexus",    "name": "Nexus",    "desc": "offline native agent, always local, no API keys"},
        {"id": "picoclaw", "name": "PicoClaw", "desc": "lightweight worker, cost-zero agentic tasks"},
        {"id": "openclaw", "name": "OpenClaw", "desc": "full ecosystem, 13,700+ skills, your existing stack"},
    ]

    for rt in runtimes_info:
        checked = "x" if rt["id"] in recommended else " "
        color   = G if rt["id"] in recommended else D
        print(f"  {color}[{checked}] {rt['name']:<12}{R}  {D}— {rt['desc']}{R}")
        if rt["id"] == "openclaw" and tier == "A":
            print(f"      {D}(works on this device with a cloud model — needs API key){R}")

    print()
    print(f"  {D}(Recommended for your hardware. Change anything.){R}")
    print()

    try:
        raw = input("  Runtimes [n/p/o or combos e.g. n+p+o, Enter for recommended]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        raw = ""

    if not raw:
        selected = list(recommended)
    else:
        # Support both "n+p+o" and "npo" style input
        if "+" in raw or "," in raw or " " in raw:
            parts = raw.replace(",", "+").replace(" ", "+").split("+")
        else:
            # No delimiter — treat each char as a selection e.g. "npo"
            parts = list(raw)
        selected = []
        for part in parts:
            part = part.strip()
            if part in ("n", "nexus"):      selected.append("nexus")
            elif part in ("p", "picoclaw"): selected.append("picoclaw")
            elif part in ("o", "openclaw"): selected.append("openclaw")
        if "nexus" not in selected:
            selected.insert(0, "nexus")

    # Deduplicate
    seen, final = set(), []
    for r in selected:
        if r not in seen:
            seen.add(r)
            final.append(r)

    state.runtimes = final

    # Backward compat fields
    if "openclaw" in final and "nexus" in final:
        state.runtime = "both"
    elif "openclaw" in final:
        state.runtime = "openclaw"
    else:
        state.runtime = "core"

    state.enable_picoclaw = "picoclaw" in final
    state.enable_a2a      = getattr(state, "enable_a2a", False)

    if "openclaw" in final:
        try:
            from bootstrap.profile_selector import recommended_openclaw_model
            from bootstrap.hardware_probe import HardwareProfile
            hw = HardwareProfile(ram_gb=ram, gpu_vram_gb=vram)
            state.openclaw_model = recommended_openclaw_model(hw)
        except Exception:
            pass

    labels        = {"nexus": "Nexus", "picoclaw": "PicoClaw", "openclaw": "OpenClaw"}
    chosen_labels = [labels.get(r, r) for r in final]
    print(f"\n  {G}✓{R}  Runtimes selected: {', '.join(chosen_labels)}")

    state.mark_done("runtime_choice")
    return True
