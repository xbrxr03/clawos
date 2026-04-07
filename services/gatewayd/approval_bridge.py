# SPDX-License-Identifier: AGPL-3.0-or-later
"""WhatsApp approval helpers for reply-based allow/deny flows."""
from __future__ import annotations

import re
from collections import deque
from typing import Any, Callable


APPROVE_WORDS = {"a", "allow", "approve", "approved", "yes", "y"}
DENY_WORDS = {"d", "deny", "denied", "block", "no", "n"}


class WhatsAppApprovalBridge:
    def __init__(self, send_message: Callable[[str], None] | None = None):
        self._send_message = send_message
        self._pending_order: deque[str] = deque()
        self._pending_meta: dict[str, dict[str, str]] = {}

    def set_sender(self, send_message: Callable[[str], None] | None):
        self._send_message = send_message

    def pending_count(self) -> int:
        return len(self._pending_order)

    async def notify_request(self, request_id: str, tool: str, target: str, workspace: str) -> None:
        if request_id not in self._pending_meta:
            self._pending_order.append(request_id)
        self._pending_meta[request_id] = {
            "tool": tool,
            "target": target,
            "workspace": workspace,
        }
        if self._send_message:
            self._send_message(self._format_prompt(request_id, tool, target, workspace))

    async def handle_reply(self, text: str) -> dict[str, Any]:
        normalized = (text or "").strip().lower()
        if not normalized:
            return {"handled": False}

        approve: bool | None = None
        head = normalized.split()[0]
        if head in APPROVE_WORDS:
            approve = True
        elif head in DENY_WORDS:
            approve = False
        if approve is None:
            return {"handled": False}

        request_id = self._extract_request_id(normalized) or (self._pending_order[-1] if self._pending_order else "")
        if not request_id:
            return {"handled": False}

        from services.policyd.service import get_engine

        decided = get_engine().decide_approval(request_id, approve)
        meta = self._pending_meta.pop(request_id, {})
        try:
            self._pending_order.remove(request_id)
        except ValueError:
            pass

        if not decided:
            return {"handled": True, "message": f"Approval {request_id} was already resolved."}

        action = "Approved" if approve else "Denied"
        tool = meta.get("tool", "request")
        return {"handled": True, "message": f"{action} {request_id} for {tool}."}

    def _extract_request_id(self, text: str) -> str:
        for token in re.findall(r"[a-z0-9_-]{6,}", text):
            if token in self._pending_meta:
                return token
        return ""

    def _format_prompt(self, request_id: str, tool: str, target: str, workspace: str) -> str:
        return (
            f"Approval needed [{request_id}]\n"
            f"Tool: {tool}\n"
            f"Target: {target[:80]}\n"
            f"Workspace: {workspace}\n"
            "Reply yes or no to decide."
        )
