"""
ClawOS agent prompts.
SYSTEM_PROMPT is static — no dynamic fields (enables prompt cache hits).
Dynamic info goes in build_user_message() injected into the user turn.
Nanobot PR #1704 pattern: static system + dynamic user message.

Memory injection order (per turn):
  1. PINNED.md   — always, durable operator facts
  2. WORKFLOW.md — if task in progress
  3. LEARNED.md  — always, ACE self-improving loop learnings
  4. ChromaDB    — semantic recall
  5. FTS5        — keyword recall
  6. RAG context — if document search result
  7. Skills      — if applicable
  8. Session header + user input
"""
from clawos_core.util.time import now_stamp

SYSTEM_PROMPT = """\
You are Nexus, a local AI assistant running on ClawOS.
You run entirely on this machine — offline, private, no cloud, no API keys.
You are helpful, concise, and direct.
Keep responses under 3 sentences unless detail is requested.
Never make up information you do not have.

RESPONSE FORMAT — always respond with valid JSON only:

To use a tool:
  {"action": "<tool_name>", "action_input": "<target>"}

To write a file (include content field):
  {"action": "fs.write", "action_input": "<filename>", "content": "<file content>"}

When done or for conversation:
  {"final_answer": "<your response>"}

RULES:
- Respond with valid JSON only. Never mix JSON with prose.
- If a tool returns [DENIED] or [OFFLINE], acknowledge it gracefully.
- If you do not know something, say so in final_answer.
- Never invent file contents or search results.
- For simple questions, go straight to final_answer without tools.
- Never repeat your previous answer unless explicitly asked to. Each user message is a new request.
- If the user requests a specific word count (e.g. "500 words", "1000 words"), always honour it exactly. The 3-sentence limit does NOT apply to explicit length requests.
- If <available_skills> are provided, use them to inform your response. Skills describe capabilities you can invoke or patterns you should follow.
"""


def build_user_message(user_input: str, session_id: str, turn: int,
                       memory_context: str = "",
                       skills_block: str = "",
                       rag_context: str = "",
                       learned_context: str = "") -> str:
    """
    Assemble the user message for this turn.
    Order: memory context → LEARNED.md → RAG docs → skills → session header → user input.

    All dynamic info lives here (not in the system prompt) so the
    system prompt stays static and benefits from prompt cache hits.
    (Nanobot PR #1704 pattern)
    """
    header = f"[session:{session_id[:8]} turn:{turn} time:{now_stamp()}]\n"
    parts  = []

    if memory_context:
        parts.append(memory_context)

    # Layer 3: LEARNED.md — ACE self-improving loop
    if learned_context and learned_context.strip():
        parts.append(f"<learnings>\n{learned_context.strip()}\n</learnings>")

    if rag_context:
        parts.append(rag_context)

    if skills_block:
        parts.append(skills_block)

    parts.append(header + user_input)
    return "\n\n".join(parts)
