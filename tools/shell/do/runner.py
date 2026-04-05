"""
ClawOS /do — Command runner
============================
Executes shell commands via subprocess.
Writes every execution to a Merkle-chained audit log.
"""
import hashlib
import os as _os
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_WINDOWS_CMD_BUILTINS = {
    "assoc", "break", "call", "cd", "chcp", "chdir", "cls", "copy", "date",
    "del", "dir", "echo", "erase", "for", "ftype", "md", "mkdir", "move",
    "path", "pause", "popd", "prompt", "pushd", "rd", "ren", "rename",
    "rmdir", "set", "start", "time", "title", "type", "ver", "vol",
}


def _audit_path() -> Path:
    """Audit log lives in ~/clawos/logs/ when in ClawOS mode, else ~/.clawos/do-audit.jsonl."""
    try:
        from clawos_core.constants import LOGS_DIR
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return LOGS_DIR / "do-audit.jsonl"
    except Exception:
        p = Path.home() / ".clawos"
        p.mkdir(exist_ok=True)
        return p / "do-audit.jsonl"


def _prev_hash(audit_file: Path) -> str:
    """Get the hash of the last audit entry for Merkle chaining."""
    if not audit_file.exists():
        return "0" * 64
    try:
        lines = audit_file.read_text().strip().splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line:
                entry = json.loads(line)
                return entry.get("entry_hash", "0" * 64)
    except Exception:
        pass
    return "0" * 64


def _write_audit(
    request: str,
    commands: list[str],
    exit_code: int,
    is_dangerous: bool,
    approved: bool,
    dry_run: bool,
    cwd: str,
    elapsed: float,
    audit_file: Path,
):
    prev = _prev_hash(audit_file)
    entry_data = {
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "request":      request,
        "commands":     commands,
        "exit_code":    exit_code,
        "is_dangerous": is_dangerous,
        "approved":     approved,
        "dry_run":      dry_run,
        "cwd":          cwd,
        "elapsed_s":    round(elapsed, 2),
        "user":         os.environ.get("USER", "unknown"),
    }
    raw = json.dumps(entry_data, sort_keys=True)
    entry_hash = hashlib.sha256((prev + raw).encode()).hexdigest()
    entry_data["prev_hash"]  = prev
    entry_data["entry_hash"] = entry_hash
    with open(audit_file, "a") as f:
        f.write(json.dumps(entry_data) + "\n")


def _should_use_windows_shell(cmd: str, argv: list[str]) -> bool:
    if _os.name != "nt":
        return False
    if not argv:
        return True
    if argv[0].lower() in _WINDOWS_CMD_BUILTINS:
        return True
    return any(ch in cmd for ch in ("|", "&", ">", "<", "(", ")"))


def run_commands(
    commands: list[str],
    request: str,
    is_dangerous: bool,
    dry_run: bool = False,
    no_audit: bool = False,
) -> int:
    """
    Execute a list of shell commands sequentially.
    Stops on first failure. Returns final exit code.
    """
    audit_file = _audit_path()

    if dry_run:
        if not no_audit:
            _write_audit(request, commands, 0, is_dangerous, False, True, str(Path.cwd()), 0.0, audit_file)
        return 0

    last_code = 0
    t0 = time.time()

    for cmd in commands:
        print()
        try:
            import shlex as _shlex
            try:
                import re as _re
                home_dir = _os.path.expanduser("~")
                cmd = _re.sub(r"(?<![\w])~(?![\w])", lambda _m: home_dir, cmd)
                _argv = _shlex.split(cmd, posix=(_os.name != "nt"))
            except ValueError:
                if _os.name == "nt":
                    _argv = ["cmd", "/d", "/c", cmd]
                else:
                    _argv = ["bash", "-c", cmd]
            if _should_use_windows_shell(cmd, _argv):
                result = subprocess.run(["cmd", "/d", "/c", cmd], text=True)
            else:
                result = subprocess.run(_argv, text=True)
            last_code = result.returncode
        except KeyboardInterrupt:
            print()
            last_code = 130
            break
        except Exception as e:
            print(f"  [error] {e}")
            last_code = 1
            break

        if last_code != 0:
            break

    elapsed = time.time() - t0

    if not no_audit:
        _write_audit(request, commands, last_code, is_dangerous, True, False, str(Path.cwd()), elapsed, audit_file)

    return last_code


def dry_preview(commands: list[str]) -> list[str]:
    """
    Try to enumerate files that would be affected by the commands.
    Best-effort — returns empty list if it can't figure it out.
    """
    affected = []
    for cmd in commands:
        parts = cmd.split()
        if not parts:
            continue
        verb = parts[0]
        # For rm, find, ls — try to enumerate targets
        if verb in ("rm", "ls", "find", "cat", "head", "tail") and len(parts) > 1:
            try:
                import glob
                for pattern in parts[1:]:
                    if pattern.startswith("-"):
                        continue
                    matches = glob.glob(os.path.expandvars(os.path.expanduser(pattern)))
                    affected.extend(matches[:20])
            except Exception:
                pass
    return list(dict.fromkeys(affected))  # deduplicate preserving order


def get_history(n: int = 10) -> list[dict]:
    """Return last N audit entries."""
    audit_file = _audit_path()
    if not audit_file.exists():
        return []
    try:
        lines = audit_file.read_text().strip().splitlines()
        entries = []
        for line in reversed(lines):
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
            if len(entries) >= n:
                break
        return list(reversed(entries))
    except Exception:
        return []


def infer_undo(entries: list[dict]) -> Optional[str]:
    """
    Look at recent history and infer the inverse of the last non-dangerous command.
    Supports: mv, mkdir, touch, cp.
    """
    for entry in reversed(entries):
        if entry.get("is_dangerous") or not entry.get("approved"):
            continue
        for cmd in entry.get("commands", []):
            parts = cmd.split()
            if not parts:
                continue
            verb = parts[0]
            try:
                if verb == "mv" and len(parts) == 3:
                    return f"mv {parts[2]} {parts[1]}"
                if verb == "mkdir" and len(parts) >= 2:
                    target = parts[-1]
                    return f"rmdir {target}"
                if verb == "touch" and len(parts) == 2:
                    return f"rm {parts[1]}"
                if verb == "cp" and len(parts) == 3:
                    return f"rm {parts[2]}"
            except Exception:
                continue
    return None
