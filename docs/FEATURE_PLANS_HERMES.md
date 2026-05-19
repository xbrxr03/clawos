# ClawOS Feature Plans — Hermes-Agent Inspired Improvements

> Derived from analysis of [NousResearch/hermes-agent](https://github.com/NousResearch/Hermes-Agent) (154K★).
> These are implementation specs, not code. Each plan is a GitHub Issue ready to be created.

---

## P0-1: Auto-Skill Creation from Successful Tasks

### Problem
ClawOS has `skilld` (BM25 retrieval) and `ace` (LEARNED.md self-improvement), but no loop that detects "I just did something complex and repeatable" and auto-generates a SKILL.md. Users must write skills manually.

### Goal
After a multi-tool, multi-turn task completes successfully, the agent should:
1. Detect that the task was complex enough to warrant a skill (≥3 tool calls OR ≥2 turns)
2. Prompt itself to generate a SKILL.md summarizing the pattern
3. Save it to `~/.claw/skills/auto/<slug>.md`
4. On subsequent turns, `skilld` can retrieve and inject it

### Architecture

```
AgentRuntime._run_llm_turn()
  → task completes successfully
  → _should_auto_skill(history) → bool
  → _generate_skill(history) → SKILL.md content
  → skilld.save_auto_skill(slug, content)
```

### New Files
- `services/skilld/auto_skill.py` — detection heuristics + skill generation prompt + save logic

### Modified Files
- `runtimes/agent/runtime.py` — call auto_skill after successful multi-tool turns
- `services/skilld/service.py` — add `save_auto_skill(slug, content)` method
- `clawos_core/constants.py` — add `AUTO_SKILLS_DIR`, `AUTO_SKILL_MIN_TOOLS`, `AUTO_SKILL_MIN_TURNS`

### Detection Heuristic
```python
def should_auto_skill(history: list[dict]) -> bool:
    """True if the completed task was complex enough to warrant a skill."""
    tool_calls = sum(1 for m in history if m.get("tool_calls"))
    turns = len([m for m in history if m["role"] == "user"])
    return tool_calls >= 3 or turns >= 2
```

### Skill Generation Prompt
```
Given this completed task, create a SKILL.md that captures the reusable pattern.
Format:
---
name: <short-kebab-name>
trigger: <when to activate this skill>
pinned: false
---

# <Skill Name>

## When to use
<1-2 sentence description>

## Steps
1. <step>
2. <step>

## Tools used
- <tool>: <what it was used for>

## Example input
<original user request>
```

### Save Location
`~/.claw/skills/auto/<slug>.md` — already on skilld's load path, no config changes needed.

### Success Criteria
- [ ] Multi-tool task auto-generates a SKILL.md in `~/.claw/skills/auto/`
- [ ] Generated skill is retrievable by `skilld` on subsequent turns
- [ ] `clawctl skill list` shows auto-generated skills with `[auto]` tag
- [ ] Skills are NOT generated for trivial single-tool tasks
- [ ] Duplicate detection: if a similar skill already exists, update it instead of creating a new one

### Estimated Effort
2-3 days

---

## P0-2: Context Compression with Prompt Caching

### Problem
ClawOS currently handles long conversations by hard-truncating history to `MAX_HISTORY * 2` messages (24 messages). This:
- Loses important context from early turns
- Wastes tokens on full tool outputs that are no longer relevant
- Doesn't leverage Anthropic/Ollama prompt caching

### Goal
Replace hard truncation with lossy summarization of older turns, preserving the most recent N turns verbatim and injecting cache breakpoints at the system prompt boundary.

### Architecture

```
Current flow:
  [system_prompt] + [_history[-24:]] + [user_msg]

New flow:
  [system_prompt ← cache breakpoint] 
  + [compressed_summary of old turns] 
  + [_history[-12:] verbatim] 
  + [user_msg ← cache breakpoint]
```

### New Files
- `runtimes/agent/compression.py` — `ContextCompressor` class

### Modified Files
- `runtimes/agent/runtime.py` — replace `_history[-(MAX_HISTORY*2):]` with compressed context assembly
- `clawos_core/constants.py` — add `MAX_VERBATIM_TURNS=12`, `COMPRESSION_THRESHOLD_TOKENS=6000`, `CACHE_BREAKPOINT_MARKER`

### ContextCompressor Implementation

```python
class ContextCompressor:
    """Lossy summarization of middle conversation turns."""
    
    def compress(self, history: list[dict], max_verbatim: int = 12) -> list[dict]:
        """
        If history > max_verbatim turns:
          1. Keep system prompt as-is
          2. Summarize turns [0..-max_verbatim] into a single system message
          3. Keep turns [-max_verbatim:] verbatim
        Otherwise, return history as-is.
        """
        if len(history) <= max_verbatim * 2:
            return history
        
        old_turns = history[:-max_verbatim]
        recent_turns = history[-max_verbatim:]
        summary = self._summarize(old_turns)
        return [
            {"role": "system", "content": f"[Earlier conversation summary]\n{summary}"},
            *recent_turns
        ]
    
    def _summarize(self, turns: list[dict]) -> str:
        """Use a fast model (qwen2.5:3b) to summarize old turns."""
        # Fallback: extract key facts without LLM
        ...
```

### Cache Breakpoints
For Ollama with Anthropic-compatible endpoints, inject cache control markers:
```python
# In _build_messages():
messages = [
    {"role": "system", "content": sys_prompt, "cache_control": {"type": "ephemeral"}},
    *compressed_history,
    {"role": "user", "content": user_msg, "cache_control": {"type": "ephemeral"}},
]
```
Ollama's OpenAI-compatible layer ignores unknown keys, so this is safe even when not using Anthropic.

### Tool Output Compression
Tool results >500 chars should be summarized after the turn completes:
```python
for msg in history:
    if msg["role"] == "tool" and len(msg["content"]) > 500:
        msg["content"] = _compress_tool_output(msg["content"])
```

### Success Criteria
- [ ] Conversations >24 turns maintain context via summary instead of hard truncation
- [ ] Recent 12 turns always preserved verbatim
- [ ] Tool outputs >500 chars are compressed in history
- [ ] Fallback path: if LLM summarization fails, use extractive compression (keep first/last + key facts)
- [ ] Token usage logged per turn for monitoring
- [ ] `clawctl observ calls` shows compression stats (turns compressed, tokens saved)

### Estimated Effort
3-5 days

---

## P1-1: Local Subagent Delegation

### Problem
ClawOS has A2A for remote agent delegation, but no local subagent spawning. Complex tasks that could run in parallel (e.g., "refactor module A while writing tests for module B") must run sequentially in a single agent session, consuming the full context window.

### Goal
Add a `delegate` tool to `toolbridge` that spawns a child `AgentRuntime` with its own isolated context, runs it to completion, and returns results. Zero context pollution in the parent.

### Architecture

```
User: "Refactor auth.py and write tests for it"
  → AgentRuntime (parent)
    → tool call: delegate(task="Refactor auth.py", model="qwen2.5-coder:7b")
    → tool call: delegate(task="Write tests for auth.py", model="qwen2.5:7b")
  ← Both results returned, parent synthesizes final answer
```

### New Files
- `tools/delegate/delegate.py` — delegate tool implementation
- `runtimes/agent/subagent.py` — `SubAgentRunner` class

### Modified Files
- `runtimes/agent/tool_schemas.py` — add `delegate` to `ALL_TOOLS` and `SENSITIVE_TOOLS`
- `services/toolbridge/service.py` — register `delegate` in dispatch table
- `services/policyd/service.py` — add `delegate` to approval-gated tools (spawns child agents)
- `clawos_core/constants.py` — add `MAX_SUBAGENTS=3`, `SUBAGENT_TIMEOUT=120`

### SubAgentRunner

```python
class SubAgentRunner:
    """Isolated child agent that runs a single task and returns results."""
    
    def __init__(self, task: str, model: str = FAST_MODEL, 
                 workspace_id: str = DEFAULT_WORKSPACE, timeout: int = 120):
        self.task = task
        self.model = model
        self.workspace_id = workspace_id
        self.timeout = timeout
    
    async def run(self) -> SubAgentResult:
        """Run the subagent and return results."""
        runtime = AgentRuntime(
            model_override=self.model,
            workspace_id=self.workspace_id,
            history=[],  # isolated — no parent context
        )
        try:
            result = await asyncio.wait_for(
                runtime.run_turn(self.task),
                timeout=self.timeout
            )
            return SubAgentResult(success=True, output=result, tool_calls=runtime.tool_log)
        except asyncio.TimeoutError:
            return SubAgentResult(success=False, output="Subagent timed out", tool_calls=[])
```

### Delegate Tool Schema
```json
{
  "name": "delegate",
  "description": "Spawn an isolated subagent to handle a task. Use for parallel work or tasks that need a fresh context window.",
  "parameters": {
    "type": "object",
    "properties": {
      "task": {"type": "string", "description": "Clear description of what the subagent should do"},
      "model": {"type": "string", "description": "Model to use (default: fast model)", "enum": ["qwen2.5:3b", "qwen2.5:7b", "qwen2.5-coder:7b"]},
      "timeout": {"type": "integer", "description": "Timeout in seconds (default: 120)"}
    },
    "required": ["task"]
  }
}
```

### Policy Gating
- `delegate` is SENSITIVE — requires approval for first use in a session
- After approval, subsequent delegates in the same session are auto-approved
- Max 3 concurrent subagents (prevents runaway spawning)
- Subagents inherit workspace but NOT conversation history

### Success Criteria
- [ ] `delegate` tool spawns an isolated AgentRuntime with its own context
- [ ] Parent agent can spawn multiple delegates in parallel
- [ ] Delegate results are returned to parent without polluting parent context
- [ ] Policy gate: first delegate requires approval, subsequent are auto-approved
- [ ] Max concurrent delegates enforced (default: 3)
- [ ] Timeout enforced per delegate
- [ ] `clawctl logs agentd` shows delegate lifecycle (spawn, complete, timeout)

### Estimated Effort
3-4 days

---

## P1-2: Session FTS5 Search Across Conversations

### Problem
ClawOS stores conversation history in `HISTORY.md` and `memd` SQLite, but there's no way to search across past sessions. "What did I ask about the API refactor last week?" requires manual HISTORY.md grep.

### Goal
Add FTS5 full-text search across all past session transcripts in `memd`, accessible via `clawctl` and the `fs.search` tool.

### Architecture

```
memd SQLite:
  sessions table (new):
    - id TEXT PRIMARY KEY
    - workspace_id TEXT
    - started_at TIMESTAMP
    - ended_at TIMESTAMP
    - turn_count INTEGER
    
  session_turns table (new):
    - id INTEGER PRIMARY KEY
    - session_id TEXT → sessions.id
    - role TEXT (user/assistant/tool/system)
    - content TEXT
    - timestamp TIMESTAMP
    - FTS5 index on content

memd.recall_cross_session(query, workspace_id, n=5) → list[TurnHit]
```

### Modified Files
- `services/memd/service.py` — add `session_turns` table creation, `recall_cross_session()`, `ingest_turn()`
- `runtimes/agent/runtime.py` — call `memd.ingest_turn()` after each turn
- `tools/filesystem/search.py` — add cross-session search capability
- `clawctl/commands/` — add `clawctl search <query>` subcommand
- `clawos_core/constants.py` — add `SESSION_DB_PATH`

### Search API
```python
def recall_cross_session(self, query: str, workspace_id: str, n: int = 5) -> list[dict]:
    """FTS5 search across all past session turns."""
    sql = """
        SELECT st.session_id, st.role, st.content, st.timestamp,
               s.started_at, snippet(session_turns_fts, -1, '>>>', '<<<', '...', 32) as highlight
        FROM session_turns_fts st
        JOIN sessions s ON st.session_id = s.id
        WHERE session_turns_fts MATCH ? AND s.workspace_id = ?
        ORDER BY rank
        LIMIT ?
    """
    ...
```

### CLI
```bash
clawctl search "API refactor"              # search all sessions
clawctl search "API refactor" --workspace project-alpha  # scoped
clawctl search "API refactor" --limit 10   # more results
```

### Success Criteria
- [ ] Every turn in a session is ingested into `memd` SQLite with FTS5 index
- [ ] `clawctl search <query>` returns relevant past turns with highlighting
- [ ] `fs.search` tool can search across sessions when no workspace path is given
- [ ] Search is scoped by workspace_id
- [ ] FTS5 index created on first `memd` start (migration)
- [ ] Performance: search across 10K turns < 50ms

### Estimated Effort
1-2 days

---

## P2: User Profile Auto-Modeling (Not P0/P1 — Future)

### Summary
Add `Layer 0` to `memd`: `USER_PROFILE.md` that auto-updates after sessions. Tracks preferences, patterns, working style. Below PINNED.md in priority.

### Why P2
Requires a feedback loop that's hard to get right — bad auto-profiles are worse than none. Needs careful evaluation after P0/P1 are stable.

### Key Idea
After each session, a fast model run extracts: preferences ("I prefer concise answers"), patterns ("I always ask about tests first"), style ("I use vim, not nano"). Stored in `~/.claw/memory/USER_PROFILE.md`. Injected as Layer 0 in every context assembly.

---

## Summary

| Priority | Feature | Effort | Impact | Issue# |
|:--------|:--------|:-------|:-------|:-------|
| 🔴 P0 | Auto-skill creation | 2-3 days | High — closes learning loop | TBD |
| 🔴 P0 | Context compression + caching | 3-5 days | High — cost + quality | TBD |
| 🟡 P1 | Local subagent delegation | 3-4 days | High — parallel execution | TBD |
| 🟡 P1 | Session FTS5 search | 1-2 days | Medium — cross-session recall | TBD |
| 🟢 P2 | User profile auto-modeling | 2-3 days | Medium — personalization | TBD |

**Total P0+P1 estimated effort: 9-14 days**

### Dependencies
- P0-2 (compression) should land before P1-1 (delegation) — subagents need compressed parent context
- P1-2 (FTS5) is independent, can ship anytime
- P0-1 (auto-skill) is independent, can ship anytime

### Claude Code Integration Note
When Claude Code is set up on the Mac Mini, it can be used as the "smart model" for:
- Skill generation (auto-skill): Claude generates better SKILL.md files than qwen2.5:3b
- Context summarization: Claude compresses old turns more accurately
- Subagent tasks: Claude handles complex delegation tasks that need strong reasoning

This makes the P0/P1 features significantly more effective with Claude in the loop.