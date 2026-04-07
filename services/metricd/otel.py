# SPDX-License-Identifier: AGPL-3.0-or-later
"""
OTel span builder — GenAI semantic conventions 2026.
Builds span dicts matching the OpenTelemetry GenAI semantic conventions.
No external OTel SDK required for local JSONL export mode.
"""
import time
from clawos_core.models import TokenUsage


def build_llm_span(
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    workspace_id: str = "",
    task_id: str = "",
    tier: str = "C",
    provider: str = "ollama",
) -> TokenUsage:
    return TokenUsage(
        span_type="llm",
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=round(latency_ms, 2),
        workspace_id=workspace_id,
        task_id=task_id,
        tier=tier,
    )


def build_tool_span(
    tool_name: str,
    tool_target: str,
    tool_decision: str,
    duration_ms: float,
    workspace_id: str = "",
    task_id: str = "",
    tier: str = "C",
) -> TokenUsage:
    return TokenUsage(
        span_type="tool",
        tool_name=tool_name,
        tool_target=tool_target[:200],
        tool_decision=tool_decision,
        latency_ms=round(duration_ms, 2),
        workspace_id=workspace_id,
        task_id=task_id,
        tier=tier,
    )
