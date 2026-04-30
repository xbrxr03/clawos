# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration tests for reminderd service."""
import asyncio
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from clawos_core.constants import PORT_REMINDERD, CLAWOS_DIR
from services.reminderd.service import ReminderService

REMINDERD_URL = f"http://127.0.0.1:{PORT_REMINDERD}"


class TestReminderService:
    """Unit tests for ReminderService."""
    
    def test_add_reminder(self, tmp_path):
        """Test adding a reminder."""
        db_path = tmp_path / "test_reminders.db"
        service = ReminderService(db_path)
        
        due = datetime.now() + timedelta(hours=1)
        reminder_id = service.add_reminder("Test task", due)
        
        assert reminder_id > 0
        
        reminders = service.list_reminders()
        assert len(reminders) == 1
        assert reminders[0]["task"] == "Test task"
    
    def test_list_reminders_excludes_done(self, tmp_path):
        """Test that done reminders are excluded by default."""
        db_path = tmp_path / "test_reminders.db"
        service = ReminderService(db_path)
        
        # Add two reminders
        due = datetime.now() + timedelta(hours=1)
        id1 = service.add_reminder("Task 1", due)
        id2 = service.add_reminder("Task 2", due)
        
        # Mark one as done
        service.mark_done(id1)
        
        # Should only show one
        reminders = service.list_reminders(include_done=False)
        assert len(reminders) == 1
        assert reminders[0]["task"] == "Task 2"
        
        # Include done should show both
        reminders = service.list_reminders(include_done=True)
        assert len(reminders) == 2


@pytest.mark.asyncio
class TestReminderDaemonAPI:
    """Integration tests for reminderd HTTP API."""
    
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{REMINDERD_URL}/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["service"] == "reminderd"
        except httpx.ConnectError:
            pytest.skip("reminderd not running")
    
    async def test_create_and_list_reminders(self):
        """Test creating and listing reminders via API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Create a reminder
                due = (datetime.now() + timedelta(hours=1)).isoformat()
                response = await client.post(
                    f"{REMINDERD_URL}/reminders",
                    json={"task": "Integration test reminder", "due_at": due},
                )
                assert response.status_code == 200
                data = response.json()
                assert "id" in data
                
                # List reminders
                response = await client.get(f"{REMINDERD_URL}/reminders")
                assert response.status_code == 200
                data = response.json()
                assert "reminders" in data
                
        except httpx.ConnectError:
            pytest.skip("reminderd not running")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
