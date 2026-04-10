# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS gatewayd — Message Gateway
====================================
Routes inbound messages (WhatsApp, future channels) → agentd → reply.
"""
import asyncio
import logging
from pathlib import Path

from clawos_core.constants import CONFIG_DIR, DEFAULT_WORKSPACE
from clawos_core.events.bus import EV_WA_MSG, get_bus
from clawos_core.util.time import now_iso

log = logging.getLogger("gatewayd")


class GatewayService:
    def __init__(self):
        self._running = False
        self._channels: dict[str, object] = {}
        self._wa = None
        self._router = None
        self._approval_bridge = None
        self._bus_handler = None
        self._last_message_at = ""
        self._last_sender = ""
        self._last_workspace = DEFAULT_WORKSPACE
        self._last_preview = ""

    async def start(self):
        self._running = True
        from services.gatewayd.approval_bridge import WhatsAppApprovalBridge
        from services.gatewayd.session_router import SessionRouter

        self._router = SessionRouter()
        self._approval_bridge = WhatsAppApprovalBridge(self._send_self_message)

        async def _on_bus_event(event: dict):
            if event.get("type") == "approval_request" and self._approval_bridge:
                await self._approval_bridge.notify_request(
                    request_id=str(event.get("request_id", "")),
                    tool=str(event.get("tool", "")),
                    target=str(event.get("target", "")),
                    workspace=str(event.get("workspace", DEFAULT_WORKSPACE)),
                )

        self._bus_handler = _on_bus_event
        get_bus().subscribe(self._bus_handler)

        try:
            from services.gatewayd.channels.whatsapp import WhatsAppChannel

            self._wa = WhatsAppChannel()
            self._channels["whatsapp"] = self._wa

            async def _on_message(sender: str, text: str, media_path: str | None = None):
                await self.handle_inbound(sender, text, media_path=media_path)

            await self._wa.start(on_message=_on_message)
        except Exception as e:
            log.warning(f"WhatsApp channel not started: {e}")
        log.info("gatewayd started")

    async def stop(self):
        self._running = False
        if self._bus_handler:
            get_bus().unsubscribe(self._bus_handler)
            self._bus_handler = None
        if self._wa:
            try:
                await self._wa.stop()
            except Exception:
                pass

    async def handle_inbound(self, sender: str, text: str = "", media_path: str | None = None) -> dict:
        from services.agentd.service import get_manager

        body = str(text or "").strip()
        is_owner = bool(self._router and self._router.is_owner_jid(sender))
        if is_owner and self._approval_bridge:
            decision = await self._approval_bridge.handle_reply(body)
            if decision.get("handled"):
                if decision.get("message"):
                    self._send_whatsapp_message(sender, decision["message"])
                return {
                    "status": "approval",
                    "workspace": DEFAULT_WORKSPACE,
                    "text": body,
                    "reply": decision.get("message", ""),
                }

        workspace = DEFAULT_WORKSPACE if is_owner else self._workspace_for_sender(sender)
        message = body
        media_result: dict = {}
        if media_path:
            from services.gatewayd.media_handler import process_inbound_media

            media_result = await asyncio.to_thread(process_inbound_media, media_path)
            transcript = str(media_result.get("transcript", "")).strip()
            if transcript:
                message = f"{body}\n\nVoice note transcript:\n{transcript}".strip()
            elif not message:
                message = f"Received media attachment: {Path(media_path).name}"

        if not message:
            reply = "I received an empty message. Send text or a voice note and I will route it."
            self._send_whatsapp_message(sender, reply)
            return {"status": "ignored", "workspace": workspace, "text": "", "reply": reply}

        reply = await get_manager().chat_direct(
            message,
            workspace_id=workspace,
            channel="whatsapp",
            source=sender,
        )
        if reply:
            self._send_whatsapp_message(sender, reply)

        preview = str(media_result.get("transcript") or body or message).strip()[:160]
        self._last_message_at = now_iso()
        self._last_sender = sender
        self._last_workspace = workspace
        self._last_preview = preview
        await get_bus().publish(
            EV_WA_MSG,
            {
                "sender": sender,
                "workspace": workspace,
                "preview": preview,
                "channel": "whatsapp",
            },
        )
        return {
            "status": "routed",
            "workspace": workspace,
            "text": message,
            "reply": reply or "",
            "media": media_result,
        }

    def _workspace_for_sender(self, sender: str) -> str:
        if not self._router:
            return DEFAULT_WORKSPACE
        return self._router.get_workspace(sender)

    def routes(self) -> dict[str, str]:
        if not self._router:
            return {}
        return self._router.list_routes()

    def set_route(self, jid: str, workspace_id: str) -> dict[str, str]:
        if not jid.strip():
            raise ValueError("jid required")
        if not workspace_id.strip():
            raise ValueError("workspace_id required")
        if not self._router:
            from services.gatewayd.session_router import SessionRouter

            self._router = SessionRouter()
        self._router.set_workspace(jid.strip(), workspace_id.strip())
        return self._router.list_routes()

    def _send_self_message(self, message: str):
        if self._wa:
            self._wa.send_self(message)

    def _send_whatsapp_message(self, jid: str, message: str):
        if self._wa and message:
            self._wa.send(jid, message)

    async def send_morning_briefing(self, workspace_id: str = DEFAULT_WORKSPACE) -> bool:
        """
        Push the morning briefing to WhatsApp (self-message to the owner JID).
        Called by the scheduler at the user-configured briefing time (default 7am).
        Marks today's briefing as sent to suppress the ambient suggestion card.
        """
        if not self._wa:
            log.warning("Morning briefing skipped: WhatsApp not linked")
            return False

        try:
            from services.agentd.service import get_manager

            # Build briefing including any Kizuna brain connections discovered overnight
            brain_insight = ""
            try:
                from services.braind.service import get_brain
                brain = get_brain()
                from clawos_core.ambient import _check_brain_connections
                brain_event = _check_brain_connections()
                if brain_event:
                    brain_insight = f"\n\n🧠 *Kizuna noticed*: {brain_event.body}"
            except Exception:
                pass

            briefing_prompt = (
                "Generate a concise morning briefing for the day. Include: "
                "today's date, a quick weather note if available, any urgent tasks, "
                "and 3 things to focus on today. Keep it under 200 words."
                + brain_insight
            )

            reply = await get_manager().chat_direct(
                briefing_prompt,
                workspace_id=workspace_id,
                channel="scheduler",
                source="morning_briefing",
            )

            if reply:
                briefing_text = f"☀️ *Good morning — ClawOS Morning Briefing*\n\n{reply}"
                self._send_self_message(briefing_text)

                # Mark today's briefing as sent
                try:
                    from clawos_core.constants import CLAWOS_DIR
                    marker = CLAWOS_DIR / "state" / "briefing_sent_today.txt"
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    import time
                    marker.write_text(time.strftime("%Y-%m-%d"))
                except Exception:
                    pass

                log.info("Morning briefing sent via WhatsApp")
                return True

        except Exception as e:
            log.error(f"Morning briefing failed: {e}")

        return False

    def health(self) -> dict:
        linked = (CONFIG_DIR / "whatsapp" / ".wa_linked").exists()
        channel_status = self._wa.status() if self._wa and hasattr(self._wa, "status") else {}
        return {
            "status": "running" if self._running else "stopped",
            "whatsapp": channel_status.get("whatsapp", "linked" if linked else "not linked"),
            "channels": list(self._channels.keys()),
            "linked_phone": channel_status.get("phone_number", ""),
            "ready": channel_status.get("ready", linked),
            "last_ready_at": channel_status.get("last_ready_at", ""),
            "last_disconnect_reason": channel_status.get("last_disconnect_reason", ""),
            "last_message_at": self._last_message_at or channel_status.get("last_message_at", ""),
            "last_sender": self._last_sender,
            "last_workspace": self._last_workspace,
            "last_preview": self._last_preview,
            "routes_count": len(self.routes()),
            "approval_queue": self._approval_bridge.pending_count() if self._approval_bridge else 0,
            "restart_count": channel_status.get("restart_count", 0),
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
    import os
    import urllib.request
    from services.a2ad.peer_registry import get_registry
    from clawos_core.util.ids import task_id

    normalized_peer_url = peer_url.rstrip("/")
    registry = get_registry()
    if registry.is_blocked(normalized_peer_url):
        return f"[A2A DENIED] Peer is blocked: {normalized_peer_url}"
    if not registry.is_trusted_url(normalized_peer_url):
        return f"[A2A DENIED] Peer is not trusted: {normalized_peer_url}"

    local_peer_url = ""
    try:
        from services.a2ad.agent_card import build_card
        from services.a2ad.discovery import get_local_ip

        local_peer_url = build_card(local_ip=get_local_ip()).url.rstrip("/")
    except Exception:
        local_peer_url = ""

    payload = json.dumps({
        "id": task_id(),
        "message": {"parts": [{"type": "text", "text": intent}]},
        "metadata": {"workspace": workspace},
    }).encode()
    try:
        req = urllib.request.Request(
            normalized_peer_url + "/tasks/send",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        from clawos_core.constants import A2A_BEARER_TOKEN_ENV
        token = os.environ.get(A2A_BEARER_TOKEN_ENV, "")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        if local_peer_url:
            req.add_header("X-ClawOS-Peer-URL", local_peer_url)

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
