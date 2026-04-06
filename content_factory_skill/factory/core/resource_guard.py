# SPDX-License-Identifier: AGPL-3.0-or-later
"""
resource_guard.py — enforces resource limits on the 8GB single-machine target.

The foreman calls ResourceGuard.can_schedule(resource_class) before issuing
any lease.  All state is derived from the live lease files — no in-memory state.
"""

from core.config import RESOURCE_LIMITS, PHASE_ROUTING
from core.lease_manager import LeaseManager


class ResourceGuard:
    def __init__(self):
        self._lease_mgr = LeaseManager()

    def can_schedule(self, resource_class: str) -> bool:
        """
        Returns True if another workload of resource_class can be started.
        """
        limit = RESOURCE_LIMITS.get(resource_class, 0)
        if limit >= 999:
            return True  # light — unlimited
        current = self._count_active(resource_class)
        return current < limit

    def active_counts(self) -> dict:
        """Return {resource_class: count} for all active leases."""
        counts: dict[str, int] = {"heavy": 0, "medium": 0, "light": 0}
        for lease in self._lease_mgr.get_active_leases():
            phase = lease.get("phase", "")
            rc = self._phase_to_resource_class(phase)
            if rc:
                counts[rc] = counts.get(rc, 0) + 1
        return counts

    # ── internal ──────────────────────────────────────────────────────────────

    def _count_active(self, resource_class: str) -> int:
        count = 0
        for lease in self._lease_mgr.get_active_leases():
            phase = lease.get("phase", "")
            rc = self._phase_to_resource_class(phase)
            if rc == resource_class:
                count += 1
        return count

    @staticmethod
    def _phase_to_resource_class(phase: str) -> str | None:
        entry = PHASE_ROUTING.get(phase)
        if entry:
            return entry[2]
        return None
