# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS /do — Terminal renderer
================================
All terminal output goes through here. Uses ANSI directly (no Rich dependency).
Consistent with the ClawOS REPL colour scheme.
"""
import sys

# ANSI colours — graceful fallback
def _tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_C = _tty()
RESET  = "\033[0m"        if _C else ""
BOLD   = "\033[1m"        if _C else ""
DIM    = "\033[2m"        if _C else ""
CYAN   = "\033[38;5;117m" if _C else ""
GREEN  = "\033[38;5;84m"  if _C else ""
AMBER  = "\033[38;5;220m" if _C else ""
RED    = "\033[38;5;203m" if _C else ""
GREY   = "\033[38;5;245m" if _C else ""
PURPLE = "\033[38;5;141m" if _C else ""

def _p(col, text): return f"{col}{text}{RESET}"
def _d(text):      return f"{DIM}{GREY}{text}{RESET}"
def _b(col, text): return f"{BOLD}{col}{text}{RESET}"
def _hr():         return _d("  " + "─" * 53)


def print_generating():
    print(f"\n  {_d('Generating command...')}")


def print_context_summary(ctx: dict):
    """Show a compact one-liner of what context was used."""
    parts = []
    if ctx.get("git_branch"):
        parts.append(f"git:{ctx['git_branch']}")
    if ctx.get("cwd"):
        parts.append(ctx["cwd"])
    if parts:
        print(f"\n  {_b(PURPLE, '◆')}  {_d('Context')}  {_d(' · '.join(parts))}")


def print_command(commands: list[str], safety_tier: str):
    """Display the generated command(s) with tier-appropriate colouring."""
    colour = {
        "safe":      CYAN,
        "dangerous": AMBER,
        "critical":  RED,
    }.get(safety_tier, CYAN)

    print(f"  {_b(PURPLE, '◆')}  {_d('Command')}")
    print(_hr())
    for cmd in commands:
        print(f"  {colour}{BOLD}{cmd}{RESET}")
    print(_hr())

    if safety_tier == "dangerous":
        print(f"\n  {_p(AMBER, '▲')}  {_p(AMBER, 'Destructive — this may cause data loss or system changes')}")
    elif safety_tier == "critical":
        print(f"\n  {_p(RED, '✗')}  {_p(RED, 'CRITICAL — this could cause irreversible system damage')}")


def print_dry_run(commands: list[str], affected: list[str]):
    """Show dry-run preview with affected files."""
    print(f"\n  {_d('Dry run — command will NOT be executed')}")
    for cmd in commands:
        print(f"  {CYAN}{cmd}{RESET}")
    if affected:
        print(f"\n  {_d('Would affect:')}")
        for f in affected[:10]:
            print(f"    {_d(f)}")
        if len(affected) > 10:
            print(f"    {_d(f'... and {len(affected) - 10} more')}")


def print_success(exit_code: int, elapsed: float):
    if exit_code == 0:
        print(f"\n  {_p(GREEN, '✓')}  {_d(f'Done  ({round(elapsed, 1)}s)')}")
    else:
        print(f"\n  {_p(RED, '✗')}  {_d(f'Command exited with code {exit_code}')}")


def print_audit_note(audit_path: str):
    print(f"\n  {_d(f'Logged → {audit_path}')}")


def print_explain(explanation: str):
    print(f"\n  {_b(PURPLE, 'Explanation')}")
    print(f"  {_d(explanation[:300])}")
    print()


def confirm_run(safety_tier: str, yes_flag: bool) -> bool:
    """
    Prompt user to confirm execution.
    --yes only bypasses safe commands. Never bypasses dangerous or critical.
    Returns True if user confirms, False to cancel.
    """
    if safety_tier == "critical":
        print(f"\n  {_p(RED, '✗')}  {_p(RED, 'CRITICAL command — type')} {_b(RED, 'yes')} {_p(RED, 'in full to proceed, anything else cancels:')}")
        answer = input("  ").strip()
        return answer == "yes"

    if safety_tier == "dangerous":
        print(f"\n  {_p(AMBER, '▲')}  Type {_b(AMBER, 'y')} to confirm, anything else cancels:")
        answer = input("  ").strip().lower()
        return answer == "y"

    # Safe
    if yes_flag:
        return True
    answer = input(f"\n  {_d('Run it?')} {_d('[y/n]')} {_d('(y):')} ").strip().lower()
    return answer in ("", "y", "yes")


def print_history(entries: list[dict]):
    """Display audit log history."""
    if not entries:
        print(f"\n  {_d('No command history yet.')}\n")
        return
    print(f"\n  {_b(PURPLE, 'Command History')}\n")
    for e in entries:
        ts   = e.get("timestamp", "")[:16].replace("T", " ")
        cmds = e.get("commands", [])
        code = e.get("exit_code", "?")
        danger = e.get("is_dangerous", False)
        icon = _p(RED, "■") if danger else (_p(GREEN, "✓") if code == 0 else _p(RED, "✗"))
        cmd_str = "; ".join(cmds)[:60]
        print(f"  {icon}  {_d(ts)}  {cmd_str}")
    print()


def print_undo_suggestion(cmd: str):
    if cmd:
        print(f"\n  {_b(PURPLE, 'Suggested undo:')}")
        print(f"  {CYAN}{cmd}{RESET}")
        answer = input(f"\n  {_d('Run undo?')} {_d('[y/n]:')} ").strip().lower()
        return answer in ("y", "yes")
    else:
        print(f"\n  {_d('Could not infer undo command for last action.')}\n")
        return False
