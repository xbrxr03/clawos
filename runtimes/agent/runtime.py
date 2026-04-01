"""
ClawOS Agent Runtime — Nexus
==================================
ReAct (Reason + Act) loop. All competitive upgrades from S1 research:
  - json_repair parsing (Nanobot)
  - Token-aware context: dynamic info in user msg (Nanobot PR #1704)
  - 4-layer memory injection (Nanobot + MemOS)
  - Agent tool filtering (OpenFang #532)
  - SOUL.md + AGENTS.md workspace personality
  - Skill loader (skilld) — SKILL.md packages from ~/.claw/skills + ~/.openclaw/skills
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from clawos_core.constants import DEFAULT_MODEL, OLLAMA_HOST, MAX_ITERATIONS, MAX_HISTORY, DEFAULT_WORKSPACE
from clawos_core.util.ids import task_id, session_id
from clawos_core.models import Session
from runtimes.agent.prompts import SYSTEM_PROMPT, build_user_message
from runtimes.agent.parser import parse_response
from services.skilld.service import get_loader, format_skills_block

log = logging.getLogger("agentd")

try:
    import ollama as _ollama_lib
    OLLAMA_OK = True
except ImportError:
    OLLAMA_OK = False


async def _call_llm(messages: list, model: str) -> str:
    if not OLLAMA_OK:
        raise RuntimeError("ollama not installed: pip install ollama")
    loop = asyncio.get_event_loop()
    def _sync():
        client = _ollama_lib.Client(host=OLLAMA_HOST)
        resp   = client.chat(model=model, messages=messages,
                             options={"temperature": 0.3, "num_ctx": 4096})
        return resp["message"]["content"]
    return await loop.run_in_executor(None, _sync)


class AgentRuntime:
    """
    Single agent session. One per workspace/contact.
    """

    # Short inputs that should NOT trigger memory recall or skill scoring
    _SKIP_INPUTS = {
        "ok", "okay", "k", "yes", "no", "sure", "thanks", "thank you",
        "hi", "hello", "hey", "good", "great", "nice", "cool", "got it",
        "done", "alright", "yep", "nope", "please", "go ahead", "continue",
    }

    def __init__(self, workspace_id: str = DEFAULT_WORKSPACE,
                 model: str = DEFAULT_MODEL,
                 memory=None, tool_bridge=None, policy_client=None):
        self.workspace_id  = workspace_id
        self.model         = model
        self.memory        = memory
        self.bridge        = tool_bridge
        self.policy        = policy_client
        self.session       = Session(workspace_id=workspace_id)
        self._history:     list = []
        self._turn:        int  = 0
        self._skills       = get_loader()

    def _build_system_prompt(self) -> str:
        """Static system prompt + SOUL.md + AGENTS.md + tool list.
        No dynamic fields here — keeps this static for prompt cache hits."""
        parts = [SYSTEM_PROMPT]
        if self.memory:
            soul   = self.memory.read_soul(self.workspace_id)
            agents = self.memory.read_agents(self.workspace_id)
            if soul:
                parts.append(f"## Your Character (SOUL)\n{soul.strip()}")
            if agents:
                parts.append(f"## Operating Instructions (AGENTS)\n{agents.strip()}")
        if self.bridge:
            tool_list = self.bridge.get_tool_list_for_prompt()
            if tool_list:
                parts.append(tool_list)
        return "\n\n".join(parts)

    def _is_trivial(self, user_input: str) -> bool:
        """True for greetings/acks that should skip recall and skill scoring."""
        stripped = user_input.strip().lower().rstrip("!.,?")
        return stripped in self._SKIP_INPUTS or len(user_input.split()) <= 2

    def _get_memory_context(self, user_input: str) -> str:
        if not self.memory or self._is_trivial(user_input):
            return ""
        return self.memory.build_context_block(user_input, self.workspace_id)

    def _get_skills_block(self, user_input: str) -> str:
        """Score skills against this input and return the injection block.
        Empty string for trivial inputs — no point loading skills for 'ok'."""
        if self._is_trivial(user_input) or self._skills.count == 0:
            return ""
        top = self._skills.top(user_input)
        return format_skills_block(top)

    def _get_rag_context(self, user_input: str) -> str:
        """
        Query the workspace RAG index for relevant document chunks.
        Returns formatted context block with citations, or empty string
        if no documents are indexed or no relevant chunks found.
        """
        if self._is_trivial(user_input):
            return ""
        try:
            from pathlib import Path
            from services.ragd.service import get_rag
            ws_root = Path.home() / "clawos" / "workspace" / self.workspace_id
            rag     = get_rag(self.workspace_id, ws_root)
            # Only query if there are ingested docs
            s = rag.stats()
            if s.get("documents", 0) == 0:
                return ""
            results = rag.retrieve(user_input)
            if not results:
                return ""
            lines = ["[Project Documents]"]
            for i, r in enumerate(results, 1):
                lines.append(
                    f"[{i}] {r['title']} p.{r['page']} ({r['chunk_type']}): "
                    f"{r['content'][:300]}"
                )
            return "\n".join(lines)
        except Exception:
            return ""

    async def chat(self, user_input: str) -> str:
        self._turn       += 1
        self.session.turn = self._turn

        sys_prompt  = self._build_system_prompt()
        mem_ctx     = self._get_memory_context(user_input)
        skills_block = self._get_skills_block(user_input)

        rag_ctx  = self._get_rag_context(user_input)
        learned_ctx = self._get_learned_context()
        user_msg = build_user_message(
            user_input, self.session.session_id, self._turn,
            mem_ctx, skills_block, rag_ctx, learned_ctx
        )

        trimmed   = self._history[-(MAX_HISTORY * 2):]
        messages  = ([{"role": "system", "content": sys_prompt}]
                     + trimmed
                     + [{"role": "user", "content": user_msg}])

        # Async memory write — never block the agent loop
        if self.memory:
            asyncio.create_task(
                self.memory.remember_async(f"User: {user_input}",
                                           self.workspace_id, source="user")
            )

        tool_results = []

        for _ in range(MAX_ITERATIONS):
            try:
                raw = await _call_llm(messages, self.model)
            except RuntimeError as e:
                return f"Could not reach language model: {e}"

            parsed = parse_response(raw)

            if "final_answer" in parsed:
                answer = str(parsed["final_answer"]).strip()
                self._history.append({"role": "user",      "content": user_input})
                self._history.append({"role": "assistant",  "content": answer})
                if self.memory:
                    asyncio.create_task(
                        self.memory.remember_async(f"Nexus: {answer}",
                                                   self.workspace_id, source="agent")
                    )
                return answer

            if "parse_error" in parsed:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content":
                    'Use valid JSON: {"final_answer": "..."} or {"action": "...", "action_input": "..."}'})
                continue

            if "action" in parsed:
                tool    = str(parsed.get("action", ""))
                target  = str(parsed.get("action_input", ""))
                content = str(parsed.get("content", ""))
                result  = (await self.bridge.run(tool, target, content=content)
                           if self.bridge else "[ERROR] No tool bridge")
                tool_results.append(f"{tool}({target[:40]})")
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user",      "content": f"Observation: {result}"})
                continue

            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                'Use the JSON format: {"final_answer": "..."} or {"action": "...", "action_input": "..."}'})

        fallback = ("Reached max reasoning steps. " +
                    (f"Found: {'; '.join(tool_results)}." if tool_results else "Try rephrasing."))
        self._history.append({"role": "user",      "content": user_input})
        self._history.append({"role": "assistant",  "content": fallback})
        return fallback

    async def reset(self):
        self._history.clear()
        self._turn    = 0
        self.session  = Session(workspace_id=self.workspace_id)
        if self.memory:
            self.memory.clear_workflow(self.workspace_id)


    async def _run_ace(self, task_result: str):
        """ACE self-improving loop — extract learnings after task completion."""
        try:
            from services.memd.service import run_ace_loop
            await run_ace_loop(task_result, self.workspace_id)
        except Exception:
            pass


async def build_runtime(workspace_id: str = DEFAULT_WORKSPACE,
                        model: str = DEFAULT_MODEL) -> "AgentRuntime":
    """Build a fully wired AgentRuntime with all services."""
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from services.memd.service                import MemoryService
    from services.toolbridge.service           import ToolBridge
    from adapters.policy.local_policy_adapter  import LocalPolicyAdapter
    from clawos_core.config.loader             import get

    memory = MemoryService()
    policy = LocalPolicyAdapter(
        workspace_id  = workspace_id,
        task_id       = task_id(),
        granted_tools = get("policy.default_grants",
                            ["fs.read", "fs.write", "fs.list",
                             "web.search", "memory.read", "memory.write"]),
    )
    bridge = ToolBridge(policy_client=policy, memory_service=memory,
                        workspace_id=workspace_id)
    return AgentRuntime(workspace_id=workspace_id, model=model,
                        memory=memory, tool_bridge=bridge, policy_client=policy)
