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


# ══════════════════════════════════════════════════════════════════════════════
# A2A client: delegate tasks to remote ClawOS peers
# PicoClaw bridge: route Tier A inbound messages to picoclawd
# ══════════════════════════════════════════════════════════════════════════════

async def delegate_to_peer(peer_url: str, intent: str,
                            workspace: str = "nexus_default") -> str:
    """Send task to a remote ClawOS A2A node. Returns result text."""
    import json
    import urllib.request
    from clawos_core.util.ids import task_id

    payload = json.dumps({
        "id": task_id(),
        "message": {"parts": [{"type": "text", "text": intent}]},
        "metadata": {"workspace": workspace},
    }).encode()
    try:
        req = urllib.request.Request(
            peer_url.rstrip("/") + "/tasks/send",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        from clawos_core.constants import A2A_BEARER_TOKEN_ENV
        import os
        token = os.environ.get(A2A_BEARER_TOKEN_ENV, "")
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        artifacts = data.get("artifacts", [])
        if artifacts:
            parts = artifacts[0].get("parts", [])
            if parts:
                return parts[0].get("text", "[no response]")
        return "[no result]"
    except Exception as e:
        return f"[A2A ERROR] {e}"


def get_a2a_peers() -> list[dict]:
    """Return list of discovered A2A peers on LAN."""
    try:
        from services.a2ad.discovery import get_peers
        return get_peers()
    except Exception:
        return []


def route_to_picoclaw(message: str, sender: str = "") -> str:
    """Route message to PicoClaw on Tier A hardware."""
    try:
        from services.picoclawd.bridge import send
        return send(message, sender)
    except Exception as e:
        return f"[PICOCLAW UNAVAILABLE] {e}"
