# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS toolbridge — Tool Execution
====================================
Every tool call is gated through policyd. No exceptions.
Resolve relative paths to absolute BEFORE policyd check.
Agent tool filtering: only inject granted tools into system prompt.
"""
import asyncio
import json
import logging
import re
import subprocess
from pathlib import Path

from clawos_core.constants import CLAWOS_DIR
from clawos_core.platform import ram_snapshot_gb
from clawos_core.tool_result import ToolResult
from clawos_core.util.paths import workspace_path

log = logging.getLogger("toolbridge")

SHELL_ALLOWLIST = [
    r'^ls(\s|$)', r'^pwd$', r'^echo\s', r'^cat\s', r'^head\s', r'^tail\s',
    r'^wc\s', r'^find\s', r'^grep\s', r'^which\s', r'^whoami$', r'^date$',
    r'^df\s', r'^du\s', r'^uname', r'^hostname$', r'^ps\s',
    r'^python3?\s+[^-]', r'^pip\s', r'^git\s',
]

# Mapping from legacy tool names (used in _execute dispatch) to their
# canonical names in the NATIVE_TOOLS / tool_schemas registry.
TOOL_ALIASES = {
    "fs.read":          "read_file",
    "fs.write":         "write_file",
    "fs.list":          "list_files",
    "fs.delete":        "fs.delete",         # legacy-only, no native tool
    "fs.search":        "fs.search",          # legacy-only
    "web.search":       "web_search",
    "web.fetch":        "web.fetch",          # legacy-only
    "shell.restricted": "run_command",
    "memory.read":      "recall",
    "memory.write":     "remember",
    "memory.delete":    "memory.delete",      # legacy-only
    "system.info":      "system_stats",
    "workspace.create":  "workspace.create",   # legacy-only
    "workspace.inspect": "workspace.inspect",  # legacy-only
}


def _build_tool_descriptions() -> dict[str, str]:
    """Derive tool descriptions from tool_schemas (single source of truth).

    Falls back to NATIVE_TOOLS names when tool_schemas hasn't been imported.
    Browser tools and legacy-only tools are appended separately since they
    don't live in NATIVE_TOOLS.
    """
    from runtimes.agent.tool_schemas import ALL_SCHEMAS
    descs: dict[str, str] = {}
    for schema in ALL_SCHEMAS:
        fn = schema["function"]
        descs[fn["name"]] = fn["description"]

    # Legacy-only tools that exist in _execute but not in NATIVE_TOOLS
    descs["fs.delete"]        = "Delete a file. Requires approval."
    descs["fs.search"]        = "Search files by content. Input: query string."
    descs["web.fetch"]         = "Fetch a URL. Input: full URL."
    descs["memory.delete"]    = "Delete a memory. Input: memory_id."
    descs["workspace.create"]  = "Create a new workspace. Input: workspace name."
    descs["workspace.inspect"] = "Inspect workspace contents and memory summary."

    # Browser tools (Playwright) — disabled by default, enabled by config
    descs["browser.open"]      = "Open a URL in a sandboxed browser session. Input: url."
    descs["browser.read"]      = "Read the visible text content of the current page."
    descs["browser.click"]     = "Click an element on the current page. Input: CSS selector or text."
    descs["browser.type"]     = "Type text into a focused input field. Input: text string."
    descs["browser.screenshot"] = "Take a screenshot of the current page. Returns image path."
    descs["browser.close"]    = "Close the current browser session."
    descs["browser.scroll"]    = "Scroll the page. Input: 'up', 'down', or a CSS selector."
    descs["browser.wait"]      = "Wait for an element or condition. Input: CSS selector or milliseconds."

    return descs


# Lazy-loaded so we don't pay import cost until someone builds a prompt.
ALL_TOOL_DESCRIPTIONS: dict[str, str] | None = None


def _get_tool_descriptions() -> dict[str, str]:
    global ALL_TOOL_DESCRIPTIONS
    if ALL_TOOL_DESCRIPTIONS is None:
        ALL_TOOL_DESCRIPTIONS = _build_tool_descriptions()
    return ALL_TOOL_DESCRIPTIONS


class ToolBridge:
    def __init__(self, policy_client, memory_service, workspace_id: str, mcp_client=None):
        self.policy    = policy_client
        self.memory    = memory_service
        self.workspace = workspace_id
        self._workspace_id = workspace_id
        self._ws_root  = workspace_path(workspace_id)
        self.mcp_client = mcp_client  # MCP client for external tools

    @property
    def _ws_root_fresh(self):
        from clawos_core.util.paths import workspace_path
        return workspace_path(self._workspace_id)

    def get_tool_list_for_prompt(self) -> str:
        """Only inject granted tools — reduces tokens by 30-60%."""
        granted = set(self.policy.granted_tools)
        descs = _get_tool_descriptions()
        available = {k: v for k, v in descs.items() if k in granted}
        
        # Add MCP tools if available
        if self.mcp_client:
            mcp_tools = self.mcp_client.get_all_tools()
            available.update(mcp_tools)
        
        if not available:
            return ""
        lines = [
            "## Available Tools",
            'Use JSON: {"action": "<tool>", "action_input": "<target>"}',
            "",
        ]
        if "fs.write" in available:
            lines.insert(2, 'For writes: {"action": "fs.write", "action_input": "file.txt", "content": "..."}')
        for tool, desc in available.items():
            lines.append(f"- **{tool}**: {desc}")
        return "\n".join(lines)

    async def run_native(self, tool: str, args: dict) -> str:
        """
        Native-args entry point for the new Nexus runtime (Phase 1+).

        Takes a dict of arguments straight from the LLM's tool_call and
        dispatches to either the new tools package (runtimes.agent.tools)
        or the legacy (target, content) execute path. Policy gating is the
        same as run().
        """
        from runtimes.agent.tools import dispatch_tool, NATIVE_TOOLS

        normalized_tool = TOOL_ALIASES.get(tool, tool)

        # Build a policy "target" for legacy gating compatibility.
        # Most tools surface their primary identifier as one of these keys.
        target_keys = ("path", "name", "query", "url", "command", "text", "fact")
        policy_target = ""
        for k in target_keys:
            if k in args and args[k] is not None:
                policy_target = str(args[k])
                break
        content = str(args.get("content") or args.get("text") or "")

        # Resolve fs paths before policy
        check_target = policy_target
        fs_tools = {"fs.read", "fs.write", "fs.list", "fs.delete", "fs.search",
                     "read_file", "write_file", "list_files", "open_file"}
        if normalized_tool in fs_tools:
            try:
                check_target = str(self._resolve_path(policy_target or "."))
            except (OSError, RuntimeError, AttributeError) as e:
                log.debug(f"unexpected: {e}")
                pass
                pass

        decision, reason = await self.policy.check(normalized_tool, check_target, content)
        if decision == "DENY":
            log.warning(f"Tool blocked: {normalized_tool} — {reason}")
            return str(ToolResult.denied(reason))
        if decision == "QUEUE":
            return str(ToolResult.pending(normalized_tool))

        try:
            if normalized_tool in NATIVE_TOOLS:
                # New native-args dispatch (runtimes.agent.tools.*)
                ctx = {
                    "workspace_id": self.workspace,
                    "ws_root":      self._ws_root_fresh,
                    "memory":       self.memory,
                    "bridge":       self,
                }
                result = await dispatch_tool(normalized_tool, args, ctx)
            else:
                # Fall back to the legacy (target, content) dispatch
                result = await self._execute(normalized_tool, policy_target, content)
        except (OSError, RuntimeError, TypeError) as e:
            result = str(ToolResult.error(f"{normalized_tool} failed: {e}", error=type(e).__name__))
            log.error(f"Tool error: {normalized_tool}: {e}")

        # Run after-hooks
        try:
            ctx = {"workspace_id": self.workspace, "task_id": self.policy.task_id}
            await self.policy._get_engine().hooks.run_after(normalized_tool, policy_target, str(result), ctx)
        except (OSError, RuntimeError, AttributeError) as e:
            log.debug(f"unexpected: {e}")
            pass

        return result if isinstance(result, str) else str(result)

    async def run(self, tool: str, target: str, content: str = "", **kwargs) -> str:
        if not content and "content" in kwargs:
            content = kwargs["content"]
        normalized_tool = TOOL_ALIASES.get(tool, tool)

        # Resolve paths before policyd check
        check_target = target
        if normalized_tool in ("fs.read", "fs.write", "fs.list", "fs.delete", "fs.search"):
            check_target = str(self._resolve_path(target))

        decision, reason = await self.policy.check(normalized_tool, check_target, content)

        if decision == "DENY":
            log.warning(f"Tool blocked: {normalized_tool}({target[:50]}) — {reason}")
            return str(ToolResult.denied(reason))
        if decision == "QUEUE":
            return str(ToolResult.pending(f"{normalized_tool}({target})"))

        try:
            result = await self._execute(normalized_tool, target, content)
        except (OSError, RuntimeError, TypeError) as e:
            result = str(ToolResult.error(f"{normalized_tool} failed: {e}", error=type(e).__name__))
            log.error(f"Tool error: {normalized_tool}({target[:40]}): {e}")

        # AfterToolCall hooks
        try:
            ctx = {"workspace_id": self.workspace, "task_id": self.policy.task_id}
            await self.policy._get_engine().hooks.run_after(normalized_tool, target, result, ctx)
        except (OSError, RuntimeError, AttributeError) as e:
            log.debug(f"unexpected: {e}")
            pass

        return result

    async def _execute(self, tool: str, target: str, content: str = "") -> str:
        loop = asyncio.get_event_loop()
        async def _sync_wrap(fn, *a):
            return fn(*a)
        dispatch = {
            "fs.read":          lambda: loop.run_in_executor(None, self._fs_read, target),
            "fs.write":         lambda: loop.run_in_executor(None, self._fs_write, target, content),
            "fs.list":          lambda: loop.run_in_executor(None, self._fs_list, target),
            "fs.delete":        lambda: loop.run_in_executor(None, self._fs_delete, target),
            "fs.search":        lambda: loop.run_in_executor(None, self._fs_search, target),
            "web.search":       lambda: self._web_search(target),
            "web.fetch":        lambda: self._web_fetch(target),
            "shell.restricted": lambda: loop.run_in_executor(None, self._shell, target),
            "memory.read":      lambda: _sync_wrap(self._memory_read, target),
            "memory.write":     lambda: _sync_wrap(self._memory_write, target),
            "memory.delete":    lambda: _sync_wrap(self._memory_delete, target),
            "system.info":      lambda: _sync_wrap(self._system_info),
            "workspace.create":   lambda: _sync_wrap(self._ws_create, target),
            "workspace.inspect":  lambda: _sync_wrap(self._ws_inspect),
            "browser.open":       lambda: self._browser_dispatch("open", target),
            "browser.read":       lambda: self._browser_dispatch("read", target),
            "browser.click":      lambda: self._browser_dispatch("click", target),
            "browser.type":       lambda: self._browser_dispatch("type", target),
            "browser.screenshot": lambda: self._browser_dispatch("screenshot", target),
            "browser.close":      lambda: self._browser_dispatch("close", target),
        }
        fn = dispatch.get(tool)
        if fn is None:
            # Check if it's an MCP tool
            if self.mcp_client and tool.startswith("mcp."):
                return await self._execute_mcp_tool(tool, target, content)
            return str(ToolResult.error(f"Unknown tool: {tool}", error="unknown_tool"))
        result = fn()
        if asyncio.iscoroutine(result):
            return await result
        return await result

    async def _execute_mcp_tool(self, tool_name: str, target: str, content: str = "") -> str:
        """Execute an MCP tool with proper argument handling."""
        try:
            # Parse arguments from target/content
            arguments = {}
            if target:
                arguments["target"] = target
            if content:
                arguments["content"] = content
            
            # Try to parse as JSON if target looks like JSON
            if target and target.strip().startswith("{"):
                try:
                    arguments = json.loads(target)
                except json.JSONDecodeError as e:
                    log.debug(f"suppressed: {e}")
            
            result = await self.mcp_client.execute_tool(tool_name, arguments)
            return result
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"MCP tool execution failed: {e}")
            return f"[MCP ERROR] {tool_name}: {str(e)}"

    def _resolve_path(self, target: str) -> Path:
        if Path(target).is_absolute():
            return Path(target).resolve()
        return (self._ws_root / target).resolve()

    def _fs_read(self, target: str) -> str:
        path = self._resolve_path(target)
        if not path.exists():
            return str(ToolResult.error(f"File not found: {target}", error="not_found"))
        if not path.is_file():
            return str(ToolResult.error(f"Not a file: {target}", error="not_file"))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 8000:
                text = text[:8000] + f"\n...[truncated, {len(text)} total chars]"
            return str(ToolResult.ok(text))
        except (IOError, OSError) as e:
            return str(ToolResult.error(str(e), error=type(e).__name__))

    def _fs_write(self, target: str, content: str) -> str:
        path = self._resolve_path(target)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return str(ToolResult.ok(f"Written {len(content)} chars to {path.name}"))
        except (IOError, OSError) as e:
            return str(ToolResult.error(str(e), error=type(e).__name__))

    def _fs_list(self, target: str) -> str:
        path = self._ws_root if not target or target in (".", "") else self._resolve_path(target)
        if not path.exists():
            return f"[ERROR] Directory not found: {target}"
        try:
            entries = sorted(path.iterdir())[:50]
            lines = [f"  {'/' if e.is_dir() else ''}{e.name}" +
                     (f" ({e.stat().st_size}B)" if e.is_file() else "")
                     for e in entries]
            return "\n".join(lines) or "(empty)"
        except (OSError, PermissionError) as e:
            return f"[ERROR] {e}"

    def _fs_delete(self, target: str) -> str:
        path = self._resolve_path(target)
        if not path.exists():
            return str(ToolResult.error(f"Not found: {target}", error="not_found"))
        path.unlink()
        return str(ToolResult.ok(f"Deleted {path.name}"))

    def _fs_search(self, query: str) -> str:
        try:
            result = subprocess.run(
                ["grep", "-r", "--include=*.txt", "--include=*.md",
                 "-l", query, str(self._ws_root)],
                capture_output=True, text=True, timeout=10
            )
            files = result.stdout.strip().split("\n")
            files = [f for f in files if f]
            return "\n".join(files[:20]) if files else "[SEARCH] No matches"
        except FileNotFoundError:
            matches = []
            for path in self._ws_root.rglob("*"):
                if len(matches) >= 20:
                    break
                if not path.is_file() or path.suffix.lower() not in (".md", ".txt"):
                    continue
                try:
                    if query in path.read_text(encoding="utf-8", errors="replace"):
                        matches.append(str(path))
                except (OSError, UnicodeDecodeError):
                    continue
            return "\n".join(matches) if matches else "[SEARCH] No matches"
        except (OSError, UnicodeDecodeError) as e:
            return f"[ERROR] {e}"

    async def _web_search(self, query: str) -> str:
        try:
            import aiohttp
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status != 200:
                        return f"[SEARCH] HTTP {r.status}"
                    html = await r.text()
                    import re as _re
                    snippets = _re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html)
                    clean = [_re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:5]]
                    return "\n".join(clean) if clean else "[SEARCH] No results"
        except OSError:
            return "[OFFLINE] No internet connection"
        except (aiohttp.ClientError, OSError, ConnectionError) as e:
            return f"[SEARCH ERROR] {e}"

    async def _web_fetch(self, url: str) -> str:
        try:
            import aiohttp, re as _re
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    text = await r.text()
                    clean = _re.sub(r'\s+', ' ', _re.sub(r'<[^>]+>', ' ', text)).strip()
                    return clean[:4000]
        except OSError:
            return "[OFFLINE] Cannot fetch URL"
        except (aiohttp.ClientError, OSError, ConnectionError) as e:
            return f"[FETCH ERROR] {e}"

    def _shell(self, command: str) -> str:
        if not any(re.match(p, command.strip()) for p in SHELL_ALLOWLIST):
            return str(ToolResult.error(f"Command not in allowlist: {command}", error="denied"))
        try:
            import shlex
            try:
                argv = shlex.split(command)
            except ValueError:
                return str(ToolResult.denied("Could not parse command"))
            r = subprocess.run(argv, capture_output=True,
                               text=True, timeout=15, cwd=str(self._ws_root))
            out = (r.stdout + r.stderr)[:4000]
            return out.strip() or "[OK] No output"
        except subprocess.TimeoutExpired:
            return str(ToolResult.error("Command timed out", error="timeout"))
        except (OSError, subprocess.SubprocessError) as e:
            return f"[ERROR] {e}"

    def _memory_read(self, query: str) -> str:
        results = self.memory.recall(query, self.workspace)
        if not results:
            return "[MEMORY] No relevant memories"
        return "\n".join(f"- {r[:150]}" for r in results)

    def _memory_write(self, text: str) -> str:
        mid = self.memory.remember(text, self.workspace, source="agent")
        return f"[MEMORY] Saved (id:{mid})"

    def _memory_delete(self, memory_id: str) -> str:
        self.memory.forget(memory_id, self.workspace)
        return f"[MEMORY] Deleted {memory_id}"

    def _system_info(self) -> str:
        import shutil
        disk_root = Path.cwd().anchor or "/"
        disk = shutil.disk_usage(disk_root)
        ram_used, ram_total = self._memory_usage_gb()
        return (f"Disk: {round(disk.free/1e9,1)}GB free of {round(disk.total/1e9,1)}GB | "
                f"RAM: {ram_used}/{ram_total}GB used")

    def _memory_usage_gb(self) -> tuple[float, float]:
        snap = ram_snapshot_gb()
        return snap.get("used_gb", 0.0), snap.get("total_gb", 0.0)

    def _ws_create(self, name: str) -> str:
        ws = workspace_path(name)
        return f"[OK] Workspace '{name}' created at {ws}"

    def _ws_inspect(self) -> str:
        entries = list(self._ws_root.iterdir()) if self._ws_root.exists() else []
        mem_count = len(self.memory.get_all(self.workspace))
        return f"Workspace: {self.workspace} | Files: {len(entries)} | Memories: {mem_count}"

    async def _browser_dispatch(self, action: str, target: str = "") -> str:
        """Route browser.* tool calls through the Playwright adapter (Phase 13).

        Falls back gracefully when Playwright is not installed or browser is
        disabled in config — the test suite exercises this path.
        """
        try:
            from adapters.browser.session_manager import get as get_session
            session = await get_session(self._workspace_id)
            if session is None:
                return "[browser disabled] Set browser.enabled=true in config to use browser tools."
            if action == "open":
                return await session.goto(target)
            elif action == "read":
                return await session.inner_text("body")
            elif action == "click":
                return await session.click(target)
            elif action == "type":
                return await session.type(target)
            elif action == "screenshot":
                path = self._ws_root / "screenshot.png"
                return await session.screenshot(str(path))
            elif action == "close":
                await session.close()
                return "[browser] session closed"
            else:
                return f"[ERROR] Unknown browser action: {action}"
        except (OSError, RuntimeError, TimeoutError) as e:
            return f"[browser error] {e}"
