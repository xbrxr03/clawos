# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for calendard — Calendar service."""
import pytest
from services.calendard.engine import CalendarEvent, create_event, list_events, delete_event, export_ical


class TestCalendarEvent:
    def test_create(self):
        event = CalendarEvent(id="abc", title="Meeting", start_time="2026-06-03T10:00:00Z")
        assert event.all_day is False
        assert event.tags == []

    def test_to_dict(self):
        event = CalendarEvent(id="abc", title="Meet", description="Team sync")
        d = event.to_dict()
        assert d["title"] == "Meet"

    def test_save_and_load(self, tmp_path):
        import services.calendard.engine as eng
        old_dir = eng.CALENDAR_DIR
        eng.CALENDAR_DIR = tmp_path
        try:
            event = CalendarEvent(id="evt1", title="Sprint Review", start_time="2026-06-05T14:00:00Z",
                                  end_time="2026-06-05T15:00:00Z", tags=["work"])
            event.save()
            loaded = CalendarEvent.load("evt1")
            assert loaded is not None
            assert loaded.title == "Sprint Review"
            assert loaded.tags == ["work"]
        finally:
            eng.CALENDAR_DIR = old_dir

    def test_load_nonexistent(self):
        assert CalendarEvent.load("nonexistent") is None

    def test_to_ical(self):
        event = CalendarEvent(id="abc", title="Test Event", start_time="20260603T100000Z",
                              end_time="20260603T110000Z")
        ical = event.to_ical()
        assert "BEGIN:VEVENT" in ical
        assert "Test Event" in ical


class TestCreateEvent:
    def test_create(self, tmp_path):
        import services.calendard.engine as eng
        old_dir = eng.CALENDAR_DIR
        eng.CALENDAR_DIR = tmp_path
        try:
            event = create_event(title="Daily Standup", start_time="2026-06-03T09:00:00Z",
                                 tags=["daily"])
            assert event.title == "Daily Standup"
            assert event.id != ""
        finally:
            eng.CALENDAR_DIR = old_dir


class TestListEvents:
    def test_list(self, tmp_path):
        import services.calendard.engine as eng
        old_dir = eng.CALENDAR_DIR
        eng.CALENDAR_DIR = tmp_path
        try:
            create_event(title="Event A", start_time="2026-06-03T10:00:00Z", tags=["work"])
            create_event(title="Event B", start_time="2026-06-04T10:00:00Z", tags=["personal"])
            all_events = list_events()
            assert len(all_events) == 2
            work_events = list_events(tag="work")
            assert len(work_events) == 1
        finally:
            eng.CALENDAR_DIR = old_dir


class TestDeleteEvent:
    def test_delete(self, tmp_path):
        import services.calendard.engine as eng
        old_dir = eng.CALENDAR_DIR
        eng.CALENDAR_DIR = tmp_path
        try:
            event = create_event(title="Delete Me")
            assert delete_event(event.id) is True
            assert CalendarEvent.load(event.id) is None
        finally:
            eng.CALENDAR_DIR = old_dir


class TestExportICal:
    def test_export(self, tmp_path):
        import services.calendard.engine as eng
        old_dir = eng.CALENDAR_DIR
        eng.CALENDAR_DIR = tmp_path
        try:
            create_event(title="Sprint", start_time="20260603T100000Z")
            ical = export_ical()
            assert "BEGIN:VCALENDAR" in ical
            assert "END:VCALENDAR" in ical
        finally:
            eng.CALENDAR_DIR = old_dir