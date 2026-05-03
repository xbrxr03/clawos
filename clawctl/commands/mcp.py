# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl mcp — Manage MCP (Model Context Protocol) servers
=========================================================
MCP is the "USB-C for AI agents" - universal protocol for tools and resources.

Usage:
  clawctl mcp list              List configured MCP servers
  clawctl mcp add <name>        Add an MCP server
  clawctl mcp remove <name>     Remove an MCP server
  clawctl mcp discover          Auto-discover MCP servers
  clawctl mcp test <name>       Test connection to MCP server
  clawctl mcp init              Create default MCP configuration

Examples:
  clawctl mcp init
  clawctl mcp add filesystem --stdio "npx -y @modelcontextprotocol/server-filesystem ~"
  clawctl mcp add github --stdio "npx -y @modelcontextprotocol/server-github" --env GITHUB_TOKEN=xxx
  clawctl mcp test filesystem
"""
import json
import subprocess
from pathlib import Path

import click

from clawos_core.constants import CLAWOS_DIR

CONFIG_PATH = Path.home() / ".clawos-runtime" / "config" / "mcp.json"

DEFAULT_SERVERS = {
    "filesystem": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(Path.home())]
    },
    "github": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""}
    },
    "fetch": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-fetch"]
    },
    "puppeteer": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-puppeteer"]
    },
    "sqlite": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-sqlite", str(Path.home() / ".clawos-runtime" / "memory.db")]
    }
}


def load_config():
    """Load MCP configuration."""
    if not CONFIG_PATH.exists():
        return {"servers": {}, "settings": {"auto_discover": True}}
    
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        click.echo(f"Error loading config: {e}")
        return {"servers": {}, "settings": {"auto_discover": True}}


def save_config(config):
    """Save MCP configuration."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


@click.group(name="mcp", help="Manage MCP (Model Context Protocol) servers")
def mcp_group():
    """Manage MCP servers for connecting to external tools and resources."""
    pass


@mcp_group.command(name="init", help="Create default MCP configuration")
def mcp_init():
    """Initialize MCP with default server configurations."""
    if CONFIG_PATH.exists():
        click.confirm("MCP config already exists. Overwrite?", abort=True)
    
    config = {
        "servers": DEFAULT_SERVERS,
        "settings": {
            "auto_discover": True,
            "max_concurrent": 5
        }
    }
    
    save_config(config)
    click.echo(f"✓ Created MCP config at {CONFIG_PATH}")
    click.echo(f"✓ Added {len(DEFAULT_SERVERS)} default servers:")
    for name in DEFAULT_SERVERS:
        click.echo(f"  - {name}")
    click.echo("\nTo activate, restart ClawOS or run: clawctl mcp test <name>")


@mcp_group.command(name="list", help="List configured MCP servers")
def mcp_list():
    """List all configured MCP servers."""
    config = load_config()
    servers = config.get("servers", {})
    
    if not servers:
        click.echo("No MCP servers configured. Run: clawctl mcp init")
        return
    
    click.echo(f"\n{'Name':<20} {'Transport':<10} {'Status':<15}")
    click.echo("-" * 50)
    
    for name, server_config in servers.items():
        transport = server_config.get("transport", "stdio")
        cmd = server_config.get("command", [])
        cmd_str = cmd[0] if cmd else "unknown"
        
        # Quick status check
        status = "configured"
        if transport == "stdio" and cmd_str == "npx":
            # Check if npx is available
            try:
                subprocess.run(["which", "npx"], capture_output=True, check=True)
                status = "ready"
            except:
                status = "needs npx"
        
        click.echo(f"{name:<20} {transport:<10} {status:<15}")
    
    click.echo(f"\nTotal: {len(servers)} servers configured")


@mcp_group.command(name="add", help="Add an MCP server")
@click.argument("name")
@click.option("--stdio", "stdio_cmd", help="stdio command (e.g., 'npx -y @modelcontextprotocol/server-filesystem ~')")
@click.option("--http", "http_url", help="HTTP endpoint URL")
@click.option("--env", "env_vars", multiple=True, help="Environment variables (KEY=value)")
def mcp_add(name, stdio_cmd, http_url, env_vars):
    """Add a new MCP server configuration."""
    config = load_config()
    
    if name in config["servers"]:
        click.confirm(f"Server '{name}' already exists. Overwrite?", abort=True)
    
    server_config = {}
    
    if stdio_cmd:
        server_config["transport"] = "stdio"
        server_config["command"] = stdio_cmd.split()
    elif http_url:
        server_config["transport"] = "http"
        server_config["url"] = http_url
    else:
        click.echo("Error: Must specify --stdio or --http")
        return
    
    # Parse environment variables
    if env_vars:
        env_dict = {}
        for env_var in env_vars:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                env_dict[key] = value
        if env_dict:
            server_config["env"] = env_dict
    
    config["servers"][name] = server_config
    save_config(config)
    
    click.echo(f"✓ Added MCP server '{name}'")
    click.echo(f"  Transport: {server_config['transport']}")
    if stdio_cmd:
        click.echo(f"  Command: {stdio_cmd}")
    if http_url:
        click.echo(f"  URL: {http_url}")


@mcp_group.command(name="remove", help="Remove an MCP server")
@click.argument("name")
def mcp_remove(name):
    """Remove an MCP server configuration."""
    config = load_config()
    
    if name not in config["servers"]:
        click.echo(f"Error: Server '{name}' not found")
        return
    
    del config["servers"][name]
    save_config(config)
    
    click.echo(f"✓ Removed MCP server '{name}'")


@mcp_group.command(name="discover", help="Discover available MCP servers")
def mcp_discover():
    """Discover MCP servers from common locations."""
    click.echo("🔍 Discovering MCP servers...\n")
    
    found = []
    
    # Check for common MCP servers via npx
    common_servers = [
        ("filesystem", "@modelcontextprotocol/server-filesystem"),
        ("github", "@modelcontextprotocol/server-github"),
        ("fetch", "@modelcontextprotocol/server-fetch"),
        ("puppeteer", "@modelcontextprotocol/server-puppeteer"),
        ("sqlite", "@modelcontextprotocol/server-sqlite"),
        ("postgres", "@modelcontextprotocol/server-postgres"),
    ]
    
    for name, package in common_servers:
        try:
            # Check if package exists on npm (quick check)
            result = subprocess.run(
                ["npm", "view", package, "name"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                found.append((name, package, "npm"))
        except:
            pass
    
    if found:
        click.echo(f"Found {len(found)} MCP packages available via npx:\n")
        for name, package, source in found:
            click.echo(f"  {name:<15} {package:<40} ({source})")
        click.echo("\nRun 'clawctl mcp init' to add default configurations")
    else:
        click.echo("No MCP servers discovered. Install Node.js and npm to use MCP servers.")


@mcp_group.command(name="test", help="Test connection to MCP server")
@click.argument("name")
def mcp_test(name):
    """Test connection to an MCP server."""
    config = load_config()
    
    if name not in config["servers"]:
        click.echo(f"Error: Server '{name}' not configured")
        return
    
    server_config = config["servers"][name]
    transport = server_config.get("transport", "stdio")
    
    click.echo(f"Testing MCP server '{name}'...")
    click.echo(f"  Transport: {transport}")
    
    if transport == "stdio":
        cmd = server_config.get("command", [])
        click.echo(f"  Command: {' '.join(cmd)}")
        
        # Check if command exists
        if cmd and cmd[0] == "npx":
            try:
                subprocess.run(["which", "npx"], capture_output=True, check=True)
                click.echo("  ✓ npx is available")
            except:
                click.echo("  ✗ npx not found. Install Node.js.")
                return
        
        click.echo("\n✓ Configuration looks valid")
        click.echo("  (Full test requires starting the MCP server)")
        
    elif transport == "http":
        url = server_config.get("url", "")
        click.echo(f"  URL: {url}")
        
        # Try HTTP connection
        try:
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                click.echo(f"  ✓ HTTP {resp.status}")
        except (OSError, ConnectionRefusedError, TimeoutError) as e:
            click.echo(f"  ✗ Connection failed: {e}")


@mcp_group.command(name="show", help="Show MCP server configuration")
@click.argument("name")
def mcp_show(name):
    """Show detailed configuration for an MCP server."""
    config = load_config()
    
    if name not in config["servers"]:
        click.echo(f"Error: Server '{name}' not found")
        return
    
    server_config = config["servers"][name]
    
    click.echo(f"\nMCP Server: {name}")
    click.echo("-" * 40)
    
    for key, value in server_config.items():
        if key == "env":
            click.echo(f"{key}:")
            for env_key, env_val in value.items():
                # Mask sensitive values
                display_val = env_val if len(env_val) < 20 else env_val[:10] + "..."
                click.echo(f"  {env_key}={display_val}")
        elif isinstance(value, list):
            click.echo(f"{key}: {' '.join(value)}")
        else:
            click.echo(f"{key}: {value}")


@mcp_group.command(name="template", help="Show MCP server templates")
@click.argument("template_name", required=False)
def mcp_template(template_name):
    """Show available MCP server templates."""
    templates = {
        "filesystem": {
            "description": "Access local filesystem",
            "command": "npx -y @modelcontextprotocol/server-filesystem ~/workspace"
        },
        "github": {
            "description": "GitHub API access",
            "command": "npx -y @modelcontextprotocol/server-github",
            "env": "GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here"
        },
        "fetch": {
            "description": "Web fetching",
            "command": "npx -y @modelcontextprotocol/server-fetch"
        },
        "puppeteer": {
            "description": "Browser automation",
            "command": "npx -y @modelcontextprotocol/server-puppeteer"
        },
        "sqlite": {
            "description": "SQLite database",
            "command": "npx -y @modelcontextprotocol/server-sqlite /path/to/db.sqlite"
        }
    }
    
    if template_name:
        if template_name not in templates:
            click.echo(f"Unknown template: {template_name}")
            click.echo(f"Available: {', '.join(templates.keys())}")
            return
        
        template = templates[template_name]
        click.echo(f"\nTemplate: {template_name}")
        click.echo(f"Description: {template['description']}")
        click.echo(f"Command: {template['command']}")
        if "env" in template:
            click.echo(f"Env: {template['env']}")
    else:
        click.echo("\nAvailable MCP Server Templates:")
        click.echo("-" * 50)
        for name, template in templates.items():
            click.echo(f"\n{name}")
            click.echo(f"  {template['description']}")
            click.echo(f"  clawctl mcp add {name} --stdio \"{template['command']}\"")
