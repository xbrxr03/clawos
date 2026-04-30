#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Calendar ICS Importer
=====================
Watch ~/.clawos/calendars/ for .ics files and auto-import to SQLite.

Usage:
    python3 -m tools.calendar.import_ics [file.ics]
    
Or run as a daemon:
    python3 -m tools.calendar.import_ics --watch
"""
import argparse
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, List, Optional

from clawos_core.constants import CLAWOS_DIR

log = logging.getLogger("calendar.import")

CALENDARS_DIR = CLAWOS_DIR / "calendars"
CALENDAR_DB = CLAWOS_DIR / "calendar.db"


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    description: str
    location: str
    start: datetime
    end: datetime
    is_all_day: bool
    source_file: str


def parse_ics_datetime(value: str) -> datetime:
    """Parse various ICS datetime formats."""
    value = value.strip()
    
    # Handle all-day dates (YYYYMMDD)
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d")
    
    # Handle UTC datetime (YYYYMMDDTHHMMSSZ)
    if value.endswith('Z'):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    
    # Handle local datetime (YYYYMMDDTHHMMSS)
    if 'T' in value:
        return datetime.strptime(value, "%Y%m%dT%H%M%S")
    
    # Fallback
    return datetime.now()


def parse_ics_file(ics_path: Path) -> Iterator[CalendarEvent]:
    """Parse an ICS file and yield CalendarEvents."""
    log.info(f"Parsing {ics_path}")
    
    content = ics_path.read_text(encoding='utf-8', errors='ignore')
    
    # Split into VEVENT blocks
    events = re.split(r'BEGIN:VEVENT', content)[1:]  # Skip header
    
    for event_block in events:
        if 'END:VEVENT' not in event_block:
            continue
        
        event_text = event_block.split('END:VEVENT')[0]
        
        # Extract fields
        def extract(pattern: str, default: str = "") -> str:
            match = re.search(pattern, event_text, re.IGNORECASE)
            return match.group(1).strip() if match else default
        
        uid = extract(r'UID:(.+?)(?:\r?\n|\r)', str(hash(event_text)))
        summary = extract(r'SUMMARY:(.+?)(?:\r?\n|\r)', "Untitled")
        description = extract(r'DESCRIPTION:(.+?)(?:\r?\n[\w-]+:|\r?\n\r?\n|\r\r)', "")
        location = extract(r'LOCATION:(.+?)(?:\r?\n|\r)', "")
        
        # Handle multi-line description continuation
        desc_lines = [description]
        for line in event_text.split('\n'):
            if line.startswith(' ') and desc_lines:
                desc_lines[-1] += line[1:]
            elif line.upper().startswith('DESCRIPTION:'):
                break
        description = desc_lines[0] if desc_lines else ""
        
        # Parse dates
        dtstart = extract(r'DTSTART[^:]*:(.+?)(?:\r?\n|\r)')
        dtend = extract(r'DTEND[^:]*:(.+?)(?:\r?\n|\r)')
        
        try:
            start = parse_ics_datetime(dtstart) if dtstart else datetime.now()
        except:
            start = datetime.now()
        
        try:
            end = parse_ics_datetime(dtend) if dtend else start + timedelta(hours=1)
        except:
            end = start + timedelta(hours=1)
        
        # All-day if no time component
        is_all_day = 'T' not in dtstart if dtstart else False
        
        yield CalendarEvent(
            uid=uid,
            summary=summary.replace('\\,', ',').replace('\\n', '\n'),
            description=description.replace('\\,', ',').replace('\\n', '\n'),
            location=location.replace('\\,', ','),
            start=start,
            end=end,
            is_all_day=is_all_day,
            source_file=ics_path.name,
        )


class CalendarStore:
    """SQLite-backed calendar storage."""
    
    def __init__(self, db_path: Path = CALENDAR_DB):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    uid TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    description TEXT,
                    location TEXT,
                    start_timestamp REAL NOT NULL,
                    end_timestamp REAL NOT NULL,
                    is_all_day INTEGER DEFAULT 0,
                    source_file TEXT,
                    imported_at REAL DEFAULT (unixepoch())
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_start 
                ON events(start_timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_source 
                ON events(source_file)
            """)
    
    def import_event(self, event: CalendarEvent) -> bool:
        """Import a single event. Returns True if new, False if updated."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT 1 FROM events WHERE uid = ?",
                (event.uid,)
            ).fetchone()
            
            conn.execute("""
                INSERT INTO events 
                (uid, summary, description, location, start_timestamp, 
                 end_timestamp, is_all_day, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    summary=excluded.summary,
                    description=excluded.description,
                    location=excluded.location,
                    start_timestamp=excluded.start_timestamp,
                    end_timestamp=excluded.end_timestamp,
                    is_all_day=excluded.is_all_day,
                    source_file=excluded.source_file,
                    imported_at=unixepoch()
            """, (
                event.uid, event.summary, event.description, event.location,
                event.start.timestamp(), event.end.timestamp(),
                int(event.is_all_day), event.source_file
            ))
            
            return existing is None
    
    def get_today_events(self) -> List[dict]:
        """Get today's events."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM events 
                WHERE start_timestamp >= ? AND start_timestamp < ?
                ORDER BY start_timestamp
            """, (today.timestamp(), tomorrow.timestamp())).fetchall()
            
            return [
                {
                    "uid": r["uid"],
                    "summary": r["summary"],
                    "description": r["description"],
                    "location": r["location"],
                    "start": datetime.fromtimestamp(r["start_timestamp"]).isoformat(),
                    "end": datetime.fromtimestamp(r["end_timestamp"]).isoformat(),
                    "is_all_day": bool(r["is_all_day"]),
                }
                for r in rows
            ]
    
    def get_upcoming(self, days: int = 7) -> List[dict]:
        """Get upcoming events."""
        now = datetime.now()
        future = now + timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM events 
                WHERE start_timestamp >= ? AND start_timestamp <= ?
                ORDER BY start_timestamp
                LIMIT 50
            """, (now.timestamp(), future.timestamp())).fetchall()
            
            return [
                {
                    "uid": r["uid"],
                    "summary": r["summary"],
                    "description": r["description"],
                    "location": r["location"],
                    "start": datetime.fromtimestamp(r["start_timestamp"]).isoformat(),
                    "end": datetime.fromtimestamp(r["end_timestamp"]).isoformat(),
                    "is_all_day": bool(r["is_all_day"]),
                }
                for r in rows
            ]


def import_ics_file(ics_path: Path, store: CalendarStore) -> tuple[int, int]:
    """Import a single ICS file. Returns (added, updated)."""
    added = 0
    updated = 0
    
    for event in parse_ics_file(ics_path):
        is_new = store.import_event(event)
        if is_new:
            added += 1
        else:
            updated += 1
    
    log.info(f"Imported {ics_path.name}: {added} new, {updated} updated")
    return added, updated


def watch_and_import():
    """Watch calendar directory for new files."""
    CALENDARS_DIR.mkdir(parents=True, exist_ok=True)
    store = CalendarStore()
    
    # Import existing files
    imported_files: set[str] = set()
    for ics_file in CALENDARS_DIR.glob("*.ics"):
        import_ics_file(ics_file, store)
        imported_files.add(ics_file.name)
    
    log.info(f"Watching {CALENDARS_DIR} for new .ics files...")
    
    # Watch loop
    while True:
        time.sleep(5)
        
        for ics_file in CALENDARS_DIR.glob("*.ics"):
            # Simple mtime check would be better but this works for now
            if ics_file.name not in imported_files:
                import_ics_file(ics_file, store)
                imported_files.add(ics_file.name)


def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    
    parser = argparse.ArgumentParser(description="Import calendar ICS files")
    parser.add_argument("files", nargs="*", help="ICS files to import")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch for new files")
    parser.add_argument("--today", "-t", action="store_true", help="Show today's events")
    parser.add_argument("--upcoming", "-u", action="store_true", help="Show upcoming events")
    
    args = parser.parse_args()
    
    store = CalendarStore()
    
    if args.today:
        events = store.get_today_events()
        print(f"Today's events ({len(events)}):")
        for e in events:
            print(f"  {e['summary']} at {e['start']}")
        return
    
    if args.upcoming:
        events = store.get_upcoming()
        print(f"Upcoming events ({len(events)}):")
        for e in events:
            print(f"  {e['summary']} at {e['start']}")
        return
    
    if args.watch:
        watch_and_import()
        return
    
    if args.files:
        for ics_path in args.files:
            import_ics_file(Path(ics_path), store)
    else:
        # Import all in calendar dir
        CALENDARS_DIR.mkdir(parents=True, exist_ok=True)
        for ics_file in CALENDARS_DIR.glob("*.ics"):
            import_ics_file(ics_file, store)


if __name__ == "__main__":
    main()
