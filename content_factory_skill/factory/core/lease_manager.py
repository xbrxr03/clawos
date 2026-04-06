# SPDX-License-Identifier: AGPL-3.0-or-later
"""
lease_manager.py — lease issuance, lookup, expiry, and reclaim.

Design:
  - Foreman is the ONLY caller of write_lease().
  - Agents call request_lease() to check if the foreman has assigned them work.
  - Two files per active lease:
      /factory/state/leases/{job_id}.json        — indexed by job  (foreman reads)
      /factory/state/leases/{agent_id}.lease.json — indexed by agent (agent reads)
  - File writes are atomic (write to .tmp then rename) to prevent partial reads.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from core.config import LEASES_DIR, LEASE_TTL_SECONDS, LEASE_TTL_BY_CLASS, ACTIVE_DIR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _is_expired(expiration_iso: str) -> bool:
    exp = datetime.fromisoformat(expiration_iso)
    return _now() > exp


def _atomic_write(path: Path, data: dict):
    """Write JSON atomically using a temp file + rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


class LeaseManager:

    # ── foreman-only ──────────────────────────────────────────────────────────

    def write_lease(
        self, job_id: str, agent_id: str, phase: str,
        resource_class: str = "light",
    ) -> dict:
        """
        Issue a new lease.  Called exclusively by the foreman.
        TTL is determined by resource_class — heavy jobs get much longer
        leases because CPU image generation takes 10-15 min per image.
        Writes two index files so both job and agent can look up their lease.
        """
        now = _now()
        ttl = LEASE_TTL_BY_CLASS.get(resource_class, LEASE_TTL_SECONDS)
        lease = {
            "job_id":           job_id,
            "agent_id":         agent_id,
            "phase":            phase,
            "resource_class":   resource_class,
            "lease_start":      _iso(now),
            "lease_expiration": _iso(now + timedelta(seconds=ttl)),
        }
        LEASES_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write(LEASES_DIR / f"{job_id}.json",           lease)
        _atomic_write(LEASES_DIR / f"{agent_id}.lease.json",   lease)
        return lease

    # ── agent-facing ──────────────────────────────────────────────────────────

    def request_lease(self, agent_id: str) -> Optional[dict]:
        """
        Check if the foreman has issued a lease for this agent.
        Returns the job dict if a valid, non-expired lease exists; else None.
        """
        token_path = LEASES_DIR / f"{agent_id}.lease.json"
        if not token_path.exists():
            return None

        try:
            lease = json.loads(token_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

        if _is_expired(lease["lease_expiration"]):
            token_path.unlink(missing_ok=True)
            return None

        # Load the actual job
        job_path = ACTIVE_DIR / lease["job_id"] / "job.json"
        if not job_path.exists():
            return None

        try:
            return json.loads(job_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def release_lease(self, job_id: str, agent_id: str):
        """Remove both lease index files. Called by agent on completion or error."""
        (LEASES_DIR / f"{agent_id}.lease.json").unlink(missing_ok=True)
        (LEASES_DIR / f"{job_id}.json").unlink(missing_ok=True)

    # ── foreman maintenance ───────────────────────────────────────────────────

    def get_expired_leases(self) -> list[dict]:
        """
        Return all leases that have passed their expiration time.
        Foreman calls this every tick to reclaim stalled jobs.
        """
        expired = []
        for p in LEASES_DIR.glob("*.json"):
            if ".lease." in p.name:
                continue  # skip per-agent index; only scan per-job index
            try:
                lease = json.loads(p.read_text())
                if _is_expired(lease["lease_expiration"]):
                    expired.append(lease)
            except (json.JSONDecodeError, OSError):
                pass
        return expired

    def get_active_leases(self) -> list[dict]:
        """Return all non-expired leases (used by foreman to count active workloads)."""
        active = []
        for p in LEASES_DIR.glob("*.json"):
            if ".lease." in p.name:
                continue
            try:
                lease = json.loads(p.read_text())
                if not _is_expired(lease["lease_expiration"]):
                    active.append(lease)
            except (json.JSONDecodeError, OSError):
                pass
        return active

    def has_active_lease(self, job_id: str) -> bool:
        p = LEASES_DIR / f"{job_id}.json"
        if not p.exists():
            return False
        try:
            lease = json.loads(p.read_text())
            return not _is_expired(lease["lease_expiration"])
        except Exception:
            return False
