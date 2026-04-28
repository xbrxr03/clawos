# SPDX-License-Identifier: AGPL-3.0-or-later
"""
MCP Client for ClawOS Toolbridge
=================================
Implements Model Context Protocol client to connect ClawOS to external MCP servers.
MCP is the "USB-C for AI agents" - universal protocol for tools and resources.

Supports:
- stdio transport (local MCP servers)
- HTTP/SSE transport (remote MCP servers)
- Auto-discovery from MCP registry
- Tool translation from MCP format to ClawOS format

Reference: https://modelcontextprotocol.io
"""
import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

log = logging.getLogger("toolbridge.mcp")


class MCPTransport:
    """Base class for MCP transport layers."""
    
    async def send(self, message: dict) -> dict:
        raise NotImplementedError
    
    async def close(self):
        pass


class StdioTransport(MCPTransport):
    """MCP stdio transport - for local MCP servers."""
    
    def __init__(self, command: list[str], cwd: Optional[str] = None):
        self.command = command
        self.cwd = cwd
        self.process: Optional[subprocess.Process] = None
        self._lock = asyncio.Lock()
    
    async def connect(self):
        """Start the MCP server process."""
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd
        )
        log.info(f"MCP stdio process started: {' '.join(self.command)}")
    
    async def send(self, message: dict) -> dict:
        """Send JSON-RPC message and receive response."""
        if not self.process or self.process.stdin is None:
            raise RuntimeError("MCP process not connected")
        
        async with self._lock:
            # Send message
            msg_json = json.dumps(message) + "\n"
            self.process.stdin.write(msg_json.encode())
            await self.process.stdin.drain()
            
            # Read response
            response_line = await self.process.stdout.readline()
            return json.loads(response_line.decode())
    
    async def close(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()
            log.info("MCP stdio process terminated")


class HTTPTransport(MCPTransport):
    """MCP HTTP/SSE transport - for remote MCP servers."""
    
    def __init__(self, base_url: str, headers: Optional[dict] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.client: Optional[httpx.AsyncClient] = None
    
    async def connect(self):
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0
        )
        log.info(f"MCP HTTP client initialized: {self.base_url}")
    
    async def send(self, message: dict) -> dict:
        """Send JSON-RPC message via HTTP POST."""
        if not self.client:
            raise RuntimeError("MCP HTTP client not connected")
        
        response = await self.client.post("/mcp", json=message)
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        if self.client:
            await self.client.aclose()
            log.info("MCP HTTP client closed")


class MCPServerConnection:
    """Connection to a single MCP server."""
    
    def __init__(self, name: str, transport: MCPTransport):
        self.name = name
        self.transport = transport
        self.tools: list[dict] = []
        self.resources: list[dict] = []
        self._initialized = False
    
    async def initialize(self):
        """Initialize connection and discover capabilities."""
        await self.transport.connect()
        
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "ClawOS",
                    "version": "0.1.0"
                }
            }
        }
        
        response = await self.transport.send(init_request)
        if "error" in response:
            raise RuntimeError(f"MCP initialize failed: {response['error']}")
        
        # Send initialized notification
        await self.transport.send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        
        self._initialized = True
        log.info(f"MCP server '{self.name}' initialized")
        
        # Discover tools
        await self._discover_tools()
        await self._discover_resources()
    
    async def _discover_tools(self):
        """Discover available tools from MCP server."""
        response = await self.transport.send({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        })
        
        if "error" not in response:
            self.tools = response.get("result", {}).get("tools", [])
            log.info(f"Discovered {len(self.tools)} tools from '{self.name}'")
    
    async def _discover_resources(self):
        """Discover available resources from MCP server."""
        response = await self.transport.send({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list"
        })
        
        if "error" not in response:
            self.resources = response.get("result", {}).get("resources", [])
            log.info(f"Discovered {len(self.resources)} resources from '{self.name}'")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        if not self._initialized:
            raise RuntimeError("MCP connection not initialized")
        
        response = await self.transport.send({
            "jsonrpc": "2.0",
            "id": asyncio.get_event_loop().time(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        })
        
        if "error" in response:
            raise RuntimeError(f"Tool call failed: {response['error']}")
        
        return response.get("result", {})
    
    async def read_resource(self, uri: str) -> dict:
        """Read a resource from the MCP server."""
        if not self._initialized:
            raise RuntimeError("MCP connection not initialized")
        
        response = await self.transport.send({
            "jsonrpc": "2.0",
            "id": asyncio.get_event_loop().time(),
            "method": "resources/read",
            "params": {
                "uri": uri
            }
        })
        
        if "error" in response:
            raise RuntimeError(f"Resource read failed: {response['error']}")
        
        return response.get("result", {})
    
    async def close(self):
        await self.transport.close()


class MCPClient:
    """
    MCP Client Manager for ClawOS.
    
    Manages connections to multiple MCP servers and translates
    MCP tools/resources into ClawOS tool format.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.connections: dict[str, MCPServerConnection] = {}
        self.config_path = config_path or Path.home() / ".clawos-runtime" / "config" / "mcp.json"
        self._tool_cache: dict[str, tuple[str, dict]] = {}  # tool_name -> (server_name, tool_def)
    
    async def load_config(self):
        """Load MCP server configurations."""
        if not self.config_path.exists():
            log.info(f"No MCP config found at {self.config_path}")
            return
        
        try:
            with open(self.config_path) as f:
                config = json.load(f)
            
            servers = config.get("servers", {})
            for name, server_config in servers.items():
                await self.connect_server(name, server_config)
                
        except Exception as e:
            log.error(f"Failed to load MCP config: {e}")
    
    async def connect_server(self, name: str, config: dict):
        """Connect to an MCP server from config."""
        transport_type = config.get("transport", "stdio")
        
        try:
            if transport_type == "stdio":
                command = config.get("command", [])
                if isinstance(command, str):
                    command = ["npx", "-y", command]
                cwd = config.get("cwd")
                transport = StdioTransport(command, cwd)
            
            elif transport_type == "http":
                url = config.get("url")
                headers = config.get("headers", {})
                transport = HTTPTransport(url, headers)
            
            else:
                log.error(f"Unknown MCP transport type: {transport_type}")
                return
            
            connection = MCPServerConnection(name, transport)
            await connection.initialize()
            
            self.connections[name] = connection
            
            # Update tool cache
            for tool in connection.tools:
                tool_name = f"mcp.{name}.{tool['name']}"
                self._tool_cache[tool_name] = (name, tool)
            
            log.info(f"Connected to MCP server '{name}' with {len(connection.tools)} tools")
            
        except Exception as e:
            log.error(f"Failed to connect to MCP server '{name}': {e}")
    
    def get_all_tools(self) -> dict[str, str]:
        """Get all MCP tools formatted for ClawOS tool descriptions."""
        descriptions = {}
        for tool_name, (_, tool_def) in self._tool_cache.items():
            desc = tool_def.get("description", "No description")
            descriptions[tool_name] = f"[MCP] {desc}"
        return descriptions
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute an MCP tool and return result as string."""
        if tool_name not in self._tool_cache:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
        
        server_name, tool_def = self._tool_cache[tool_name]
        connection = self.connections.get(server_name)
        
        if not connection:
            raise RuntimeError(f"MCP server '{server_name}' not connected")
        
        # Extract original tool name (remove mcp.{server}. prefix)
        original_name = tool_name.split(".")[-1]
        
        try:
            result = await connection.call_tool(original_name, arguments)
            
            # Format result for ClawOS
            content = result.get("content", [])
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                        elif item.get("type") == "image":
                            text_parts.append(f"[Image: {item.get('mimeType', 'unknown')}]")
                        elif item.get("type") == "resource":
                            resource = item.get("resource", {})
                            text_parts.append(f"[Resource: {resource.get('uri', 'unknown')}]")
                return "\n".join(text_parts)
            else:
                return str(content)
                
        except Exception as e:
            log.error(f"MCP tool execution failed: {e}")
            return f"Error executing {tool_name}: {str(e)}"
    
    async def close_all(self):
        """Close all MCP connections."""
        for name, connection in self.connections.items():
            try:
                await connection.close()
                log.info(f"Closed MCP connection '{name}'")
            except Exception as e:
                log.error(f"Error closing MCP connection '{name}': {e}")
        
        self.connections.clear()
        self._tool_cache.clear()


# Default MCP server configurations for popular tools
DEFAULT_MCP_SERVERS = {
    "filesystem": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(Path.home())]
    },
    "github": {
        "transport": "stdio", 
        "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""}
    },
    "postgres": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"]
    },
    "puppeteer": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-puppeteer"]
    },
    "fetch": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-fetch"]
    }
}


async def create_default_config(path: Path):
    """Create default MCP configuration file."""
    config = {
        "servers": DEFAULT_MCP_SERVERS,
        "settings": {
            "auto_discover": True,
            "max_concurrent": 5
        }
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    
    log.info(f"Created default MCP config at {path}")
