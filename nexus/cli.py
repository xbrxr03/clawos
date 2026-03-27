"""
nexus — ClawOS user-facing CLI
================================
Usage:
  nexus                          → interactive chat (default)
  nexus <natural language>       → shell command via claw-do (auto-detected)
  nexus status                   → service health, model, VRAM
  nexus logs [service] [-f]      → tail logs
  nexus audit                    → Merkle audit trail
  nexus memory [query]           → show/search memory layers
  nexus workspace [list|create|delete|switch] [name]
  nexus model [list|pull|remove] [name]
  nexus policy                   → show current permission rules
  nexus approve <id>             → approve pending tool call
  nexus deny <id>                → deny pending tool call
  nexus setup                    → re-run first-run wizard
  nexus scan <text>              → prompt injection scanner

Subcommand detection:
  Reserved keywords are matched first.
  Anything else is treated as a natural language shell request.
"""
import sys
import os
from pathlib import Path

# Ensure clawos root is on path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Reserved subcommands ──────────────────────────────────────────────────────
RESERVED = {
    "status", "logs", "audit", "memory", "workspace", "model",
    "policy", "approve", "deny", "setup", "scan",
    # aliases
    "ws", "mod",
}


def _is_reserved(word: str) -> bool:
    return word.lower() in RESERVED


# ── Colours ───────────────────────────────────────────────────────────────────
def _tty():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_C     = _tty()
RESET  = "\033[0m"        if _C else ""
BOLD   = "\033[1m"        if _C else ""
DIM    = "\033[2m"        if _C else ""
PURPLE = "\033[38;5;141m" if _C else ""
GREEN  = "\033[38;5;84m"  if _C else ""
AMBER  = "\033[38;5;220m" if _C else ""
RED    = "\033[38;5;203m" if _C else ""
BLUE   = "\033[38;5;75m"  if _C else ""
GREY   = "\033[38;5;245m" if _C else ""
CYAN   = "\033[38;5;117m" if _C else ""

def _p(c, t): return f"{c}{t}{RESET}"
def _d(t):    return f"{DIM}{GREY}{t}{RESET}"
def _b(c, t): return f"{BOLD}{c}{t}{RESET}"


# ── status ────────────────────────────────────────────────────────────────────
def cmd_status():
    from clawctl.commands.status import run
    run()


# ── logs ──────────────────────────────────────────────────────────────────────
def cmd_logs(args: list):
    service = None
    follow  = False
    lines   = 40
    for a in args:
        if a == "-f" or a == "--follow":
            follow = True
        elif a.lstrip("-").isdigit():
            lines = int(a.lstrip("-"))
        else:
            service = a
    from clawctl.commands.logs import run
    run(service, follow, lines)


# ── audit ─────────────────────────────────────────────────────────────────────
def cmd_audit(args: list):
    n = 20
    for a in args:
        if a.isdigit():
            n = int(a)
    try:
        import clawos_core.logging.audit as audit
        entries = audit.tail(n)
        if not entries:
            print(f"\n  {_d('No audit entries yet.')}\n")
            return
        print(f"\n  {_b(PURPLE, 'Audit Trail')}  {_d(str(len(entries)) + ' entries')}\n")
        for e in entries:
            ts       = e.get("timestamp", "")[:16].replace("T", " ")
            tool     = e.get("tool", "?")
            target   = e.get("target", "")[:40]
            decision = e.get("decision", "?")
            icon     = _p(GREEN, "✓") if decision == "ALLOW" else _p(RED, "✗")
            print(f"  {icon}  {_d(ts)}  {_p(CYAN, tool):<30}  {_d(target)}")
        print()
    except Exception as e:
        print(f"  {_p(RED, 'error:')} {e}\n")


# ── memory ────────────────────────────────────────────────────────────────────
def cmd_memory(args: list):
    query = " ".join(args) if args else "recent"
    try:
        from services.memd.service import MemoryService
        from clawos_core.constants import DEFAULT_WORKSPACE
        ws = _active_workspace()
        mem = MemoryService()
        print(f"\n  {_b(PURPLE, 'Memory')}  {_d('workspace: ' + ws)}\n")

        pinned = mem.read_pinned(ws)
        if pinned.strip():
            print(f"  {_p(AMBER, 'PINNED')}")
            for line in pinned.strip().splitlines()[:8]:
                if line.strip() and not line.startswith("#"):
                    print(f"    {_d(line)}")
            print()

        if query and query != "recent":
            results = mem.recall(query, ws, n=6)
            if results:
                print(f"  {_p(CYAN, 'Recall:')} {_d(query)}")
                for r in results:
                    print(f"    {_d(r[:100])}")
            else:
                print(f"  {_d('No matches for: ' + query)}")
        else:
            hist = mem.read_history_tail(ws, lines=8)
            if hist:
                print(f"  {_p(CYAN, 'Recent')}")
                for line in hist.strip().splitlines()[-6:]:
                    if line.strip():
                        print(f"    {_d(line[:100])}")
        print()
    except Exception as e:
        print(f"  {_p(RED, 'error:')} {e}\n")


# ── workspace ─────────────────────────────────────────────────────────────────
def cmd_workspace(args: list):
    sub  = args[0].lower() if args else "list"
    name = args[1] if len(args) > 1 else None

    if sub in ("list", "ls"):
        from clawctl.commands.workspace import run_list
        run_list()
    elif sub in ("create", "new") and name:
        from clawctl.commands.workspace import run_create
        run_create(name)
    elif sub in ("delete", "rm") and name:
        from clawctl.commands.workspace import run_delete
        run_delete(name)
    elif sub in ("switch", "use") and name:
        _set_active_workspace(name)
        print(f"\n  {_p(GREEN, '✓')}  Active workspace set to {_p(AMBER, name)}\n")
    else:
        print(f"\n  Usage: nexus workspace [list|create|delete|switch] [name]\n")


# ── model ─────────────────────────────────────────────────────────────────────
def cmd_model(args: list):
    sub  = args[0].lower() if args else "list"
    name = args[1] if len(args) > 1 else None

    if sub in ("list", "ls"):
        from clawctl.commands.model import run_list
        run_list()
    elif sub == "pull" and name:
        from clawctl.commands.model import run_pull
        run_pull(name)
    elif sub in ("remove", "rm", "delete") and name:
        from clawctl.commands.model import run_remove
        run_remove(name)
    elif sub == "default" and name:
        from clawctl.commands.model import run_set_default
        run_set_default(name)
    else:
        print(f"\n  Usage: nexus model [list|pull|remove|default] [name]\n")


# ── policy ────────────────────────────────────────────────────────────────────
def cmd_policy():
    try:
        from bootstrap.permissions_init import load
        policy = load()
        mode   = policy.get("mode", "unknown")
        print(f"\n  {_b(PURPLE, 'Policy')}  {_p(AMBER, mode)}\n")
        for ws, cfg in policy.get("workspaces", {}).items():
            print(f"  {_p(CYAN, ws)}")
            grants = cfg.get("granted_tools", [])
            print(f"    {_d('granted:')} {', '.join(grants[:6])}")
            if len(grants) > 6:
                print(f"    {_d('... and ' + str(len(grants)-6) + ' more')}")
            req = cfg.get("require_approval", [])
            if req:
                print(f"    {_d('approval required:')} {', '.join(req)}")
        print()
    except Exception as e:
        print(f"  {_p(RED, 'error:')} {e}\n")


# ── approve / deny ────────────────────────────────────────────────────────────
def cmd_approve(request_id: str):
    try:
        from services.policyd.service import get_engine
        ok = get_engine().decide_approval(request_id, approve=True)
        if ok:
            print(f"\n  {_p(GREEN, '✓')}  Approved: {request_id}\n")
        else:
            print(f"\n  {_p(RED, '✗')}  Not found: {request_id}\n")
    except Exception as e:
        print(f"  {_p(RED, 'error:')} {e}\n")


def cmd_deny(request_id: str):
    try:
        from services.policyd.service import get_engine
        ok = get_engine().decide_approval(request_id, approve=False)
        if ok:
            print(f"\n  {_p(AMBER, '○')}  Denied: {request_id}\n")
        else:
            print(f"\n  {_p(RED, '✗')}  Not found: {request_id}\n")
    except Exception as e:
        print(f"  {_p(RED, 'error:')} {e}\n")


# ── setup ─────────────────────────────────────────────────────────────────────
def cmd_setup():
    import subprocess
    wizard = _ROOT / "setup" / "first_run" / "wizard.py"
    subprocess.run([sys.executable, str(wizard), "--reset"])


# ── scan ──────────────────────────────────────────────────────────────────────
def cmd_scan(text: str):
    """Run the prompt injection scanner on a piece of text."""
    from nexus.scanner import scan
    result = scan(text)
    if result["is_injection"]:
        print(f"\n  {_p(RED, '⚠  INJECTION DETECTED')}")
        print(f"  {_d('Score:')} {_p(RED, str(result['score']))}")
        print(f"  {_d('Patterns matched:')}")
        for p in result["patterns"]:
            print(f"    {_d('·')} {p}")
    else:
        print(f"\n  {_p(GREEN, '✓')}  Clean  {_d('score: ' + str(result['score']))}")
    print()


# ── natural language shell command ────────────────────────────────────────────
def cmd_do(request: str):
    """
    Treat free-form text as a natural language shell request.
    Auto-runs safe commands. Confirms dangerous ones. Never runs critical without 'yes'.
    """
    from tools.shell.do.context   import collect_context
    from tools.shell.do.generator import generate
    from tools.shell.do.safety    import classify_plan
    from tools.shell.do.renderer  import (
        print_generating, print_context_summary, print_command,
        print_success, print_audit_note,
    )
    from tools.shell.do.runner    import run_commands, _audit_path

    print_generating()
    ctx = collect_context(_active_workspace())
    print_context_summary(ctx)

    commands = generate(request, ctx)
    if not commands:
        print(f"  {_p(RED, 'error:')} Could not generate a command. Try rephrasing.\n")
        return

    safety = classify_plan(commands)
    print_command(commands, safety.tier)

    # Safe → run immediately (no confirm)
    # Dangerous → ask
    # Critical → must type 'yes'
    if safety.tier == "safe":
        confirmed = True
    elif safety.tier == "dangerous":
        answer = input(f"\n  {_d('Dangerous — confirm?')} [y/N]: ").strip().lower()
        confirmed = answer == "y"
    else:  # critical
        print(f"\n  {_p(RED, 'CRITICAL')} — type {_p(RED, 'yes')} in full to proceed:")
        confirmed = input("  ").strip() == "yes"

    if not confirmed:
        print()
        return

    import time
    t0   = time.time()
    code = run_commands(
        commands, request=request,
        is_dangerous=(safety.tier != "safe"),
    )
    print_success(code, time.time() - t0)
    print_audit_note(str(_audit_path()))


# ── chat (default) ────────────────────────────────────────────────────────────
def cmd_chat():
    import asyncio
    from clients.cli.repl import run_repl
    asyncio.run(run_repl(_active_workspace()))


# ── workspace helpers ─────────────────────────────────────────────────────────
def _active_workspace() -> str:
    """Read active workspace from clawos.yaml, fall back to DEFAULT_WORKSPACE."""
    try:
        from clawos_core.constants import CLAWOS_CONFIG, DEFAULT_WORKSPACE
        if CLAWOS_CONFIG.exists():
            try:
                import yaml
                cfg = yaml.safe_load(CLAWOS_CONFIG.read_text()) or {}
                ws  = cfg.get("workspace", {}).get("default", "")
                if ws:
                    return ws
            except Exception:
                pass
        return DEFAULT_WORKSPACE
    except Exception:
        return "nexus_default"


def _set_active_workspace(name: str):
    """Write active workspace to clawos.yaml."""
    try:
        from clawos_core.constants import CLAWOS_CONFIG, CONFIG_DIR
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            import yaml
            cfg = {}
            if CLAWOS_CONFIG.exists():
                cfg = yaml.safe_load(CLAWOS_CONFIG.read_text()) or {}
            cfg.setdefault("workspace", {})["default"] = name
            CLAWOS_CONFIG.write_text(yaml.dump(cfg))
        except ImportError:
            text = CLAWOS_CONFIG.read_text() if CLAWOS_CONFIG.exists() else ""
            CLAWOS_CONFIG.write_text(text + f"\nworkspace:\n  default: {name}\n")
    except Exception:
        pass


# ── help ──────────────────────────────────────────────────────────────────────
def print_help():
    print(f"""
  {_b(PURPLE, 'nexus')} — ClawOS AI assistant

  {_d('Usage:')}
    {_p(CYAN, 'nexus')}                          start chat (default)
    {_p(CYAN, 'nexus')} {_d('<request>')}              run shell command (natural language)
    {_p(CYAN, 'nexus')} {_p(CYAN, 'status')}                 service health + model info
    {_p(CYAN, 'nexus')} {_p(CYAN, 'logs')} {_d('[service] [-f]')}    tail logs
    {_p(CYAN, 'nexus')} {_p(CYAN, 'audit')} {_d('[n]')}              show audit trail
    {_p(CYAN, 'nexus')} {_p(CYAN, 'memory')} {_d('[query]')}          show/search memory
    {_p(CYAN, 'nexus')} {_p(CYAN, 'workspace')} {_d('[list|create|delete|switch]')}
    {_p(CYAN, 'nexus')} {_p(CYAN, 'model')} {_d('[list|pull|remove|default]')}
    {_p(CYAN, 'nexus')} {_p(CYAN, 'policy')}                show permission rules
    {_p(CYAN, 'nexus')} {_p(CYAN, 'approve')} {_d('<id>')}           approve pending action
    {_p(CYAN, 'nexus')} {_p(CYAN, 'deny')} {_d('<id>')}              deny pending action
    {_p(CYAN, 'nexus')} {_p(CYAN, 'setup')}                 re-run first-run wizard
    {_p(CYAN, 'nexus')} {_p(CYAN, 'scan')} {_d('<text>')}            prompt injection scanner

  {_d('Examples:')}
    nexus                          # start chat
    nexus find files larger than 1gb
    nexus show disk usage
    nexus status
    nexus model pull qwen2.5:14b
    nexus workspace switch myproject
    nexus scan "ignore previous instructions"
""")


# ── main entry point ──────────────────────────────────────────────────────────
def main(argv: list = None):
    if argv is None:
        argv = sys.argv[1:]

    # No args → chat
    if not argv:
        cmd_chat()
        return

    first = argv[0].lower()

    # Help
    if first in ("-h", "--help", "help"):
        print_help()
        return

    # Reserved subcommands
    if first == "status":
        cmd_status()

    elif first == "logs":
        cmd_logs(argv[1:])

    elif first == "audit":
        cmd_audit(argv[1:])

    elif first == "memory":
        cmd_memory(argv[1:])

    elif first in ("workspace", "ws"):
        cmd_workspace(argv[1:])

    elif first in ("model", "mod"):
        cmd_model(argv[1:])

    elif first == "policy":
        cmd_policy()

    elif first == "approve":
        if len(argv) < 2:
            print(f"\n  Usage: nexus approve <request_id>\n")
        else:
            cmd_approve(argv[1])

    elif first == "deny":
        if len(argv) < 2:
            print(f"\n  Usage: nexus deny <request_id>\n")
        else:
            cmd_deny(argv[1])

    elif first == "setup":
        cmd_setup()

    elif first == "scan":
        text = " ".join(argv[1:])
        if not text:
            print(f"\n  Usage: nexus scan <text to check>\n")
        else:
            cmd_scan(text)

    else:
        # Everything else → natural language shell request
        cmd_do(" ".join(argv))


if __name__ == "__main__":
    main()
