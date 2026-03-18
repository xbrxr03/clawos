"""
ClawOS clawd — Orchestration Daemon
=====================================
Hardware detection, scheduler supervisor, service coordinator.
Heartbeat: reads HEARTBEAT.md and schedules proactive tasks.
"""
import asyncio
import logging
from pathlib import Path
from clawos_core.config.loader import load as load_config
from clawos_core.constants import DEFAULT_WORKSPACE

log = logging.getLogger("clawd")


class OrchestrationDaemon:
    def __init__(self):
        self.config   = load_config()
        self.profile  = self.config.get("_profile", "balanced")
        self._running = False

    async def start(self):
        self._running = True
        log.info(f"clawd started — profile={self.profile}")
        asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        self._running = False

    async def _heartbeat_loop(self):
        """Check HEARTBEAT.md and emit scheduled tasks. Full impl in S3."""
        while self._running:
            await asyncio.sleep(300)   # check every 5 minutes

    def hardware_info(self) -> dict:
        from clawos_core.constants import HARDWARE_JSON
        if HARDWARE_JSON.exists():
            import json
            return json.loads(HARDWARE_JSON.read_text())
        return {}

    def health(self) -> dict:
        return {
            "status":  "running" if self._running else "stopped",
            "profile": self.profile,
        }


_daemon = None

def get_daemon() -> OrchestrationDaemon:
    global _daemon
    if _daemon is None:
        _daemon = OrchestrationDaemon()
    return _daemon
