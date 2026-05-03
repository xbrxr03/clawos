# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Workflow tools — list and run ClawOS workflows from workflows/ engine.
"""
from __future__ import annotations

import logging

log = logging.getLogger("agent.tools.workflows")


async def list_workflows(args: dict, ctx: dict) -> str:
    try:
        from workflows.engine import get_engine
    except ImportError as e:
        return f"[ERROR] workflows engine unavailable: {e}"
    try:
        engine = get_engine()
        names: list[str] = []
        # Engine surfaces vary; try the known introspection points
        for attr in ("list_workflows", "list_names", "names"):
            obj = getattr(engine, attr, None)
            if callable(obj):
                names = list(obj())
                break
            if obj is not None:
                names = list(obj)
                break
        if not names:
            # Fallback: scan workflows/ dir
            from pathlib import Path
            wf_root = Path(__file__).resolve().parents[3] / "workflows"
            names = sorted(
                p.name for p in wf_root.iterdir()
                if p.is_dir() and not p.name.startswith("_") and not p.name.startswith(".")
            )
    except (AttributeError, TypeError, OSError) as e:
        return f"[ERROR] {e}"
    if not names:
        return "(no workflows registered)"
    return "\n".join(f"- {n}" for n in names)


async def run_workflow(args: dict, ctx: dict) -> str:
    name = (args.get("name") or "").strip()
    params = args.get("params") or {}
    if not name:
        return "[ERROR] workflow name required"
    if not isinstance(params, dict):
        return "[ERROR] params must be an object"

    try:
        from workflows.engine import get_engine
    except ImportError as e:
        return f"[ERROR] workflows engine unavailable: {e}"

    try:
        engine = get_engine()
        # Try the most likely run signatures in order
        for attr in ("run", "execute", "invoke"):
            fn = getattr(engine, attr, None)
            if callable(fn):
                result = fn(name, params)
                # Workflow result might be a coroutine
                import asyncio as _a
                if _a.iscoroutine(result):
                    result = await result
                # Normalise to string
                if hasattr(result, "ok"):
                    ok = bool(result.ok)
                    summary = getattr(result, "summary", "") or getattr(result, "output", "")
                    return f"[{'OK' if ok else 'FAIL'}] {name}: {str(summary)[:600]}"
                return f"[OK] {name}: {str(result)[:600]}"
        return "[ERROR] workflow engine has no run/execute/invoke method"
    except KeyError:
        return f"[ERROR] unknown workflow: {name}"
    except Exception as e:  # workflow execution may raise arbitrary errors
        return f"[ERROR] {name}: {e}"
