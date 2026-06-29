# SPDX-License-Identifier: AGPL-3.0-or-later
"""
calendard — Calendar Service
=============================
Local event management. Events stored as JSON in ~/.clawos/calendar/.
Supports iCal export for integration with external calendars.
"""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger("calendard")

try:
    from clawos_core.constants import CONFIG_DIR
    CALENDAR_DIR = CONFIG_DIR / "calendar"
except (ImportError, ModuleNotFoundError):
    CALENDAR_DIR = Path.home() / ".clawos" / "calendar"


@dataclass
class CalendarEvent:
    id: str
    title: str
    description: str = ""
    start_time: str = ""  # ISO format
    end_time: str = ""
    all_day: bool = False
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self) -> None:
        CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
        path = CALENDAR_DIR / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, event_id: str) -> Optional["CalendarEvent"]:
        path = CALENDAR_DIR / f"{event_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**data)
        except (json.JSONDecodeError, ValueError):
            return None

    def to_ical(self) -> str:
        """Export as iCal VEVENT."""
        uid = f"{self.id}@clawos"
        dtstart = self.start_time.replace("-", "").replace(":", "").replace("+", "+")
        dtend = self.end_time.replace("-", "").replace(":", "").replace("+", "+") if self.end_time else ""
        lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}",
            f"DTSTART:{dtstart}",
        ]
        if dtend:
            lines.append(f"DTEND:{dtend}")
        lines.extend([
            f"SUMMARY:{self.title}",
            f"DESCRIPTION:{self.description}",
            "END:VEVENT",
        ])
        return "\r\n".join(lines)


def create_event(title: str, description: str = "", start_time: str = "",
                  end_time: str = "", all_day: bool = False, tags: list[str] | None = None) -> CalendarEvent:
    import secrets
    event_id = secrets.token_hex(6)
    event = CalendarEvent(
        id=event_id, title=title, description=description,
        start_time=start_time, end_time=end_time,
        all_day=all_day, tags=tags or [],
    )
    event.save()
    return event


def list_events(from_date: str | None = None, to_date: str | None = None, tag: str | None = None) -> list[dict]:
    """List events with optional date range and tag filter."""
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    events = []
    for path in sorted(CALENDAR_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            continue
        if tag and tag not in data.get("tags", []):
            continue
        if from_date and data.get("start_time", "") < from_date:
            continue
        if to_date and data.get("start_time", "") > to_date:
            continue
        events.append(data)
    return events


def delete_event(event_id: str) -> bool:
    path = CALENDAR_DIR / f"{event_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def export_ical() -> str:
    """Export all events as iCal."""
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    events = []
    for path in CALENDAR_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            event = CalendarEvent(**data)
            events.append(event.to_ical())
        except (json.JSONDecodeError, ValueError):
            continue
    calendar = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ClawOS//Calendar//EN",
        *events,
        "END:VCALENDAR",
    ]
    return "\r\n".join(calendar)