# SPDX-License-Identifier: AGPL-3.0-or-later
"""Health dashboard - real-time service status overview.

Redirects to the full status command which handles all 22 services
including daemon detection via PID files.
"""
from clawctl.commands.status import run

__all__ = ["run"]