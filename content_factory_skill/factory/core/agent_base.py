"""
agent_base.py — base class that every agent inherits.

Provides:
  - boot / register / idle loop
  - heartbeat publishing
  - lease lifecycle (request → execute → release)
  - event emission helpers
  - artifact read/write helpers
  - structured file logging

Agents only need to implement:
  - phase_name  (property)
  - resource_class  (property)
  - process_job(job)  (the actual work)
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psutil

from core.config import (
    AGENTS_STATE, LOGS_DIR, ARTIFACTS_DIR,
    HEARTBEAT_INTERVAL,
)
from core.event_logger import EventLogger
from core.job_store import JobStore
from core.lease_manager import LeaseManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentBase(ABC):
    """
    Long-running agent base class.

    Subclass, implement phase_name / resource_class / process_job,
    then call agent.run() from the service entry point.
    """

    POLL_INTERVAL = 2   # seconds to wait when inbox is empty

    def __init__(self, agent_id: str):
        self.agent_id      = agent_id
        self.job_store     = JobStore()
        self.lease_manager = LeaseManager()
        self.event_logger  = EventLogger()
        self._current_job: Optional[dict] = None
        self._proc         = psutil.Process()

        AGENTS_STATE.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        self.logger = self._build_logger()

    # ── subclass contract ─────────────────────────────────────────────────────

    @property
    @abstractmethod
    def phase_name(self) -> str:
        """The pipeline phase this agent is responsible for."""

    @property
    @abstractmethod
    def resource_class(self) -> str:
        """'heavy' | 'medium' | 'light'"""

    @abstractmethod
    def process_job(self, job: dict):
        """
        Perform the actual work for this phase.

        Rules:
          1. Always call self.artifact_exists(job_id, filename) before
             generating anything — support safe resume.
          2. Write all output via self.write_artifact().
          3. Raise any exception on unrecoverable error; the base class
             handles retry / failed bookkeeping.
        """

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        self._register()
        self.logger.info(f"[{self.agent_id}] registered — entering idle loop")
        last_hb = 0.0

        while True:
            now = time.monotonic()

            # Heartbeat
            if now - last_hb >= HEARTBEAT_INTERVAL:
                self._publish_heartbeat()
                last_hb = now

            # Check for operator pause signal
            if self._is_paused():
                self.logger.debug(f"[{self.agent_id}] paused by operator signal")
                self._write_agent_state("paused")
                time.sleep(self.POLL_INTERVAL)
                continue

            # Check for a lease the foreman has issued us
            job = self.lease_manager.request_lease(self.agent_id)
            if job:
                self._current_job = job
                self._execute(job)
                self._current_job = None
            else:
                time.sleep(self.POLL_INTERVAL)

    def _is_paused(self) -> bool:
        """Return True if an operator has written a pause signal for this agent."""
        from core.config import AGENTS_STATE
        return (AGENTS_STATE / f"{self.agent_id}.signal").exists()

    # ── registration / heartbeat ──────────────────────────────────────────────

    def _register(self):
        self._write_agent_state("idle")
        self.event_logger.emit(
            "system", self.agent_id, "registered", "boot",
            f"{self.agent_id} started"
        )

    def _publish_heartbeat(self):
        self._write_agent_state(
            "processing" if self._current_job else "idle",
            self._current_job,
        )

    def _write_agent_state(self, status: str, job: Optional[dict] = None):
        try:
            mem_mb = self._proc.memory_info().rss // (1024 * 1024)
            cpu    = self._proc.cpu_percent(interval=None)
        except psutil.NoSuchProcess:
            mem_mb, cpu = 0, 0.0

        record = {
            "agent_id":       self.agent_id,
            "resource_class": self.resource_class,
            "phase_name":     self.phase_name,
            "status":         status,
            "current_job":    job["job_id"] if job else None,
            "cpu_percent":    cpu,
            "memory_mb":      mem_mb,
            "timestamp":      _now(),
        }
        path = AGENTS_STATE / f"{self.agent_id}.json"
        tmp  = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2))
        tmp.replace(path)

    # ── execution ─────────────────────────────────────────────────────────────

    def _execute(self, job: dict):
        job_id = job["job_id"]
        start  = time.monotonic()

        try:
            self.logger.info(f"[{self.agent_id}] starting job={job_id} phase={self.phase_name}")
            self.job_store.update_phase(job_id, self.phase_name)
            self.event_logger.emit(job_id, self.agent_id, "start",
                                   self.phase_name, f"Starting {self.phase_name}")

            self.process_job(job)

            elapsed = round(time.monotonic() - start, 2)
            metric_key = f"{self.phase_name.rstrip('ing')}_duration_s"  # e.g. writing → writ
            self.job_store.record_metric(job_id, f"{self.phase_name}_duration_s", elapsed)

            self.event_logger.emit(job_id, self.agent_id, "complete",
                                   self.phase_name,
                                   f"Completed {self.phase_name} in {elapsed}s")
            self.logger.info(f"[{self.agent_id}] completed job={job_id} in {elapsed}s")

            # Advance the job to the next phase and release the lease
            self.job_store.advance_phase(job_id)
            self.lease_manager.release_lease(job_id, self.agent_id)
            self.job_store.clear_lease(job_id)

            # Re-queue for the next phase if not complete
            updated = self.job_store.load(job_id)
            if updated and updated.get("phase") not in ("complete", "failed"):
                self._return_to_inbox(job_id)

        except Exception as exc:
            elapsed = round(time.monotonic() - start, 2)
            self.logger.error(f"[{self.agent_id}] error job={job_id}: {exc}", exc_info=True)
            self.event_logger.emit(job_id, self.agent_id, "error",
                                   self.phase_name, str(exc))
            self.job_store.record_error(job_id, str(exc))

            # Foreman handles retry/fail on next tick via expired lease
            # (we intentionally do NOT release the lease here so foreman sees it expired)

    def _return_to_inbox(self, job_id: str):
        """Move an active job back to the inbox so the foreman re-routes it."""
        import shutil
        from core.config import ACTIVE_DIR, INBOX_DIR
        src = ACTIVE_DIR / job_id
        dst = INBOX_DIR / job_id
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
            job = self.job_store.load(job_id)
            if job:
                job["status"] = "pending"
                job["assigned_agent"] = None
                job["lease"] = None
                (dst / "job.json").write_text(json.dumps(job, indent=2))

    # ── artifact helpers ──────────────────────────────────────────────────────

    def artifact_dir(self, job_id: str) -> Path:
        p = ARTIFACTS_DIR / job_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def artifact_path(self, job_id: str, filename: str) -> Path:
        return self.artifact_dir(job_id) / filename

    def artifact_exists(self, job_id: str, filename: str) -> bool:
        """Check before generating — enables safe resume after crash."""
        return self.artifact_path(job_id, filename).exists()

    def write_artifact(self, job_id: str, filename: str, content):
        """
        Write content to the artifact dir and register in job.json.

        content can be: str, bytes, dict, or list.
        """
        dest = self.artifact_path(job_id, filename)
        if isinstance(content, bytes):
            dest.write_bytes(content)
        elif isinstance(content, (dict, list)):
            dest.write_text(json.dumps(content, indent=2))
        else:
            dest.write_text(str(content))
        self.job_store.register_artifact(job_id, filename.split(".")[0], str(dest))
        self.event_logger.emit(
            job_id, self.agent_id, "artifact_written",
            self.phase_name, f"Wrote {filename}",
        )
        self.logger.debug(f"[{self.agent_id}] artifact written: {dest}")
        return dest

    def read_artifact(self, job_id: str, filename: str) -> Optional[str]:
        """Read a text artifact written by an earlier phase."""
        p = self.artifact_path(job_id, filename)
        if p.exists():
            return p.read_text()
        return None

    # ── logger setup ─────────────────────────────────────────────────────────

    def _build_logger(self) -> logging.Logger:
        log = logging.getLogger(self.agent_id)
        log.setLevel(logging.DEBUG)
        if not log.handlers:
            log_path = LOGS_DIR / f"{self.agent_id}.log"
            fh = logging.FileHandler(log_path)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))
            log.addHandler(fh)
            # Also echo to stdout so systemd journal captures it
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter(
                "%(asctime)s  [%(name)s]  %(levelname)s  %(message)s",
                datefmt="%H:%M:%S",
            ))
            log.addHandler(sh)
        return log
