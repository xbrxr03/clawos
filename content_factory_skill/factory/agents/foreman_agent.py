# SPDX-License-Identifier: AGPL-3.0-or-later
"""
foreman_agent.py — the control plane.

Responsibilities:
  - Every tick: scan inbox, count active workloads, issue leases within limits.
  - Every tick: scan for expired leases and reclaim/retry/fail stalled jobs.
  - Publish own heartbeat and register in agent state.

The foreman is the ONLY process that writes leases.
Agents never pick jobs directly.
"""

import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import psutil

from core.config import (
    AGENTS_STATE, LOGS_DIR, PHASE_ROUTING, RESOURCE_LIMITS,
    FOREMAN_TICK, HEARTBEAT_INTERVAL, PHASE_SEQUENCE,
    SCHEDULE_MIN_PER_CLASS, INBOX_MAX_DEPTH, RETRY_BACKOFF_SECONDS,
)
from core.event_logger import EventLogger
from core.job_store import JobStore
from core.lease_manager import LeaseManager
from core.resource_guard import ResourceGuard


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ForemanAgent:
    AGENT_ID = "foreman_agent"

    def __init__(self):
        self.job_store      = JobStore()
        self.lease_manager  = LeaseManager()
        self.resource_guard = ResourceGuard()
        self.event_logger   = EventLogger()
        self._proc          = psutil.Process()
        self.logger         = self._build_logger()
        self._last_hb       = 0.0

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        self._register()
        self.logger.info("[foreman] started — entering scheduling loop")

        while True:
            now = time.monotonic()
            if now - self._last_hb >= HEARTBEAT_INTERVAL:
                self._publish_heartbeat()
                self._last_hb = now

            self._reclaim_stalled_leases()
            self._schedule_pending_jobs()
            time.sleep(FOREMAN_TICK)

    # ── scheduling ────────────────────────────────────────────────────────────

    def _schedule_pending_jobs(self):
        """
        Fair scheduling with starvation prevention.

        Algorithm:
          1. Group routable inbox jobs by resource class.
          2. For each resource class, try to issue up to SCHEDULE_MIN_PER_CLASS
             leases — guaranteeing forward progress even when a higher-priority
             class is at capacity.  This prevents heavy (visual) jobs from
             starving medium (writer) jobs indefinitely.
          3. After the guaranteed-minimum pass, fill remaining capacity with
             highest-priority jobs regardless of class.
        """
        inbox_jobs = self.job_store.load_all_inbox()
        if not inbox_jobs:
            return

        # Build a snapshot of what's currently running (persisted leases)
        active_counts = self.resource_guard.active_counts()
        # Track leases issued THIS tick so we don't double-count
        issued: dict[str, int] = {}

        # ── Step 1: resolve routing for each inbox job ────────────────────────
        routable: list[tuple[dict, str, str, str]] = []  # (job, agent, phase, res_class)
        for job in inbox_jobs:
            phase       = job.get("phase", "created")
            routing_key = "created" if phase == "created" else phase

            if routing_key not in PHASE_ROUTING:
                continue
            if self.lease_manager.has_active_lease(job["job_id"]):
                continue
            # Respect paused jobs — operator has halted scheduling for this job
            if job.get("status") == "paused":
                continue

            agent_id, next_phase, res_class = PHASE_ROUTING[routing_key]
            routable.append((job, agent_id, next_phase, res_class))

        if not routable:
            return

        # ── Step 2: group by resource class ───────────────────────────────────
        by_class: dict[str, list] = {}
        for entry in routable:
            rc = entry[3]
            by_class.setdefault(rc, []).append(entry)

        # ── Step 3: guaranteed-minimum pass (anti-starvation) ─────────────────
        # Each class that has capacity gets at least one job scheduled per tick.
        scheduled_ids: set[str] = set()

        for res_class, entries in by_class.items():
            min_slots = SCHEDULE_MIN_PER_CLASS.get(res_class, 1)
            slots_used = 0
            for job, agent_id, next_phase, rc in entries:
                if slots_used >= min_slots:
                    break
                running = active_counts.get(rc, 0) + issued.get(rc, 0)
                limit   = RESOURCE_LIMITS.get(rc, 1)
                if running >= limit:
                    break
                if self._issue_lease(job, agent_id, next_phase, rc):
                    issued[rc]  = issued.get(rc, 0) + 1
                    slots_used += 1
                    scheduled_ids.add(job["job_id"])

        # ── Step 4: fill remaining capacity with highest-priority jobs ─────────
        for job, agent_id, next_phase, rc in routable:
            if job["job_id"] in scheduled_ids:
                continue
            running = active_counts.get(rc, 0) + issued.get(rc, 0)
            limit   = RESOURCE_LIMITS.get(rc, 1)
            if running >= limit:
                self.logger.debug(
                    f"[foreman] {rc} limit reached ({running}/{limit}), "
                    f"deferring {job['job_id']}"
                )
                continue
            if self._issue_lease(job, agent_id, next_phase, rc):
                issued[rc] = issued.get(rc, 0) + 1

    def _issue_lease(self, job: dict, agent_id: str, next_phase: str, res_class: str) -> bool:
        """Promote job to active and write its lease. Returns True on success."""
        job_id = job["job_id"]
        self.logger.info(
            f"[foreman] issuing lease: job={job_id} → "
            f"agent={agent_id} phase={next_phase} [{res_class}]"
        )
        try:
            self.job_store.promote_to_active(job_id)
        except Exception as exc:
            self.logger.error(f"[foreman] failed to promote {job_id}: {exc}")
            return False
        lease = self.lease_manager.write_lease(job_id, agent_id, next_phase, res_class)
        self.job_store.set_lease(job_id, lease)
        self.event_logger.emit(
            job_id, self.AGENT_ID, "lease_issued",
            next_phase, f"Assigned to {agent_id} [{res_class}]",
        )
        return True

    # ── stall recovery ────────────────────────────────────────────────────────

    def _reclaim_stalled_leases(self):
        from datetime import datetime, timezone, timedelta
        for lease in self.lease_manager.get_expired_leases():
            job_id   = lease["job_id"]
            agent_id = lease["agent_id"]
            phase    = lease["phase"]

            self.logger.warning(
                f"[foreman] lease expired: job={job_id} agent={agent_id} phase={phase}"
            )
            self.event_logger.emit(
                job_id, self.AGENT_ID, "lease_expired",
                phase, f"Reclaiming from {agent_id}"
            )

            job = self.job_store.load(job_id)
            if not job:
                # Job file missing — clean up orphaned lease
                self.lease_manager.release_lease(job_id, agent_id)
                continue

            retries = job.get("retry_count", 0)
            max_r   = job.get("max_retries", 3)

            if retries < max_r:
                self.logger.info(f"[foreman] retrying {job_id} (attempt {retries+1}/{max_r})")
                self.event_logger.emit(job_id, self.AGENT_ID, "retry", phase,
                                       f"Retry {retries+1}/{max_r}")
                self.job_store.mark_retry(job_id)
            else:
                self.logger.error(f"[foreman] failing {job_id} after {retries} retries")
                self.event_logger.emit(job_id, self.AGENT_ID, "failed", phase,
                                       f"Max retries exceeded ({retries})")
                self.job_store.mark_failed(job_id, f"max retries exceeded after {retries} attempts")

            self.lease_manager.release_lease(job_id, agent_id)

    # ── registration / heartbeat ──────────────────────────────────────────────

    def _register(self):
        self._write_state("idle")
        self.event_logger.emit("system", self.AGENT_ID, "registered", "boot",
                               "Foreman started")

    def _publish_heartbeat(self):
        self._write_state("running")

    def _write_state(self, status: str):
        try:
            mem_mb = self._proc.memory_info().rss // (1024 * 1024)
            cpu    = self._proc.cpu_percent(interval=None)
        except psutil.NoSuchProcess:
            mem_mb, cpu = 0, 0.0

        record = {
            "agent_id":    self.AGENT_ID,
            "status":      status,
            "cpu_percent": cpu,
            "memory_mb":   mem_mb,
            "timestamp":   _now(),
        }
        path = AGENTS_STATE / f"{self.AGENT_ID}.json"
        tmp  = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2))
        tmp.replace(path)

    # ── logger ────────────────────────────────────────────────────────────────

    def _build_logger(self) -> logging.Logger:
        log = logging.getLogger(self.AGENT_ID)
        log.setLevel(logging.DEBUG)
        if not log.handlers:
            fh = logging.FileHandler(LOGS_DIR / f"{self.AGENT_ID}.log")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(message)s"
            ))
            log.addHandler(fh)
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter(
                "%(asctime)s  [foreman]  %(levelname)s  %(message)s",
                datefmt="%H:%M:%S",
            ))
            log.addHandler(sh)
        return log


if __name__ == "__main__":
    ForemanAgent().run()
