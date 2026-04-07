# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS /do — Command generator
================================
Calls Ollama, parses the response, returns a list of shell command strings.
System prompt is static (cacheable). Dynamic context goes in user message only.
"""
import json
import os
from pathlib import Path

try:
    from json_repair import repair_json
    _HAS_REPAIR = True
except ImportError:
    _HAS_REPAIR = False

OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = "qwen2.5:7b"


def _system_prompt() -> str:
    """
    Static system prompt — never include dynamic data here (breaks prompt cache).
    The HOME path is injected via the user message context block instead.
    """
    return (
        "You are a shell command generator for Linux. "
        "Output ONLY a single shell command as plain text.\n\n"
        "PATH RULES — follow exactly:\n"
        "- ALWAYS use ~ for paths inside the home directory. "
        "NEVER use /home/<username> or any absolute home path.\n"
        "- Example: list clawos files → ls ~/clawos   NOT ls /clawos or ls /home/user/clawos\n"
        "- Example: find files at home → find ~ ...   NOT find /home/...\n"
        "- Use absolute paths only for system directories: /etc, /var, /usr, /tmp\n\n"
        "OUTPUT FORMAT:\n"
        "- Plain text only. No markdown. No backticks. No explanation.\n"
        "- Example correct output: du -sh ~/clawos\n"
        "- Only use a JSON array [\"cmd1\",\"cmd2\"] when the task truly needs "
        "multiple separate commands run in sequence.\n"
        "- NEVER split a single command's flags into array items. "
        "Wrong: [\"du\",\"-sh\",\"*\"]   Right: \"du -sh *\"\n"
        "- When uncertain, prefer a safe read-only command (ls, find, du, df, cat)."
    )


def _clean_raw(raw: str) -> str:
    """Strip markdown fences, backticks, language tags from model output."""
    raw = raw.strip()
    for fence in ["```bash\n", "```sh\n", "```shell\n", "```\n", "```bash", "```sh", "```"]:
        if raw.startswith(fence):
            raw = raw[len(fence):]
        if raw.endswith(fence.rstrip()):
            raw = raw[: -len(fence.rstrip())]
    if raw.startswith("`") and raw.endswith("`") and raw.count("`") == 2:
        raw = raw[1:-1]
    return raw.strip()


def _parse(raw: str) -> list[str]:
    """Parse model output into a list of shell command strings."""
    cleaned = _clean_raw(raw)
    if not cleaned:
        return []

    candidate = cleaned
    if _HAS_REPAIR:
        try:
            candidate = repair_json(cleaned)
        except Exception:
            pass

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            items = [str(x).strip() for x in parsed if str(x).strip()]
            # If all items have no spaces and don't start with / or ~,
            # the model incorrectly split one command — rejoin
            if items and all(" " not in x for x in items) and all(not x.startswith(("/", "~", "$")) for x in items):
                return [" ".join(items)]
            return items
        if isinstance(parsed, str) and parsed.strip():
            return [parsed.strip()]
    except (json.JSONDecodeError, ValueError):
        pass

    return [cleaned]


def _normalise_request(request: str) -> str:
    """
    Replace /home/<username> style paths in the request with ~ so the
    model never sees an absolute home path and doesn't get confused by
    its own PATH RULES instruction (which forbids generating /home/...).
    """
    import re
    import os
    home = os.path.expanduser("~")
    # Replace the literal home path with ~
    request = request.replace(home, "~")
    # Also replace /home/<any-word> patterns that look like home dirs
    request = re.sub(r"/home/\w+", "~", request)
    return request


def _validate(commands: list[str]) -> list[str]:
    """
    Reject obviously broken outputs like bare '.' or empty strings.
    A valid command must contain at least one space or be a known
    single-word command (ls, pwd, etc.).
    """
    KNOWN_SINGLE = {"ls", "pwd", "whoami", "date", "uptime", "df", "free", "uname"}
    good = []
    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue
        if " " not in cmd and cmd not in KNOWN_SINGLE and not cmd.startswith(("~/", "/", "~")):
            # Likely garbage — skip
            continue
        good.append(cmd)
    return good


def generate(request: str, context: dict, model: str = None) -> list[str]:
    """
    Generate shell command(s) for the given natural language request.
    Returns a list of command strings, or empty list on failure.
    """
    try:
        import ollama as _ollama
    except ImportError:
        print("  [error] ollama Python package not installed — run: pip install ollama")
        return []

    model = model or os.environ.get("CLAWDO_MODEL", DEFAULT_MODEL)

    # Normalise /home/<user> → ~ before sending to model
    request = _normalise_request(request)

    # Build context block for user message (dynamic info stays OUT of system prompt)
    from tools.shell.do.context import format_context
    ctx_block = format_context(context)
    user_msg = f"{ctx_block}\n\nRequest: {request}" if ctx_block else f"Request: {request}"

    try:
        resp = _ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user",   "content": user_msg},
            ],
            options={"temperature": 0.1},
        )
        raw = resp["message"]["content"]
        return _validate(_parse(raw))
    except Exception as e:
        print(f"  [error] Ollama call failed: {e}")
        return []
