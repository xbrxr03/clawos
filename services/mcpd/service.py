# SPDX-License-Identifier: AGPL-3.0-or-later
"""
mcpd - MCP Server Manager
=========================
Manages MCP (Model Context Protocol) server connections, tool registry,
and JSON-RPC relay for agents. Supports both stdio and HTTP transport.

Server config is persisted to ~/.clawos/mcp_servers.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("mcpd")

try:
    from clawos_core.constants import CONFIG_DIR
    MCP_CONFIG_PATH = CONFIG_DIR / "mcp_servers.json"
except Exception:
    MCP_CONFIG_PATH = Path.home() / ".clawos" / "mcp_servers.json"


# ── Data model ────────────────────────────────────────────────────────────────
@dataclass
class MCPTool:
    name: str
    description: str
    server_id: str
    input_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    server_id: str
    mime_type: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MCPServerConfig:
    id: str
    name: str
    transport: str              # "stdio" | "http"
    command: List[str] = field(default_factory=list)   # stdio only
    endpoint: str = ""          # http only
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    status: str = "disconnected"  # disconnected | connected | error
    error: str = ""
    tools: List[dict] = field(default_factory=list)
    resources: List[dict] = field(default_factory=list)
    prompts: List[dict] = field(default_factory=list)
    connected_at: str = ""
    added_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        return asdict(self)


# ── Persistence ───────────────────────────────────────────────────────────────
def _load_configs() -> List[MCPServerConfig]:
    if not MCP_CONFIG_PATH.exists():
        return []
    try:
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
        return [MCPServerConfig(**s) for s in data]
    except Exception as exc:
        log.warning("Failed to load MCP server configs: %s", exc)
        return []


def _save_configs(configs: List[MCPServerConfig]) -> None:
    MCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MCP_CONFIG_PATH.write_text(
        json.dumps([asdict(c) for c in configs], indent=2),
        encoding="utf-8",
    )


# ── Service ───────────────────────────────────────────────────────────────────
class MCPService:
    def __init__(self) -> None:
        self._configs: List[MCPServerConfig] = _load_configs()
        # Live stdio clients keyed by server id
        self._stdio_clients: Dict[str, Any] = {}

    # ── Server registry ───────────────────────────────────────────────────────

    def list_servers(self) -> List[dict]:
        return [c.to_dict() for c in self._configs]

    def get_server(self, server_id: str) -> Optional[MCPServerConfig]:
        return next((c for c in self._configs if c.id == server_id), None)

    def add_server(
        self,
        name: str,
        transport: str,
        command: Optional[List[str]] = None,
        endpoint: str = "",
        env: Optional[Dict[str, str]] = None,
    ) -> MCPServerConfig:
        cfg = MCPServerConfig(
            id=secrets.token_urlsafe(8),
            name=name,
            transport=transport,
            command=command or [],
            endpoint=endpoint,
            env=env or {},
        )
        self._configs.append(cfg)
        _save_configs(self._configs)
        return cfg

    def remove_server(self, server_id: str) -> bool:
        before = len(self._configs)
        self._configs = [c for c in self._configs if c.id != server_id]
        if len(self._configs) < before:
            _save_configs(self._configs)
            # Stop stdio client if running
            client = self._stdio_clients.pop(server_id, None)
            if client:
                asyncio.create_task(client.stop())
            return True
        return False

    def update_server(self, server_id: str, patch: dict) -> Optional[MCPServerConfig]:
        cfg = self.get_server(server_id)
        if not cfg:
            return None
        allowed = {"name", "command", "endpoint", "env", "enabled"}
        for k, v in patch.items():
            if k in allowed and hasattr(cfg, k):
                setattr(cfg, k, v)
        _save_configs(self._configs)
        return cfg

    # ── Connection ────────────────────────────────────────────────────────────

    async def connect(self, server_id: str) -> MCPServerConfig:
        cfg = self.get_server(server_id)
        if not cfg:
            raise ValueError(f"Server not found: {server_id}")

        if cfg.transport == "http":
            return await self._connect_http(cfg)
        elif cfg.transport == "stdio":
            return await self._connect_stdio(cfg)
        else:
            raise ValueError(f"Unknown transport: {cfg.transport}")

    async def _connect_http(self, cfg: MCPServerConfig) -> MCPServerConfig:
        from services.mcpd.protocol import HttpMCPClient
        client = HttpMCPClient(cfg.endpoint)
        try:
            await asyncio.get_event_loop().run_in_executor(None, client.initialize)
            tools = await asyncio.get_event_loop().run_in_executor(None, client.list_tools)
            resources = await asyncio.get_event_loop().run_in_executor(None, client.list_resources)
            prompts = await asyncio.get_event_loop().run_in_executor(None, client.list_prompts)
            cfg.tools = tools
            cfg.resources = resources
            cfg.prompts = prompts
            cfg.status = "connected"
            cfg.error = ""
            cfg.connected_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        except Exception as exc:
            cfg.status = "error"
            cfg.error = str(exc)
            log.warning("HTTP MCP connect failed for %s: %s", cfg.name, exc)
        _save_configs(self._configs)
        return cfg

    async def _connect_stdio(self, cfg: MCPServerConfig) -> MCPServerConfig:
        from services.mcpd.protocol import StdioMCPClient
        # Stop existing client if any
        old = self._stdio_clients.pop(cfg.id, None)
        if old:
            await old.stop()
        client = StdioMCPClient(cfg.command, env=cfg.env or None)
        try:
            await client.initialize()
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts = await client.list_prompts()
            cfg.tools = tools
            cfg.resources = resources
            cfg.prompts = prompts
            cfg.status = "connected"
            cfg.error = ""
            cfg.connected_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._stdio_clients[cfg.id] = client
        except Exception as exc:
            cfg.status = "error"
            cfg.error = str(exc)
            await client.stop()
            log.warning("Stdio MCP connect failed for %s: %s", cfg.name, exc)
        _save_configs(self._configs)
        return cfg

    # ── Tool catalog ──────────────────────────────────────────────────────────

    def list_all_tools(self) -> List[dict]:
        tools = []
        for cfg in self._configs:
            if cfg.status == "connected":
                for t in cfg.tools:
                    tools.append({**t, "server_id": cfg.id, "server_name": cfg.name})
        return tools

    def list_all_resources(self) -> List[dict]:
        resources = []
        for cfg in self._configs:
            if cfg.status == "connected":
                for r in cfg.resources:
                    resources.append({**r, "server_id": cfg.id, "server_name": cfg.name})
        return resources

    # ── Tool call relay ───────────────────────────────────────────────────────

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict) -> dict:
        cfg = self.get_server(server_id)
        if not cfg:
            raise ValueError(f"Server not found: {server_id}")
        if cfg.status != "connected":
            raise RuntimeError(f"Server not connected: {cfg.name}")

        if cfg.transport == "http":
            from services.mcpd.protocol import HttpMCPClient
            client = HttpMCPClient(cfg.endpoint)
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.call_tool(tool_name, arguments)
            )
        elif cfg.transport == "stdio":
            client = self._stdio_clients.get(cfg.id)
            if not client:
                raise RuntimeError(f"Stdio client not running for {cfg.name}")
            return await client.call_tool(tool_name, arguments)
        else:
            raise ValueError(f"Unknown transport: {cfg.transport}")

    async def read_resource(self, server_id: str, uri: str) -> dict:
        cfg = self.get_server(server_id)
        if not cfg:
            raise ValueError(f"Server not found: {server_id}")
        if cfg.transport == "http":
            from services.mcpd.protocol import HttpMCPClient
            client = HttpMCPClient(cfg.endpoint)
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.read_resource(uri)
            )
        elif cfg.transport == "stdio":
            client = self._stdio_clients.get(cfg.id)
            if not client:
                raise RuntimeError(f"Stdio client not running for {cfg.name}")
            return await client.call("resources/read", {"uri": uri})
        raise ValueError(f"Unknown transport: {cfg.transport}")

    # ── Well-known servers ────────────────────────────────────────────────────

    WELL_KNOWN: List[dict] = [
        {
            "id": "filesystem",
            "name": "Filesystem",
            "description": "Read and write local files via MCP",
            "transport": "stdio",
            "command_template": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "{path}"],
            "category": "storage",
        },
        {
            "id": "brave-search",
            "name": "Brave Search",
            "description": "Web search via Brave Search API",
            "transport": "stdio",
            "command_template": ["npx", "-y", "@modelcontextprotocol/server-brave-search"],
            "env_required": ["BRAVE_API_KEY"],
            "category": "search",
        },
        {
            "id": "github",
            "name": "GitHub",
            "description": "Read GitHub repos, issues, and PRs",
            "transport": "stdio",
            "command_template": ["npx", "-y", "@modelcontextprotocol/server-github"],
            "env_required": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
            "category": "dev",
        },
        {
            "id": "sqlite",
            "name": "SQLite",
            "description": "Query and inspect local SQLite databases",
            "transport": "stdio",
            "command_template": ["uvx", "mcp-server-sqlite", "--db-path", "{db_path}"],
            "category": "storage",
        },
        {
            "id": "memory",
            "name": "Memory",
            "description": "Persistent key-value memory for agents",
            "transport": "stdio",
            "command_template": ["npx", "-y", "@modelcontextprotocol/server-memory"],
            "category": "memory",
        },
        {
            "id": "fetch",
            "name": "Fetch",
            "description": "Fetch web content and convert to Markdown",
            "transport": "stdio",
            "command_template": ["uvx", "mcp-server-fetch"],
            "category": "web",
        },
        {
            "id": "puppeteer",
            "name": "Puppeteer",
            "description": "Browser automation and screenshots",
            "transport": "stdio",
            "command_template": ["npx", "-y", "@modelcontextprotocol/server-puppeteer"],
            "category": "web",
        },
        {
            "id": "slack",
            "name": "Slack",
            "description": "Read and post Slack messages",
            "transport": "stdio",
            "command_template": ["npx", "-y", "@modelcontextprotocol/server-slack"],
            "env_required": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
            "category": "communication",
        },
    ]


_service: Optional[MCPService] = None


def get_service() -> MCPService:
    global _service
    if _service is None:
        _service = MCPService()
    return _service
