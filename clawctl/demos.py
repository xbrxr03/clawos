# SPDX-License-Identifier: AGPL-3.0-or-later
"""Clawctl demos subcommand - run the v1.0 flagship demos."""
import asyncio
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
import httpx

from clawos_core.constants import PORT_REMINDERD, PORT_WAKETRD, PORT_DASHD


@click.group(name="demos")
def demos_cli():
    """Run ClawOS v1.0 flagship demos."""
    pass


@demos_cli.command(name="morning-briefing")
@click.option("--voice/--text", "use_voice", default=True, help="Use voice or text output")
def morning_briefing(use_voice):
    """Trigger the morning briefing (Demo 1)."""
    click.echo("🏠 Morning Briefing")
    click.echo("==================")
    
    try:
        r = httpx.post(f"http://localhost:{PORT_WAKETRD}/trigger", timeout=60.0)
        if r.status_code == 200:
            data = r.json()
            if data.get("triggered"):
                click.echo(f"✅ {data.get('action', 'briefing')}")
                if data.get("text"):
                    click.echo("\n---")
                    click.echo(data["text"])
                    click.echo("---")
            else:
                click.echo(f"⏳ {data.get('reason', 'Not triggered')}")
        else:
            click.echo(f"❌ Error: {r.status_code}")
    except httpx.ConnectError:
        click.echo("❌ waketrd not running. Start with: clawctl services start")
    except httpx.TimeoutError:
        click.echo("⏱️ Timeout (LLM may be slow)")


@demos_cli.command(name="essay-editor")
@click.option("--style", default="engaging", 
              type=click.Choice(["formal", "casual", "academic", "concise", "engaging"]),
              help="Writing style")
@click.option("--text", help="Input text (or reads from clipboard)")
@click.option("--skip-grammar", is_flag=True, help="Skip grammar check")
@click.option("--verbose", is_flag=True, help="Show intermediate steps")
def essay_editor(style, text, skip_grammar, verbose):
    """Grammar check and rewrite text (Demo 2)."""
    click.echo("📝 Essay Editor")
    click.echo("==============")
    
    # Build command
    cmd = [
        sys.executable, 
        "-m", "demos.essay_to_editor",
        "--style", style
    ]
    if text:
        cmd.extend(["--text", text])
    if skip_grammar:
        cmd.append("--skip-grammar")
    if verbose:
        cmd.append("--verbose")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Error: {e}")
        sys.exit(1)


@demos_cli.command(name="approval-test")
def approval_test():
    """Test the approval popup system (Demo 3)."""
    click.echo("🛡️ Approval Popup Test")
    click.echo("=====================")
    
    # Check if Tauri binary exists
    tauri_bin = Path.home() / ".clawos-runtime" / "bin" / "clawos-command-center"
    if not tauri_bin.exists():
        # Try build location
        tauri_bin = Path(__file__).parent.parent / "desktop" / "command-center" / "src-tauri" / "target" / "release" / "clawos-command-center"
    
    if tauri_bin.exists():
        click.echo(f"✅ Tauri binary found: {tauri_bin}")
        click.echo("\nTo test approval popup:")
        click.echo("1. Run: clawos-command-center (opens main window)")
        click.echo("2. In another terminal: clawos")
        click.echo("3. Type: 'delete all files in ~/Downloads'")
        click.echo("4. Approval popup should appear as floating window")
    else:
        click.echo("⚠️ Tauri binary not found")
        click.echo("Build with: cd desktop/command-center && cargo tauri build")
    
    # Also check if any approvals are pending via API (may need auth)
    try:
        r = httpx.get(f"http://localhost:{PORT_DASHD}/api/approvals", timeout=2.0)
        if r.status_code == 200:
            data = r.json()
            approvals = data.get("approvals", [])
            if approvals:
                click.echo(f"\n📝 Found {len(approvals)} pending approval(s):")
                for a in approvals:
                    click.echo(f"  - {a.get('tool')}: {a.get('target', 'N/A')}")
    except Exception:
        pass  # Auth or connection error, ignore


@demos_cli.command(name="list")
def list_demos():
    """List all available demos."""
    click.echo("🎬 ClawOS v1.0 Demos")
    click.echo("===================\n")
    
    demos = [
        ("morning-briefing", "Say 'Hey JARVIS' → Get spoken briefing"),
        ("essay-editor", "Clipboard → Grammar → Rewrite → Paste"),
        ("approval-test", "Test the approval popup system"),
    ]
    
    for name, desc in demos:
        click.echo(f"  clawctl demos {name:20} {desc}")
    
    click.echo("\nRun 'clawctl demos <name> --help' for options")


# Alias commands for convenience
@click.command(name="briefing")
def briefing_cmd():
    """Alias for 'demos morning-briefing'."""
    morning_briefing.callback(use_voice=True)


@click.command(name="rewrite")
@click.option("--style", default="engaging")
@click.argument("text", required=False)
def rewrite_cmd(style, text):
    """Alias for 'demos essay-editor'."""
    essay_editor.callback(style=style, text=text, skip_grammar=False, verbose=False)
