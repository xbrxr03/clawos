"""config.py — all factory paths and constants."""
import os
from pathlib import Path

def _resolve_root() -> Path:
    env = os.environ.get("FACTORY_ROOT")
    if env:
        return Path(env)
    home_factory = Path.home() / "factory"
    if home_factory.exists():
        return home_factory
    return Path(__file__).parent.parent

ROOT = _resolve_root()
JOBS_ROOT     = ROOT / "jobs"
INBOX_DIR     = JOBS_ROOT / "inbox"
ACTIVE_DIR    = JOBS_ROOT / "active"
COMPLETED_DIR = JOBS_ROOT / "completed"
FAILED_DIR    = JOBS_ROOT / "failed"
ARTIFACTS_DIR = ROOT / "artifacts"
LOGS_DIR      = ROOT / "logs"
STATE_DIR     = ROOT / "state"
AGENTS_STATE  = STATE_DIR / "agents"
EVENTS_FILE   = STATE_DIR / "events" / "events.jsonl"
METRICS_FILE  = STATE_DIR / "metrics" / "system.json"
LEASES_DIR    = STATE_DIR / "leases"
DASHBOARD_DIR = ROOT / "dashboard"

LEASE_TTL_SECONDS  = 300
LEASE_TTL_BY_CLASS = {"heavy": 7200, "medium": 900, "light": 300}
HEARTBEAT_INTERVAL = 5
FOREMAN_TICK       = 3
MONITOR_TICK       = 10
RETRY_BACKOFF_SECONDS = 30
RESOURCE_LIMITS    = {"heavy": 1, "medium": 2, "light": 999}
SCHEDULE_MIN_PER_CLASS = {"heavy": 1, "medium": 1, "light": 999}
INBOX_MAX_DEPTH    = 50

PHASE_ROUTING = {
    "created":     ("writer_agent",    "writing",     "medium"),
    "writing":     ("writer_agent",    "writing",     "medium"),
    "voice":       ("voice_agent",     "voice",       "light"),
    "assembling":  ("assembler_agent", "assembling",  "light"),
    "visualizing": ("visual_agent",    "visualizing", "heavy"),
    "rendering":   ("render_agent",    "rendering",   "medium"),
    "uploading":   ("upload_agent",    "uploading",   "light"),
}
PHASE_SEQUENCE = [
    "writing", "voice", "assembling",
    "visualizing", "rendering", "uploading", "complete"
]
TERMINAL_PHASES = {"complete", "failed"}
MAX_RETRIES = 3

def ensure_dirs():
    for d in [
        INBOX_DIR, ACTIVE_DIR, COMPLETED_DIR, FAILED_DIR,
        ARTIFACTS_DIR, LOGS_DIR, AGENTS_STATE, LEASES_DIR,
        STATE_DIR / "events", STATE_DIR / "metrics", DASHBOARD_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)

ensure_dirs()
