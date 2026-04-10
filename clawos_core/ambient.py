# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Ambient Intelligence — ClawOS proactive suggestion engine.

Runs background checks every 30 minutes via the scheduler.
Produces AttentionEvent objects consumed by the Overview page as action cards.
The user is never interrupted — suggestions appear quietly and expire.

Categories:
  - nexus_noticed   — Kizuna brain discovered something (new connections, ingestion ready)
  - approval_needed — pending approvals > 10 minutes old
  - briefing_ready  — morning briefing not yet delivered today
  - brain_update    — agent expanded the brain with new knowledge
  - system_health   — disk / file clutter / service degradation
  - workflow_nudge  — no workflow run in > 7 days
"""
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("ambient")

# ── Types ────────────────────────────────────────────────────────────────────


@dataclass
class AttentionEvent:
    """A proactive suggestion surfaced to the Overview page."""

    id: str
    category: str           # nexus_noticed | approval_needed | briefing_ready | ...
    title: str
    body: str
    action_label: str = ""  # Button label, e.g. "Run Now"
    action_route: str = ""  # Frontend route or workflow id to trigger
    priority: int = 50      # 0 = low, 100 = critical
    expires_at: float = 0.0 # Unix timestamp, 0 = never
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "body": self.body,
            "action_label": self.action_label,
            "action_route": self.action_route,
            "priority": self.priority,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }


# ── Ambient check functions ──────────────────────────────────────────────────

def _check_downloads_clutter() -> Optional[AttentionEvent]:
    """Flag if Downloads folder has > 50 files."""
    try:
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return None
        count = sum(1 for _ in downloads.iterdir())
        if count >= 50:
            return AttentionEvent(
                id="downloads_clutter",
                category="system_health",
                title=f"Downloads folder has {count} files",
                body="Kizuna can organise and summarise your downloads folder. Most of these are probably safe to archive.",
                action_label="Organise Downloads",
                action_route="/workflows?run=organize-downloads",
                priority=40,
                expires_at=time.time() + 86400,  # 24h
            )
    except Exception as e:
        log.debug(f"Downloads check failed: {e}")
    return None


def _check_disk_usage() -> Optional[AttentionEvent]:
    """Flag if root disk > 80% full."""
    try:
        usage = shutil.disk_usage("/")
        pct = (usage.used / usage.total) * 100
        if pct >= 80:
            free_gb = (usage.free / (1024 ** 3))
            return AttentionEvent(
                id="disk_usage",
                category="system_health",
                title=f"Disk is {pct:.0f}% full ({free_gb:.1f} GB free)",
                body="Running low on disk space. Consider archiving old files or removing unused models.",
                action_label="Run Disk Report",
                action_route="/workflows?run=disk-report",
                priority=70,
                expires_at=time.time() + 3600,  # 1h
            )
    except Exception as e:
        log.debug(f"Disk check failed: {e}")
    return None


def _check_pending_approvals() -> Optional[AttentionEvent]:
    """Flag approvals pending > 10 minutes."""
    try:
        from clawos_core.presence import get_presence_payload
        payload = get_presence_payload()
        approvals = payload.get("approvals", [])
        old_approvals = []
        cutoff = time.time() - 600  # 10 minutes
        for a in approvals:
            created = a.get("created_at", time.time())
            if isinstance(created, str):
                import datetime
                try:
                    dt = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.timestamp()
                except Exception:
                    continue
            if created < cutoff:
                old_approvals.append(a)

        if old_approvals:
            count = len(old_approvals)
            return AttentionEvent(
                id="pending_approvals",
                category="approval_needed",
                title=f"{count} approval{'s' if count > 1 else ''} waiting",
                body=f"{count} agent action{'s are' if count > 1 else ' is'} waiting for your review — some for over 10 minutes.",
                action_label="Review Now",
                action_route="/approvals",
                priority=90,
                expires_at=0,  # Never expire until dismissed
            )
    except Exception as e:
        log.debug(f"Approvals check failed: {e}")
    return None


def _check_morning_briefing() -> Optional[AttentionEvent]:
    """Flag if morning briefing hasn't been sent today."""
    try:
        from clawos_core.constants import CLAWOS_DIR
        marker = CLAWOS_DIR / "state" / "briefing_sent_today.txt"
        today = time.strftime("%Y-%m-%d")
        if marker.exists():
            content = marker.read_text().strip()
            if content == today:
                return None  # Already sent
        # Morning window: 6am–11am local
        hour = int(time.strftime("%H"))
        if 6 <= hour <= 11:
            return AttentionEvent(
                id="briefing_ready",
                category="briefing_ready",
                title="Morning briefing ready",
                body="Your daily briefing hasn't been delivered yet. Run it now to get weather, calendar, and news.",
                action_label="Send Briefing",
                action_route="/workflows?run=morning-briefing",
                priority=60,
                expires_at=time.time() + 7200,  # Expires after 2h
            )
    except Exception as e:
        log.debug(f"Briefing check failed: {e}")
    return None


def _check_workflow_nudge() -> Optional[AttentionEvent]:
    """Nudge if no workflow has run in > 7 days."""
    try:
        from clawos_core.constants import CLAWOS_DIR
        log_file = CLAWOS_DIR / "logs" / "workflow_runs.log"
        if not log_file.exists():
            return None
        mtime = log_file.stat().st_mtime
        days_since = (time.time() - mtime) / 86400
        if days_since >= 7:
            return AttentionEvent(
                id="workflow_nudge",
                category="workflow_nudge",
                title=f"No workflows run in {days_since:.0f} days",
                body="You haven't run any automations recently. Try 'Morning Briefing' or 'Organise Downloads' to get started.",
                action_label="Browse Workflows",
                action_route="/workflows",
                priority=20,
                expires_at=time.time() + 86400,
            )
    except Exception as e:
        log.debug(f"Workflow nudge check failed: {e}")
    return None


def _check_brain_connections() -> Optional[AttentionEvent]:
    """Surface Kizuna-discovered connections if graph recently grew."""
    try:
        from services.braind.service import get_brain
        brain = get_brain()
        stats = brain.stats()
        node_count = stats.get("node_count", 0)

        if node_count < 10:
            return None

        # Check if graph grew in last 24h by comparing to cached count
        from clawos_core.constants import CLAWOS_DIR
        cache = CLAWOS_DIR / "state" / "brain_node_count.txt"
        cache.parent.mkdir(parents=True, exist_ok=True)
        prev = int(cache.read_text().strip()) if cache.exists() else 0
        cache.write_text(str(node_count))

        delta = node_count - prev
        if delta >= 5:
            return AttentionEvent(
                id="brain_connections",
                category="nexus_noticed",
                title=f"Kizuna discovered {delta} new connections overnight",
                body=f"Your knowledge graph grew by {delta} nodes. Open Kizuna to explore the new connections.",
                action_label="Open Kizuna",
                action_route="/brain",
                priority=55,
                expires_at=time.time() + 86400,
            )
    except Exception as e:
        log.debug(f"Brain connections check failed: {e}")
    return None


# ── Main check runner ────────────────────────────────────────────────────────

_CHECKS = [
    _check_downloads_clutter,
    _check_disk_usage,
    _check_pending_approvals,
    _check_morning_briefing,
    _check_workflow_nudge,
    _check_brain_connections,
]

# In-memory store of current suggestions (refreshed every 30min)
_current_suggestions: list[AttentionEvent] = []
_last_check_at: float = 0.0
_CHECK_INTERVAL = 30 * 60  # 30 minutes


def run_checks(force: bool = False) -> list[AttentionEvent]:
    """
    Run all ambient checks. Returns list of AttentionEvent.
    Results are cached for 30 minutes unless force=True.
    """
    global _current_suggestions, _last_check_at

    now = time.time()
    if not force and (now - _last_check_at) < _CHECK_INTERVAL:
        return _current_suggestions

    suggestions: list[AttentionEvent] = []
    for check in _CHECKS:
        try:
            result = check()
            if result is not None:
                # Skip if expired
                if result.expires_at == 0 or result.expires_at > now:
                    suggestions.append(result)
        except Exception as e:
            log.warning(f"Ambient check {check.__name__} failed: {e}")

    # Sort by priority descending
    suggestions.sort(key=lambda e: e.priority, reverse=True)

    _current_suggestions = suggestions
    _last_check_at = now
    log.info(f"Ambient checks complete: {len(suggestions)} suggestion(s)")
    return suggestions


def get_suggestions() -> list[dict]:
    """Return current suggestions as serializable dicts."""
    return [s.to_dict() for s in run_checks()]


def dismiss_suggestion(suggestion_id: str) -> bool:
    """Remove a suggestion from the current list by id."""
    global _current_suggestions
    before = len(_current_suggestions)
    _current_suggestions = [s for s in _current_suggestions if s.id != suggestion_id]
    return len(_current_suggestions) < before
