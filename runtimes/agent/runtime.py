# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Agent Runtime — Nexus
==================================
Native Ollama function-calling agent loop.

4-tier priority pipeline (Nexus Windows pattern):
  1. Memory fast-path  — short recall queries answered from memd directly
  2. Confirmation      — pending approval responses ("yes", "no")
  3. Deterministic     — regex intent classifier (greetings, app open, volume,
                          reminders, time, simple recall) → no LLM
  4. LLM with tools    — native Ollama tool_calls; multi-tool turns supported

Per-turn dynamic model routing: 3b / 7b / coder-7b based on input + tools.
Memory injection (PINNED, LEARNED, semantic recall, RAG, skills) preserved
from the previous runtime — assembled into the user message, not the system
prompt, so the system prompt stays cache-friendly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from clawos_core.constants import (
    DEFAULT_MODEL, OLLAMA_HOST, MAX_ITERATIONS, MAX_HISTORY, DEFAULT_WORKSPACE,
)
from clawos_core.util.ids import task_id, session_id  # noqa: F401
from clawos_core.models import Session
from runtimes.agent.prompts import build_user_message
from runtimes.agent.intents import Intent, classify
from runtimes.agent.router import pick_model, FAST_MODEL, SMART_MODEL
from runtimes.agent.tool_schemas import (
    ALL_TOOLS, SENSITIVE_TOOLS, schemas_for_tier,
)
from services.skilld.service import get_loader, format_skills_block

log = logging.getLogger("agentd")

try:
    import ollama as _ollama_lib
    OLLAMA_OK = True
except ImportError:
    OLLAMA_OK = False


# ── system prompt (static, cache-friendly) ───────────────────────────────────

SYSTEM_PROMPT = """\
You are Nexus, a local AI assistant running on ClawOS.
You run entirely on this machine — offline, private, no cloud, no API keys.
You are helpful, concise, and direct.

How to behave:
- For simple questions, answer directly without using tools.
- When a task needs a tool, call it. If multiple tools are needed, call them
  all in the same response when they are independent.
- Keep replies under 3 sentences unless the user asks for length explicitly,
  or you are presenting tool results that need detail.
- If a tool returns an error or [DENIED], acknowledge it gracefully and
  suggest an alternative if you can think of one.
- Never invent file contents, search results, or facts you don't have.
- If <available_skills> are provided in the user message, use them to inform
  your answer.
- For multi-step tasks (e.g. "write an essay and paste it into Notepad"),
  call the tools in order: generate the content, put it on the clipboard,
  open the target app, then paste.
- After all tool calls finish, give a short natural-language summary of what
  was done. Address the user as "sir" only if they prefer the JARVIS persona.
"""


# ── helpers ──────────────────────────────────────────────────────────────────

def _ollama_client():
    if not OLLAMA_OK:
        raise RuntimeError("ollama not installed: pip install ollama")
    return _ollama_lib.Client(host=OLLAMA_HOST)


async def _call_llm_native(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    temperature: float = 0.3,
    num_ctx: int = 4096,
) -> dict:
    """
    Call Ollama with native tool support. Returns the assistant message dict
    which may include `content` and/or `tool_calls`.
    """
    loop = asyncio.get_event_loop()

    def _sync():
        client = _ollama_client()
        kwargs: dict[str, Any] = {
            "model":    model,
            "messages": messages,
            "options":  {"temperature": temperature, "num_ctx": num_ctx},
        }
        if tools:
            kwargs["tools"] = tools
        resp = client.chat(**kwargs)
        # ollama-python returns either dict or pydantic-ish object; normalise.
        msg = resp["message"] if isinstance(resp, dict) else resp.message
        if not isinstance(msg, dict):
            msg = {
                "role":       getattr(msg, "role", "assistant"),
                "content":    getattr(msg, "content", "") or "",
                "tool_calls": getattr(msg, "tool_calls", None) or [],
            }
        return msg

    return await loop.run_in_executor(None, _sync)


def _short_text(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


# ── runtime ──────────────────────────────────────────────────────────────────

class AgentRuntime:
    """Single agent session (one per workspace/contact)."""

    _SKIP_INPUTS = {
        "ok", "okay", "k", "yes", "no", "sure", "thanks", "thank you",
        "hi", "hello", "hey", "good", "great", "nice", "cool", "got it",
        "done", "alright", "yep", "nope", "please", "go ahead", "continue",
    }

    def __init__(
        self,
        workspace_id: str = DEFAULT_WORKSPACE,
        model: str = DEFAULT_MODEL,
        memory=None,
        tool_bridge=None,
        policy_client=None,
    ):
        self.workspace_id = workspace_id
        self.model        = model
        self.memory       = memory
        self.bridge       = tool_bridge
        self.policy       = policy_client
        self.session      = Session(workspace_id=workspace_id)
        self._history: list[dict] = []
        self._turn = 0
        self._skills = get_loader()
        # Awaiting-confirmation state. Set when a pending [PENDING APPROVAL]
        # comes back from the bridge — next user input may be "yes/no".
        self._awaiting_confirmation: dict | None = None

    # ── trivial classification ──────────────────────────────────────────

    def _is_trivial(self, user_input: str) -> bool:
        stripped = user_input.strip().lower().rstrip("!.,?")
        return stripped in self._SKIP_INPUTS or len(user_input.split()) <= 2

    # ── context assembly ────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        parts = [SYSTEM_PROMPT]
        if self.memory:
            soul   = self.memory.read_soul(self.workspace_id)
            agents = self.memory.read_agents(self.workspace_id)
            if soul:   parts.append(f"## Your Character (SOUL)\n{soul.strip()}")
            if agents: parts.append(f"## Operating Instructions (AGENTS)\n{agents.strip()}")
            identity = self._read_identity()
            if identity: parts.append(f"## Identity (IDENTITY)\n{identity.strip()}")
        return "\n\n".join(parts)

    def _read_identity(self) -> str:
        try:
            from clawos_core.util.paths import memory_path
            p = memory_path(self.workspace_id) / "IDENTITY.md"
            if p.exists():
                return p.read_text(encoding="utf-8")
        except Exception:
            pass
        return ""

    def _get_memory_context(self, user_input: str) -> str:
        if not self.memory or self._is_trivial(user_input):
            return ""
        try:
            return self.memory.build_context_block(user_input, self.workspace_id)
        except Exception:
            return ""

    def _get_skills_block(self, user_input: str) -> str:
        if self._is_trivial(user_input) or self._skills.count == 0:
            return ""
        try:
            top = self._skills.top(user_input)
            return format_skills_block(top)
        except Exception:
            return ""

    def _get_learned_context(self) -> str:
        try:
            from services.memd.service import get_learned
            return get_learned(self.workspace_id)
        except Exception:
            return ""

    def _get_rag_context(self, user_input: str) -> str:
        if self._is_trivial(user_input):
            return ""
        try:
            from services.ragd.service import get_rag
            ws_root = Path.home() / "clawos" / "workspace" / self.workspace_id
            rag = get_rag(self.workspace_id, ws_root)
            if rag.stats().get("documents", 0) == 0:
                return ""
            results = rag.retrieve(user_input)
            if not results:
                return ""
            lines = ["[Project Documents]"]
            for i, r in enumerate(results, 1):
                lines.append(f"[{i}] {r['title']} p.{r['page']} ({r['chunk_type']}): {r['content'][:300]}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_kizuna_context(self, user_input: str) -> str:
        """Kizuna knowledge graph — entity-anchored facts for the query."""
        if self._is_trivial(user_input):
            return ""
        try:
            from services.memd.service import query_graph
            # Pull the most prominent noun-ish tokens (cheap heuristic)
            words = [w for w in user_input.split() if len(w) > 3 and w[0].isalpha()]
            if not words:
                return ""
            # Hit graph for top 2 candidate entities; merge results
            chunks: list[str] = []
            for w in words[:2]:
                try:
                    g = query_graph(w.strip(".,!?"), self.workspace_id, depth=1)
                except Exception:
                    g = ""
                if g and g.strip():
                    chunks.append(g.strip())
            return ("[Knowledge Graph]\n" + "\n".join(chunks)) if chunks else ""
        except Exception:
            return ""

    def _history_tokens(self) -> int:
        # Rough: 4 chars per token. Used by router only.
        return sum(len(m.get("content") or "") for m in self._history) // 4

    # ── tier-1: memory fast-path ────────────────────────────────────────

    async def _try_memory_fast_path(self, user_input: str) -> str | None:
        """
        For "what did I tell you about X" type queries, hit memd directly
        and return a short formed answer. Returns None to fall through.
        """
        match = classify(user_input)
        if match.intent != Intent.MEMORY_RECALL:
            return None
        if not self.memory:
            return None
        topic = match.args.get("topic", "")
        try:
            hits = self.memory.recall(topic, self.workspace_id, n=3)
        except Exception:
            return None
        if not hits:
            return None
        # Concise reply. We could route to the LLM for prettier phrasing, but
        # the fast-path's whole point is no-LLM speed.
        lines = [f"From memory about {topic!r}:"]
        for h in hits[:3]:
            lines.append(f"- {_short_text(h, 220)}")
        return "\n".join(lines)

    # ── tier-2: pending-confirmation responses ──────────────────────────

    async def _try_confirmation_response(self, user_input: str) -> str | None:
        """
        If we're awaiting confirmation from a previous turn and this input is
        clearly yes/no, resolve the pending approval and return the result.
        """
        if not self._awaiting_confirmation:
            return None
        s = user_input.strip().lower().rstrip(".!?")
        approve = s in {"yes", "y", "yep", "yeah", "ok", "okay", "sure", "approve", "do it", "go ahead", "confirm"}
        deny    = s in {"no", "n", "nope", "cancel", "stop", "abort", "deny", "don't", "do not"}
        if not (approve or deny):
            return None
        pending = self._awaiting_confirmation
        self._awaiting_confirmation = None
        if deny:
            return f"Cancelled — {pending.get('description', 'task')} not executed."
        # Approve: re-run the tool now that policy will see it as approved.
        # We resolve via policy client so the queued request is marked allowed.
        try:
            req_id = pending.get("request_id")
            if req_id and self.policy and hasattr(self.policy, "resolve"):
                await self.policy.resolve(req_id, allow=True)
        except Exception:
            pass
        # Re-execute the tool with the bridge — it should now pass policy.
        tool = pending["tool"]
        args = pending["args"]
        result = await self._exec_tool(tool, args)
        return f"Done. {_short_text(str(result), 200)}"

    # ── tier-3: deterministic intents ───────────────────────────────────

    async def _try_deterministic(self, user_input: str) -> str | None:
        """
        Handle clearly-deterministic intents without invoking the LLM.
        Returns a final-answer string, or None to fall through to the LLM.
        """
        match = classify(user_input)
        if match.intent == Intent.LLM_NEEDED:
            return None

        if match.intent == Intent.GREETING:
            return "Hello. How can I help?"

        if match.intent == Intent.ACK:
            return "Acknowledged."

        if match.intent == Intent.TIME_QUERY:
            r = await self._exec_tool("get_time", {})
            return str(r) if r else "I couldn't read the system clock."

        if match.intent == Intent.VOLUME_SET:
            args = match.args
            if "level" in args:
                r = await self._exec_tool("set_volume", {"level": args["level"]})
                return f"Volume set to {args['level']}%." if r else "Couldn't set the volume."
            direction = args.get("direction")
            if direction in ("up", "down"):
                cur = await self._exec_tool("get_volume", {})
                try:
                    cur_level = int(str(cur).strip().rstrip("%"))
                except Exception:
                    cur_level = 50
                step = 10 if direction == "up" else -10
                new_level = max(0, min(100, cur_level + step))
                await self._exec_tool("set_volume", {"level": new_level})
                return f"Volume {direction} — now {new_level}%."
            if direction in ("mute", "unmute"):
                level = 0 if direction == "mute" else 50
                await self._exec_tool("set_volume", {"level": level})
                return f"{direction.capitalize()}d."
            return None

        if match.intent == Intent.APP_OPEN:
            r = await self._exec_tool("open_app", {"name": match.args.get("app", "")})
            return f"Opening {match.args.get('app')}." if r else f"Couldn't open {match.args.get('app')}."

        if match.intent == Intent.REMINDER_LIST:
            r = await self._exec_tool("list_reminders", {})
            return str(r) if r else "No upcoming reminders."

        if match.intent == Intent.REMINDER_ADD:
            args = match.args
            r = await self._exec_tool("add_reminder", {
                "task": args.get("task", ""),
                "when": args.get("when", "") or "in 1 hour",
            })
            return f"Reminder set: {args.get('task')} — {args.get('when') or 'in 1 hour'}."

        if match.intent == Intent.MORNING_BRIEFING:
            try:
                from runtimes.agent.briefing import morning_briefing
                return await morning_briefing(self)
            except ImportError:
                return None

        return None

    # ── tier-4: LLM with native tool calling ────────────────────────────

    async def _llm_turn(self, user_input: str) -> str:
        """Full LLM turn with native tool calling and multi-step support."""
        self._turn += 1
        self.session.turn = self._turn

        sys_prompt   = self._build_system_prompt()
        mem_ctx      = self._get_memory_context(user_input)
        skills_block = self._get_skills_block(user_input)
        rag_ctx      = self._get_rag_context(user_input)
        learned_ctx  = self._get_learned_context()
        kg_ctx       = self._get_kizuna_context(user_input)

        # Apply token budget — preserves priority order, trims the tail.
        from runtimes.agent.context_budget import fit_blocks, DEFAULT_BUDGET_TOKENS
        budgeted = fit_blocks(
            [
                ("memory",   mem_ctx),
                ("learned",  learned_ctx),
                ("graph",    kg_ctx),
                ("rag",      rag_ctx),
                ("skills",   skills_block),
            ],
            budget_tokens=DEFAULT_BUDGET_TOKENS,
        )
        block_map = {label: text for label, text in budgeted}

        user_msg = build_user_message(
            user_input, self.session.session_id, self._turn,
            block_map.get("memory", ""),
            block_map.get("skills", ""),
            block_map.get("rag", ""),
            # learned + graph share the "learned" slot via concatenation
            (block_map.get("learned", "") + ("\n\n" + block_map["graph"] if "graph" in block_map else "")).strip(),
        )

        trimmed = self._history[-(MAX_HISTORY * 2):]
        messages = (
            [{"role": "system", "content": sys_prompt}]
            + trimmed
            + [{"role": "user", "content": user_msg}]
        )

        # Async memory write — never block the agent loop
        if self.memory:
            asyncio.create_task(
                self.memory.remember_async(f"User: {user_input}", self.workspace_id, source="user")
            )

        # Pick model + tools for this turn
        granted = set(self._granted_tool_names())
        decision = pick_model(user_input, history_tokens=self._history_tokens())
        tools = schemas_for_tier(decision.tier, granted)
        log.debug(f"turn {self._turn}: model={decision.model} ({decision.reason}), tools={len(tools)}")

        executed: list[dict] = []
        final_text = ""

        for iteration in range(MAX_ITERATIONS):
            try:
                msg = await _call_llm_native(messages, decision.model, tools=tools)
            except RuntimeError as e:
                return f"Could not reach language model: {e}"

            content    = (msg.get("content") or "").strip()
            tool_calls = msg.get("tool_calls") or []

            # Append assistant turn to history regardless
            messages.append({
                "role":       "assistant",
                "content":    content,
                "tool_calls": tool_calls or None,
            })

            if not tool_calls:
                # Final answer
                final_text = content or "Done."
                break

            # Execute every tool call in this batch. Independent calls run
            # concurrently — the planner can mark dependencies in future work.
            results = await self._exec_tool_batch(tool_calls)
            for call, result in zip(tool_calls, results):
                fn   = call.get("function") or {}
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except Exception: args = {}
                executed.append({"tool": name, "args": args, "result": result})
                # Track pending approvals so the next turn can resolve them
                if isinstance(result, str) and result.startswith("[PENDING APPROVAL]"):
                    self._awaiting_confirmation = {
                        "tool":        name,
                        "args":        args,
                        "description": f"{name}({_short_text(json.dumps(args), 60)})",
                        "request_id":  None,  # populated by policy event subscriber
                    }
                # Append tool message so the model sees the result next turn
                messages.append({
                    "role":      "tool",
                    "tool_name": name,
                    "content":   _short_text(str(result), 4000),
                })

            # If any call is awaiting approval, stop the loop and tell user
            if self._awaiting_confirmation:
                pend = self._awaiting_confirmation
                final_text = (
                    f"I need your approval to run **{pend['tool']}** "
                    f"({_short_text(json.dumps(pend['args']), 80)}). "
                    f"Reply yes or no."
                )
                break

            # Otherwise loop — the model will see tool results and decide next step
        else:
            # Hit MAX_ITERATIONS — synthesize a fallback
            final_text = (
                f"Reached step limit. Tools used: "
                f"{', '.join(s['tool'] for s in executed) or 'none'}."
            )

        # Persist conversation tail
        self._history.append({"role": "user", "content": user_input})
        self._history.append({"role": "assistant", "content": final_text})

        # Async post-turn writes
        if self.memory:
            asyncio.create_task(
                self.memory.remember_async(f"Nexus: {final_text}", self.workspace_id, source="agent")
            )
        if not self._is_trivial(user_input) and len(final_text) > 80:
            asyncio.create_task(self._run_ace(f"Task: {user_input}\nAnswer: {final_text}"))

        return final_text

    # ── tool execution ──────────────────────────────────────────────────

    def _granted_tool_names(self) -> list[str]:
        """Tools the policy currently grants. Falls back to ALL_TOOLS keys."""
        if self.policy and getattr(self.policy, "granted_tools", None):
            return list(self.policy.granted_tools)
        return list(ALL_TOOLS.keys())

    async def _exec_tool(self, name: str, args: dict) -> Any:
        """Execute a single tool through the bridge. Returns raw result."""
        if not self.bridge:
            return "[ERROR] No tool bridge"
        if hasattr(self.bridge, "run_native"):
            return await self.bridge.run_native(name, args)
        # Legacy fallback: marshal into the old (target, content) signature.
        target = args.get("path") or args.get("name") or args.get("query") or args.get("text") or ""
        content = args.get("content") or ""
        return await self.bridge.run(name, str(target), content=str(content))

    async def _exec_tool_batch(self, tool_calls: list[dict]) -> list[Any]:
        """Run a batch of tool calls concurrently."""
        async def _one(call):
            fn   = call.get("function") or {}
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try: args = json.loads(args)
                except Exception: args = {}
            try:
                return await self._exec_tool(name, args)
            except Exception as e:
                return f"[ERROR] {name}: {e}"
        return await asyncio.gather(*[_one(c) for c in tool_calls])

    # ── public API ──────────────────────────────────────────────────────

    async def chat(self, user_input: str) -> str:
        """
        Main entry point. Runs the 4-tier priority pipeline.
        Returns a final-answer string ready for display or TTS.
        """
        # Tier 2: pending confirmation — check this FIRST so a "yes" right
        # after a sensitive request resolves it instead of being classified
        # as an ack.
        r = await self._try_confirmation_response(user_input)
        if r is not None:
            self._history.append({"role": "user", "content": user_input})
            self._history.append({"role": "assistant", "content": r})
            return r

        # Tier 1: memory fast-path
        r = await self._try_memory_fast_path(user_input)
        if r is not None:
            self._history.append({"role": "user", "content": user_input})
            self._history.append({"role": "assistant", "content": r})
            return r

        # Tier 3: deterministic intents
        r = await self._try_deterministic(user_input)
        if r is not None:
            self._history.append({"role": "user", "content": user_input})
            self._history.append({"role": "assistant", "content": r})
            return r

        # Tier 4: full LLM turn
        return await self._llm_turn(user_input)

    async def chat_with_steps(self, user_input: str) -> dict:
        """Like chat() but returns tool_steps for UI display."""
        # Run through the same pipeline; we capture executed tools via a
        # lightweight observer pattern — collect from history changes. For
        # the deterministic and fast-path tiers, no tool steps are surfaced
        # (they ran inside the tier-3 handlers).
        before_turn = self._turn
        reply = await self.chat(user_input)
        # If turn advanced, the LLM ran — no separate step list (yet); for now
        # we return an empty steps list. A future revision can wire an emitter
        # into _exec_tool_batch.
        steps_used = self._turn > before_turn
        return {"reply": reply, "tool_steps": [], "llm_used": steps_used}

    async def reset(self):
        self._history.clear()
        self._turn = 0
        self.session = Session(workspace_id=self.workspace_id)
        self._awaiting_confirmation = None
        if self.memory:
            try: self.memory.clear_workflow(self.workspace_id)
            except Exception: pass

    async def _run_ace(self, task_result: str):
        """
        Post-task background work:
          1. ACE self-improving loop  → writes LEARNED.md
          2. Kizuna graph write-back  → adds entities/relations to memd's KG
        Fire-and-forget; failures must never break the user-facing reply.
        """
        try:
            from services.memd.service import run_ace_loop
            await run_ace_loop(task_result, self.workspace_id)
        except Exception:
            pass
        try:
            from services.memd.service import add_to_graph
            add_to_graph(task_result, self.workspace_id, source="agent_task")
        except Exception:
            pass


# ── factory ──────────────────────────────────────────────────────────────────

async def build_runtime(
    workspace_id: str = DEFAULT_WORKSPACE,
    model: str = DEFAULT_MODEL,
) -> AgentRuntime:
    """Build a fully wired AgentRuntime with all services."""
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from services.memd.service              import MemoryService
    from services.toolbridge.service        import ToolBridge
    from adapters.policy.local_policy_adapter import LocalPolicyAdapter
    from clawos_core.config.loader          import get

    memory = MemoryService()
    policy = LocalPolicyAdapter(
        workspace_id  = workspace_id,
        task_id       = task_id(),
        granted_tools = get(
            "policy.default_grants",
            list(ALL_TOOLS.keys()),  # default: grant everything; user policy can narrow
        ),
    )
    bridge = ToolBridge(
        policy_client   = policy,
        memory_service  = memory,
        workspace_id    = workspace_id,
    )
    return AgentRuntime(
        workspace_id = workspace_id,
        model        = model,
        memory       = memory,
        tool_bridge  = bridge,
        policy_client = policy,
    )
