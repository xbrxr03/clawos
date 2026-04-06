# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl budget — show per-workspace token usage."""
from clawctl.ui.banner import success, error, info, table
from clawos_core.constants import DEFAULT_DAILY_TOKEN_BUDGET


def run():
    """Show today and this week's token usage per workspace."""
    print()
    try:
        from services.metricd.service import get_metrics
        m = get_metrics()
        summary = m.workspace_summary()
        if not summary:
            info("No token usage recorded yet.")
            return
        rows = []
        for ws in summary:
            wid   = ws["workspace_id"]
            today = ws["tokens_today"]
            week  = m.week_tokens(wid)
            limit = DEFAULT_DAILY_TOKEN_BUDGET
            pct   = round(today / limit * 100) if limit > 0 else 0
            over  = " ⚠ OVER BUDGET" if m.is_over_budget(wid) else ""
            rows.append((wid, f"{today:,}", f"{week:,}", f"{pct}%{over}"))
        table(rows, headers=("workspace", "tokens today", "tokens this week", "budget %"))
        print(f"\n  Daily limit: {DEFAULT_DAILY_TOKEN_BUDGET:,} tokens per workspace\n")
    except Exception as e:
        error(f"metricd unavailable: {e}")
    print()
