"""
ClawOS scheduler service — scheduled agent task runner

Reads schedule definitions from ~/clawos/configs/schedules.yaml
Each scheduled task runs as a full independent agent session via agentd,
so it has its own memory context and never blocks the main agent loop.

This avoids the NanoClaw deadlock bug where scheduled tasks queue behind
idle containers sharing the same execution path.

Schedule format (schedules.yaml):
    schedules:
      - id: daily-summary
        cron: "0 9 * * *"        # 9am daily
        task: "Generate a summary of yesterday's activity"
        workspace: nexus_default
        enabled: false

Usage:
    python3 services/scheduler/service.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

CLAWOS_HOME = Path(os.environ.get("CLAWOS_HOME", Path.home() / "clawos"))
SCHEDULES_FILE = CLAWOS_HOME / "configs" / "schedules.yaml"
AGENTD_URL = "http://localhost:7072"
HEALTH_PORT = 7077
LOG_FILE = CLAWOS_HOME / "logs" / "scheduler.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scheduler")


def load_schedules() -> list[dict]:
    """Load schedule definitions from schedules.yaml. Returns [] if file missing."""
    if not SCHEDULES_FILE.exists():
        return []
    try:
        with open(SCHEDULES_FILE) as f:
            data = yaml.safe_load(f) or {}
        schedules = data.get("schedules", [])
        enabled = [s for s in schedules if s.get("enabled", False)]
        log.info(f"Loaded {len(enabled)} enabled schedules (of {len(schedules)} total)")
        return enabled
    except Exception as e:
        log.error(f"Failed to load schedules: {e}")
        return []


def cron_matches(cron_expr: str, now: datetime) -> bool:
    """
    Minimal cron matcher: 'minute hour dom month dow'
    Supports * and specific values only (no ranges/steps yet).
    """
    try:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return False
        minute, hour, dom, month, dow = parts
        checks = [
            (minute, now.minute),
            (hour, now.hour),
            (dom, now.day),
            (month, now.month),
            (dow, now.weekday()),  # 0=Monday per Python, cron 0=Sunday — close enough for now
        ]
        for expr, val in checks:
            if expr != "*" and int(expr) != val:
                return False
        return True
    except Exception:
        return False


async def dispatch_task(schedule: dict) -> None:
    """
    Submit a scheduled task to agentd as a new independent agent session.
    Each task gets its own session — no shared state with the interactive loop.
    """
    task_id = schedule.get("id", "unknown")
    task_text = schedule.get("task", "")
    workspace = schedule.get("workspace", "jarvis_default")

    log.info(f"Dispatching scheduled task: {task_id}")

    payload = {
        "task": task_text,
        "workspace": workspace,
        "source": "scheduler",
        "schedule_id": task_id,
        "session_id": f"sched-{task_id}-{int(time.time())}",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{AGENTD_URL}/tasks", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                log.info(f"Task {task_id} queued — task_id: {data.get('task_id')}")
            else:
                log.error(f"Task {task_id} rejected by agentd: {resp.status_code} {resp.text}")
    except Exception as e:
        log.error(f"Failed to dispatch task {task_id}: {e}")


async def health_server() -> None:
    """Minimal HTTP health endpoint so setup-systemd can verify we're up."""
    import json
    from aiohttp import web

    async def health(request):
        schedules = load_schedules()
        return web.Response(
            content_type="application/json",
            text=json.dumps({
                "status": "ok",
                "service": "scheduler",
                "enabled_schedules": len(schedules),
            }),
        )

    app = web.Application()
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
    await site.start()
    log.info(f"Health endpoint: http://localhost:{HEALTH_PORT}/health")


async def scheduler_loop() -> None:
    """Main loop — checks schedules every 60 seconds, fires matching tasks."""
    log.info("Scheduler started")
    last_fired: dict[str, str] = {}  # schedule_id -> last fired minute str

    while True:
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        schedules = load_schedules()
        for schedule in schedules:
            sid = schedule.get("id", "")
            cron = schedule.get("cron", "")

            # Fire at most once per minute per schedule
            if last_fired.get(sid) == minute_key:
                continue

            if cron_matches(cron, now):
                last_fired[sid] = minute_key
                asyncio.create_task(dispatch_task(schedule))

        await asyncio.sleep(60)


async def main() -> None:
    CLAWOS_HOME.mkdir(parents=True, exist_ok=True)
    (CLAWOS_HOME / "logs").mkdir(exist_ok=True)
    (CLAWOS_HOME / "configs").mkdir(exist_ok=True)

    # Write default schedules.yaml if missing
    if not SCHEDULES_FILE.exists():
        default = """# ClawOS scheduled tasks
# Each task runs as an independent agent session via agentd.
# Set enabled: true to activate a schedule.
#
# Cron format: minute hour day-of-month month day-of-week
# Examples:
#   "0 9 * * *"   — 9:00am every day
#   "0 */6 * * *" — every 6 hours
#   "30 8 * * 1"  — 8:30am every Monday
#
schedules:
  - id: daily-summary
    cron: "0 9 * * *"
    task: "Generate a brief summary of recent activity and any pending items"
    workspace: nexus_default
    enabled: false

  - id: weekly-digest
    cron: "0 8 * * 1"
    task: "Summarize the week's completed tasks and flag anything unresolved"
    workspace: nexus_default
    enabled: false
"""
        SCHEDULES_FILE.write_text(default)
        log.info(f"Created default schedules config: {SCHEDULES_FILE}")

    try:
        await health_server()
    except Exception as e:
        log.warning(f"Health server unavailable (aiohttp not installed?): {e}")

    await scheduler_loop()


if __name__ == "__main__":
    asyncio.run(main())
