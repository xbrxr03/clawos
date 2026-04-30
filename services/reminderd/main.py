# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reminder Daemon (reminderd)
==============================
Ticks every 30s, queries reminders.db, fires desktop notifications.

Linux: notify-send + paplay
macOS: osascript (v1.1)
"""
import asyncio
import json
import logging
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from clawos_core.constants import CLAWOS_DIR, PORT_REMINDERD

log = logging.getLogger("reminderd")

REMINDER_DB_PATH = CLAWOS_DIR / "reminders.db"
CHECK_INTERVAL = 30  # seconds


@dataclass
class Reminder:
    id: int
    task: str
    due_at: datetime
    done: bool
    created_at: datetime


class ReminderStore:
    """SQLite-backed reminder storage."""
    
    def __init__(self, db_path: Path = REMINDER_DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database."""
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_due ON reminders(due_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_done ON reminders(done)")
    
    def get_due_reminders(self) -> List[Reminder]:
        """Get reminders that are due and not done."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM reminders WHERE due_at <= ? AND done = 0",
                (now,)
            ).fetchall()
            return [
                Reminder(
                    id=row["id"],
                    task=row["task"],
                    due_at=datetime.fromtimestamp(row["due_at"]),
                    done=bool(row["done"]),
                    created_at=datetime.fromtimestamp(row["created_at"]),
                )
                for row in rows
            ]
    
    def mark_done(self, reminder_id: int):
        """Mark a reminder as done."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE reminders SET done = 1 WHERE id = ?",
                (reminder_id,)
            )
    
    def add_reminder(self, task: str, due_at: datetime) -> int:
        """Add a new reminder. Returns the ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO reminders (task, due_at) VALUES (?, ?)",
                (task, due_at.timestamp())
            )
            return cursor.lastrowid


class NotificationService:
    """Cross-platform desktop notifications."""
    
    def __init__(self):
        self.linux_sound = CLAWOS_DIR / "sounds" / "notification.wav"
        if not self.linux_sound.exists():
            self.linux_sound = None
    
    def notify(self, title: str, message: str):
        """Send desktop notification."""
        # Try notify-send first (Linux)
        try:
            subprocess.run(
                ["notify-send", "--urgency=normal", "--app-name=Nexus", title, message],
                check=True,
                capture_output=True,
                timeout=5,
            )
            self._play_sound()
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Try zenity as fallback (Linux)
        try:
            subprocess.run(
                ["zenity", "--info", "--title", title, "--text", message],
                check=False,
                timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        log.warning(f"Could not send notification: {title} - {message}")
        return False
    
    def _play_sound(self):
        """Play notification sound."""
        if self.linux_sound and self.linux_sound.exists():
            try:
                subprocess.run(
                    ["paplay", str(self.linux_sound)],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass


class ReminderDaemon:
    """Main daemon that checks for due reminders."""
    
    def __init__(self):
        self.store = ReminderStore()
        self.notifier = NotificationService()
        self.running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the daemon."""
        self.running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Reminder daemon started")
    
    async def stop(self):
        """Stop the daemon."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Reminder daemon stopped")
    
    async def _loop(self):
        """Main loop - check for due reminders every 30s."""
        while self.running:
            try:
                await self._check_reminders()
            except Exception as e:
                log.error(f"Error checking reminders: {e}")
            await asyncio.sleep(CHECK_INTERVAL)
    
    async def _check_reminders(self):
        """Check for and fire due reminders."""
        due = self.store.get_due_reminders()
        for reminder in due:
            log.info(f"Firing reminder: {reminder.task}")
            self.notifier.notify("Nexus Reminder", reminder.task)
            self.store.mark_done(reminder.id)


# FastAPI app for HTTP API
app = FastAPI(title="Reminder Daemon", version="1.0.0")
daemon: Optional[ReminderDaemon] = None
store: Optional[ReminderStore] = None


@app.on_event("startup")
async def startup():
    global daemon, store
    store = ReminderStore()
    daemon = ReminderDaemon()
    await daemon.start()


@app.on_event("shutdown")
async def shutdown():
    if daemon:
        await daemon.stop()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "reminderd",
        "timestamp": time.time(),
    }


@app.get("/reminders")
async def list_reminders():
    """List all pending reminders."""
    if not store:
        raise HTTPException(status_code=503, detail="Service not ready")
    due = store.get_due_reminders()
    return {
        "reminders": [
            {
                "id": r.id,
                "task": r.task,
                "due_at": r.due_at.isoformat(),
                "done": r.done,
            }
            for r in due
        ]
    }


@app.post("/reminders")
async def create_reminder(task: str, due_at: str):
    """Create a new reminder."""
    if not store:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        due = datetime.fromisoformat(due_at)
        reminder_id = store.add_reminder(task, due)
        return {"id": reminder_id, "task": task, "due_at": due_at}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {e}")


def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    uvicorn.run(app, host="127.0.0.1", port=PORT_REMINDERD)


if __name__ == "__main__":
    main()
