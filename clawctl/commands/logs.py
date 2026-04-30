# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl logs — tail service logs with color."""
import subprocess
import sys
from pathlib import Path

import click


LOG_DIR = Path.home() / ".clawos-runtime" / "logs"


SERVICES = [
    "dashd", "clawd", "agentd", "memd", "policyd",
    "modeld", "voiced", "desktopd", "reminderd", "waketrd",
    "a2ad", "toolbridge", "scheduler", "metricd", "picoclawd",
]


def run(service, follow, lines):
    """Tail service logs with color."""
    if service:
        log_file = LOG_DIR / f"{service}.log"
        if not log_file.exists():
            click.echo(f"No logs found for {service}")
            sys.exit(1)
        
        if follow:
            subprocess.run(["tail", "-f", str(log_file)])
        else:
            subprocess.run(["tail", "-n", str(lines), str(log_file)])
    else:
        # List available logs
        click.echo("Available logs:")
        for svc in SERVICES:
            log_file = LOG_DIR / f"{svc}.log"
            if log_file.exists():
                size = log_file.stat().st_size
                size_str = f"{size / 1024:.1f}KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f}MB"
                click.echo(f"  {svc:20} {size_str:10} {log_file}")
            else:
                click.echo(f"  {svc:20} (no logs)")
