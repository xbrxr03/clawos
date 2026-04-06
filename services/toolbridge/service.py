# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS toolbridge — Tool Execution
====================================
Every tool call is gated through policyd. No exceptions.
Resolve relative paths to absolute BEFORE policyd check.
Agent tool filtering: only inject granted tools into system prompt.
"""
import asyncio
import logging
import re
import subprocess
from pathlib import Path

from clawos_core.constants import CLAWOS_DIR
from clawos_core.platform import ram_snapshot_gb
from clawos_core.util.paths import workspace_path

log = logging.getLogger("toolbridge")

SHELL_ALLOWLIST = [
    r'^ls(\s|$)', r'^pwd$', r'^echo\s', r'^cat\s', r'^head\s', r'^tail\s',
    r'^wc\s', r'^find\s', r'^grep\s', r'^which\s', r'^whoami$', r'^date$',
    r'^df\s', r'^du\s', r'^uname', r'^hostname$', r'^ps\s',
    r'^python3?\s', r'^pip\s', r'^git\s',
]

TOOL_ALIASES = {
    "shell.run": "shell.restricted",
}

ALL_TOOL_DESCRIPTIONS = {
    "fs.read":          "Read a file. Input: path relative to workspace.",
    "fs.write":         "Write content to a file. Input: filename + content field.",
    "fs.list":          "List files in a directory. Input: directory path.",
    "fs.delete":        "Delete a file. Requires approval.",
    "fs.search":        "Search files by content. Input: query string.",
    "web.search":       "Search the web. Input: search query.",
    "web.fetch":        "Fetch a URL. Input: full URL.",
    "shell.restricted": "Run allowlisted shell command. Alias: shell.run. Input: command string.",
    "memory.read":      "Search memory. Input: query string.",
    "memory.write":     "Save to memory. Input: text to remember.",
    "memory.delete":    "Delete a memory. Input: memory_id.",
    "system.info":      "Get system info: disk, RAM, services.",
    "workspace.create": "Create a new workspace. Input: workspace name.",
    "workspace.inspect":"Inspect workspace contents and memory summary.",
}


class ToolBridge:
    def __init__(self, policy_client, memory_service, workspace_id: str):
        self.policy    = policy_client
        self.memory    = memory_service
        self.workspace = workspace_id
        self._workspace_id = workspace_id
        self._ws_root  = workspace_path(workspace_id)

    @property
    def _ws_root_fresh(self):
        from clawos_core.util.paths import workspace_path
        return workspace_path(self._workspace_id)

    def get_tool_list_for_prompt(self) -> str:
        """Only inject granted tools — reduces tokens by 30-60%."""
        granted = set(self.policy.granted_tools)
        available = {k: v for k, v in ALL_TOOL_DESCRIPTIONS.items() if k in granted}
        if not available:
            return ""
        lines = [
            "## Available Tools",
            'Use JSON: {"action": "<tool>", "action_input": "<target>"}',
            'For writes: {"action": "fs.write", "action_input": "file.txt", "content": "..."}',
            "",
        ]
        for tool, desc in available.items():
            lines.append(f"- **{tool}**: {desc}")
        return "\n".join(lines)

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
            return f"[DENIED] {reason}"
        if decision == "QUEUE":
            return f"[PENDING APPROVAL] {normalized_tool}({target})"

        try:
            result = await self._execute(normalized_tool, target, content)
        except Exception as e:
            result = f"[ERROR] {normalized_tool} failed: {e}"
            log.error(f"Tool error: {normalized_tool}({target[:40]}): {e}")

        # AfterToolCall hooks
        try:
            ctx = {"workspace_id": self.workspace, "task_id": self.policy.task_id}
            await self.policy._get_engine().hooks.run_after(normalized_tool, target, result, ctx)
        except Exception:
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
            "workspace.create": lambda: _sync_wrap(self._ws_create, target),
            "workspace.inspect":lambda: _sync_wrap(self._ws_inspect),
        }
        fn = dispatch.get(tool)
        if fn is None:
            return f"[ERROR] Unknown tool: {tool}"
        result = fn()
        if asyncio.iscoroutine(result):
            return await result
        return await result

    def _resolve_path(self, target: str) -> Path:
        if Path(target).is_absolute():
            return Path(target).resolve()
        return (self._ws_root / target).resolve()

    def _fs_read(self, target: str) -> str:
        path = self._resolve_path(target)
        if not path.exists():
            return f"[ERROR] File not found: {target}"
        if not path.is_file():
            return f"[ERROR] Not a file: {target}"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 8000:
                text = text[:8000] + f"\n...[truncated, {len(text)} total chars]"
            return text
        except Exception as e:
            return f"[ERROR] {e}"

    def _fs_write(self, target: str, content: str) -> str:
        path = self._resolve_path(target)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"[OK] Written {len(content)} chars to {path.name}"
        except Exception as e:
            return f"[ERROR] {e}"

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
        except Exception as e:
            return f"[ERROR] {e}"

    def _fs_delete(self, target: str) -> str:
        path = self._resolve_path(target)
        if not path.exists():
            return f"[ERROR] Not found: {target}"
        path.unlink()
        return f"[OK] Deleted {path.name}"

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
                except Exception:
                    continue
            return "\n".join(matches) if matches else "[SEARCH] No matches"
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
            return f"[FETCH ERROR] {e}"

    def _shell(self, command: str) -> str:
        if not any(re.match(p, command.strip()) for p in SHELL_ALLOWLIST):
            return f"[DENIED] Command not in allowlist: {command}"
        try:
            import shlex
            try:
                argv = shlex.split(command)
            except ValueError:
                return "[DENIED] Could not parse command"
            r = subprocess.run(argv, capture_output=True,
                               text=True, timeout=15, cwd=str(self._ws_root))
            out = (r.stdout + r.stderr)[:4000]
            return out.strip() or "[OK] No output"
        except subprocess.TimeoutExpired:
            return "[ERROR] Command timed out"
        except Exception as e:
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
