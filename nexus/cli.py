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
    "secret", "project", "command", "plan", "workflow",
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
    # Show compression stats inline if openclaw is installed
    import shutil
    if shutil.which("openclaw"):
        _print_compression_status()


def _print_compression_status():
    try:
        from openclaw_integration.compression import (
            headroom_running, rtk_installed, headroom_stats,
            rtk_stats, HEADROOM_PORT
        )
        h = headroom_running()
        r = rtk_installed()
        if not h and not r:
            return
        print(f"  {_d('Token compression')} {_d('─'*22)}")
        if h:
            s   = headroom_stats()
            tok = s.get("tokens", {}).get("saved", 0)
            pct = s.get("tokens", {}).get("savings_percent", 0)
            tag = f" {_d(str(tok)+' saved ('+str(round(pct))+'%)')}" if tok else ""
            print("  " + _p(GREEN, "✓") + f"  headroom  proxy :{HEADROOM_PORT}{tag}")
        if r:
            s = rtk_stats()
            raw = s.get("raw", "")
            import re as _re2
            m = _re2.search(r'[\d,]+\s*tokens', raw)
            tag = f" {_d(m.group(0))}" if m else ""
            print("  " + _p(GREEN, "✓") + f"  rtk       CLI compression{tag}")
        print()
    except Exception:
        pass


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


# ── use-kimi ──────────────────────────────────────────────────────────────────
def cmd_use_kimi():
    """Log in to Ollama, pull kimi-k2.5, and reconfigure OpenClaw to use it."""
    import subprocess, json
    from pathlib import Path

    print(f"\n  {_p(CYAN, '◆')}  Switching OpenClaw to Kimi K2.5\n")

    # Step 1: ollama login
    print(f"  {_d('·')} Signing in to Ollama (a browser link will appear)...\n")
    result = subprocess.run(["ollama", "login"])
    if result.returncode != 0:
        print(f"\n  {_p(RED, '✗')}  Ollama login failed or was cancelled.\n")
        return

    # Step 2: pull kimi-k2.5
    print(f"\n  {_p(GREEN, '✓')}  Signed in.\n")
    print(f"  {_d('·')} Registering kimi-k2.5...\n")
    result = subprocess.run(["ollama", "pull", "kimi-k2.5:cloud"])
    if result.returncode != 0:
        print(f"\n  {_p(RED, '✗')}  Could not pull kimi-k2.5:cloud. Check your Ollama account.\n")
        return

    # Step 3: update ~/.openclaw/openclaw.json
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    try:
        cfg = json.loads(config_path.read_text())
        providers = cfg.setdefault("models", {}).setdefault("providers", {})
        ollama_models = providers.setdefault("ollama", {}).setdefault("models", [])
        # Insert kimi-k2.5:cloud at the front if not already present
        ids = [m["id"] for m in ollama_models]
        if "kimi-k2.5:cloud" not in ids:
            ollama_models.insert(0, {"id": "kimi-k2.5:cloud", "name": "kimi-k2.5:cloud", "contextWindow": 262144})
        # Set as primary
        cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {})["primary"] = "ollama/kimi-k2.5:cloud"
        config_path.write_text(json.dumps(cfg, indent=2))
        print(f"\n  {_p(GREEN, '✓')}  OpenClaw reconfigured → kimi-k2.5")
    except Exception as e:
        print(f"\n  {_p(RED, '✗')}  Could not update openclaw.json: {e}\n")
        return

    print(f"\n  {_p(GREEN, '✓')}  Done. Launch with:  {_p(CYAN, 'openclaw tui')}\n")


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




# ── plan mode ────────────────────────────────────────────────────────────────
def _run_plan_mode(spec: str, agent):
    """Generate a scored execution plan and wait for approval before running."""
    import asyncio
    import json

    plan_prompt = (
        "You are a planning agent. The user has described a task:\n\n"
        + spec + "\n\n"
        "Generate exactly 3 execution options ranked by approach. For each option return:\n"
        "- title: a short title (5 words max)\n"
        "- score: confidence score 1-10\n"
        "- steps: list of 3-5 concrete steps\n"
        "- risks: key risks or tradeoffs (one line)\n\n"
        "Respond with ONLY a JSON array. No prose outside the JSON."
    )

    print(f"\n  Generating plan...")
    try:
        raw = asyncio.run(agent.chat(plan_prompt))
    except Exception as e:
        print(f"  Plan generation error: {e}\n")
        return

    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            from json_repair import repair_json
            clean = repair_json(clean)
        except ImportError:
            pass
        options = json.loads(clean)
        if not isinstance(options, list):
            raise ValueError("not a list")
    except Exception:
        print("  Plan generation failed — falling back to direct execution\n")
        return

    # Display options
    print(f"\n  {'─'*56}")
    for i, opt in enumerate(options[:3], 1):
        score = opt.get("score", "?")
        title = opt.get("title", f"Option {i}")
        steps = opt.get("steps", [])
        risks = opt.get("risks", "")
        print(f"\n  {i}  {title}  [{score}/10]")
        for step in steps:
            print(f"     > {step}")
        if risks:
            print(f"     ! {risks}")

    print(f"\n  {'─'*56}")
    try:
        choice = input("  Choose option [1/2/3] or q to cancel: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if choice not in ("1", "2", "3"):
        print("  Plan cancelled.\n")
        return

    selected = options[int(choice) - 1]
    print(f"\n  Executing: {selected.get('title', '')}\n")

    execution_prompt = (
        "Execute this plan:\n"
        f"Title: {selected.get('title')}\n"
        f"Steps: {json.dumps(selected.get('steps', []))}\n\n"
        f"Original task: {spec}\n\n"
        "Execute the steps. Use tools as needed."
    )

    result = asyncio.run(agent.chat(execution_prompt))
    print(f"\n  {result}\n")

# ── nexus command (Nexus Command / openclaw-office) ───────────────────────────
def cmd_command(args: list):
    """Launch Nexus Command — openclaw-office rebranded 3D agent dashboard."""
    port = 5180
    for a in args:
        if a.isdigit():
            port = int(a)
    import subprocess, sys
    serve_script = _ROOT / "dashboard" / "nexus-command" / "serve.py"
    if not serve_script.exists():
        print(f"\n  {_p(RED, 'x')}  Nexus Command not found at {serve_script}\n")
        return
    try:
        subprocess.run([sys.executable, str(serve_script), "--port", str(port)])
    except KeyboardInterrupt:
        pass


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

# ── secret ─────────────────────────────────────────────────────────────────────
def cmd_secret(args: list):
    from services.secretd.service import get_store
    store = get_store()

    if not args:
        print(f"\n  Usage: nexus secret set <NAME> <VALUE>")
        print(f"         nexus secret get <NAME>")
        print(f"         nexus secret list")
        print(f"         nexus secret remove <NAME>\n")
        return

    sub = args[0].lower()

    if sub == "set":
        if len(args) < 3:
            print(f"\n  Usage: nexus secret set <NAME> <VALUE>\n")
            return
        name, value = args[1], " ".join(args[2:])
        if store.set(name, value):
            print(f"\n  " + _p(GREEN, "✓") + f"  Secret {_b(PURPLE, name)} stored\n")
        else:
            print(f"\n  " + _p(RED, "✗") + f"  Invalid name: {name}\n")

    elif sub == "get":
        if len(args) < 2:
            print(f"\n  Usage: nexus secret get <NAME>\n")
            return
        name  = args[1]
        value = store.get(name)
        if value is None:
            print(f"\n  " + _p(RED, "✗") + f"  Secret not found: {name}\n")
        else:
            # Show masked by default
            masked = value[:4] + "*" * max(0, len(value) - 4)
            print(f"\n  {_b(PURPLE, name)}  {_d(masked)}\n")

    elif sub == "list":
        names = store.list_names()
        print()
        if not names:
            print(f"  {_d('No secrets stored.')}")
        else:
            print(f"  {_d('Stored secrets:')}")
            for n in names:
                val = store.get(n) or ""
                masked = val[:4] + "*" * max(0, len(val) - 4)
                print(f"  {_p(GREEN, '·')}  {_b(PURPLE, n):<30} {_d(masked)}")
        print()

    elif sub == "remove":
        if len(args) < 2:
            print(f"\n  Usage: nexus secret remove <NAME>\n")
            return
        name = args[1]
        if store.remove(name):
            print(f"\n  " + _p(GREEN, "✓") + f"  Secret {_b(PURPLE, name)} removed\n")
        else:
            print(f"\n  " + _p(RED, "✗") + f"  Secret not found: {name}\n")

    else:
        print(f"\n  Unknown subcommand: {sub}\n")


# ── project ────────────────────────────────────────────────────────────────────
def cmd_project(args: list):
    from clawos_core.constants import DEFAULT_WORKSPACE, WORKSPACE_DIR
    from pathlib import Path as _Path
    import json as _json

    if not args:
        print(f"\n  Usage: nexus project start <name>")
        print(f"         nexus project switch <name>")
        print(f"         nexus project list")
        print(f"         nexus project upload <file>")
        print(f"         nexus project files")
        print(f"         nexus project forget <filename>\n")
        return

    sub = args[0].lower()

    def _ws_dir(name):
        try:
            return _Path(str(WORKSPACE_DIR)) / name
        except Exception:
            return _Path.home() / "clawos" / "workspace" / name

    def _current_ws():
        marker = _Path.home() / ".local" / "share" / "clawos" / "current_project"
        if marker.exists():
            return marker.read_text().strip()
        return DEFAULT_WORKSPACE

    def _set_current_ws(name):
        marker = _Path.home() / ".local" / "share" / "clawos" / "current_project"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(name)

    if sub == "start":
        if len(args) < 2:
            print(f"\n  Usage: nexus project start <name>\n")
            return
        name = "_".join(args[1:]).replace(" ", "_").lower()
        ws   = _ws_dir(name)
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "uploads").mkdir(exist_ok=True)
        # Ask for one-line description
        print(f"\n  Creating project {_b(PURPLE, name)}")
        try:
            desc = input(f"  Describe this project in one line: ").strip()
        except (EOFError, KeyboardInterrupt):
            desc = ""
        if desc:
            pinned = ws / "PINNED.md"
            existing = pinned.read_text() if pinned.exists() else ""
            if f"Project: {name}" not in existing:
                with open(pinned, "a") as f:
                    f.write(f"\nProject: {name}\nDescription: {desc}\n")
        _set_current_ws(name)
        print(f"  " + _p(GREEN, "✓") + f"  Project {_b(PURPLE, name)} created and active")
        if desc:
            print(f"  {_d('Pinned: ' + desc)}")
        print(f"\n  Upload docs: nexus project upload <file.pdf>\n")

    elif sub == "switch":
        if len(args) < 2:
            print(f"\n  Usage: nexus project switch <name>\n")
            return
        name = args[1]
        ws   = _ws_dir(name)
        if not ws.exists():
            print(f"\n  " + _p(RED, "✗") + f"  Project not found: {name}")
            print(f"  Create it: nexus project start {name}\n")
            return
        _set_current_ws(name)
        print(f"\n  " + _p(GREEN, "✓") + f"  Switched to {_b(PURPLE, name)}\n")

    elif sub == "list":
        try:
            ws_root = _Path(str(WORKSPACE_DIR))
        except Exception:
            ws_root = _Path.home() / "clawos" / "workspace"
        current = _current_ws()
        projects = [d for d in sorted(ws_root.iterdir()) if d.is_dir()] if ws_root.exists() else []
        print()
        if not projects:
            print(f"  {_d('No projects. Create one: nexus project start <name>')}")
        else:
            for p in projects:
                marker = f"  {_p(AMBER, '← active')}" if p.name == current else ""
                files  = list((p / "uploads").glob("*")) if (p / "uploads").exists() else []
                print(f"  {_p(GREEN, '·')}  {_b(PURPLE, p.name):<28} {_d(str(len(files))+' files')}{marker}")
        print()

    elif sub == "upload":
        if len(args) < 2:
            print(f"\n  Usage: nexus project upload <file>\n")
            return
        src  = _Path(args[1])
        if not src.exists():
            print(f"\n  " + _p(RED, "✗") + f"  File not found: {src}\n")
            return
        current = _current_ws()
        ws      = _ws_dir(current)
        dest    = ws / "uploads" / src.name
        import shutil as _shutil
        _shutil.copy2(str(src), str(dest))

        print(f"\n  Ingesting {_b(AMBER, src.name)} into {_b(PURPLE, current)} ...")
        try:
            from services.ragd.service import get_rag
            rag   = get_rag(current, ws)
            stats = rag.ingest(dest)
            if stats.get("skipped"):
                print(f"  {_p(AMBER, '⚠')}  Already indexed: {stats.get('skip_reason', '')}")
            else:
                kept  = stats.get("chunks_kept", 0)
                types = stats.get("chunk_types", {})
                print(f"  " + _p(GREEN, "✓") + f"  {kept} chunks indexed")
                if types:
                    summary = ", ".join(f"{k}={v}" for k, v in sorted(types.items()))
                    print(f"  {_d(summary)}")
        except Exception as e:
            print(f"  {_p(RED, '✗')}  Ingest failed: {e}")
        print()

    elif sub == "files":
        current = _current_ws()
        ws      = _ws_dir(current)
        try:
            from services.ragd.service import get_rag
            rag   = get_rag(current, ws)
            files = rag.list_files()
        except Exception as e:
            print(f"\n  {_p(RED, '✗')}  {e}\n")
            return
        print()
        print(f"  {_b(PURPLE, current)} {_d('— indexed documents')}")
        if not files:
            print(f"  {_d('No documents. Upload with: nexus project upload <file>')}")
        else:
            for f in files:
                print(f"  {_p(GREEN, '·')}  {_b(AMBER, f['title']):<30} "
                      f"{_d(f['type'])}  {_d(str(f['chunks'])+' chunks')}")
        print()

    elif sub == "forget":
        if len(args) < 2:
            print(f"\n  Usage: nexus project forget <filename>\n")
            return
        current  = _current_ws()
        ws       = _ws_dir(current)
        filename = args[1]
        try:
            from services.ragd.service import get_rag
            rag = get_rag(current, ws)
            ok  = rag.forget(filename)
            if ok:
                print(f"\n  " + _p(GREEN, "✓") + f"  Removed {filename} from index\n")
            else:
                print(f"\n  " + _p(RED, "✗") + f"  Not found: {filename}\n")
        except Exception as e:
            print(f"\n  {_p(RED, '✗')}  {e}\n")

    else:
        print(f"\n  Unknown subcommand: {sub}\n")


async def cmd_workflow(args: list):
    """nexus workflow [list|run|info|suggest] [...options]"""
    sub = args[0].lower() if args else "list"

    if sub == "list":
        category = None
        search   = None
        i = 1
        while i < len(args):
            if args[i] in ("--category", "-c") and i + 1 < len(args):
                category = args[i + 1]; i += 2
            elif args[i] in ("--search", "-s") and i + 1 < len(args):
                search = args[i + 1]; i += 2
            else:
                i += 1
        from workflows.engine import get_engine
        eng = get_engine()
        eng.load_registry()
        workflows = eng.list_workflows(category=category, search=search)
        if not workflows:
            print("\n  No workflows found.\n")
            return
        current_cat = None
        print()
        for meta in workflows:
            if meta.category != current_cat:
                current_cat = meta.category
                print(f"  {_p(CYAN, meta.category.upper())}")
            tag = f"  {_p(AMBER, '[destructive]')}" if meta.destructive else ""
            print(f"    {_p(GREEN, meta.id):<40}  {meta.description}{tag}")
        print(f"\n  {len(workflows)} workflows. Run: nexus workflow run <id>\n")

    elif sub == "run":
        if len(args) < 2:
            print("\n  Usage: nexus workflow run <id> [key=value ...]\n")
            return
        workflow_id = args[1]
        wf_args = {}
        for a in args[2:]:
            if "=" in a:
                k, v = a.split("=", 1)
                wf_args[k.strip()] = v.strip()
        from workflows.engine import get_engine
        eng = get_engine()
        eng.load_registry()
        if workflow_id not in eng._registry:
            print(f"\n  Unknown workflow: {workflow_id}")
            print("  Run 'nexus workflow list' to see available workflows.\n")
            return
        meta = eng._registry[workflow_id].META
        print(f"\n  Running: {meta.name}")
        print(f"  {meta.description}")
        print()
        result = await eng.run(workflow_id, wf_args)
        if result.output:
            print(result.output)
        if result.error:
            print(f"\n  {_p(AMBER, 'Error:')} {result.error}")
        ok_color = GREEN if result.status.value == "ok" else AMBER
        print(f"\n  Status: {_p(ok_color, result.status.value)}\n")

    elif sub == "info":
        if len(args) < 2:
            print("\n  Usage: nexus workflow info <id>\n")
            return
        workflow_id = args[1]
        from workflows.engine import get_engine
        eng = get_engine()
        eng.load_registry()
        if workflow_id not in eng._registry:
            print(f"\n  Unknown workflow: {workflow_id}\n")
            return
        meta = eng._registry[workflow_id].META
        print(f"\n  {_p(CYAN, meta.name)}")
        print(f"  ID:          {meta.id}")
        print(f"  Category:    {meta.category}")
        print(f"  Description: {meta.description}")
        print(f"  Tags:        {', '.join(meta.tags) or 'none'}")
        print(f"  Requires:    {', '.join(meta.requires) or 'none'}")
        print(f"  Destructive: {'yes' if meta.destructive else 'no'}")
        print(f"  Timeout:     {meta.timeout_s}s")
        print(f"\n  Run: nexus workflow run {meta.id}\n")

    elif sub == "suggest":
        user_profile = args[1] if len(args) > 1 else ""
        from workflows.discovery import CapabilityScanner
        print("\n  Scanning your machine...")
        scanner     = CapabilityScanner()
        profile     = scanner.scan()
        suggestions = scanner.suggest(profile, user_profile)
        top = suggestions[:5]
        print(f"\n  {_p(CYAN, 'Try these first:')}\n")
        for s in top:
            print(f"  {_p(GREEN, s.workflow_id):<40}  {s.reason}  ({s.relevance:.0%})")
        print(f"\n  Run: nexus workflow run <id>\n")

    else:
        print(f"\n  Usage: nexus workflow [list|run|info|suggest]\n")


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

    elif first == "use-kimi":
        cmd_use_kimi()

    elif first == "scan":
        text = " ".join(argv[1:])
        if not text:
            print(f"\n  Usage: nexus scan <text to check>\n")
        else:
            cmd_scan(text)

    elif first == "secret":
        cmd_secret(argv[1:])

    elif first == "plan":
        spec = " ".join(argv[1:])
        if not spec:
            print("\n  Usage: nexus plan <task description>\n")
        else:
            import asyncio
            from runtimes.agent.runtime import build_runtime
            ws = _active_workspace()
            agent = asyncio.run(build_runtime(ws))
            _run_plan_mode(spec, agent)

    elif first == "command":
        cmd_command(argv[1:])

    elif first == "project":
        cmd_project(argv[1:])

    elif first == "workflow":
        import asyncio
        asyncio.run(cmd_workflow(argv[1:]))

    else:
        # Everything else → natural language shell request
        cmd_do(" ".join(argv))


if __name__ == "__main__":
    main()
