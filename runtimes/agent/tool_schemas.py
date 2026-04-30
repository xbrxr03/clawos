# SPDX-License-Identifier: AGPL-3.0-or-later
"""
JSON Schema definitions for native Ollama function calling.

Each tool is described as a dict matching Ollama's tool format:
    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}

The agent loop picks a subset based on the policy grants and passes them
as the `tools=` argument to ollama.chat(). The model returns
`message.tool_calls` which we route through ToolBridge for execution.

Tools are grouped by category for readability and tier-aware filtering
(fast model gets a smaller subset, coder model gets file/code tools, etc.).
"""
from __future__ import annotations

# ── helpers ──────────────────────────────────────────────────────────────────

def _tool(name: str, description: str, params: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": params,
                "required": required or [],
            },
        },
    }


# ── Knowledge / memory ───────────────────────────────────────────────────────

REMEMBER = _tool(
    "remember",
    "Save a fact, note, or preference to long-term memory. Use sparingly — "
    "only when the user explicitly says to remember something or shares a "
    "durable preference (\"I'm vegetarian\", \"I prefer Celsius\").",
    {"text": {"type": "string", "description": "The fact or note to remember."}},
    required=["text"],
)

RECALL = _tool(
    "recall",
    "Search long-term memory for relevant facts. Returns the top matches.",
    {"query": {"type": "string", "description": "What to search for."}},
    required=["query"],
)

PIN_FACT = _tool(
    "pin_fact",
    "Pin a durable fact to PINNED.md (always-injected memory). For the most "
    "important user facts — name, location, hard preferences.",
    {"fact": {"type": "string", "description": "The durable fact to pin."}},
    required=["fact"],
)


# ── System control ───────────────────────────────────────────────────────────

OPEN_APP = _tool(
    "open_app",
    "Launch an installed application by name (case-insensitive).",
    {"name": {"type": "string", "description": "App name, e.g. 'firefox', 'spotify', 'text editor'."}},
    required=["name"],
)

FOCUS_WINDOW = _tool(
    "focus_window",
    "Bring an application's window to the foreground.",
    {"name": {"type": "string", "description": "App name to focus."}},
    required=["name"],
)

CLOSE_APP = _tool(
    "close_app",
    "Close a running application gracefully. Sensitive — requires user approval.",
    {"name": {"type": "string", "description": "App name to close."}},
    required=["name"],
)

SET_VOLUME = _tool(
    "set_volume",
    "Set the system output volume.",
    {"level": {"type": "integer", "description": "Volume 0-100.", "minimum": 0, "maximum": 100}},
    required=["level"],
)

GET_VOLUME = _tool(
    "get_volume",
    "Get the current system output volume (0-100).",
    {},
)

SYSTEM_STATS = _tool(
    "system_stats",
    "Get current CPU, RAM, and disk usage.",
    {},
)


# ── Desktop / clipboard ──────────────────────────────────────────────────────

SET_CLIPBOARD = _tool(
    "set_clipboard",
    "Write text to the system clipboard.",
    {"text": {"type": "string", "description": "Text to put on the clipboard."}},
    required=["text"],
)

GET_CLIPBOARD = _tool(
    "get_clipboard",
    "Read the current text on the system clipboard.",
    {},
)

PASTE_TO_APP = _tool(
    "paste_to_app",
    "Paste the current clipboard contents into the focused application "
    "(sends Ctrl/Cmd-V). The target app must already be focused — call "
    "focus_window first if needed.",
    {"app": {"type": "string", "description": "Optional app name to focus first.", "default": ""}},
)

TYPE_IN_APP = _tool(
    "type_in_app",
    "Type text directly into the focused application (simulates keyboard).",
    {"text": {"type": "string", "description": "Text to type."}},
    required=["text"],
)

SCREENSHOT = _tool(
    "screenshot",
    "Capture the current screen and return a path to the saved PNG.",
    {},
)


# ── Compose / content ────────────────────────────────────────────────────────

WRITE_TEXT = _tool(
    "write_text",
    "Generate written content (essay, email, summary, document) of a "
    "specified topic and length. Returns the generated text — does not "
    "save or paste it. Combine with set_clipboard / paste_to_app / write_file.",
    {
        "topic":  {"type": "string", "description": "What the text should be about."},
        "length": {"type": "string", "description": "Desired length, e.g. '500 words', 'short', '3 paragraphs'.", "default": "medium"},
        "tone":   {"type": "string", "description": "Tone, e.g. 'formal', 'casual', 'technical'.", "default": "neutral"},
    },
    required=["topic"],
)


# ── Files ────────────────────────────────────────────────────────────────────

READ_FILE = _tool(
    "read_file",
    "Read a text file from the workspace. Returns the contents.",
    {"path": {"type": "string", "description": "Workspace-relative or absolute path."}},
    required=["path"],
)

WRITE_FILE = _tool(
    "write_file",
    "Write text to a file in the workspace. Sensitive — requires approval.",
    {
        "path":    {"type": "string", "description": "Workspace path."},
        "content": {"type": "string", "description": "File contents."},
    },
    required=["path", "content"],
)

LIST_FILES = _tool(
    "list_files",
    "List files in a directory.",
    {"path": {"type": "string", "description": "Directory path.", "default": "."}},
)

OPEN_FILE = _tool(
    "open_file",
    "Open a file in its default application.",
    {"path": {"type": "string", "description": "Path to the file."}},
    required=["path"],
)

OPEN_URL = _tool(
    "open_url",
    "Open a URL in the user's default browser.",
    {"url": {"type": "string", "description": "Full URL with scheme."}},
    required=["url"],
)


# ── Productivity ─────────────────────────────────────────────────────────────

ADD_REMINDER = _tool(
    "add_reminder",
    "Add a reminder.",
    {
        "task":   {"type": "string", "description": "What to be reminded of."},
        "when":   {"type": "string", "description": "When to fire the reminder, e.g. '7pm', 'tomorrow 9am', 'in 2 hours'."},
        "repeat": {"type": "string", "description": "Optional: 'daily', 'weekly', 'none'.", "default": "none"},
    },
    required=["task", "when"],
)

LIST_REMINDERS = _tool(
    "list_reminders",
    "List upcoming reminders.",
    {"days_ahead": {"type": "integer", "description": "How far to look ahead.", "default": 7}},
)

REMOVE_REMINDER = _tool(
    "remove_reminder",
    "Delete a reminder by id.",
    {"reminder_id": {"type": "string", "description": "Reminder id."}},
    required=["reminder_id"],
)

GET_TIME = _tool(
    "get_time",
    "Get the current local time, date, and timezone.",
    {},
)

GET_WEATHER = _tool(
    "get_weather",
    "Get current weather and short forecast for a location (defaults to user's pinned location).",
    {"location": {"type": "string", "description": "City or location. Optional.", "default": ""}},
)

GET_CALENDAR_EVENTS = _tool(
    "get_calendar_events",
    "Read calendar events for a date range.",
    {
        "start": {"type": "string", "description": "Start date (YYYY-MM-DD or 'today', 'tomorrow').", "default": "today"},
        "end":   {"type": "string", "description": "End date.", "default": "today"},
    },
)

GET_NEWS = _tool(
    "get_news",
    "Get the latest headlines from configured RSS feeds.",
    {"limit": {"type": "integer", "description": "How many headlines.", "default": 5}},
)


# ── Workflows ────────────────────────────────────────────────────────────────

LIST_WORKFLOWS = _tool(
    "list_workflows",
    "List available ClawOS workflows.",
    {},
)

RUN_WORKFLOW = _tool(
    "run_workflow",
    "Run a named ClawOS workflow with parameters.",
    {
        "name":   {"type": "string", "description": "Workflow name (from list_workflows)."},
        "params": {"type": "object", "description": "Workflow parameters as key/value pairs.", "additionalProperties": True},
    },
    required=["name"],
)


# ── Web ──────────────────────────────────────────────────────────────────────

WEB_SEARCH = _tool(
    "web_search",
    "Search the web (DuckDuckGo). Requires internet — returns gracefully if offline.",
    {"query": {"type": "string", "description": "Search query."}},
    required=["query"],
)


# ── Shell (sensitive) ────────────────────────────────────────────────────────

RUN_COMMAND = _tool(
    "run_command",
    "Run a shell command. Sensitive — always requires user approval. "
    "Restricted to allowlisted commands (ls, cat, grep, git, python, etc.).",
    {"command": {"type": "string", "description": "Shell command."}},
    required=["command"],
)


# ── Catalog ──────────────────────────────────────────────────────────────────

ALL_TOOLS: dict[str, dict] = {
    # knowledge
    "remember":            REMEMBER,
    "recall":              RECALL,
    "pin_fact":            PIN_FACT,
    # system
    "open_app":            OPEN_APP,
    "focus_window":        FOCUS_WINDOW,
    "close_app":           CLOSE_APP,
    "set_volume":          SET_VOLUME,
    "get_volume":          GET_VOLUME,
    "system_stats":        SYSTEM_STATS,
    # desktop
    "set_clipboard":       SET_CLIPBOARD,
    "get_clipboard":       GET_CLIPBOARD,
    "paste_to_app":        PASTE_TO_APP,
    "type_in_app":         TYPE_IN_APP,
    "screenshot":          SCREENSHOT,
    # compose
    "write_text":          WRITE_TEXT,
    # files
    "read_file":           READ_FILE,
    "write_file":          WRITE_FILE,
    "list_files":          LIST_FILES,
    "open_file":           OPEN_FILE,
    "open_url":            OPEN_URL,
    # productivity
    "add_reminder":        ADD_REMINDER,
    "list_reminders":      LIST_REMINDERS,
    "remove_reminder":     REMOVE_REMINDER,
    "get_time":            GET_TIME,
    "get_weather":         GET_WEATHER,
    "get_calendar_events": GET_CALENDAR_EVENTS,
    "get_news":            GET_NEWS,
    # workflows
    "list_workflows":      LIST_WORKFLOWS,
    "run_workflow":        RUN_WORKFLOW,
    # web
    "web_search":          WEB_SEARCH,
    # shell
    "run_command":         RUN_COMMAND,
}

# Tools that always require approval before executing.
SENSITIVE_TOOLS = frozenset({
    "close_app",
    "write_file",
    "run_command",
})

# Tier filtering: which tools the FAST model gets to see (smaller surface area
# helps a 3B model stay focused). SMART and CODER see everything.
FAST_TOOL_SET = frozenset({
    "get_time", "get_volume", "set_volume",
    "open_app", "focus_window", "system_stats",
    "list_reminders", "add_reminder", "remove_reminder",
    "set_clipboard", "get_clipboard",
    "recall",
    "get_weather",
})


def schemas_for(tool_names: list[str]) -> list[dict]:
    """Return JSON Schema list for the given tool names. Missing names ignored."""
    return [ALL_TOOLS[n] for n in tool_names if n in ALL_TOOLS]


def schemas_for_tier(tier: str, granted_tools: set[str]) -> list[dict]:
    """
    Return tool schemas for a given model tier, intersected with policy grants.

    tier: "fast" | "smart" | "coder"
    granted_tools: tool names allowed by the policy engine
    """
    if tier == "fast":
        names = (FAST_TOOL_SET & granted_tools)
    else:
        names = granted_tools
    return [ALL_TOOLS[n] for n in sorted(names) if n in ALL_TOOLS]
