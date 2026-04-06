# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS /do — CLI entry point
==============================
Natural language → shell command generator.
Called from REPL as: /do <request>
Also callable directly: python3 -m tools.shell.do.cli <request>

Flags:
  --dry        Show command + affected files, never execute
  --yes / -y   Skip confirm for safe commands only
  --history    Show last 10 commands from audit log
  --undo       Infer and run inverse of last safe command
  --explain    Show plain-English explanation before running
  --step       Confirm each step of a multi-step plan individually
  --model/-m   Override Ollama model
  --no-context Don't inject cwd/git/history/PINNED context
  --no-audit   Skip writing to audit log
"""
import sys
import os
from pathlib import Path

# Ensure clawos root is on path when called as subprocess
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.shell.do.safety   import classify, classify_plan
from tools.shell.do.context  import collect_context
from tools.shell.do.generator import generate
from tools.shell.do.renderer  import (
    print_generating, print_context_summary, print_command,
    print_dry_run, print_success, print_audit_note, print_explain,
    confirm_run, print_history, print_undo_suggestion,
)
from tools.shell.do.runner import (
    run_commands, dry_preview, get_history, infer_undo, _audit_path,
)


def _parse_args(argv: list[str]) -> dict:
    """Minimal arg parser — no external deps."""
    args = {
        "request":    "",
        "dry":        False,
        "yes":        False,
        "history":    False,
        "undo":       False,
        "explain":    False,
        "step":       False,
        "no_context": False,
        "no_audit":   False,
        "model":      None,
        "workspace":  "jarvis_default",
    }
    i = 0
    positional = []
    while i < len(argv):
        a = argv[i]
        if a in ("--dry",):
            args["dry"] = True
        elif a in ("--yes", "-y"):
            args["yes"] = True
        elif a in ("--history",):
            args["history"] = True
        elif a in ("--undo",):
            args["undo"] = True
        elif a in ("--explain",):
            args["explain"] = True
        elif a in ("--step",):
            args["step"] = True
        elif a in ("--no-context",):
            args["no_context"] = True
        elif a in ("--no-audit",):
            args["no_audit"] = True
        elif a in ("--model", "-m"):
            i += 1
            if i < len(argv):
                args["model"] = argv[i]
        elif a in ("--workspace", "-w"):
            i += 1
            if i < len(argv):
                args["workspace"] = argv[i]
        elif not a.startswith("--"):
            positional.append(a)
        i += 1
    args["request"] = " ".join(positional).strip()
    return args


def run(argv: list[str] = None):
    if argv is None:
        argv = sys.argv[1:]

    args = _parse_args(argv)

    # ── --history ──────────────────────────────────────────────────────────────
    if args["history"]:
        entries = get_history(10)
        print_history(entries)
        return

    # ── --undo ─────────────────────────────────────────────────────────────────
    if args["undo"]:
        entries = get_history(20)
        undo_cmd = infer_undo(entries)
        should_run = print_undo_suggestion(undo_cmd)
        if should_run and undo_cmd:
            safety = classify(undo_cmd)
            if confirm_run(safety.tier, args["yes"]):
                code = run_commands(
                    [undo_cmd], request="undo",
                    is_dangerous=(safety.tier != "safe"),
                    no_audit=args["no_audit"],
                )
                print_success(code, 0)
                print_audit_note(str(_audit_path()))
        return

    # ── Need a request from here ───────────────────────────────────────────────
    if not args["request"]:
        print("  Usage: /do <natural language request>")
        print("  Flags: --dry  --yes  --history  --undo  --explain  --step")
        return

    # ── Collect context ────────────────────────────────────────────────────────
    ctx = {} if args["no_context"] else collect_context(args["workspace"])

    print_generating()
    if ctx:
        print_context_summary(ctx)

    # ── Generate ───────────────────────────────────────────────────────────────
    commands = generate(args["request"], ctx, model=args["model"])

    if not commands:
        print("  [error] Could not generate a command. Try rephrasing.")
        return

    # ── Safety ────────────────────────────────────────────────────────────────
    safety = classify_plan(commands)

    # ── --explain ──────────────────────────────────────────────────────────────
    if args["explain"]:
        explain_prompt = f"Explain in plain English what this command does: {' && '.join(commands)}"
        explanation = generate(explain_prompt, {}, model=args["model"])
        if explanation:
            print_explain(" ".join(explanation))

    # ── --dry ──────────────────────────────────────────────────────────────────
    if args["dry"]:
        affected = dry_preview(commands)
        print_command(commands, safety.tier)
        print_dry_run(commands, affected)
        if not args["no_audit"]:
            run_commands(commands, args["request"], is_dangerous=(safety.tier != "safe"),
                         dry_run=True, no_audit=args["no_audit"])
        return

    # ── Display command ────────────────────────────────────────────────────────
    print_command(commands, safety.tier)

    # ── --step: confirm each command individually ──────────────────────────────
    if args["step"] and len(commands) > 1:
        for i, cmd in enumerate(commands, 1):
            step_safety = classify(cmd)
            print(f"\n  Step {i}/{len(commands)}: {cmd}")
            if not confirm_run(step_safety.tier, args["yes"]):
                print("  Stopped.")
                return
            import time
            t0 = time.time()
            code = run_commands(
                [cmd], request=args["request"],
                is_dangerous=(step_safety.tier != "safe"),
                no_audit=args["no_audit"],
            )
            elapsed = time.time() - t0
            print_success(code, elapsed)
            if code != 0:
                print("  Stopping — step failed.")
                break
        print_audit_note(str(_audit_path()))
        return

    # ── Normal confirm + run ───────────────────────────────────────────────────
    if not confirm_run(safety.tier, args["yes"]):
        print()
        return

    import time
    t0 = time.time()
    code = run_commands(
        commands, request=args["request"],
        is_dangerous=(safety.tier != "safe"),
        no_audit=args["no_audit"],
    )
    elapsed = time.time() - t0

    print_success(code, elapsed)
    if not args["no_audit"]:
        print_audit_note(str(_audit_path()))


def main():
    run(sys.argv[1:])


if __name__ == "__main__":
    main()
