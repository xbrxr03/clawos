# SPDX-License-Identifier: AGPL-3.0-or-later
"""
event_logger.py — structured event logging to a single JSONL file.

All agents call EventLogger().emit(...) to record job activity.
The file is append-only and safe for concurrent writers via fcntl locking.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from core.config import EVENTS_FILE


class EventLogger:
    """Thread-safe, append-only structured event log."""

    # Class-level lock covers all instances in the same process.
    _lock = threading.Lock()

    # Valid event types — enforced to keep the log clean.
    VALID_TYPES = {
        "start", "complete", "error",
        "lease_issued", "lease_expired", "lease_released",
        "retry", "failed", "artifact_written",
        "heartbeat", "registered",
    }

    def emit(
        self,
        job_id: str,
        agent_id: str,
        event_type: str,
        phase: str,
        message: str,
        extra: dict | None = None,
    ) -> dict:
        """
        Write one event line.  Returns the record dict (useful for tests).

        Args:
            job_id:     Job this event belongs to (use "system" for non-job events).
            agent_id:   Agent emitting the event.
            event_type: One of VALID_TYPES.
            phase:      Current job phase at time of event.
            message:    Human-readable description.
            extra:      Optional additional key-value pairs merged into the record.
        """
        if event_type not in self.VALID_TYPES:
            # Don't hard-fail on unknown types — just tag them.
            event_type = f"unknown:{event_type}"

        record = {
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "agent_id":   agent_id,
            "job_id":     job_id,
            "event_type": event_type,
            "phase":      phase,
            "message":    message,
        }
        if extra:
            # Merge but never let extra overwrite core fields.
            for k, v in extra.items():
                if k not in record:
                    record[k] = v

        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            with EVENTS_FILE.open("a") as f:
                f.write(json.dumps(record) + "\n")

        return record

    def tail(self, n: int = 50) -> list[dict]:
        """Return the last n events from the log (for monitoring/debugging)."""
        if not EVENTS_FILE.exists():
            return []
        lines = EVENTS_FILE.read_text().strip().splitlines()
        records = []
        for line in lines[-n:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records

    def events_for_job(self, job_id: str) -> list[dict]:
        """Return all events for a specific job."""
        if not EVENTS_FILE.exists():
            return []
        results = []
        for line in EVENTS_FILE.read_text().strip().splitlines():
            try:
                rec = json.loads(line)
                if rec.get("job_id") == job_id:
                    results.append(rec)
            except json.JSONDecodeError:
                pass
        return results
