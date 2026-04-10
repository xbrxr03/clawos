# SPDX-License-Identifier: AGPL-3.0-or-later
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

  a2a peers                 — list discovered A2A nodes on LAN
  a2a card                  — print this node's Agent Card
  a2a delegate '<task>' --peer <ip>  — send task to peer node
  a2a status                — check a2ad service

  budget                    — show per-workspace token usage

  wizard                    — run first-run wizard
  chat                      — start Nexus
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

    @voice.command("mode")
    @click.argument("mode", required=False)
    def voice_mode(mode):
        from clawctl.commands.voice import run_mode; run_mode(mode or "")

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

    @main.group()
    def packs():
        """Manage first-party ClawOS packs."""
        pass

    @packs.command("list")
    def packs_list():
        from clawctl.commands.packs import run_list; run_list()

    @packs.command("install")
    @click.argument("pack_id")
    @click.option("--primary", is_flag=True, help="Set as the primary pack")
    @click.option("--provider", default="", help="Optional provider profile to bind")
    def packs_install(pack_id, primary, provider):
        from clawctl.commands.packs import run_install; run_install(pack_id, primary=primary, provider_profile=provider)

    @main.group()
    def providers():
        """Manage provider profiles."""
        pass

    @providers.command("list")
    def providers_list():
        from clawctl.commands.providers import run_list; run_list()

    @providers.command("test")
    @click.argument("profile_id")
    def providers_test(profile_id):
        from clawctl.commands.providers import run_test; run_test(profile_id)

    @providers.command("switch")
    @click.argument("profile_id")
    def providers_switch(profile_id):
        from clawctl.commands.providers import run_switch; run_switch(profile_id)

    @main.group()
    def extensions():
        """Manage trusted ClawOS extensions."""
        pass

    @extensions.command("list")
    def extensions_list():
        from clawctl.commands.extensions import run_list; run_list()

    @extensions.command("install")
    @click.argument("extension_id")
    def extensions_install(extension_id):
        from clawctl.commands.extensions import run_install; run_install(extension_id)

    @main.group()
    def rescue():
        """Import or inspect migration paths."""
        pass

    @rescue.command("openclaw")
    @click.option("--path", "path_hint", default="", help="Optional OpenClaw home path")
    def rescue_openclaw(path_hint):
        from clawctl.commands.rescue import run_openclaw; run_openclaw(path_hint)

    @main.command()
    def benchmark():
        """Show pack eval readiness and trace availability."""
        from clawctl.commands.benchmark import run; run()

    @main.command()
    def briefing():
        """Generate the current Nexus briefing."""
        from clawctl.commands.briefing import run_now; run_now()

    @main.group()
    def mission():
        """Inspect or start Nexus missions."""
        pass

    @mission.command("list")
    def mission_list():
        from clawctl.commands.mission import run_list; run_list()

    @mission.command("start")
    @click.argument("title")
    @click.option("--summary", default="", help="Optional mission summary")
    def mission_start(title, summary):
        from clawctl.commands.mission import run_start; run_start(title, summary)

    @main.group()
    def presence():
        """Inspect Nexus presence and autonomy."""
        pass

    @presence.command("show")
    def presence_show():
        from clawctl.commands.presence import run_show; run_show()

    # ── wizard + chat ─────────────────────────────────────────────────────────
    @main.command()
    @click.option("--reset", is_flag=True)
    def wizard(reset):
        """Run first-run setup wizard."""
        from setup.first_run.wizard import run; run(reset=reset)

    @main.command()
    @click.argument("workspace", default="nexus_default")
    def chat(workspace):
        """Start Nexus."""
        import subprocess, sys
        from pathlib import Path
        root = Path(__file__).parent.parent
        subprocess.run([sys.executable, str(root / "nexus" / "cli.py")],
                       env={**__import__("os").environ, "PYTHONPATH": str(root)})


# ── a2a ───────────────────────────────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def a2a():
        """A2A peer management and task delegation."""
        pass

    @a2a.command("peers")
    def a2a_peers():
        """List discovered ClawOS nodes on LAN."""
        from clawctl.commands.a2a import run_peers; run_peers()

    @a2a.command("card")
    def a2a_card():
        """Print this node Agent Card JSON."""
        from clawctl.commands.a2a import run_card; run_card()

    @a2a.command("delegate")
    @click.argument("task")
    @click.option("--peer", required=True, help="Peer IP address")
    @click.option("--workspace", default="nexus_default")
    def a2a_delegate(task, peer, workspace):
        """Delegate a task to a remote ClawOS node."""
        from clawctl.commands.a2a import run_delegate; run_delegate(task, peer, workspace)

    @a2a.command("status")
    def a2a_status():
        """Check a2ad service status."""
        from clawctl.commands.a2a import run_status; run_status()

    # ── budget ────────────────────────────────────────────────────────────────
    @main.command()
    def budget():
        """Show per-workspace token usage."""
        from clawctl.commands.budget import run; run()


if CLICK_OK:
    @main.group()
    def project():
        """Document ingestion and RAG pipeline."""
        pass

    @project.command("upload")
    @click.argument("filepath")
    @click.option("--workspace", default="nexus_default")
    def project_upload(filepath, workspace):
        """Ingest a document into RAG (pdf, txt, md, docx)."""
        from clawctl.commands.project import run_upload
        run_upload(filepath, workspace)

    @project.command("list")
    @click.option("--workspace", default="nexus_default")
    def project_list(workspace):
        """List indexed documents in workspace."""
        from clawctl.commands.project import run_list
        run_list(workspace)

    @project.command("query")
    @click.argument("question")
    @click.option("--workspace", default="nexus_default")
    def project_query(question, workspace):
        """Query indexed documents with citations."""
        from clawctl.commands.project import run_query
        run_query(question, workspace)

    @project.command("stats")
    @click.option("--workspace", default="nexus_default")
    def project_stats(workspace):
        """Show RAG index stats for workspace."""
        from clawctl.commands.project import run_stats
        run_stats(workspace)

# ── skill marketplace ─────────────────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def skill():
        """Browse and install skills from ClawHub."""
        pass

    @skill.command("search")
    @click.argument("query", default="")
    @click.option("--page", default=1, help="Page number")
    def skill_search(query, page):
        """Search ClawHub for skills."""
        from clawctl.commands.skill import run_search; run_search(query, page)

    @skill.command("install")
    @click.argument("skill_id")
    @click.option("--force", is_flag=True, help="Reinstall if already installed")
    @click.option("--no-community", is_flag=True, help="Reject community (unverified) skills")
    def skill_install(skill_id, force, no_community):
        """Install a skill from ClawHub."""
        from clawctl.commands.skill import run_install
        run_install(skill_id, force=force, allow_community=not no_community)

    @skill.command("remove")
    @click.argument("skill_id")
    def skill_remove(skill_id):
        """Remove an installed skill."""
        from clawctl.commands.skill import run_remove; run_remove(skill_id)

    @skill.command("list")
    def skill_list():
        """List installed skills."""
        from clawctl.commands.skill import run_list; run_list()

    @skill.command("verify")
    @click.argument("skill_path")
    def skill_verify(skill_path):
        """Verify Ed25519 signature of a local skill directory."""
        from clawctl.commands.skill import run_verify; run_verify(skill_path)

    @skill.command("local")
    @click.argument("skill_path")
    @click.option("--id", "skill_id", default="", help="Override skill ID")
    def skill_local(skill_path, skill_id):
        """Install skill from local path (dev mode)."""
        from clawctl.commands.skill import run_local; run_local(skill_path, skill_id)

    @skill.command("sign")
    @click.argument("skill_path")
    def skill_sign(skill_path):
        """Sign a skill with Ed25519 (requires CLAWOS_SIGN_KEY env var)."""
        from clawctl.commands.skill import run_sign; run_sign(skill_path)

# ── license ────────────────────────────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def license():
        """Manage ClawOS Premium license."""
        pass

    @license.command("activate")
    @click.argument("key")
    def license_activate(key):
        """Activate a license key (CLAW-XXXX-XXXX-XXXX-XXXX)."""
        from clawctl.commands.license import run_activate; run_activate(key)

    @license.command("status")
    def license_status():
        """Show current license status."""
        from clawctl.commands.license import run_status; run_status()

    @license.command("deactivate")
    def license_deactivate():
        """Deactivate license on this machine."""
        from clawctl.commands.license import run_deactivate; run_deactivate()


if __name__ == "__main__":
    main()

# ── project ───────────────────────────────────────────────────────────────────
