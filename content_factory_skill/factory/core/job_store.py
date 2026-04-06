# SPDX-License-Identifier: AGPL-3.0-or-later
"""
job_store.py — all reads and writes to job.json files.

The job file is the single source of truth for job state.
This module is the ONLY place that touches job.json directly.
"""

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import (
    INBOX_DIR, ACTIVE_DIR, COMPLETED_DIR, FAILED_DIR,
    PHASE_SEQUENCE, MAX_RETRIES,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_dir(base: Path, job_id: str) -> Path:
    return base / job_id


def _find_job(job_id: str) -> Optional[Path]:
    """Locate job.json regardless of which queue dir it currently lives in."""
    for base in [ACTIVE_DIR, INBOX_DIR, COMPLETED_DIR, FAILED_DIR]:
        p = base / job_id / "job.json"
        if p.exists():
            return p
    return None


class JobStore:
    # ── creation ──────────────────────────────────────────────────────────────

    def create(self, topic: str, priority: int = 5, template: str = "") -> dict:
        """
        Create a new job in the inbox and return the job dict.
        Raises RuntimeError if INBOX_MAX_DEPTH > 0 and the inbox is at capacity.
        """
        from core.config import INBOX_MAX_DEPTH
        if INBOX_MAX_DEPTH > 0:
            current_depth = sum(1 for _ in INBOX_DIR.glob("*/job.json"))
            if current_depth >= INBOX_MAX_DEPTH:
                raise RuntimeError(
                    f"Inbox at capacity ({current_depth}/{INBOX_MAX_DEPTH}). "
                    f"Wait for jobs to be processed before submitting more."
                )
        job_id = f"job_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = _now()
        job = {
            "job_id":         job_id,
            "topic":          topic,
            "status":         "pending",
            "phase":          "created",
            "priority":       priority,
            "template":       template or None,
            "pipeline_config": None,
            "retry_count":    0,
            "max_retries":    MAX_RETRIES,
            "assigned_agent": None,
            "lease":          None,
            "created_at":     now,
            "updated_at":     now,
            "artifacts": {
                "script":     None,
                "metadata":   None,
                "shots":      None,
                "images":     [],
                "thumbnail":  None,
                "voice":      None,
                "edit_plan":  None,
            },
            "events":  [],
            "metrics": {
                "writing_duration_s":      None,
                "visualizing_duration_s":  None,
                "voice_duration_s":        None,
                "assembling_duration_s":   None,
                "total_duration_s":        None,
            },
            "errors": [],
        }
        job_dir = INBOX_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "job.json").write_text(json.dumps(job, indent=2))
        return job

    # ── loading ───────────────────────────────────────────────────────────────

    def load(self, job_id: str) -> Optional[dict]:
        p = _find_job(job_id)
        if not p:
            return None
        return json.loads(p.read_text())

    def load_all_inbox(self) -> list[dict]:
        """Return all jobs in the inbox, sorted by priority (high → low), then created_at."""
        jobs = []
        for p in INBOX_DIR.glob("*/job.json"):
            try:
                jobs.append(json.loads(p.read_text()))
            except Exception:
                pass
        return sorted(jobs, key=lambda j: (-j.get("priority", 5), j.get("created_at", "")))

    def load_all_active(self) -> list[dict]:
        jobs = []
        for p in ACTIVE_DIR.glob("*/job.json"):
            try:
                jobs.append(json.loads(p.read_text()))
            except Exception:
                pass
        return jobs

    # ── saving ────────────────────────────────────────────────────────────────

    def save(self, job: dict):
        """Write a job dict back to disk. Finds current location automatically."""
        job["updated_at"] = _now()
        p = _find_job(job["job_id"])
        if p:
            p.write_text(json.dumps(job, indent=2))
        else:
            raise FileNotFoundError(f"job.json not found for {job['job_id']}")

    # ── phase transitions ─────────────────────────────────────────────────────

    def promote_to_active(self, job_id: str) -> dict:
        """Move job from inbox → active."""
        src = INBOX_DIR / job_id
        dst = ACTIVE_DIR / job_id
        shutil.move(str(src), str(dst))
        job = json.loads((dst / "job.json").read_text())
        job["status"] = "active"
        job["updated_at"] = _now()
        (dst / "job.json").write_text(json.dumps(job, indent=2))
        return job

    def advance_phase(self, job_id: str) -> dict:
        """Move to the next phase in PHASE_SEQUENCE."""
        job = self.load(job_id)
        current = job["phase"]
        if current in PHASE_SEQUENCE:
            idx = PHASE_SEQUENCE.index(current)
            if idx + 1 < len(PHASE_SEQUENCE):
                job["phase"] = PHASE_SEQUENCE[idx + 1]
        elif current == "created":
            job["phase"] = PHASE_SEQUENCE[0]  # → writing
        if job["phase"] == "complete":
            self._move_to_completed(job)
        else:
            self.save(job)
        return job

    def update_phase(self, job_id: str, phase: str):
        """Set an explicit phase (used by foreman when issuing leases)."""
        job = self.load(job_id)
        job["phase"] = phase
        job["updated_at"] = _now()
        self.save(job)

    def set_lease(self, job_id: str, lease: dict):
        job = self.load(job_id)
        job["lease"] = lease
        job["assigned_agent"] = lease["agent_id"]
        job["status"] = "active"
        self.save(job)

    def clear_lease(self, job_id: str):
        job = self.load(job_id)
        job["lease"] = None
        job["assigned_agent"] = None
        self.save(job)

    def register_artifact(self, job_id: str, key: str, path: str):
        job = self.load(job_id)
        if not job:
            return  # job not in store (e.g. tests with synthetic job_ids)
        if key.startswith("image"):
            job["artifacts"]["images"].append(path)
        elif key == "thumbnail":
            job["artifacts"]["thumbnail"] = path
        elif key in job["artifacts"]:
            job["artifacts"][key] = path
        self.save(job)

    def record_metric(self, job_id: str, key: str, value):
        job = self.load(job_id)
        job["metrics"][key] = value
        self.save(job)

    def record_error(self, job_id: str, error: str):
        job = self.load(job_id)
        job["errors"].append({"timestamp": _now(), "error": error})
        self.save(job)

    # ── failure handling ──────────────────────────────────────────────────────

    def mark_retry(self, job_id: str) -> dict:
        job = self.load(job_id)
        job["retry_count"] = job.get("retry_count", 0) + 1
        job["phase"] = "created"      # reset to re-enter pipeline from top
        job["status"] = "pending"
        job["lease"] = None
        job["assigned_agent"] = None
        job["updated_at"] = _now()
        # Move back to inbox
        src = ACTIVE_DIR / job_id
        dst = INBOX_DIR / job_id
        if src.exists():
            shutil.move(str(src), str(dst))
            (dst / "job.json").write_text(json.dumps(job, indent=2))
        return job

    def mark_failed(self, job_id: str, reason: str = "max retries exceeded") -> dict:
        job = self.load(job_id)
        job["status"] = "failed"
        job["lease"] = None
        job["assigned_agent"] = None
        job["errors"].append({"timestamp": _now(), "error": reason})
        job["updated_at"] = _now()
        self._move_to_failed(job)
        return job


    def cancel_job(self, job_id: str, reason: str = "cancelled by operator") -> dict:
        """
        Cancel a pending or active job.
        Moves it to the failed queue with status='cancelled'.
        The foreman will see the lease expire and skip retry since status is set.
        """
        job = self.load(job_id)
        if not job:
            raise FileNotFoundError(f"Job {job_id} not found")
        if job.get("status") in ("complete", "failed", "cancelled"):
            raise ValueError(f"Job {job_id} is already {job['status']} — cannot cancel")
        job["status"]         = "cancelled"
        job["lease"]          = None
        job["assigned_agent"] = None
        job["errors"].append({"timestamp": _now(), "error": reason})
        job["updated_at"] = _now()
        self._move_to_failed(job)
        return job

    def pause_job(self, job_id: str) -> dict:
        """
        Pause a pending inbox job so the foreman skips it during scheduling.
        Only works on inbox (pending) jobs — active jobs cannot be paused mid-run.
        """
        job = self.load(job_id)
        if not job:
            raise FileNotFoundError(f"Job {job_id} not found")
        if job.get("status") != "pending":
            raise ValueError(
                f"Job {job_id} is {job['status']} — only pending inbox jobs can be paused"
            )
        job["status"]     = "paused"
        job["updated_at"] = _now()
        self.save(job)
        return job

    def resume_job(self, job_id: str) -> dict:
        """Resume a previously paused job by setting status back to pending."""
        job = self.load(job_id)
        if not job:
            raise FileNotFoundError(f"Job {job_id} not found")
        if job.get("status") != "paused":
            raise ValueError(f"Job {job_id} is not paused (status={job['status']})")
        job["status"]     = "pending"
        job["updated_at"] = _now()
        self.save(job)
        return job

    def load_all(self) -> list[dict]:
        """Return every job across all queues, sorted by updated_at descending."""
        jobs = []
        for base in [ACTIVE_DIR, INBOX_DIR, COMPLETED_DIR, FAILED_DIR]:
            for p in base.glob("*/job.json"):
                try:
                    jobs.append(json.loads(p.read_text()))
                except Exception:
                    pass
        return sorted(jobs, key=lambda j: j.get("updated_at", ""), reverse=True)

    # ── queue counts ──────────────────────────────────────────────────────────

    def queue_depth(self) -> dict:
        return {
            "inbox":     sum(1 for _ in INBOX_DIR.glob("*/job.json")),
            "active":    sum(1 for _ in ACTIVE_DIR.glob("*/job.json")),
            "completed": sum(1 for _ in COMPLETED_DIR.glob("*/job.json")),
            "failed":    sum(1 for _ in FAILED_DIR.glob("*/job.json")),
        }

    # ── internal moves ────────────────────────────────────────────────────────

    def _move_to_completed(self, job: dict):
        job["status"] = "complete"
        job["updated_at"] = _now()
        src = ACTIVE_DIR / job["job_id"]
        dst = COMPLETED_DIR / job["job_id"]
        if src.exists():
            shutil.move(str(src), str(dst))
            (dst / "job.json").write_text(json.dumps(job, indent=2))
        else:
            self.save(job)

    def _move_to_failed(self, job: dict):
        for base in [ACTIVE_DIR, INBOX_DIR]:
            src = base / job["job_id"]
            if src.exists():
                dst = FAILED_DIR / job["job_id"]
                shutil.move(str(src), str(dst))
                (dst / "job.json").write_text(json.dumps(job, indent=2))
                return
