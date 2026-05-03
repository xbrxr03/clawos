# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS event bus — lightweight asyncio pub/sub.
All services publish events here. Dashboard subscribes via WebSocket.
"""
import asyncio
import logging
from typing import Callable
from clawos_core.util.time import now_iso

log = logging.getLogger("events")

# Event type constants
EV_LOG          = "log"
EV_TASK_UPDATE  = "task_update"
EV_TOOL_CALL    = "tool_call"
EV_APPROVAL_REQ = "approval_request"
EV_APPROVAL_DEC = "approval_decided"
EV_SERVICE_UP   = "service_up"
EV_SERVICE_DOWN = "service_down"
EV_HEARTBEAT    = "heartbeat"
EV_CHAT_MSG     = "chat_message"
EV_WA_MSG       = "whatsapp_message"


class EventBus:
    """Simple asyncio pub/sub event bus."""

    def __init__(self):
        self._subscribers: list[Callable] = []
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    def subscribe(self, fn: Callable):
        self._subscribers.append(fn)

    def unsubscribe(self, fn: Callable):
        if fn in self._subscribers:
            self._subscribers.remove(fn)

    async def publish(self, event_type: str, data: dict = None):
        event = {
            "type":      event_type,
            "timestamp": now_iso(),
            **(data or {}),
        }
        await self._queue.put(event)
        dead = []
        for fn in self._subscribers:
            try:
                result = fn(event)
                if asyncio.iscoroutine(result):
                    await result
            except (OSError, RuntimeError, AttributeError) as e:
                log.debug(f"EventBus subscriber error: {e}")
                dead.append(fn)
        for fn in dead:
            self.unsubscribe(fn)

    def publish_sync(self, event_type: str, data: dict = None):
        """Fire-and-forget from sync context."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event_type, data))
        except RuntimeError:
            pass  # no running loop — silently drop

    async def emit_log(self, level: str, service: str, message: str):
        await self.publish(EV_LOG, {"level": level, "service": service, "message": message})

    async def emit_task(self, task_id: str, status: str, detail: str = ""):
        await self.publish(EV_TASK_UPDATE, {"task_id": task_id, "status": status, "detail": detail})

    async def emit_approval(self, request_id: str, tool: str, target: str, workspace: str):
        await self.publish(EV_APPROVAL_REQ, {
            "request_id": request_id, "tool": tool,
            "target": target, "workspace": workspace,
        })


# Global singleton
_bus: EventBus = None

def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
