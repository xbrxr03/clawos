# SPDX-License-Identifier: AGPL-3.0-or-later
"""
MCP JSON-RPC 2.0 protocol implementation.

Supports two transport modes:
  - stdio: spawn a subprocess, communicate via stdin/stdout JSON-RPC
  - http:  POST JSON-RPC payloads to an HTTP endpoint
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from typing import Any, Dict, Optional

log = logging.getLogger("mcpd.protocol")

_JSONRPC = "2.0"
_TIMEOUT = 15


def _make_request(method: str, params: Optional[dict] = None, req_id: Any = 1) -> dict:
    return {"jsonrpc": _JSONRPC, "id": req_id, "method": method, "params": params or {}}


def _make_notification(method: str, params: Optional[dict] = None) -> dict:
    return {"jsonrpc": _JSONRPC, "method": method, "params": params or {}}


class HttpMCPClient:
    """JSON-RPC client for HTTP-transport MCP servers."""

    def __init__(self, endpoint: str, headers: Optional[dict] = None):
        self.endpoint = endpoint.rstrip("/")
        self.headers = headers or {}
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def call(self, method: str, params: Optional[dict] = None) -> dict:
        payload = json.dumps(_make_request(method, params, self._next_id())).encode()
        h = {"Content-Type": "application/json", **self.headers}
        req = urllib.request.Request(self.endpoint, data=payload, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
                result = json.loads(resp.read())
            if "error" in result:
                raise RuntimeError(f"MCP error {result['error'].get('code')}: {result['error'].get('message')}")
            return result.get("result", {})
        except Exception as exc:
            raise RuntimeError(f"HTTP MCP call failed ({method}): {exc}") from exc

    def initialize(self) -> dict:
        return self.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ClawOS", "version": "1.0"},
        })

    def list_tools(self) -> list[dict]:
        result = self.call("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self.call("tools/call", {"name": name, "arguments": arguments})

    def list_resources(self) -> list[dict]:
        try:
            result = self.call("resources/list")
            return result.get("resources", [])
        except Exception:
            return []

    def read_resource(self, uri: str) -> dict:
        return self.call("resources/read", {"uri": uri})

    def list_prompts(self) -> list[dict]:
        try:
            result = self.call("prompts/list")
            return result.get("prompts", [])
        except Exception:
            return []


class StdioMCPClient:
    """JSON-RPC client for stdio-transport MCP servers (subprocess)."""

    def __init__(self, command: list[str], env: Optional[dict] = None):
        self.command = command
        self.env = env
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._req_id = 0
        self._initialized = False

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def _ensure_started(self) -> None:
        if self._proc and self._proc.returncode is None:
            return
        import os
        proc_env = os.environ.copy()
        if self.env:
            proc_env.update(self.env)
        self._proc = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=proc_env,
        )

    async def _send(self, payload: dict) -> None:
        assert self._proc and self._proc.stdin
        line = (json.dumps(payload) + "\n").encode()
        self._proc.stdin.write(line)
        await self._proc.stdin.drain()

    async def _recv(self) -> dict:
        assert self._proc and self._proc.stdout
        line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=_TIMEOUT)
        return json.loads(line)

    async def call(self, method: str, params: Optional[dict] = None) -> dict:
        await self._ensure_started()
        req_id = self._next_id()
        await self._send(_make_request(method, params, req_id))
        response = await self._recv()
        if "error" in response:
            raise RuntimeError(f"MCP error {response['error'].get('code')}: {response['error'].get('message')}")
        return response.get("result", {})

    async def initialize(self) -> dict:
        if self._initialized:
            return {}
        result = await self.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ClawOS", "version": "1.0"},
        })
        await self._send(_make_notification("notifications/initialized"))
        self._initialized = True
        return result

    async def list_tools(self) -> list[dict]:
        result = await self.call("tools/list")
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:
        return await self.call("tools/call", {"name": name, "arguments": arguments})

    async def list_resources(self) -> list[dict]:
        try:
            result = await self.call("resources/list")
            return result.get("resources", [])
        except Exception:
            return []

    async def list_prompts(self) -> list[dict]:
        try:
            result = await self.call("prompts/list")
            return result.get("prompts", [])
        except Exception:
            return []

    async def stop(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=3)
            except Exception:
                pass
