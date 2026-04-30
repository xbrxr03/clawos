# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration tests for calendar importer."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tools.calendar.import_ics import parse_ics_file, CalendarStore


class TestCalendarImporter:
    """Tests for calendar ICS importer."""

    def test_parse_ics_datetime(self):
        """Test datetime parsing from various ICS formats."""
        from tools.calendar.import_ics import parse_ics_datetime

        # Test all-day date
        dt = parse_ics_datetime("20250430")
        assert dt.year == 2025
        assert dt.month == 4
        assert dt.day == 30

        # Test UTC datetime
        dt = parse_ics_datetime("20250430T140000Z")
        assert dt.hour == 14
        assert dt.minute == 0

        # Test local datetime
        dt = parse_ics_datetime("20250430T100000")
        assert dt.hour == 10
        assert dt.minute == 0

    def test_parse_simple_ics(self, tmp_path):
        """Test parsing a simple ICS file."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:test-1@test.com
DTSTART:20260430T100000Z
DTEND:20260430T110000Z
SUMMARY:Test Meeting
DESCRIPTION:A test meeting
LOCATION:Conference Room
END:VEVENT
END:VCALENDAR"""

        ics_file = tmp_path / "test.ics"
        ics_file.write_text(ics_content)

        events = list(parse_ics_file(ics_file))
        assert len(events) == 1
        assert events[0].summary == "Test Meeting"
        assert events[0].location == "Conference Room"
        assert not events[0].is_all_day

    def test_parse_all_day_event(self, tmp_path):
        """Test parsing an all-day event."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:test-2@test.com
DTSTART:20260430
DTEND:20260501
SUMMARY:All Day Event
END:VEVENT
END:VCALENDAR"""

        ics_file = tmp_path / "test.ics"
        ics_file.write_text(ics_content)

        events = list(parse_ics_file(ics_file))
        assert len(events) == 1
        assert events[0].is_all_day is True
        assert events[0].summary == "All Day Event"


class TestCalendarStore:
    """Tests for CalendarStore."""

    def test_import_event(self, tmp_path):
        """Test importing an event."""
        db_path = tmp_path / "test_calendar.db"
        store = CalendarStore(db_path)

        from tools.calendar.import_ics import CalendarEvent
        event = CalendarEvent(
            uid="test-1",
            summary="Test Event",
            description="Description",
            location="Location",
            start=datetime.now() + timedelta(days=1),
            end=datetime.now() + timedelta(days=1, hours=1),
            is_all_day=False,
            source_file="test.ics",
        )

        is_new = store.import_event(event)
        assert is_new is True

        # Import again should be update
        is_new = store.import_event(event)
        assert is_new is False

    def test_get_upcoming(self, tmp_path):
        """Test getting upcoming events."""
        db_path = tmp_path / "test_calendar.db"
        store = CalendarStore(db_path)

        from tools.calendar.import_ics import CalendarEvent

        # Add future event
        future_event = CalendarEvent(
            uid="future-1",
            summary="Future Event",
            description="",
            location="",
            start=datetime.now() + timedelta(days=1),
            end=datetime.now() + timedelta(days=1, hours=1),
            is_all_day=False,
            source_file="test.ics",
        )
        store.import_event(future_event)

        # Add past event
        past_event = CalendarEvent(
            uid="past-1",
            summary="Past Event",
            description="",
            location="",
            start=datetime.now() - timedelta(days=1),
            end=datetime.now() - timedelta(days=1, hours=1),
            is_all_day=False,
            source_file="test.ics",
        )
        store.import_event(past_event)

        upcoming = store.get_upcoming(days=7)
        assert len(upcoming) == 1
        assert upcoming[0]["summary"] == "Future Event"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
