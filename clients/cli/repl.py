"""
Claw Core — interactive REPL
Demo-ready TUI with colours, typing indicator, clean layout.
"""
import asyncio
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from clawos_core.constants import DEFAULT_WORKSPACE, VERSION_FULL

# ── ANSI colours (graceful fallback if terminal doesn't support) ──────────────
def _supports_colour():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

C = _supports_colour()
RESET  = "\033[0m"      if C else ""
BOLD   = "\033[1m"      if C else ""
DIM    = "\033[2m"      if C else ""
PURPLE = "\033[38;5;141m" if C else ""
GREEN  = "\033[38;5;84m"  if C else ""
AMBER  = "\033[38;5;220m" if C else ""
RED    = "\033[38;5;203m" if C else ""
BLUE   = "\033[38;5;75m"  if C else ""
GREY   = "\033[38;5;245m" if C else ""
CYAN   = "\033[38;5;117m" if C else ""

def _p(colour, text):   return f"{colour}{text}{RESET}"
def _b(colour, text):   return f"{BOLD}{colour}{text}{RESET}"
def _d(text):           return f"{DIM}{GREY}{text}{RESET}"

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
  {_p(CYAN, '/help')}             show this help
  {_p(CYAN, '/quit')}             exit
"""

THINKING_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

def _hr():
    return _d("  " + "─" * 52)

def _tag(label, colour):
    return f"{colour}{BOLD} {label} {RESET}"

def _status_line(workspace: str, model: str, turn: int) -> str:
    return (f"  {_d('ws:')} {_p(AMBER, workspace)}"
            f"  {_d('model:')} {_p(BLUE, model.split(':')[0])}"
            f"  {_d('turn:')} {_p(GREY, str(turn))}")


class ThinkingIndicator:
    def __init__(self):
        self._stop  = False
        self._task  = None

    async def start(self):
        self._stop = False
        self._task = asyncio.create_task(self._spin())

    async def stop(self):
        self._stop = True
        if self._task:
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass
        # Clear the line
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

    from runtimes.agent.runtime import build_runtime
    from services.memd.service   import MemoryService

    # Loading indicator
    print(f"  {_p(AMBER, '◆')} Loading workspace {_b(AMBER, workspace)} ...", end="", flush=True)
    try:
        agent  = await build_runtime(workspace)
        memory = MemoryService()
    except Exception as e:
        print(f"\n\n  {_p(RED, '✗')} Could not start: {_p(RED, str(e))}")
        print(f"  {_d('Make sure Ollama is running: ollama serve')}\n")
        return

    model_name = agent.model
    turn       = 0
    spinner    = ThinkingIndicator()

    print(f"\r  {_p(GREEN, '✓')} Ready  {_d('—')} {_d('type /help for commands')}")
    print(_hr())
    print(_status_line(workspace, model_name, turn))
    print()

    current_ws = workspace

    while True:
        try:
            prompt = f"  {_b(PURPLE, 'you')} {_d('›')} "
            raw = input(prompt).strip()
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

            elif cmd == "/workspace":
                if arg:
                    current_ws = arg
                    print(f"  {_p(AMBER, '◆')} Switching to {_b(AMBER, arg)} ...", end="", flush=True)
                    from runtimes.agent.runtime import build_runtime as br
                    agent = await br(current_ws)
                    turn  = 0
                    print(f"\r  {_p(GREEN, '✓')} Workspace: {_b(AMBER, current_ws)}\n")

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

        # Print reply with nice formatting
        print(f"  {_b(GREEN, 'jarvis')} {_d('›')}", end=" ")
        # Word-wrap at ~70 chars
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
    ws = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WORKSPACE
    asyncio.run(run_repl(ws))


if __name__ == "__main__":
    main()
