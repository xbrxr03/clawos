# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl framework commands."""
from __future__ import annotations

import sys


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("No frameworks found.")
        return
    col_w = {"name": 16, "version": 8, "state": 12, "compatible": 10, "description": 50}
    header = (
        f"{'NAME':<{col_w['name']}} "
        f"{'VERSION':<{col_w['version']}} "
        f"{'STATE':<{col_w['state']}} "
        f"{'COMPAT':<{col_w['compatible']}} "
        f"DESCRIPTION"
    )
    print(header)
    print("-" * 100)
    for row in rows:
        compat = "✓" if row.get("compatible", True) else "✗ " + row.get("incompatible_reason", "")[:20]
        state = row.get("state", "available")
        state_display = {
            "available":  "available",
            "installing": "installing…",
            "installed":  "installed",
            "running":    "● running",
            "error":      "✗ error",
            "removing":   "removing…",
        }.get(state, state)
        desc = row.get("description", "")[:45]
        print(
            f"{row['name']:<{col_w['name']}} "
            f"{row['version']:<{col_w['version']}} "
            f"{state_display:<{col_w['state']}} "
            f"{compat:<{col_w['compatible']}} "
            f"{desc}"
        )


def run_list() -> None:
    from services.frameworkd.service import list_frameworks
    rows = list_frameworks()
    print(f"\n  Framework Store  ({len(rows)} frameworks)\n")
    _print_table(rows)
    print()


def run_install(name: str) -> None:
    from services.frameworkd.service import install_framework
    print(f"Installing {name}…")
    result = install_framework(name)
    if result["ok"]:
        print(f"✓ {name} installed successfully")
        print(f"  Start it: clawctl framework start {name}")
        print(f"  Use it:   clawctl framework use {name}")
    else:
        print(f"✗ Failed to install {name}: {result['message']}", file=sys.stderr)
        sys.exit(1)


def run_remove(name: str) -> None:
    from services.frameworkd.service import remove_framework
    import click
    if not click.confirm(f"Remove {name}?"):
        return
    result = remove_framework(name)
    if result["ok"]:
        print(f"✓ {name} removed")
    else:
        print(f"✗ Failed: {result['message']}", file=sys.stderr)
        sys.exit(1)


def run_start(name: str) -> None:
    from services.frameworkd.service import start_framework
    result = start_framework(name)
    if result["ok"]:
        print(f"✓ {name} started")
    else:
        print(f"✗ Could not start {name}", file=sys.stderr)
        sys.exit(1)


def run_stop(name: str) -> None:
    from services.frameworkd.service import stop_framework
    result = stop_framework(name)
    print(f"{'✓' if result['ok'] else '✗'} {name} {'stopped' if result['ok'] else 'stop failed'}")


def run_use(name: str) -> None:
    from services.frameworkd.service import set_active_framework
    result = set_active_framework(name)
    if result["ok"]:
        print(f"✓ Active framework set to: {result['active']}")
        print("  All inbound messages (voice, chat, dashboard) will route through it.")
    else:
        print(f"✗ {result.get('error', 'Failed')}", file=sys.stderr)
        sys.exit(1)


def run_status() -> None:
    from services.frameworkd.service import all_statuses, get_active_framework
    rows = all_statuses()
    active = get_active_framework()
    print(f"\n  Framework Status  (active: {active})\n")
    header = f"{'NAME':<18} {'STATE':<14} {'SYSTEMD':<10} {'HTTP':<6} PORT"
    print(header)
    print("-" * 60)
    for row in rows:
        marker = "→ " if row["name"] == active else "  "
        http = "✓" if row.get("http_ok") else "-"
        print(
            f"{marker}{row['name']:<16} "
            f"{row['state']:<14} "
            f"{row.get('systemd', '-'):<10} "
            f"{http:<6} "
            f"{row.get('port', '-')}"
        )
    print()
