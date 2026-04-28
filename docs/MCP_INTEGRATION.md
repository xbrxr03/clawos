# MCP (Model Context Protocol) Integration

**Status:** ✅ Implemented  
**Date:** April 26, 2026  
**ClawOS Version:** 0.1.0+

---

## What is MCP?

**MCP (Model Context Protocol)** is the "USB-C for AI agents" — a universal protocol for connecting AI assistants to data sources and tools.

- **Created by:** Anthropic (launched Nov 2024)
- **Adopted by:** Microsoft, AWS, and growing ecosystem
- **Available tools:** 600+ integrations via MCP
- **Protocol:** JSON-RPC based, supports stdio and HTTP transports

---

## Quick Start

### 1. Initialize MCP Configuration

```bash
clawctl mcp init
```

This creates default configuration with 5 popular MCP servers:
- **filesystem** - Access local filesystem
- **github** - GitHub API integration
- **fetch** - Web fetching
- **puppeteer** - Browser automation
- **sqlite** - SQLite database access

### 2. List Configured Servers

```bash
clawctl mcp list
```

Output:
```
Name                 Transport  Status         
--------------------------------------------------
filesystem           stdio      ready          
github               stdio      ready          
fetch                stdio      ready          
puppeteer            stdio      ready          
sqlite               stdio      ready          

Total: 5 servers configured
```

### 3. Test a Server

```bash
clawctl mcp test filesystem
```

### 4. Use MCP Tools in Nexus

Start Nexus and MCP tools are automatically available:

```bash
nexus
```

In the chat, you can now use:
- `mcp.filesystem.read_file` - Read files via MCP
- `mcp.filesystem.list_directory` - List directories
- `mcp.fetch.fetch_url` - Fetch web pages
- `mcp.github.search_repositories` - Search GitHub

---

## Adding Custom MCP Servers

### From npm (stdio transport)

```bash
clawctl mcp add postgres \
  --stdio "npx -y @modelcontextprotocol/server-postgres postgresql://localhost/mydb"
```

### From HTTP endpoint

```bash
clawctl mcp add remote-tools \
  --http "https://tools.example.com/mcp" \
  --env "API_KEY=your_key_here"
```

### With environment variables

```bash
clawctl mcp add github \
  --stdio "npx -y @modelcontextprotocol/server-github" \
  --env "GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxx"
```

---

## MCP Tool Naming Convention

MCP tools are namespaced to avoid conflicts:

```
mcp.{server_name}.{tool_name}
```

Examples:
- `mcp.filesystem.read_file`
- `mcp.filesystem.list_directory`
- `mcp.github.search_repositories`
- `mcp.fetch.fetch_url`
- `mcp.puppeteer.navigate`

---

## Configuration File

MCP configuration is stored in:

```
~/.clawos-runtime/config/mcp.json
```

Example structure:

```json
{
  "servers": {
    "filesystem": {
      "transport": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/home/user"]
    },
    "github": {
      "transport": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxx"
      }
    },
    "remote": {
      "transport": "http",
      "url": "https://tools.example.com/mcp",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  },
  "settings": {
    "auto_discover": true,
    "max_concurrent": 5
  }
}
```

---

## Available MCP Servers

### Official Anthropic Servers

| Package | Description | Install |
|---------|-------------|---------|
| `@modelcontextprotocol/server-filesystem` | Local filesystem access | Built-in |
| `@modelcontextprotocol/server-github` | GitHub API integration | Built-in |
| `@modelcontextprotocol/server-postgres` | PostgreSQL database | `clawctl mcp add postgres --stdio "npx -y @modelcontextprotocol/server-postgres <connection_string>"` |
| `@modelcontextprotocol/server-sqlite` | SQLite database | Built-in |
| `@modelcontextprotocol/server-fetch` | Web fetching | Built-in |
| `@modelcontextprotocol/server-puppeteer` | Browser automation | Built-in |
| `@modelcontextprotocol/server-slack` | Slack integration | Manual add |
| `@modelcontextprotocol/server-google-maps` | Google Maps API | Manual add |

### Community Servers

Discover more at [MCP Community Servers](https://github.com/modelcontextprotocol/servers):

```bash
# Redis
clawctl mcp add redis --stdio "npx -y @modelcontextprotocol/server-redis redis://localhost:6379"

# Brave Search
clawctl mcp add brave --stdio "npx -y @modelcontextprotocol/server-brave-search" --env "BRAVE_API_KEY=xxx"

# Stripe
clawctl mcp add stripe --stdio "npx -y @modelcontextprotocol/server-stripe" --env "STRIPE_API_KEY=sk_xxx"
```

---

## CLI Reference

### `clawctl mcp init`
Create default MCP configuration with 5 built-in servers.

### `clawctl mcp list`
List all configured MCP servers with their status.

### `clawctl mcp add <name>`
Add a new MCP server.

Options:
- `--stdio <command>` - stdio transport command
- `--http <url>` - HTTP endpoint URL
- `--env <KEY=value>` - Environment variables (can specify multiple)

### `clawctl mcp remove <name>`
Remove an MCP server configuration.

### `clawctl mcp test <name>`
Test connection to an MCP server.

### `clawctl mcp discover`
Discover available MCP servers from npm registry.

### `clawctl mcp template [name]`
Show MCP server templates. If no name provided, shows all templates.

### `clawctl mcp show <name>`
Show detailed configuration for an MCP server.

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Nexus Agent                          │
│                    (ReAct loop)                             │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    ToolBridge                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Native Tools (fs.*, web.*, memory.*, etc.)             ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │  MCP Tools (mcp.*)                                      ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     ││
│  │  │ MCP Client  │  │ MCP Client  │  │ MCP Client  │     ││
│  │  │ (filesystem)│  │  (github)   │  │   (fetch)   │     ││
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     ││
│  └─────────┼────────────────┼────────────────┼────────────┘│
└────────────┼────────────────┼────────────────┼─────────────┘
             │                │                │
        ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
        │  npx    │      │  npx    │      │  npx    │
        │(stdio)  │      │(stdio)  │      │(stdio)  │
        └────┬────┘      └────┬────┘      └────┬────┘
             │                │                │
        ┌────▼────────────────▼────────────────▼────┐
        │         MCP Servers (Node.js)             │
        │  ┌─────────┐ ┌─────────┐ ┌─────────┐     │
        │  │filesystem│ │ github  │ │  fetch  │     │
        │  └─────────┘ └─────────┘ └─────────┘     │
        └───────────────────────────────────────────┘
```

### Transport Types

**stdio Transport:**
- Spawns MCP server as subprocess
- Communicates via stdin/stdout
- Best for local tools (npx-based)
- Example: filesystem, github, fetch

**HTTP Transport:**
- Connects to remote MCP endpoint
- Communicates via HTTP POST
- Best for cloud-hosted tools
- Example: enterprise tool APIs

---

## Demo Script

Run the included demo:

```bash
python3 scripts/mcp-demo.py
```

This will:
1. Create default MCP configuration
2. Connect to configured servers
3. List available tools
4. Test tool execution

---

## Troubleshooting

### "npx not found"

Install Node.js:
```bash
# Ubuntu/Debian
sudo apt install nodejs npm

# macOS
brew install node
```

### "MCP server failed to start"

Check the server is installed:
```bash
npx -y @modelcontextprotocol/server-filesystem --help
```

### "Connection refused"

For HTTP transport, verify the endpoint:
```bash
curl https://tools.example.com/mcp/health
```

### Tools not appearing in Nexus

1. Restart ClawOS services:
   ```bash
   bash scripts/dev_boot.sh
   ```

2. Verify MCP config loaded:
   ```bash
   clawctl mcp list
   ```

---

## Security Considerations

⚠️ **Important:** MCP servers run with the same permissions as ClawOS.

- **Filesystem server** can access any path you configure
- **GitHub server** uses your personal access token
- **Browser automation** can interact with any website

**Best practices:**
1. Review each MCP server's permissions before adding
2. Use specific paths (not `~` or `/`) for filesystem server
3. Store tokens in environment variables, not config files
4. Regularly audit configured MCP servers

---

## Roadmap

### Phase 1: Client Support ✅ (Complete)
- Connect to external MCP servers
- Use MCP tools in Nexus

### Phase 2: Server Mode (Planned)
- Expose ClawOS services as MCP server
- Other AI assistants can use ClawOS tools

### Phase 3: Marketplace (Planned)
- Curated MCP server registry
- One-click install from marketplace
- Verified/sandboxed servers

---

## Resources

- **MCP Specification:** https://modelcontextprotocol.io
- **Official Servers:** https://github.com/modelcontextprotocol/servers
- **Community Servers:** https://github.com/modelcontextprotocol/servers/tree/main/src
- **Microsoft MCP Tutorial:** https://github.com/microsoft/mcp-for-beginners

---

## Contributing

To add support for a new MCP transport or feature:

1. Edit `services/toolbridge/mcp_client.py`
2. Add transport class inheriting from `MCPTransport`
3. Update `MCPServerConnection` to use new transport
4. Test with `python3 scripts/mcp-demo.py`
5. Submit PR with documentation update

---

**With MCP integration, ClawOS can now access 600+ tools and services.**

Your personal AI assistant just got a lot more capable.
