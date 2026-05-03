# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Structured tool result — replaces ad-hoc string matching in the agent loop.

Tools return ToolResult instead of raw strings with [ERROR], [DENIED] etc.
For backward compatibility, str(ToolResult) produces the legacy format.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["ok", "error", "denied", "pending", "offline"]


@dataclass
class ToolResult:
    """Structured result from a tool execution.

    ok:       True if the tool succeeded
    text:     Human-readable result or error message
    status:   Machine-readable status code
    error:    Error detail (None unless status is error/denied)
    """
    ok: bool
    text: str
    status: Status = "ok"
    error: str | None = None

    def __str__(self) -> str:
        """Backward-compatible string format for legacy consumers."""
        if self.ok:
            return self.text
        if self.status == "denied":
            return f"[DENY:{self.error or 'unspecified'}] {self.text}"
        if self.status == "pending":
            return f"[PENDING] {self.text}"
        if self.status == "offline":
            return f"[OFFLINE] {self.text}"
        return f"[ERR:{self.error or 'unknown'}] {self.text}"

    @classmethod
    def ok(cls, text: str) -> ToolResult:
        return cls(ok=True, text=text, status="ok")

    @classmethod
    def error(cls, text: str, error: str = "unknown") -> ToolResult:
        return cls(ok=False, text=text, status="error", error=error)

    @classmethod
    def denied(cls, reason: str) -> ToolResult:
        return cls(ok=False, text=reason, status="denied", error=reason)

    @classmethod
    def pending(cls, tool: str) -> ToolResult:
        return cls(ok=False, text=tool, status="pending", error="approval_required")

    @classmethod
    def offline(cls, text: str) -> ToolResult:
        return cls(ok=False, text=text, status="offline", error="no_connection")

    def to_dict(self) -> dict:
        return {"ok": self.ok, "text": self.text, "status": self.status, "error": self.error}