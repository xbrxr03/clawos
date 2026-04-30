# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reminder service client."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from clawos_core.constants import CLAWOS_DIR

REMINDER_DB_PATH = CLAWOS_DIR / "reminders.db"


class ReminderService:
    """Client for reminder operations."""
    
    def __init__(self, db_path: Path = REMINDER_DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Ensure database exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    due_at REAL NOT NULL,
                    done INTEGER DEFAULT 0,
                    created_at REAL DEFAULT (unixepoch())
                )
            """)
    
    def add_reminder(self, task: str, due_at: datetime) -> int:
        """Add a new reminder."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO reminders (task, due_at) VALUES (?, ?)",
                (task, due_at.timestamp())
            )
            return cursor.lastrowid
    
    def list_reminders(self, include_done: bool = False) -> List[dict]:
        """List reminders."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if include_done:
                rows = conn.execute(
                    "SELECT * FROM reminders ORDER BY due_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE done = 0 ORDER BY due_at"
                ).fetchall()
            return [
                {
                    "id": row["id"],
                    "task": row["task"],
                    "due_at": datetime.fromtimestamp(row["due_at"]).isoformat(),
                    "done": bool(row["done"]),
                }
                for row in rows
            ]
    
    def mark_done(self, reminder_id: int):
        """Mark a reminder as done."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))
