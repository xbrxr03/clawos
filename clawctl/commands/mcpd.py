# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl mcpd — Manage MCP Server Daemon
========================================
Control the ClawOS MCP server that exposes ClawOS capabilities
to external AI assistants via Model Context Protocol.

Usage:
  clawctl mcpd status     Check MCP server status
  clawctl mcpd start      Start MCP server
  clawctl mcpd stop       Stop MCP server
  clawctl mcpd info       Show MCP server info and capabilities

The MCP server runs on port 7077 by default and exposes:
- Tools: clawos_skill_execute, clawos_memory_search, etc.
- Resources: clawos://skills, clawos://workflows, etc.
- Prompts: clawos_daily_briefing, clawos_task_planner
"""
import json
import subprocess
import urllib.request
from pathlib import Path

import click

from clawos_core.constants import PORT_MCPD

MCP_ENDPOINT = f"http://127.0.0.1:{PORT_MCPD}/mcp"
HEALTH_ENDPOINT = f"http://127.0.0.1:{PORT_MCPD}/health"


def _is_running() -> bool:
    """Check if MCP server is running."""
    try:
        req = urllib.request.Request(HEALTH_ENDPOINT, method="GET", timeout=2)
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except:
        return False


def _send_request(method: str, params: dict) -> dict:
    """Send JSON-RPC request to MCP server."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    req = urllib.request.Request(
        MCP_ENDPOINT,
        data=json.dumps(request).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


@click.group(name="mcpd", help="Manage MCP Server Daemon")
def mcpd_group():
    """Manage the ClawOS MCP server."""
    pass


@mcpd_group.command(name="status", help="Check MCP server status")
def mcpd_status():
    """Check if MCP server is running."""
    if _is_running():
        try:
            req = urllib.request.Request(HEALTH_ENDPOINT, method="GET", timeout=2)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                click.echo(f"✓ MCP server is running on port {PORT_MCPD}")
                click.echo(f"  Protocol version: {data.get('protocol_version', 'unknown')}")
                click.echo(f"  Service: {data.get('service', 'unknown')}")
        except Exception as e:
            click.echo(f"⚠ MCP server responded but with error: {e}")
    else:
        click.echo(f"✗ MCP server is not running on port {PORT_MCPD}")
        click.echo(f"  Start with: python3 -m services.mcpd.main")


@mcpd_group.command(name="start", help="Start MCP server")
def mcpd_start():
    """Start the MCP server."""
    if _is_running():
        click.echo("✓ MCP server is already running")
        return
    
    try:
        # Start in background
        subprocess.Popen(
            ["python3", "-m", "services.mcpd.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        click.echo("✓ MCP server starting...")
        click.echo(f"  Check status: clawctl mcpd status")
    except Exception as e:
        click.echo(f"✗ Failed to start MCP server: {e}")


@mcpd_group.command(name="stop", help="Stop MCP server")
def mcpd_stop():
    """Stop the MCP server."""
    if not _is_running():
        click.echo("✓ MCP server is not running")
        return
    
    try:
        # Find and kill the process
        result = subprocess.run(
            ["pkill", "-f", "services.mcpd.main"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            click.echo("✓ MCP server stopped")
        else:
            click.echo("⚠ Could not stop MCP server (may require manual kill)")
    except Exception as e:
        click.echo(f"✗ Error stopping MCP server: {e}")


@mcpd_group.command(name="info", help="Show MCP server capabilities")
def mcpd_info():
    """Show MCP server information and capabilities."""
    if not _is_running():
        click.echo("✗ MCP server is not running")
        click.echo("  Start with: clawctl mcpd start")
        return
    
    try:
        # Get tools
        tools_response = _send_request("tools/list", {})
        tools = tools_response.get("result", {}).get("tools", [])
        
        # Get resources
        resources_response = _send_request("resources/list", {})
        resources = resources_response.get("result", {}).get("resources", [])
        
        # Get prompts
        prompts_response = _send_request("prompts/list", {})
        prompts = prompts_response.get("result", {}).get("prompts", [])
        
        click.echo("\n╔══════════════════════════════════════════════════╗")
        click.echo("║         ClawOS MCP Server Capabilities           ║")
        click.echo("╚══════════════════════════════════════════════════╝\n")
        
        # Tools
        click.echo(f"🔧 Tools ({len(tools)}):")
        for tool in tools:
            click.echo(f"  • {tool['name']}")
            desc = tool.get('description', '')
            if len(desc) > 60:
                desc = desc[:57] + "..."
            click.echo(f"    {desc}")
        
        # Resources
        click.echo(f"\n📚 Resources ({len(resources)}):")
        for resource in resources:
            click.echo(f"  • {resource['uri']}")
            click.echo(f"    {resource.get('name', '')}")
        
        # Prompts
        click.echo(f"\n💬 Prompts ({len(prompts)}):")
        for prompt in prompts:
            click.echo(f"  • {prompt['name']}")
            click.echo(f"    {prompt.get('description', '')}")
        
        click.echo(f"\n📡 Endpoint: {MCP_ENDPOINT}")
        click.echo(f"   Health:   {HEALTH_ENDPOINT}")
        
    except Exception as e:
        click.echo(f"✗ Error querying MCP server: {e}")


@mcpd_group.command(name="test", help="Test MCP server with sample request")
@click.option("--tool", default="clawos_system_info", help="Tool to test")
def mcpd_test(tool):
    """Test MCP server with a sample request."""
    if not _is_running():
        click.echo("✗ MCP server is not running")
        return
    
    try:
        click.echo(f"Testing tool: {tool}")
        
        result = _send_request("tools/call", {
            "name": tool,
            "arguments": {}
        })
        
        if "error" in result:
            click.echo(f"✗ Error: {result['error']}")
        else:
            content = result.get("result", {}).get("content", [])
            for item in content:
                if item.get("type") == "text":
                    click.echo(f"\nResult:\n{item['text']}")
        
    except Exception as e:
        click.echo(f"✗ Test failed: {e}")


@mcpd_group.command(name="clients", help="Show how to connect to ClawOS MCP")
def mcpd_clients():
    """Show connection instructions for various MCP clients."""
    click.echo("\n╔══════════════════════════════════════════════════╗")
    click.echo("║     Connecting to ClawOS MCP Server              ║")
    click.echo("╚══════════════════════════════════════════════════╝\n")
    
    click.echo("📡 Server URL: http://localhost:7077/mcp\n")
    
    click.echo("Claude Desktop Config:")
    click.echo("  Add to claude_desktop_config.json:")
    click.echo("""
  {
    "mcpServers": {
      "clawos": {
        "url": "http://localhost:7077/mcp"
      }
    }
  }
""")
    
    click.echo("Cursor IDE Config:")
    click.echo("  Add to .cursor/mcp.json:")
    click.echo("""
  {
    "servers": [
      {
        "name": "clawos",
        "url": "http://localhost:7077/mcp"
      }
    ]
  }
""")
    
    click.echo("Generic HTTP MCP Client:")
    click.echo(f"  Endpoint: http://localhost:7077/mcp")
    click.echo(f"  Health:   http://localhost:7077/health\n")
    
    click.echo("Available capabilities:")
    click.echo("  • Execute any ClawOS skill")
    click.echo("  • Search and save to memory")
    click.echo("  • Run workflows")
    click.echo("  • Access system information")
