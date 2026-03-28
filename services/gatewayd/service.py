"""
ClawOS gatewayd — Message Gateway
====================================
Routes inbound messages (WhatsApp, future channels) → agentd → reply.
"""
import asyncio
import logging
from clawos_core.constants import CONFIG_DIR

log = logging.getLogger("gatewayd")


class GatewayService:
    def __init__(self):
        self._running  = False
        self._channels = {}
        self._wa       = None

    async def start(self):
        self._running = True
        # Wire WhatsApp channel if available
        try:
            from services.gatewayd.channels.whatsapp import WhatsAppChannel
            self._wa = WhatsAppChannel()
            self._channels["whatsapp"] = self._wa

            async def _on_message(sender: str, text: str):
                try:
                    from services.agentd.service import get_manager
                    reply = await get_manager().chat_direct(
                        text, source=f"whatsapp:{sender}"
                    )
                    if self._wa and reply:
                        self._wa.send(sender, reply)
                except Exception as e:
                    log.error(f"WhatsApp message handler error: {e}")

            await self._wa.start(on_message=_on_message)
        except Exception as e:
            log.warning(f"WhatsApp channel not started: {e}")
        log.info("gatewayd started")

    async def stop(self):
        self._running = False
        if self._wa:
            try:
                await self._wa.stop()
            except Exception:
                pass

    def health(self) -> dict:
        linked = (CONFIG_DIR / "whatsapp" / ".wa_linked").exists()
        return {
            "status":   "running" if self._running else "stopped",
            "whatsapp": "linked" if linked else "not linked",
            "channels": list(self._channels.keys()),
        }


_svc = None


def get_service() -> GatewayService:
    global _svc
    if _svc is None:
        _svc = GatewayService()
    return _svc
