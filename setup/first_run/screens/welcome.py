"""Screen 1 — Welcome."""
from clawos_core.constants import VERSION_FULL

BANNER = f"""
  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝
  {VERSION_FULL} | local · offline · private · free
"""


def run(state) -> bool:
    print(BANNER)
    print("  Welcome to ClawOS — your private AI agent OS.")
    print("  Everything runs on this machine. No cloud. No API keys. No bill.")
    print()
    print("  This wizard takes ~2 minutes and sets up:")
    print("    • Hardware profile (auto-detected)")
    print("    • AI runtime (Claw Core or OpenClaw)")
    print("    • Voice (optional)")
    print("    • WhatsApp (optional)")
    print("    • Permissions")
    print()
    ans = input("  Press Enter to start, or Q to quit: ").strip().lower()
    if ans == "q":
        return False
    state.mark_done("welcome")
    return True
