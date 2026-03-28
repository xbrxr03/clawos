"""
Nexus — interactive REPL
Demo-ready TUI with colours, typing indicator, clean layout.
"""
import asyncio
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from clawos_core.constants import DEFAULT_WORKSPACE, VERSION_FULL

# ── ANSI colours ──────────────────────────────────────────────────────────────
def _supports_colour():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

C = _supports_colour()
RESET  = "\033[0m"        if C else ""
BOLD   = "\033[1m"        if C else ""
DIM    = "\033[2m"        if C else ""
PURPLE = "\033[38;5;141m" if C else ""
GREEN  = "\033[38;5;84m"  if C else ""
AMBER  = "\033[38;5;220m" if C else ""
RED    = "\033[38;5;203m" if C else ""
BLUE   = "\033[38;5;75m"  if C else ""
GREY   = "\033[38;5;245m" if C else ""
CYAN   = "\033[38;5;117m" if C else ""

def _p(colour, text):  return f"{colour}{text}{RESET}"
def _b(colour, text):  return f"{BOLD}{colour}{text}{RESET}"
def _d(text):          return f"{DIM}{GREY}{text}{RESET}"

BANNER = f"""
{PURPLE}{BOLD}  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝{RESET}
  {_d('v' + VERSION_FULL)} {_d('·')} {_d('local')} {_d('·')} {_d('offline')} {_d('·')} {_d('private')}
  {_d('─' * 50)}
"""

HELP = f"""
  {_b(PURPLE, 'Commands')}

  {_p(CYAN, '/pin')} {_d('<fact>')}      pin a permanent fact
  {_p(CYAN, '/memory')}           show recalled memories
  {_p(CYAN, '/reset')}            clear conversation history
  {_p(CYAN, '/status')}           model + service health
  {_p(CYAN, '/workspace')} {_d('<w>')}   switch workspace
  {_p(CYAN, '/forget')} {_d('<id>')}     delete a memory
  {_p(CYAN, '/skills')}           list loaded skills
  {_p(CYAN, '/skills reload')}    rescan skill directories
  {_p(CYAN, '/do')} {_d('<request>')}    natural language shell command
  {_p(CYAN, '/setup')}            re-run first-run wizard
  {_p(CYAN, '/help')}             show this help
  {_p(CYAN, '/quit')}             exit
"""

THINKING_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

def _hr():
    return _d("  " + "─" * 52)

def _status_line(workspace: str, model: str, turn: int) -> str:
    return (f"  {_d('ws:')} {_p(AMBER, workspace)}"
            f"  {_d('model:')} {_p(BLUE, model.split(':')[0])}"
            f"  {_d('turn:')} {_p(GREY, str(turn))}")


def _resolve_workspace(arg: str) -> str:
    """
    Determine the active workspace.
    Priority: explicit CLI arg > clawos.yaml workspace.default > DEFAULT_WORKSPACE.
    Filters out wizard flags (--reset, --from) that must never be workspace names.
    """
    WIZARD_FLAGS = {"--reset", "--from", "--help", "-h"}

    if arg and arg not in WIZARD_FLAGS and not arg.startswith("--"):
        return arg

    # Read from clawos.yaml
    try:
        from clawos_core.constants import CLAWOS_CONFIG
        if CLAWOS_CONFIG.exists():
            try:
                import yaml
                cfg = yaml.safe_load(CLAWOS_CONFIG.read_text()) or {}
                ws = cfg.get("workspace", {}).get("default", "")
                if ws and ws.strip():
                    return ws.strip()
            except Exception:
                for line in CLAWOS_CONFIG.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("default:"):
                        val = line.split(":", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
    except Exception:
        pass

    return DEFAULT_WORKSPACE


class ThinkingIndicator:
    def __init__(self):
        self._stop = False
        self._task = None

    async def start(self):
        self._stop = False
        self._task = asyncio.create_task(self._spin())

    async def stop(self):
        self._stop = True
        if self._task:
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass
        sys.stdout.write("\r" + " " * 30 + "\r")
        sys.stdout.flush()

    async def _spin(self):
        i = 0
        while not self._stop:
            frame = THINKING_FRAMES[i % len(THINKING_FRAMES)]
            sys.stdout.write(f"\r  {_p(PURPLE, frame)} {_d('thinking...')}")
            sys.stdout.flush()
            i += 1
            await asyncio.sleep(0.08)


async def run_repl(workspace: str = DEFAULT_WORKSPACE):
    print(BANNER)

    from runtimes.agent.runtime  import build_runtime
    from services.memd.service   import MemoryService
    from services.skilld.service import get_loader, reload_skills

    print(f"  {_p(AMBER, '◆')} Loading workspace {_b(AMBER, workspace)} ...", end="", flush=True)
    try:
        agent  = await build_runtime(workspace)
        memory = MemoryService()
    except Exception as e:
        print(f"\n\n  {_p(RED, '✗')} Could not start: {_p(RED, str(e))}")
        print(f"  {_d('Make sure Ollama is running: ollama serve')}\n")
        return

    skills     = get_loader()
    model_name = agent.model
    turn       = 0
    spinner    = ThinkingIndicator()

    skill_count = skills.count
    skill_hint  = (f" {_d('·')} {_p(CYAN, str(skill_count))} {_d('skill' + ('' if skill_count == 1 else 's') + ' loaded')}"
                   if skill_count else "")

    print(f"\r  {_p(GREEN, '✓')} Ready  {_d('—')} {_d('type /help for commands')}{skill_hint}")
    print(_hr())
    print(_status_line(workspace, model_name, turn))
    print()

    current_ws = workspace

    while True:
        try:
            raw = input(f"  {_b(PURPLE, 'you')} {_d('›')} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  {_p(GREEN, '◆')} Goodbye.\n")
            break

        if not raw:
            continue

        # ── Slash commands ────────────────────────────────────────────────────
        if raw.startswith("/"):
            parts = raw.split(None, 1)
            cmd   = parts[0].lower()
            arg   = parts[1] if len(parts) > 1 else ""

            if cmd == "/quit":
                print(f"\n  {_p(GREEN, '◆')} Goodbye.\n")
                break

            elif cmd == "/help":
                print(HELP)

            elif cmd == "/reset":
                await agent.reset()
                turn = 0
                print(f"  {_p(GREEN, '✓')} Conversation cleared.\n")

            elif cmd == "/memory":
                mems = memory.recall("recent", current_ws)
                if mems:
                    print(f"\n  {_b(PURPLE, 'Memory')}")
                    for m in mems[:8]:
                        print(f"  {_p(GREY, '·')} {_d(m[:110])}")
                    print()
                else:
                    print(f"  {_d('No memories yet.')}\n")

            elif cmd == "/pin":
                if arg:
                    memory.append_pinned(current_ws, arg)
                    print(f"  {_p(GREEN, '◈')} Pinned: {_p(AMBER, arg)}\n")
                else:
                    print(f"  {_d('Usage: /pin <fact>')}\n")

            elif cmd == "/forget":
                if arg:
                    memory.forget(arg, current_ws)
                    print(f"  {_p(AMBER, '◌')} Forgotten: {_d(arg)}\n")


            elif cmd == "/plan":
                if arg:
                    try:
                        from nexus.cli import _run_plan_mode
                        _run_plan_mode(arg, agent)
                    except Exception as e:
                        print(f"  plan error: {e}\n")
                else:
                    print("  Usage: /plan <task description>\n")
            elif cmd == "/do":
                if arg:
                    from tools.shell.do.cli import run as _do_run
                    # Split arg into argv-style list preserving flags
                    import shlex
                    try:
                        _do_run(shlex.split(arg))
                    except Exception as _e:
                        print(f"  {_d(str(_e))}\n")
                else:
                    print(f"  {_d('Usage: /do <request> [--dry] [--yes] [--history] [--undo] [--explain] [--step]')}\n")

            elif cmd == "/setup":
                import subprocess
                wizard = Path(__file__).parent.parent.parent / "setup" / "first_run" / "wizard.py"
                if wizard.exists():
                    print(f"  {_p(AMBER, '◆')} Launching setup wizard ...\n")
                    subprocess.run(["python3", str(wizard), "--reset"])
                else:
                    print(f"  {_d('Wizard not found at')} {wizard}\n")

            elif cmd == "/workspace":
                if arg:
                    current_ws = arg
                    print(f"  {_p(AMBER, '◆')} Switching to {_b(AMBER, arg)} ...", end="", flush=True)
                    from runtimes.agent.runtime import build_runtime as br
                    agent = await br(current_ws)
                    turn  = 0
                    print(f"\r  {_p(GREEN, '✓')} Workspace: {_b(AMBER, current_ws)}\n")
                else:
                    print(f"  {_d('Current workspace:')} {_p(AMBER, current_ws)}\n")

            elif cmd == "/status":
                from services.modeld.ollama_client import is_running, list_models
                running = is_running()
                models  = [m.get("name","?") for m in list_models()]
                print(f"\n  {_b(PURPLE, 'Status')}")
                icon = _p(GREEN, '✓') if running else _p(RED, '✗')
                print(f"  {icon} Ollama:    {'running' if running else 'not running'}")
                print(f"  {_p(BLUE, '◆')} Models:    {_p(AMBER, ', '.join(models) or 'none')}")
                print(f"  {_p(BLUE, '◆')} Workspace: {_p(AMBER, current_ws)}")
                print(f"  {_p(BLUE, '◆')} Turn:      {_d(str(turn))}")
                print()

            elif cmd == "/skills":
                if arg.strip().lower() == "reload":
                    n = reload_skills()
                    skills = get_loader()
                    print(f"  {_p(GREEN, '✓')} Reloaded — {_p(CYAN, str(n))} skills found.\n")
                else:
                    skill_list = skills.list_all()
                    if not skill_list:
                        print(f"\n  {_d('No skills loaded.')}")
                        print(f"  {_d('Add SKILL.md packages to ~/.claw/skills/ or ~/.openclaw/skills/')}\n")
                    else:
                        print(f"\n  {_b(PURPLE, 'Skills')}  {_d(str(len(skill_list)) + ' loaded')}\n")
                        for s in skill_list:
                            pin_tag = f" {_p(AMBER, '[pinned]')}" if s["pinned"] else ""
                            src_tag = _d(f"({s['source']})")
                            print(f"  {_p(CYAN, '◆')} {_b(PURPLE, s['name'])}{pin_tag}  {src_tag}")
                            if s["description"]:
                                print(f"    {_d(s['description'][:80])}")
                            if s["triggers"]:
                                print(f"    {_d('triggers: ' + ', '.join(s['triggers'][:5]))}")
                        print()

            else:
                print(f"  {_p(RED, '?')} Unknown: {_d(cmd)}  {_d('(type /help)')}\n")
            continue

        # ── Chat ──────────────────────────────────────────────────────────────
        turn += 1
        await spinner.start()
        t0 = time.time()
        try:
            reply = await agent.chat(raw)
        except Exception as e:
            await spinner.stop()
            print(f"  {_p(RED, '✗')} {_p(RED, str(e))}\n")
            continue

        elapsed = time.time() - t0
        await spinner.stop()

        # Emit task event to dashboard event bus
        try:
            from clawos_core.events.bus import get_bus
            import asyncio as _asyncio
            _asyncio.create_task(get_bus().emit_task(
                f"repl-{turn}", "completed", raw[:80]
            ))
        except Exception:
            pass

        print(f"  {_b(GREEN, 'nexus')} {_d('›')}", end=" ")
        words = reply.split()
        line  = ""
        first = True
        for word in words:
            if len(line) + len(word) + 1 > 68:
                print(line)
                line = ("           " if not first else "") + word
                first = False
            else:
                line = (line + " " + word).strip() if line else word
        if line:
            print(line)

        print(f"\n  {_d('─' * 52)}")
        print(_status_line(current_ws, model_name, turn)
              + f"  {_d(str(round(elapsed, 1)) + 's')}")
        print()


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    workspace = _resolve_workspace(arg)
    asyncio.run(run_repl(workspace))


if __name__ == "__main__":
    main()
