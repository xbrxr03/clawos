"""
ClawOS shared data models.
All services import from here — single source of truth for types.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from clawos_core.util.ids import task_id, session_id, entry_id, req_id
from clawos_core.util.time import now_iso


# ── Policy ────────────────────────────────────────────────────────────────────
class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY  = "DENY"
    QUEUE = "QUEUE"


@dataclass
class AuditEntry:
    tool:       str
    target:     str
    decision:   str
    reason:     str
    task_id:    str     = ""
    workspace:  str     = ""
    timestamp:  str     = field(default_factory=now_iso)
    entry_id:   str     = field(default_factory=entry_id)
    prev_hash:  str     = ""
    entry_hash: str     = ""

    def compute_hash(self) -> str:
        content = f"{self.prev_hash}{self.entry_id}{self.tool}{self.target}{self.decision}{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {k: v for k, v in vars(self).items()}


@dataclass
class ApprovalRequest:
    import asyncio
    tool:       str
    target:     str
    content:    str     = ""
    request_id: str     = field(default_factory=req_id)
    task_id:    str     = ""
    workspace:  str     = ""
    timestamp:  str     = field(default_factory=now_iso)
    decision:   Optional[Decision] = None
    event:      object  = field(default_factory=lambda: __import__('asyncio').Event())


# ── Task ──────────────────────────────────────────────────────────────────────
class TaskStatus(str, Enum):
    QUEUED    = "queued"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    intent:      str
    workspace:   str        = "default"
    task_id:     str        = field(default_factory=task_id)
    status:      TaskStatus = TaskStatus.QUEUED
    created_at:  str        = field(default_factory=now_iso)
    started_at:  Optional[str] = None
    finished_at: Optional[str] = None
    result:      Optional[str] = None
    error:       Optional[str] = None
    channel:     str        = "cli"     # cli | whatsapp | dashboard | a2a

    def to_dict(self) -> dict:
        d = vars(self).copy()
        d["status"] = self.status.value
        return d


# ── Session ───────────────────────────────────────────────────────────────────
@dataclass
class Session:
    workspace_id: str
    session_id:   str        = field(default_factory=session_id)
    created_at:   str        = field(default_factory=now_iso)
    channel:      str        = "cli"
    contact_id:   str        = ""
    history:      list       = field(default_factory=list)
    turn:         int        = 0


# ── Tool call ─────────────────────────────────────────────────────────────────
@dataclass
class ToolCall:
    tool:       str
    target:     str
    content:    str     = ""
    task_id:    str     = ""
    workspace:  str     = ""
    timestamp:  str     = field(default_factory=now_iso)


@dataclass
class ToolResult:
    tool:       str
    target:     str
    output:     str
    decision:   str     = "ALLOW"
    duration_s: float   = 0.0


# ── metricd: Token usage ──────────────────────────────────────────────────────
@dataclass
class TokenUsage:
    """OTel GenAI span data for one LLM call or tool execution."""
    span_type:      str        # "llm" | "tool"
    model:          str        = ""
    provider:       str        = "ollama"
    input_tokens:   int        = 0
    output_tokens:  int        = 0
    latency_ms:     float      = 0.0
    workspace_id:   str        = ""
    task_id:        str        = ""
    tool_name:      str        = ""
    tool_target:    str        = ""
    tool_decision:  str        = ""
    tier:           str        = "C"
    timestamp:      str        = field(default_factory=now_iso)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return vars(self).copy()


# ── A2A Protocol ──────────────────────────────────────────────────────────────
@dataclass
class AgentSkill:
    name:        str
    description: str


@dataclass
class AgentCard:
    """Served at GET /.well-known/agent.json — A2A agent discovery."""
    name:         str
    description:  str
    url:          str
    version:      str        = "1.0"
    skills:       List[AgentSkill] = field(default_factory=list)
    tier:         str        = "C"
    model:        str        = "qwen2.5:7b"
    voice:        bool       = False
    offline:      bool       = True
    workspace_id: str        = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "authentication": {"schemes": ["Bearer"]},
            "capabilities": {"streaming": True, "pushNotifications": False},
            "skills": [{"name": s.name, "description": s.description} for s in self.skills],
            "metadata": {
                "tier": self.tier,
                "model": self.model,
                "voice": self.voice,
                "offline": self.offline,
                "workspace_id": self.workspace_id,
            }
        }


@dataclass
class A2ATask:
    """Inbound task received via A2A protocol."""
    task_id:     str        = field(default_factory=task_id)
    intent:      str        = ""
    workspace:   str        = "nexus_default"
    sender_url:  str        = ""
    auth_token:  str        = ""
    status:      str        = "pending"
    created_at:  str        = field(default_factory=now_iso)
    result:      Optional[str] = None

    def to_dict(self) -> dict:
        d = vars(self).copy()
        d.pop("auth_token", None)   # never serialize token
        return d
