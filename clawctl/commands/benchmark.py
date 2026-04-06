# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl benchmark - inspect pack eval readiness and trace volume."""
from __future__ import annotations

from clawos_core.catalog import list_eval_suites, list_traces

from clawctl.ui.banner import info, table


def run():
    print()
    suites = list_eval_suites()
    rows = [(suite.id, suite.pack_id, suite.status, len(suite.checks)) for suite in suites]
    table(rows, headers=("eval", "pack", "status", "checks"))
    traces = list_traces(limit=10)
    info(f"Recent traces available: {len(traces)}")
    print()
