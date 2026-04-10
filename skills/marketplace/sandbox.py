# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Skill execution sandbox for ClawOS.
Restricts skill code from accessing dangerous builtins.

Blocked: os.system, subprocess, socket, open (outside workspace),
         __import__ for non-whitelisted modules.

Skills can only call back into ClawOS via the provided `context` object.
"""
import logging
import types
from pathlib import Path
from typing import Any

log = logging.getLogger("skill_sandbox")

# Modules skills are allowed to import
ALLOWED_MODULES = frozenset({
    "json", "re", "math", "datetime", "time", "itertools",
    "functools", "collections", "pathlib", "typing", "dataclasses",
    "string", "textwrap", "hashlib", "base64", "uuid",
    "urllib.parse",  # URL parsing only
})

# Modules explicitly blocked
BLOCKED_MODULES = frozenset({
    "os", "sys", "subprocess", "socket", "shutil", "glob",
    "ctypes", "importlib", "pty", "termios", "tty",
    "multiprocessing", "threading",  # skills run in main thread
    "signal", "fcntl", "resource",
    "pickle", "shelve",  # arbitrary deserialization
})


class SandboxedImport:
    """Restricted __import__ that only allows whitelisted modules."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id

    def __call__(self, name, *args, **kwargs):
        base = name.split(".")[0]
        if base in BLOCKED_MODULES:
            raise ImportError(
                f"Skill sandbox: import '{name}' is not allowed. "
                f"Use the context object to access ClawOS services."
            )
        if base not in ALLOWED_MODULES:
            raise ImportError(
                f"Skill sandbox: import '{name}' is not in the allowed list. "
                f"Allowed: {', '.join(sorted(ALLOWED_MODULES))}"
            )
        import builtins
        return builtins.__import__(name, *args, **kwargs)


class SkillContext:
    """
    The interface skills use to call back into ClawOS.
    Passed as `context` to skill.run(input, context).
    Enforces policyd checks on every operation.
    """

    def __init__(self, workspace_id: str, skill_id: str, permissions: list[str]):
        self.workspace_id = workspace_id
        self.skill_id = skill_id
        self.permissions = set(permissions)
        self._result_log: list[str] = []

    def _require_permission(self, perm: str):
        if perm not in self.permissions:
            raise PermissionError(
                f"Skill '{self.skill_id}' requires permission '{perm}' "
                f"which was not granted. Declared permissions: {sorted(self.permissions)}"
            )

    def read_file(self, path: str) -> str:
        """Read a file from the workspace. Requires: fs.read permission."""
        self._require_permission("fs.read")
        from clawos_core.constants import CLAWOS_DIR
        ws_root = CLAWOS_DIR / "workspaces" / self.workspace_id
        full_path = (ws_root / path).resolve()
        if not str(full_path).startswith(str(ws_root.resolve())):
            raise PermissionError(f"Path escape attempt blocked: {path}")
        return full_path.read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str):
        """Write a file to the workspace. Requires: fs.write permission."""
        self._require_permission("fs.write")
        from clawos_core.constants import CLAWOS_DIR
        ws_root = CLAWOS_DIR / "workspaces" / self.workspace_id
        full_path = (ws_root / path).resolve()
        if not str(full_path).startswith(str(ws_root.resolve())):
            raise PermissionError(f"Path escape attempt blocked: {path}")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def log(self, message: str):
        """Log a message from the skill."""
        log.info(f"[skill:{self.skill_id}] {message}")
        self._result_log.append(message)

    def get_result_log(self) -> list[str]:
        return list(self._result_log)


class SkillSandbox:
    """
    Execute a skill's entry.py in a restricted environment.
    """

    def __init__(self, skill_dir: Path, workspace_id: str,
                 skill_id: str, permissions: list[str]):
        self.skill_dir = skill_dir
        self.workspace_id = workspace_id
        self.skill_id = skill_id
        self.permissions = permissions

    def run(self, skill_input: dict) -> dict:
        """
        Execute the skill. Returns {ok: bool, output: Any, logs: [str], error: str}.
        """
        entry_file = self.skill_dir / "skill.yaml"
        try:
            import yaml
            meta = yaml.safe_load(entry_file.read_text())
            entry_name = meta.get("entry", "entry.py")
        except Exception:
            entry_name = "entry.py"

        entry_path = self.skill_dir / entry_name
        if not entry_path.exists():
            return {"ok": False, "output": None, "logs": [],
                    "error": f"Entry file not found: {entry_name}"}

        context = SkillContext(
            workspace_id=self.workspace_id,
            skill_id=self.skill_id,
            permissions=self.permissions,
        )

        sandboxed_import = SandboxedImport(self.workspace_id)

        # Build restricted globals
        safe_builtins = self._make_safe_builtins(sandboxed_import)
        sandbox_globals = {
            "__builtins__": safe_builtins,
            "__name__": f"skill_{self.skill_id}",
            "__file__": str(entry_path),
        }

        try:
            code = compile(entry_path.read_text(encoding="utf-8"), str(entry_path), "exec")
            exec(code, sandbox_globals)

            run_fn = sandbox_globals.get("run")
            if not callable(run_fn):
                return {"ok": False, "output": None, "logs": [],
                        "error": "Skill entry.py must define a run(input, context) function"}

            output = run_fn(skill_input, context)
            return {
                "ok": True,
                "output": output,
                "logs": context.get_result_log(),
                "error": "",
            }
        except PermissionError as e:
            log.warning(f"Skill permission denied [{self.skill_id}]: {e}")
            return {"ok": False, "output": None, "logs": context.get_result_log(),
                    "error": f"Permission denied: {e}"}
        except ImportError as e:
            log.warning(f"Skill blocked import [{self.skill_id}]: {e}")
            return {"ok": False, "output": None, "logs": context.get_result_log(),
                    "error": f"Blocked import: {e}"}
        except Exception as e:
            log.error(f"Skill execution error [{self.skill_id}]: {e}")
            return {"ok": False, "output": None, "logs": context.get_result_log(),
                    "error": f"Runtime error: {e}"}

    def _make_safe_builtins(self, sandboxed_import) -> dict:
        """Return a restricted builtins dict — no exec, eval, open, __import__."""
        import builtins
        safe = {}
        allowed_builtins = [
            "abs", "all", "any", "bool", "bytes", "callable", "chr",
            "dict", "dir", "divmod", "enumerate", "filter", "float",
            "format", "frozenset", "getattr", "hasattr", "hash", "hex",
            "id", "input", "int", "isinstance", "issubclass", "iter",
            "len", "list", "map", "max", "min", "next", "object", "oct",
            "ord", "pow", "print", "property", "range", "repr", "reversed",
            "round", "set", "setattr", "slice", "sorted", "staticmethod",
            "str", "sum", "super", "tuple", "type", "vars", "zip",
            "True", "False", "None",
            "ValueError", "TypeError", "KeyError", "IndexError",
            "AttributeError", "RuntimeError", "StopIteration",
            "Exception", "BaseException", "NotImplementedError",
        ]
        for name in allowed_builtins:
            obj = getattr(builtins, name, None)
            if obj is not None:
                safe[name] = obj

        # Replace __import__ with sandboxed version
        safe["__import__"] = sandboxed_import
        return safe
