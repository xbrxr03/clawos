# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl wf - list and run built-in ClawOS workflows."""
from __future__ import annotations

import asyncio
import sys
from typing import Optional

from clawctl.ui.banner import error, info, success, table, warn


def _engine():
    from workflows.engine import get_engine
    eng = get_engine()
    eng.load_registry()
    return eng


def run_list(category: Optional[str] = None, search: Optional[str] = None) -> None:
    print()
    try:
        eng = _engine()
    except Exception as exc:
        error(f"Could not load workflow registry: {exc}")
        print()
        return

    workflows = eng.list_workflows(category=category, search=search)
    if not workflows:
        info("No workflows match the given filters.")
        print()
        return

    rows = []
    for m in workflows:
        agent_tag = "" if m.needs_agent else "[no-llm]"
        destructive_tag = "[destructive]" if m.destructive else ""
        tags_col = "  ".join(filter(None, [agent_tag, destructive_tag]))
        rows.append((m.id, m.category, m.name, tags_col))

    table(rows, headers=("ID", "CATEGORY", "NAME", "FLAGS"))
    print()
    info(f"{len(workflows)} workflow(s) found. Run 'clawctl wf info <id>' or 'clawctl wf run <id>'.")
    print()


def run_info(workflow_id: str) -> None:
    print()
    try:
        eng = _engine()
    except Exception as exc:
        error(f"Could not load workflow registry: {exc}")
        print()
        return

    workflows = {m.id: m for m in eng.list_workflows()}
    meta = workflows.get(workflow_id)
    if meta is None:
        error(f"Unknown workflow: {workflow_id}")
        info("Run 'clawctl wf list' to see available workflows.")
        print()
        return

    info(f"ID:          {meta.id}")
    info(f"Name:        {meta.name}")
    info(f"Category:    {meta.category}")
    info(f"Description: {meta.description}")
    info(f"Tags:        {', '.join(meta.tags) if meta.tags else '(none)'}")
    info(f"Requires:    {', '.join(meta.requires) if meta.requires else '(none)'}")
    info(f"Platforms:   {', '.join(meta.platforms) if meta.platforms else 'all'}")
    info(f"Needs LLM:   {'yes' if meta.needs_agent else 'no'}")
    info(f"Destructive: {'yes' if meta.destructive else 'no'}")
    info(f"Timeout:     {meta.timeout_s}s")
    print()


def run_run(
    workflow_id: str,
    kvpairs: list[str],
    workspace: str = "nexus_default",
    dry_run: bool = False,
) -> None:
    args: dict = {}
    for kv in kvpairs:
        if "=" in kv:
            k, _, v = kv.partition("=")
            # coerce booleans
            if v.lower() == "true":
                v = True  # type: ignore[assignment]
            elif v.lower() == "false":
                v = False  # type: ignore[assignment]
            args[k.strip()] = v
        else:
            warn(f"Ignoring malformed argument (expected key=value): {kv!r}")

    if dry_run:
        args.setdefault("dry_run", True)

    print()
    info(f"Running workflow: {workflow_id}")
    if args:
        info(f"Args: {args}")
    print()

    try:
        eng = _engine()
    except Exception as exc:
        error(f"Could not load workflow registry: {exc}")
        print()
        sys.exit(1)

    async def _run():
        return await eng.run(workflow_id, args, workspace_id=workspace)

    try:
        result = asyncio.run(_run())
    except KeyError as exc:
        error(str(exc))
        info("Run 'clawctl wf list' to see available workflows.")
        print()
        sys.exit(1)
    except Exception as exc:
        error(f"Workflow execution error: {exc}")
        print()
        sys.exit(1)

    from workflows.engine import WorkflowStatus

    if result.status == WorkflowStatus.OK:
        success(f"Workflow finished: {result.status.value}")
    elif result.status == WorkflowStatus.SKIPPED:
        warn(f"Workflow skipped: {result.error or 'no reason given'}")
    else:
        error(f"Workflow failed: {result.error or '(no detail)'}")

    if result.output:
        print()
        print(result.output)

    if result.metadata:
        print()
        for k, v in result.metadata.items():
            info(f"{k}: {v}")

    print()
    if result.status == WorkflowStatus.FAILED:
        sys.exit(1)
