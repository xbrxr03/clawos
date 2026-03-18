"""
clawctl — ClawOS control CLI
==============================
Usage: clawctl <command> [args]

Commands:
  status                    — show all service health
  start  [service]          — start all services or one
  stop   [service]          — stop services
  restart [service]         — restart services
  logs   [service] [-f]     — show logs
  doctor [--fix]            — diagnose and fix issues

  model list                — list installed Ollama models
  model pull <name>         — pull a model
  model remove <name>       — remove a model
  model default <name>      — set default model

  workspace list            — list workspaces
  workspace create <name>   — create a workspace
  workspace delete <name>   — delete a workspace

  voice status              — check voice dependencies
  voice enable              — enable voice (push-to-talk)
  voice disable             — disable voice
  voice test                — test TTS

  whatsapp status           — check WhatsApp link
  whatsapp link             — scan QR to link phone
  whatsapp unlink           — unlink phone
  whatsapp test             — send test message

  openclaw status           — check OpenClaw installation
  openclaw install [model]  — install and configure OpenClaw
  openclaw start            — start OpenClaw gateway
  openclaw stop             — stop OpenClaw gateway
  openclaw config [model]   — regenerate OpenClaw config

  wizard                    — run first-run wizard
  chat                      — start interactive chat (Claw Core)
"""
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import click
    CLICK_OK = True
except ImportError:
    CLICK_OK = False

if not CLICK_OK:
    # Fallback minimal CLI without click
    def main():
        args = sys.argv[1:]
        if not args:
            print(__doc__)
            return
        _dispatch_plain(args)
    def _dispatch_plain(args):
        cmd = args[0]
        sub = args[1] if len(args) > 1 else None
        rest = args[2:] if len(args) > 2 else []
        _run_command(cmd, sub, rest)
else:
    @click.group()
    def main():
        """ClawOS control CLI."""
        pass

    # ── status ────────────────────────────────────────────────────────────────
    @main.command()
    def status():
        """Show all service health."""
        from clawctl.commands.status import run; run()

    # ── start / stop / restart ────────────────────────────────────────────────
    @main.command()
    @click.argument("service", required=False)
    @click.option("--dev", is_flag=True, help="Dev mode (no systemd)")
    def start(service, dev):
        """Start all services or one named service."""
        from clawctl.commands.start import run; run(service, dev)

    @main.command()
    @click.argument("service", required=False)
    def stop(service):
        """Stop services."""
        from clawctl.commands.stop import run; run(service)

    @main.command()
    @click.argument("service", required=False)
    def restart(service):
        """Restart services."""
        from clawctl.commands.stop  import run as s; s(service)
        from clawctl.commands.start import run as t; t(service)

    # ── logs ──────────────────────────────────────────────────────────────────
    @main.command()
    @click.argument("service", required=False)
    @click.option("-f", "--follow", is_flag=True)
    @click.option("-n", "--lines", default=40)
    def logs(service, follow, lines):
        """Tail logs."""
        from clawctl.commands.logs import run; run(service, follow, lines)

    # ── doctor ────────────────────────────────────────────────────────────────
    @main.command()
    @click.option("--fix", is_flag=True, help="Auto-fix safe issues")
    def doctor(fix):
        """Diagnose ClawOS issues."""
        from clawctl.commands.doctor import run; run(fix)

    # ── model ─────────────────────────────────────────────────────────────────
    @main.group()
    def model():
        """Manage Ollama models."""
        pass

    @model.command("list")
    def model_list():
        from clawctl.commands.model import run_list; run_list()

    @model.command("pull")
    @click.argument("name")
    def model_pull(name):
        from clawctl.commands.model import run_pull; run_pull(name)

    @model.command("remove")
    @click.argument("name")
    def model_remove(name):
        from clawctl.commands.model import run_remove; run_remove(name)

    @model.command("default")
    @click.argument("name")
    def model_default(name):
        from clawctl.commands.model import run_set_default; run_set_default(name)

    # ── workspace ─────────────────────────────────────────────────────────────
    @main.group()
    def workspace():
        """Manage workspaces."""
        pass

    @workspace.command("list")
    def ws_list():
        from clawctl.commands.workspace import run_list; run_list()

    @workspace.command("create")
    @click.argument("name")
    def ws_create(name):
        from clawctl.commands.workspace import run_create; run_create(name)

    @workspace.command("delete")
    @click.argument("name")
    def ws_delete(name):
        from clawctl.commands.workspace import run_delete; run_delete(name)

    # ── voice ─────────────────────────────────────────────────────────────────
    @main.group()
    def voice():
        """Manage voice pipeline."""
        pass

    @voice.command("status")
    def voice_status():
        from clawctl.commands.voice import run_status; run_status()

    @voice.command("enable")
    def voice_enable():
        from clawctl.commands.voice import run_enable; run_enable()

    @voice.command("disable")
    def voice_disable():
        from clawctl.commands.voice import run_disable; run_disable()

    @voice.command("test")
    def voice_test():
        from clawctl.commands.voice import run_test; run_test()

    # ── whatsapp ──────────────────────────────────────────────────────────────
    @main.group()
    def whatsapp():
        """Manage WhatsApp gateway."""
        pass

    @whatsapp.command("status")
    def wa_status():
        from clawctl.commands.whatsapp import run_status; run_status()

    @whatsapp.command("link")
    def wa_link():
        from clawctl.commands.whatsapp import run_link; run_link()

    @whatsapp.command("unlink")
    def wa_unlink():
        from clawctl.commands.whatsapp import run_unlink; run_unlink()

    @whatsapp.command("test")
    def wa_test():
        from clawctl.commands.whatsapp import run_test; run_test()

    # ── openclaw ──────────────────────────────────────────────────────────────
    @main.group()
    def openclaw():
        """Manage optional OpenClaw runtime."""
        pass

    @openclaw.command("status")
    def oc_status():
        from clawctl.commands.openclaw import run_status; run_status()

    @openclaw.command("install")
    @click.argument("model", required=False)
    def oc_install(model):
        from clawctl.commands.openclaw import run_install; run_install(model)

    @openclaw.command("start")
    def oc_start():
        from clawctl.commands.openclaw import run_start; run_start()

    @openclaw.command("stop")
    def oc_stop():
        from clawctl.commands.openclaw import run_stop; run_stop()

    @openclaw.command("config")
    @click.argument("model", required=False)
    def oc_config(model):
        from clawctl.commands.openclaw import run_config; run_config(model)

    @openclaw.command("restart")
    def oc_restart():
        from clawctl.commands.openclaw import run_restart; run_restart()

    @openclaw.command("whatsapp")
    def oc_whatsapp():
        """Link WhatsApp via OpenClaw (QR scan)."""
        from clawctl.commands.openclaw import run_whatsapp; run_whatsapp()

    @openclaw.command("onboard")
    def oc_onboard():
        """Run OpenClaw full onboard wizard."""
        from clawctl.commands.openclaw import run_onboard; run_onboard()

    # ── wizard + chat ─────────────────────────────────────────────────────────
    @main.command()
    @click.option("--reset", is_flag=True)
    def wizard(reset):
        """Run first-run setup wizard."""
        from setup.first_run.wizard import run; run(reset=reset)

    @main.command()
    @click.argument("workspace", default="jarvis_default")
    def chat(workspace):
        """Start interactive Jarvis chat."""
        import asyncio
        from clients.cli.repl import run_repl
        asyncio.run(run_repl(workspace))


if __name__ == "__main__":
    main()
