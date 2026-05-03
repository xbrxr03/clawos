# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS metricd — OTel Metrics + Token Tracking
===============================================
Wraps every Ollama call and tool execution in an OTel span.
Tracks token usage per workspace. Enforces optional budget limits.
Exports: local JSONL (always) + optional OTLP remote.

Usage from runtime:
    from services.metricd.service import get_metrics
    metrics = get_metrics()
    metrics.record_llm(model, input_tokens, output_tokens, latency_ms, workspace_id, task_id)
    metrics.record_tool(tool, target, decision, duration_ms, workspace_id, task_id)
"""
import asyncio
import logging
from typing import Optional
from clawos_core.models import TokenUsage
from services.metricd.otel import build_llm_span, build_tool_span
from services.metricd import budget as _budget
from services.metricd import exporter as _exporter
from clawos_core.config.loader import get

log = logging.getLogger("metricd")
_instance: Optional["MetricsService"] = None


class MetricsService:
    def __init__(self):
        self._enabled      = get("metricd.enabled", True)
        self._export_local = get("metricd.export_local", True)
        self._export_otlp  = get("metricd.export_otlp", False)
        self._otlp_ep      = get("metricd.otlp_endpoint", "")
        self._budget_on    = get("metricd.budget.enabled", False)
        self._daily_limit  = get("metricd.budget.daily_tokens_per_workspace",
                                 100_000)
        self._action       = get("metricd.budget.action_on_limit", "warn")
        # Detect tier from hardware
        try:
            from bootstrap.hardware_probe import load_saved, get_tier
            self._tier = get_tier(load_saved())
        except (ImportError, ModuleNotFoundError):
            self._tier = "C"
        log.info(f"metricd started (tier={self._tier} budget={'on' if self._budget_on else 'off'})")

    # ── Public recording API ──────────────────────────────────────────────────
    def record_llm(self, model: str, input_tokens: int, output_tokens: int,
                   latency_ms: float, workspace_id: str = "", task_id: str = ""):
        if not self._enabled:
            return
        span = build_llm_span(model, input_tokens, output_tokens, latency_ms,
                               workspace_id, task_id, self._tier)
        self._emit(span)
        if self._budget_on and workspace_id:
            _budget.add_tokens(workspace_id, span.total_tokens)

    def record_tool(self, tool_name: str, tool_target: str, tool_decision: str,
                    duration_ms: float, workspace_id: str = "", task_id: str = ""):
        if not self._enabled:
            return
        span = build_tool_span(tool_name, tool_target, tool_decision, duration_ms,
                                workspace_id, task_id, self._tier)
        self._emit(span)

    def is_over_budget(self, workspace_id: str) -> bool:
        if not self._budget_on:
            return False
        over = _budget.is_over_budget(workspace_id, self._daily_limit)
        if over:
            log.warning(f"Budget exceeded for workspace: {workspace_id}")
        return over

    def budget_action(self) -> str:
        return self._action

    def workspace_summary(self) -> list[dict]:
        return _budget.all_workspaces_summary()

    def today_tokens(self, workspace_id: str) -> int:
        return _budget.get_today(workspace_id)

    def week_tokens(self, workspace_id: str) -> int:
        return _budget.get_week(workspace_id)

    # ── Internal ──────────────────────────────────────────────────────────────
    def _emit(self, span: TokenUsage):
        if self._export_local:
            _exporter.export_local(span)
        if self._export_otlp and self._otlp_ep:
            _exporter.export_otlp(span, self._otlp_ep)


def get_metrics() -> MetricsService:
    global _instance
    if _instance is None:
        _instance = MetricsService()
    return _instance
