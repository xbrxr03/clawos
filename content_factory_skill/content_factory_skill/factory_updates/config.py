# SPDX-License-Identifier: AGPL-3.0-or-later
"""
config.py — all paths and runtime constants for the factory.
Every other module imports from here; nothing hardcodes paths directly.

ROOT resolution order (first match wins):
  1. FACTORY_ROOT environment variable
  2. /factory          (production — standard install path)
  3. Directory of this file (development fallback)
"""

import os
from pathlib import Path

# ── root ──────────────────────────────────────────────────────────────────────
def _resolve_root() -> Path:
    # 1. Explicit env override — useful for testing and alternate deployments
    env = os.environ.get("FACTORY_ROOT")
    if env:
        return Path(env)
    # 2. Standard production install path
    production = Path("/factory")
    if production.exists():
        return production
    # 3. Development fallback — directory containing this config file
    return Path(__file__).parent.parent

ROOT = _resolve_root()

# ── job queue dirs ────────────────────────────────────────────────────────────
JOBS_ROOT       = ROOT / "jobs"
INBOX_DIR       = JOBS_ROOT / "inbox"
ACTIVE_DIR      = JOBS_ROOT / "active"
COMPLETED_DIR   = JOBS_ROOT / "completed"
FAILED_DIR      = JOBS_ROOT / "failed"

# ── artifacts ─────────────────────────────────────────────────────────────────
ARTIFACTS_DIR   = ROOT / "artifacts"

# ── logs ──────────────────────────────────────────────────────────────────────
LOGS_DIR        = ROOT / "logs"

# ── state (observable by dashboard) ──────────────────────────────────────────
STATE_DIR       = ROOT / "state"
AGENTS_STATE    = STATE_DIR / "agents"
EVENTS_FILE     = STATE_DIR / "events" / "events.jsonl"
METRICS_FILE    = STATE_DIR / "metrics" / "system.json"
LEASES_DIR      = STATE_DIR / "leases"

# ── dashboard static files ────────────────────────────────────────────────────
DASHBOARD_DIR   = ROOT / "dashboard"

# ── lease settings ────────────────────────────────────────────────────────────
LEASE_TTL_SECONDS   = 300     # 5 min; foreman reclaims after this
HEARTBEAT_INTERVAL  = 5       # seconds between agent heartbeat writes
FOREMAN_TICK        = 3       # seconds between foreman scheduling ticks
MONITOR_TICK        = 10      # seconds between metric snapshots

# ── resource limits ───────────────────────────────────────────────────────────
RESOURCE_LIMITS = {
    "heavy":  1,
    "medium": 1,
    "light":  999,
}

# ── starvation prevention ─────────────────────────────────────────────────────
# The foreman guarantees each resource class gets at least one scheduling
# attempt per tick, regardless of higher-priority class demand.
# Without this, a full inbox of visual jobs would starve writer jobs forever.
#
# Implementation: the foreman groups inbox jobs by resource class, then
# schedules one job per class per tick (round-robin across classes) before
# filling remaining capacity in priority order.
SCHEDULE_MIN_PER_CLASS = {
    "heavy":  1,   # at most 1 heavy per tick anyway (matches RESOURCE_LIMITS)
    "medium": 1,   # guarantee at least 1 medium slot per tick if available
    "light":  999, # light is unlimited — no starvation possible
}

# ── inbox backpressure ────────────────────────────────────────────────────────
# Maximum number of jobs allowed in the inbox at one time.
# New job submissions via factoryctl are rejected when this limit is reached.
# Set to 0 to disable (unlimited inbox).
INBOX_MAX_DEPTH = 50

# ── phase → (agent_id, next_phase, resource_class) ───────────────────────────
PHASE_ROUTING = {
    "created":     ("writer_agent",    "writing",     "medium"),
    "writing":     ("writer_agent",    "writing",     "medium"),
    "voice":       ("voice_agent",     "voice",       "light"),
    "assembling":  ("assembler_agent", "assembling",  "light"),
    "visualizing": ("visual_agent",    "visualizing", "heavy"),
    "rendering":   ("render_agent",    "rendering",   "medium"),
    "uploading":   ("upload_agent",    "uploading",   "light"),
}

# Phases in pipeline order
# Visual runs after voice+assembly so it gets max RAM.
# Rendering runs after visual (needs all images).
# Uploading runs last, waits for scheduled time.
PHASE_SEQUENCE = ["writing", "voice", "assembling", "visualizing", "rendering", "uploading", "complete"]

# Phases that are terminal (no further routing)
TERMINAL_PHASES = {"complete", "failed"}

# Max retries before a job is permanently failed
MAX_RETRIES = 3

# ── ensure all dirs exist on import ──────────────────────────────────────────
def ensure_dirs():
    for d in [
        INBOX_DIR, ACTIVE_DIR, COMPLETED_DIR, FAILED_DIR,
        ARTIFACTS_DIR, LOGS_DIR,
        AGENTS_STATE, LEASES_DIR,
        STATE_DIR / "events",
        STATE_DIR / "metrics",
        DASHBOARD_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)

ensure_dirs()
