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

  framework install openclaw — install OpenClaw via the Framework Store
  framework start openclaw  — start OpenClaw gateway
  framework status          — show all framework statuses

  a2a peers                 — list discovered A2A nodes on LAN
  a2a card                  — print this node's Agent Card
  a2a delegate '<task>' --peer <ip>  — send task to peer node
  a2a status                — check a2ad service

  budget                    — show per-workspace token usage

  wf list [--category <c>] [--search <q>]  — list workflows
  wf info <id>              — show workflow details
  wf run <id> [key=value …] [--dry-run]   — run a workflow

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
    @click.option("--reset", is_flag=True, help="Clear persisted wizard state before opening")
    def wizard(reset):
        """Open the browser-based first-run setup wizard.
        The legacy TUI wizard was removed — setup now lives in the Command Center
        at http://localhost:7070/setup (launched automatically by install.sh).
        """
        import webbrowser
        if reset:
            try:
                from clawos_core.constants import SETUP_STATE_JSON
                if SETUP_STATE_JSON.exists():
                    SETUP_STATE_JSON.unlink()
                    click.echo(f"Cleared {SETUP_STATE_JSON}")
            except Exception as exc:
                click.echo(f"Could not clear setup state: {exc}", err=True)
        url = "http://localhost:7070/setup"
        click.echo(f"Opening {url} — make sure dashd is running (bash scripts/dev_boot.sh).")
        try:
            webbrowser.open(url)
        except Exception:
            pass

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


# ── framework store ───────────────────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def framework():
        """Browse and manage AI agent frameworks from the Framework Store."""
        pass

    @framework.command("list")
    def framework_list():
        """List all available frameworks with install status."""
        from clawctl.commands.framework import run_list; run_list()

    @framework.command("install")
    @click.argument("name")
    def framework_install(name):
        """Install a framework from the store."""
        from clawctl.commands.framework import run_install; run_install(name)

    @framework.command("remove")
    @click.argument("name")
    def framework_remove(name):
        """Remove an installed framework."""
        from clawctl.commands.framework import run_remove; run_remove(name)

    @framework.command("start")
    @click.argument("name")
    def framework_start(name):
        """Start an installed framework's systemd service."""
        from clawctl.commands.framework import run_start; run_start(name)

    @framework.command("stop")
    @click.argument("name")
    def framework_stop(name):
        """Stop a running framework."""
        from clawctl.commands.framework import run_stop; run_stop(name)

    @framework.command("use")
    @click.argument("name")
    def framework_use(name):
        """Set the active framework for agent routing."""
        from clawctl.commands.framework import run_use; run_use(name)

    @framework.command("status")
    def framework_status():
        """Show status of all installed frameworks."""
        from clawctl.commands.framework import run_status; run_status()

# ── omi (ambient AI integration) ──────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def omi():
        """OMI ambient AI integration (BasedHardware)."""
        pass

    @omi.command("status")
    def omi_status():
        """Show webhook URL, last event, conversation count."""
        from clawctl.commands.omi import run_status; run_status()

    @omi.command("history")
    @click.option("-n", "--limit", default=20, help="Number of conversations to show")
    def omi_history(limit):
        """List recent OMI conversations from archive."""
        from clawctl.commands.omi import run_history; run_history(limit)

    @omi.command("show")
    @click.argument("conv_id")
    def omi_show(conv_id):
        """Show full conversation detail."""
        from clawctl.commands.omi import run_show; run_show(conv_id)

    @omi.command("setup")
    def omi_setup():
        """Print webhook URLs to paste into OMI app settings."""
        from clawctl.commands.omi import run_setup; run_setup()


# ── ace (self-improving loop) ──────────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def ace():
        """Inspect and control the ACE self-improving loop (LEARNED.md)."""
        pass

    @ace.command("status")
    @click.option("--workspace", default="nexus_default")
    def ace_status(workspace):
        """Show LEARNED.md size, entry count, last write timestamp."""
        from clawctl.commands.ace import run_status; run_status(workspace)

    @ace.command("show")
    @click.option("--workspace", default="nexus_default")
    def ace_show(workspace):
        """Print current LEARNED.md content."""
        from clawctl.commands.ace import run_show; run_show(workspace)

    @ace.command("clear")
    @click.option("--workspace", default="nexus_default")
    @click.option("--yes", is_flag=True, help="Skip confirmation")
    def ace_clear(workspace, yes):
        """Truncate LEARNED.md (irreversible)."""
        from clawctl.commands.ace import run_clear; run_clear(workspace, confirm=not yes)

    @ace.command("pause")
    @click.option("--workspace", default="nexus_default")
    def ace_pause(workspace):
        """Stop writing new entries to LEARNED.md."""
        from clawctl.commands.ace import run_pause; run_pause(workspace)

    @ace.command("resume")
    @click.option("--workspace", default="nexus_default")
    def ace_resume(workspace):
        """Resume writing entries to LEARNED.md."""
        from clawctl.commands.ace import run_resume; run_resume(workspace)


# ── wf (workflows) ────────────────────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def wf():
        """List and run built-in ClawOS workflows."""
        pass

    @wf.command("list")
    @click.option("--category", "-c", default=None, help="Filter by category (files, documents, developer, …)")
    @click.option("--search", "-s", default=None, help="Full-text search across name, description, tags")
    def wf_list(category, search):
        """List all available workflows."""
        from clawctl.commands.workflow import run_list
        run_list(category=category, search=search)

    @wf.command("info")
    @click.argument("workflow_id")
    def wf_info(workflow_id):
        """Show details for a single workflow."""
        from clawctl.commands.workflow import run_info
        run_info(workflow_id)

    @wf.command("run")
    @click.argument("workflow_id")
    @click.argument("kvpairs", nargs=-1, metavar="[key=value ...]")
    @click.option("--workspace", "-w", default="nexus_default", help="Workspace ID")
    @click.option("--dry-run", is_flag=True, help="Preview actions without making changes")
    def wf_run(workflow_id, kvpairs, workspace, dry_run):
        """Run a workflow. Pass arguments as key=value pairs."""
        from clawctl.commands.workflow import run_run
        run_run(workflow_id, list(kvpairs), workspace=workspace, dry_run=dry_run)


# ── mcp (Model Context Protocol) ────────────────────────────────────────────
if CLICK_OK:
    @main.group()
    def mcp():
        """Manage MCP (Model Context Protocol) servers."""
        pass

    @mcp.command("init")
    def mcp_init():
        """Create default MCP configuration."""
        from clawctl.commands.mcp import mcp_init as run_init
        run_init()

    @mcp.command("list")
    def mcp_list():
        """List configured MCP servers."""
        from clawctl.commands.mcp import mcp_list as run_list
        run_list()

    @mcp.command("add")
    @click.argument("name")
    @click.option("--stdio", "stdio_cmd", help="stdio command")
    @click.option("--http", "http_url", help="HTTP endpoint URL")
    @click.option("--env", "env_vars", multiple=True, help="Environment variables")
    def mcp_add(name, stdio_cmd, http_url, env_vars):
        """Add an MCP server."""
        from clawctl.commands.mcp import mcp_add as run_add
        run_add(name, stdio_cmd, http_url, env_vars)

    @mcp.command("remove")
    @click.argument("name")
    def mcp_remove(name):
        """Remove an MCP server."""
        from clawctl.commands.mcp import mcp_remove as run_remove
        run_remove(name)

    @mcp.command("test")
    @click.argument("name")
    def mcp_test(name):
        """Test connection to MCP server."""
        from clawctl.commands.mcp import mcp_test as run_test
        run_test(name)

    @mcp.command("discover")
    def mcp_discover():
        """Discover available MCP servers."""
        from clawctl.commands.mcp import mcp_discover as run_discover
        run_discover()

    @mcp.command("template")
    @click.argument("template_name", required=False)
    def mcp_template(template_name):
        """Show MCP server templates."""
        from clawctl.commands.mcp import mcp_template as run_template
        run_template(template_name)

    # ── mcpd (MCP Server Daemon) ─────────────────────────────────────────────
    @main.group()
    def mcpd():
        """Manage ClawOS MCP Server (exposes ClawOS to external AI)."""
        pass

    @mcpd.command("status")
    def mcpd_status():
        """Check MCP server status."""
        from clawctl.commands.mcpd import mcpd_status as run_status
        run_status()

    @mcpd.command("start")
    def mcpd_start():
        """Start the MCP server."""
        from clawctl.commands.mcpd import mcpd_start as run_start
        run_start()

    @mcpd.command("stop")
    def mcpd_stop():
        """Stop the MCP server."""
        from clawctl.commands.mcpd import mcpd_stop as run_stop
        run_stop()

    @mcpd.command("info")
    def mcpd_info():
        """Show MCP server capabilities."""
        from clawctl.commands.mcpd import mcpd_info as run_info
        run_info()

    @mcpd.command("test")
    @click.option("--tool", default="clawos_system_info", help="Tool to test")
    def mcpd_test(tool):
        """Test MCP server with sample request."""
        from clawctl.commands.mcpd import mcpd_test as run_test
        run_test(tool)

    @mcpd.command("clients")
    def mcpd_clients():
        """Show connection instructions for MCP clients."""
        from clawctl.commands.mcpd import mcpd_clients as run_clients
        run_clients()

    # ── observ (Observability) ─────────────────────────────────────────────
    @main.group()
    def observ():
        """Observability and tracing for LLM calls, costs, latency."""
        pass

    @observ.command("status")
    def observ_status():
        """Check observability service status."""
        from clawctl.commands.observ import observ_status as run_status
        run_status()

    @observ.command("calls")
    @click.option("--workspace", "-w", help="Filter by workspace")
    @click.option("--service", "-s", help="Filter by service")
    @click.option("--model", "-m", help="Filter by model")
    @click.option("--hours", "-h", default=24, help="Time window in hours")
    @click.option("--limit", "-l", default=20, help="Number of calls")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def observ_calls(workspace, service, model, hours, limit, as_json):
        """Show recent LLM calls."""
        from clawctl.commands.observ import observ_calls as run_calls
        run_calls(workspace, service, model, hours, limit, as_json)

    @observ.command("stats")
    @click.option("--workspace", "-w", help="Filter by workspace")
    @click.option("--hours", "-h", default=24, help="Time window in hours")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def observ_stats(workspace, hours, as_json):
        """Show aggregate statistics."""
        from clawctl.commands.observ import observ_stats as run_stats
        run_stats(workspace, hours, as_json)

    @observ.command("cost")
    @click.option("--workspace", "-w", help="Filter by workspace")
    @click.option("--days", "-d", default=7, help="Time window in days")
    def observ_cost(workspace, days):
        """Show cost breakdown."""
        from clawctl.commands.observ import observ_cost as run_cost
        run_cost(workspace, days)

    @observ.command("latency")
    @click.option("--workspace", "-w", help="Filter by workspace")
    @click.option("--hours", "-h", default=24, help="Time window in hours")
    def observ_latency(workspace, hours):
        """Show latency analysis."""
        from clawctl.commands.observ import observ_latency as run_latency
        run_latency(workspace, hours)

    @observ.command("workspaces")
    def observ_workspaces():
        """List workspaces with activity."""
        from clawctl.commands.observ import observ_workspaces as run_workspaces
        run_workspaces()

    @observ.command("export")
    @click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json")
    @click.option("--output", "-o", help="Output file")
    @click.option("--hours", "-h", default=168, help="Time window in hours")
    @click.option("--workspace", "-w", help="Filter by workspace")
    def observ_export(fmt, output, hours, workspace):
        """Export observability data."""
        from clawctl.commands.observ import observ_export as run_export
        run_export(fmt, output, hours, workspace)

    # ── durable (Durable Workflows) ──────────────────────────────────────────
    @main.group()
    def durable():
        """Durable workflow management with checkpoint/resume."""
        pass

    @durable.command("runs")
    @click.option("--workflow", "-w", help="Filter by workflow ID")
    @click.option("--status", "-s", type=click.Choice(["pending", "running", "completed", "failed", "cancelled"]))
    @click.option("--limit", "-l", default=20, help="Number of runs")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def durable_runs(workflow, status, limit, as_json):
        """List workflow runs."""
        from clawctl.commands.durable import durable_runs as run_runs
        run_runs(workflow, status, limit, as_json)

    @durable.command("show")
    @click.argument("run_id")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def durable_show(run_id, as_json):
        """Show run details."""
        from clawctl.commands.durable import durable_show as run_show
        run_show(run_id, as_json)

    @durable.command("resume")
    @click.argument("run_id")
    def durable_resume(run_id):
        """Resume a workflow run."""
        from clawctl.commands.durable import durable_resume as run_resume
        run_resume(run_id)

    @durable.command("cancel")
    @click.argument("run_id")
    def durable_cancel(run_id):
        """Cancel a running workflow."""
        from clawctl.commands.durable import durable_cancel as run_cancel
        run_cancel(run_id)

    @durable.command("stats")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def durable_stats(as_json):
        """Show workflow statistics."""
        from clawctl.commands.durable import durable_stats as run_stats
        run_stats(as_json)

    @durable.command("cleanup")
    @click.option("--days", "-d", default=30, help="Delete runs older than N days")
    @click.option("--yes", is_flag=True, help="Skip confirmation")
    def durable_cleanup(days, yes):
        """Clean up old workflow runs."""
        from clawctl.commands.durable import durable_cleanup as run_cleanup
        run_cleanup(days, yes)

    # ── code (Code Companion) ───────────────────────────────────────────────
    @main.group()
    def code():
        """Code companion - developer AI assistant with LSP integration."""
        pass

    @code.command("index")
    @click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
    @click.option("--workspace", "-w", default="code_default", help="Workspace name")
    @click.option("--verbose", "-v", is_flag=True, help="Show progress")
    def code_index(path, workspace, verbose):
        """Index a codebase for semantic search."""
        from clawctl.commands.code import code_index as run_index
        run_index(path, workspace, verbose)

    @code.command("search")
    @click.argument("query")
    @click.option("--workspace", "-w", default="code_default", help="Workspace name")
    @click.option("--limit", "-l", default=10, help="Number of results")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def code_search(query, workspace, limit, as_json):
        """Search codebase using semantic search."""
        from clawctl.commands.code import code_search as run_search
        run_search(query, workspace, limit, as_json)

    @code.command("explain")
    @click.argument("location")
    @click.option("--workspace", "-w", default="code_default", help="Workspace name")
    def code_explain(location, workspace):
        """Explain code at location (file:line)."""
        from clawctl.commands.code import code_explain as run_explain
        run_explain(location, workspace)

    @code.command("review")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def code_review(file_path, as_json):
        """Review code for issues."""
        from clawctl.commands.code import code_review as run_review
        run_review(file_path, as_json)

    @code.command("test")
    @click.argument("symbol")
    @click.option("--file", "-f", required=True, help="File containing symbol")
    @click.option("--workspace", "-w", default="code_default", help="Workspace name")
    def code_test(symbol, file, workspace):
        """Generate test cases."""
        from clawctl.commands.code import code_test as run_test
        run_test(symbol, file, workspace)

    @code.command("status")
    @click.option("--workspace", "-w", default="code_default", help="Workspace name")
    def code_status(workspace):
        """Show code companion status."""
        from clawctl.commands.code import code_status as run_status
        run_status(workspace)


if __name__ == "__main__":
    main()
