"""
ClawOS gatewayd — Message Gateway
====================================
Routes inbound messages (WhatsApp, future channels) → agentd → reply.
Full implementation in Session 3.
"""
import asyncio
import logging
from clawos_core.constants import CONFIG_DIR

log = logging.getLogger("gatewayd")


class GatewayService:
    def __init__(self):
        self._running  = False
        self._channels = {}

    async def start(self):
        self._running = True
        log.info("gatewayd started")

    async def stop(self):
        self._running = False

    def health(self) -> dict:
        linked = (CONFIG_DIR / "whatsapp" / ".wa_linked").exists()
        return {
            "status":    "running" if self._running else "stopped",
            "whatsapp":  "linked" if linked else "not linked",
            "channels":  list(self._channels.keys()),
        }


_svc = None

def get_service() -> GatewayService:
    global _svc
    if _svc is None:
        _svc = GatewayService()
    return _svc
