# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Per-workspace token budgets.
Reads from configs/defaults.yaml metricd.budget section.
Enforced by policyd via MetricsService.is_over_budget().
"""
import json
import sqlite3
from pathlib import Path
from clawos_core.constants import LOGS_DIR, DEFAULT_DAILY_TOKEN_BUDGET
from clawos_core.util.time import now_iso


_BUDGET_DB = LOGS_DIR / "budget.db"


def _open_db() -> sqlite3.Connection:
    _BUDGET_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_BUDGET_DB), check_same_thread=False)
    db.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL,
            day          TEXT NOT NULL,
            tokens       INTEGER DEFAULT 0
        )
    """)
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_ws_day
        ON token_usage(workspace_id, day)
    """)
    db.commit()
    return db


def add_tokens(workspace_id: str, tokens: int):
    """Increment today's token count for this workspace."""
    day = now_iso()[:10]   # YYYY-MM-DD
    db = _open_db()
    db.execute("""
        INSERT INTO token_usage (workspace_id, day, tokens)
        VALUES (?, ?, ?)
        ON CONFLICT(workspace_id, day) DO UPDATE SET tokens = tokens + excluded.tokens
    """, (workspace_id, day, tokens))
    db.commit()
    db.close()


def get_today(workspace_id: str) -> int:
    """Return today's token count for workspace."""
    day = now_iso()[:10]
    db = _open_db()
    row = db.execute(
        "SELECT tokens FROM token_usage WHERE workspace_id=? AND day=?",
        (workspace_id, day)
    ).fetchone()
    db.close()
    return row[0] if row else 0


def get_week(workspace_id: str) -> int:
    """Return this week's total tokens for workspace."""
    from datetime import date, timedelta
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    db = _open_db()
    row = db.execute(
        "SELECT SUM(tokens) FROM token_usage WHERE workspace_id=? AND day >= ?",
        (workspace_id, week_start)
    ).fetchone()
    db.close()
    return row[0] or 0


def is_over_budget(workspace_id: str, daily_limit: int = DEFAULT_DAILY_TOKEN_BUDGET) -> bool:
    """Return True if workspace has exceeded its daily token budget."""
    if daily_limit <= 0:
        return False
    return get_today(workspace_id) >= daily_limit


def all_workspaces_summary() -> list[dict]:
    """Return token usage summary for all workspaces (for dashboard)."""
    day = now_iso()[:10]
    db = _open_db()
    rows = db.execute(
        "SELECT workspace_id, SUM(tokens) FROM token_usage WHERE day=? GROUP BY workspace_id",
        (day,)
    ).fetchall()
    db.close()
    return [{"workspace_id": r[0], "tokens_today": r[1]} for r in rows]
