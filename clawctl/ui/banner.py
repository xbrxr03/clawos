# SPDX-License-Identifier: AGPL-3.0-or-later
"""ClawOS terminal UI helpers."""
from __future__ import annotations

from clawos_core.constants import VERSION_FULL

BANNER = f"""
  ____ _                 ___  ____
 / ___| | __ ___      __/ _ \\/ ___|
| |   | |/ _` \\ \\ /\\ / / | | \\___ \\
| |___| | (_| |\\ V  V /| |_| |___) |
 \\____|_|\\__,_| \\_/\\_/  \\___/|____/
  ClawOS {VERSION_FULL} | local | offline | private
"""

MINI = "  [ClawOS] "

_STATUS_ICONS = {
    "active": "[ok]",
    "running": "[ok]",
    "inactive": "[--]",
    "failed": "[!!]",
    "unknown": "[??]",
    "ok": "[ok]",
    "down": "[!!]",
}


def print_banner():
    print(BANNER)


def status_icon(status: str) -> str:
    return _STATUS_ICONS.get((status or "").lower(), "[??]")


def table(rows: list[tuple], headers: tuple | None = None):
    if not rows:
        print("  (empty)")
        return

    all_rows = ([headers] + list(rows)) if headers else list(rows)
    widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(all_rows[0]))]

    if headers:
        header_line = "  " + "  ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers)))
        rule_line = "  " + "  ".join("-" * widths[i] for i in range(len(widths)))
        print(header_line)
        print(rule_line)
        rows = list(rows)

    for row in rows:
        print("  " + "  ".join(str(row[i]).ljust(widths[i]) for i in range(len(row))))


def success(msg: str):
    print(f"  [ok]  {msg}")


def error(msg: str):
    print(f"  [!!]  {msg}")


def info(msg: str):
    print(f"  [..]  {msg}")


def warn(msg: str):
    print(f"  [!]   {msg}")
