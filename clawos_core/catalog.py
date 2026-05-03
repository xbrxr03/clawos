# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Static product catalog and competitive-platform helpers for ClawOS.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from clawos_core.constants import CONFIG_DIR, DEFAULT_MODEL, OTEL_JSONL, TRACES_JSONL

_STUDIO_DIR = CONFIG_DIR / "studio" / "programs"
from clawos_core.models import (
    EvalSuite,
    ExtensionManifest,
    OpenClawImportManifest,
    ProviderProfile,
    TraceRecord,
    UseCasePack,
    WorkflowProgram,
)
from clawos_core.util.ids import task_id
from clawos_core.util.time import now_iso


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}


def list_packs() -> list[UseCasePack]:
    return [
        UseCasePack(
            id="daily-briefing-os",
            name="Daily Briefing OS",
            category="operations",
            description="Morning and evening briefings across inbox, calendar, notes, and daily priorities.",
            wave="wave-1",
            setup_summary="Connect calendars, notes, and optional chat delivery for a daily operational briefing.",
            dashboards=["briefing", "approvals", "calendar", "notes"],
            default_workflows=["daily_digest", "meeting_notes", "folder_summary"],
            extension_recommendations=["calendar-connectors", "notes-connectors", "chat-bridges"],
            provider_recommendations=["local-ollama", "openai-compatible"],
            policy_pack="recommended",
            eval_suite_id="eval-daily-briefing",
        ),
        UseCasePack(
            id="sales-meeting-operator",
            name="Sales and Meeting Operator",
            category="business",
            description="Lead research, meeting prep, follow-up drafts, and action packets with approval-safe defaults.",
            wave="wave-1",
            setup_summary="Prepare lead dossiers, meeting briefs, and follow-up drafts without leaving the command center.",
            dashboards=["pipeline", "meetings", "approvals"],
            default_workflows=["meeting_notes", "csv_summary", "csv_to_report"],
            extension_recommendations=["calendar-connectors", "notes-connectors", "research-engine"],
            provider_recommendations=["local-ollama", "openai-compatible", "azure-openai"],
            policy_pack="business-draft-only",
            eval_suite_id="eval-sales-operator",
        ),
        UseCasePack(
            id="chat-app-command-center",
            name="Chat-App Personal Command Center",
            category="assistant",
            description="Persistent context and quick actions through chat bridges, notes, and reminders.",
            wave="wave-1",
            setup_summary="Turn WhatsApp, Telegram, or Discord into a local-first command center with memory and approvals.",
            dashboards=["inbox", "memory", "activity"],
            default_workflows=["daily_digest", "process_report", "organize_downloads"],
            extension_recommendations=["chat-bridges", "notes-connectors"],
            provider_recommendations=["local-ollama"],
            policy_pack="personal-os",
            eval_suite_id="eval-chat-command-center",
        ),
        UseCasePack(
            id="coding-autopilot",
            name="Coding Autopilot",
            category="developer",
            description="Repo summaries, TODO mining, PR review, and safe overnight coding with review-first controls.",
            wave="wave-1",
            setup_summary="Queue coding runs, inspect traces, and keep merges behind human approval.",
            dashboards=["repos", "tasks", "traces"],
            default_workflows=["repo_summary", "find_todos", "pr_review", "write_readme"],
            extension_recommendations=["remote-workbench", "mcp-manager", "browser-workbench"],
            provider_recommendations=["local-ollama", "openai-compatible", "anthropic-api"],
            policy_pack="developer-workstation",
            eval_suite_id="eval-coding-autopilot",
        ),
        UseCasePack(
            id="research-newsroom",
            name="Research and Newsroom",
            category="research",
            description="Source-backed research, watchlists, syntheses, and briefing outputs with citations.",
            wave="wave-2",
            setup_summary="Collect, summarize, and cite sources through a staged local-first research flow.",
            dashboards=["research", "traces", "approvals"],
            default_workflows=["summarize_pdf", "batch_summarize", "extract_tables"],
            extension_recommendations=["research-engine", "browser-workbench"],
            provider_recommendations=["local-ollama", "openai-compatible", "openrouter"],
            policy_pack="research",
            eval_suite_id="eval-research-newsroom",
        ),
        UseCasePack(
            id="social-media-studio",
            name="Social Media Studio",
            category="content",
            description="Idea generation, drafting, adaptation, and approval-gated publishing handoff.",
            wave="wave-2",
            setup_summary="Run a local-first content pipeline with drafts, source grounding, and review checkpoints.",
            dashboards=["content", "approvals", "calendar"],
            default_workflows=["rewrite", "proofread", "caption_images"],
            extension_recommendations=["research-engine", "chat-bridges"],
            provider_recommendations=["local-ollama", "openai-compatible"],
            policy_pack="content-studio",
            eval_suite_id="eval-social-studio",
        ),
        UseCasePack(
            id="travel-personal-admin",
            name="Travel and Personal Admin",
            category="assistant",
            description="Itinerary packets, reminders, inbox cleanup, and travel prep with approvals for external actions.",
            wave="wave-2",
            setup_summary="Coordinate travel logistics and personal admin while keeping external actions behind approvals.",
            dashboards=["travel", "briefing", "approvals"],
            default_workflows=["daily_digest", "meeting_notes", "folder_summary"],
            extension_recommendations=["calendar-connectors", "browser-workbench", "chat-bridges"],
            provider_recommendations=["local-ollama"],
            policy_pack="personal-os",
            eval_suite_id="eval-travel-admin",
        ),
        UseCasePack(
            id="home-health-hub",
            name="Home and Health Hub",
            category="lifestyle",
            description="Privacy-first summaries across routines, smart-home events, and personal telemetry.",
            wave="wave-3",
            setup_summary="Keep home and health signals local, summarized, and reviewable from one dashboard.",
            dashboards=["home", "health", "alerts"],
            default_workflows=["daily_digest", "process_report"],
            extension_recommendations=["home-health-connectors", "chat-bridges"],
            provider_recommendations=["local-ollama"],
            policy_pack="family-shared-device",
            eval_suite_id="eval-home-health",
        ),
        UseCasePack(
            id="small-business-operator",
            name="Small Business Operator",
            category="business",
            description="Ops packets across finance, reporting, scheduling, and business administration.",
            wave="wave-3",
            setup_summary="Run finance, reporting, and workflow review loops from a local-first operator dashboard.",
            dashboards=["ops", "reports", "approvals"],
            default_workflows=["csv_summary", "csv_to_report", "log_summarize"],
            extension_recommendations=["calendar-connectors", "notes-connectors", "research-engine"],
            provider_recommendations=["local-ollama", "azure-openai", "openai-compatible"],
            policy_pack="business-draft-only",
            eval_suite_id="eval-small-business",
        ),
        UseCasePack(
            id="remote-workbench-gpu-operator",
            name="Remote Workbench / GPU Operator",
            category="infrastructure",
            description="Run coding, research, and browser jobs on remote boxes or GPU hosts with traceable delegation.",
            wave="wave-3",
            setup_summary="Attach trusted remote workbenches for heavier jobs without leaving the ClawOS surface.",
            dashboards=["remote", "traces", "tasks"],
            default_workflows=["repo_summary", "process_report", "port_scan"],
            extension_recommendations=["remote-workbench", "mcp-manager", "a2a-federation"],
            provider_recommendations=["local-ollama", "openai-compatible"],
            policy_pack="security-sensitive",
            eval_suite_id="eval-remote-workbench",
        ),
    ]


def get_pack(pack_id: str) -> UseCasePack | None:
    for pack in list_packs():
        if pack.id == pack_id:
            return pack
    return None


def list_provider_profiles() -> list[ProviderProfile]:
    ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    return [
        ProviderProfile(
            id="local-ollama",
            name="Local Ollama",
            kind="ollama",
            endpoint=ollama_host,
            auth_mode="none",
            default_model=DEFAULT_MODEL,
            fallback_order=["openai-compatible", "openrouter"],
            local_only=True,
            privacy_posture="fully local",
            cost_posture="electricity only",
        ),
        ProviderProfile(
            id="anthropic-api",
            name="Anthropic API",
            kind="anthropic",
            endpoint="https://api.anthropic.com/v1/messages",
            auth_mode="api-key",
            default_model="claude-sonnet-4-20250514",
            fallback_order=["local-ollama"],
            privacy_posture="cloud",
            cost_posture="usage-based",
            auth_env="ANTHROPIC_API_KEY",
        ),
        ProviderProfile(
            id="openai-api",
            name="OpenAI API",
            kind="openai",
            endpoint="https://api.openai.com/v1/responses",
            auth_mode="api-key",
            default_model="gpt-4.1",
            fallback_order=["local-ollama"],
            privacy_posture="cloud",
            cost_posture="usage-based",
            auth_env="OPENAI_API_KEY",
        ),
        ProviderProfile(
            id="azure-openai",
            name="Azure OpenAI",
            kind="azure-openai",
            endpoint="https://example-resource.openai.azure.com/",
            auth_mode="api-key",
            default_model="gpt-4.1",
            fallback_order=["local-ollama"],
            privacy_posture="cloud",
            cost_posture="usage-based",
            auth_env="AZURE_OPENAI_API_KEY",
        ),
        ProviderProfile(
            id="openai-compatible",
            name="OpenAI-Compatible",
            kind="openai-compatible",
            endpoint="http://127.0.0.1:8000/v1",
            auth_mode="optional-api-key",
            default_model=DEFAULT_MODEL,
            fallback_order=["local-ollama", "openrouter"],
            privacy_posture="hybrid",
            cost_posture="depends on endpoint",
            auth_env="OPENAI_COMPATIBLE_API_KEY",
        ),
        ProviderProfile(
            id="openrouter",
            name="OpenRouter",
            kind="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            auth_mode="api-key",
            default_model="moonshotai/kimi-k2",
            fallback_order=["local-ollama"],
            privacy_posture="cloud",
            cost_posture="usage-based",
            auth_env="OPENROUTER_API_KEY",
        ),
    ]


def get_provider_profile(profile_id: str) -> ProviderProfile | None:
    for profile in list_provider_profiles():
        if profile.id == profile_id:
            return profile
    return None


def list_extensions() -> list[ExtensionManifest]:
    return [
        ExtensionManifest(
            id="browser-workbench",
            name="Browser Workbench",
            category="tooling",
            description="Playwright-backed browsing with session isolation, approvals, and trace capture.",
            trust_tier="Verified",
            permissions=["browser", "network"],
            network_access="external-optional",
            packs=["research-newsroom", "travel-personal-admin", "coding-autopilot"],
        ),
        ExtensionManifest(
            id="research-engine",
            name="Research Engine",
            category="tooling",
            description="Broad-source research and citation synthesis with resumable staged runs.",
            trust_tier="Verified",
            permissions=["web_search", "filesystem"],
            network_access="external-optional",
            packs=["research-newsroom", "social-media-studio", "sales-meeting-operator"],
        ),
        ExtensionManifest(
            id="mcp-manager",
            name="MCP Manager",
            category="protocol",
            description="Install, scope, and audit local or remote MCP servers from within Command Center.",
            trust_tier="Verified",
            permissions=["filesystem", "network", "subprocess"],
            network_access="hybrid",
            packs=["coding-autopilot", "remote-workbench-gpu-operator"],
        ),
        ExtensionManifest(
            id="a2a-federation",
            name="A2A Federation",
            category="protocol",
            description="Peer discovery and delegated work across trusted ClawOS nodes.",
            trust_tier="Verified",
            permissions=["network"],
            network_access="hybrid",
            packs=["remote-workbench-gpu-operator"],
        ),
        ExtensionManifest(
            id="calendar-connectors",
            name="Calendar Connectors",
            category="connector",
            description="Calendar ingestion and scheduling context for briefing and meetings workflows.",
            trust_tier="Verified",
            permissions=["calendar", "network"],
            network_access="external-optional",
            packs=["daily-briefing-os", "sales-meeting-operator", "travel-personal-admin"],
            requires_secrets=["GOOGLE_CALENDAR_TOKEN"],
        ),
        ExtensionManifest(
            id="notes-connectors",
            name="Notes Connectors",
            category="connector",
            description="PKM connectors for notes, meeting packets, and long-term operating context.",
            trust_tier="Verified",
            permissions=["filesystem", "notes"],
            packs=["daily-briefing-os", "sales-meeting-operator", "chat-app-command-center"],
        ),
        ExtensionManifest(
            id="chat-bridges",
            name="Chat Bridges",
            category="channel",
            description="WhatsApp and chat-app entry points for command-center messaging and summaries.",
            trust_tier="Verified",
            permissions=["network", "messaging"],
            network_access="external-optional",
            packs=["chat-app-command-center", "daily-briefing-os", "travel-personal-admin"],
        ),
        ExtensionManifest(
            id="remote-workbench",
            name="Remote Workbench",
            category="infrastructure",
            description="Trusted remote execution targets for coding, research, and GPU-backed tasks.",
            trust_tier="Verified",
            permissions=["ssh", "network", "filesystem"],
            network_access="hybrid",
            packs=["coding-autopilot", "remote-workbench-gpu-operator"],
        ),
        ExtensionManifest(
            id="home-health-connectors",
            name="Home and Health Connectors",
            category="connector",
            description="Home Assistant and wearable summaries with privacy-first local ingestion.",
            trust_tier="Community",
            permissions=["network", "health"],
            network_access="external-optional",
            packs=["home-health-hub"],
            requires_secrets=["HOME_ASSISTANT_TOKEN"],
        ),
    ]


def get_extension(extension_id: str) -> ExtensionManifest | None:
    for extension in list_extensions():
        if extension.id == extension_id:
            return extension
    return None


def list_workflow_programs() -> list[WorkflowProgram]:
    user_programs = _load_user_programs()
    builtin = [
        WorkflowProgram(
            id="program-daily-briefing",
            name="Daily Briefing Loop",
            pack_id="daily-briefing-os",
            summary="Collect calendar, notes, and task signals into a briefing packet.",
            checkpoints=["collect-data", "summarize", "draft-briefing"],
            approval_points=["deliver-external-message"],
            triggers=["scheduled-morning", "scheduled-evening"],
        ),
        WorkflowProgram(
            id="program-sales-meeting",
            name="Sales Meeting Flow",
            pack_id="sales-meeting-operator",
            summary="Turn a lead or meeting into research, prep, and follow-up artifacts.",
            checkpoints=["collect-context", "draft-packet", "follow-up"],
            approval_points=["send-follow-up"],
            triggers=["manual", "calendar-event"],
        ),
        WorkflowProgram(
            id="program-coding-autopilot",
            name="Coding Autopilot Run",
            pack_id="coding-autopilot",
            summary="Summarize repo, plan work, execute in isolation, and queue review.",
            checkpoints=["plan", "execute", "review"],
            approval_points=["merge", "shell-sensitive"],
            triggers=["manual", "scheduled-overnight"],
        ),
    ]
    user_ids = {p.id for p in user_programs}
    return user_programs + [p for p in builtin if p.id not in user_ids]


def _load_user_programs() -> list[WorkflowProgram]:
    if not _STUDIO_DIR.exists():
        return []
    programs = []
    for path in sorted(_STUDIO_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            programs.append(WorkflowProgram(**{
                k: v for k, v in data.items()
                if k in WorkflowProgram.__dataclass_fields__
            }))
        except (json.JSONDecodeError, ValueError):
            continue
    return programs


def get_workflow_program(program_id: str) -> WorkflowProgram | None:
    for p in list_workflow_programs():
        if p.id == program_id:
            return p
    return None


def save_workflow_program(data: dict) -> dict:
    _STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    program_id = str(data.get("id", "")).strip()
    if not program_id:
        raise ValueError("id required")
    path = _STUDIO_DIR / f"{program_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def delete_workflow_program(program_id: str) -> bool:
    path = _STUDIO_DIR / f"{program_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_eval_suites() -> list[EvalSuite]:
    return [
        EvalSuite(
            id="eval-daily-briefing",
            name="Daily Briefing Reliability",
            pack_id="daily-briefing-os",
            description="Checks freshness, prioritization, and delivery quality.",
            checks=["sources attached", "meeting prep included", "priority ordering"],
        ),
        EvalSuite(
            id="eval-sales-operator",
            name="Sales Operator Accuracy",
            pack_id="sales-meeting-operator",
            description="Checks dossier quality, follow-up completeness, and draft safety.",
            checks=["account context", "next steps", "draft-only mode"],
        ),
        EvalSuite(
            id="eval-chat-command-center",
            name="Chat Command Center Continuity",
            pack_id="chat-app-command-center",
            description="Checks channel continuity, memory quality, and command routing.",
            checks=["memory carry-over", "channel routing", "summary quality"],
        ),
        EvalSuite(
            id="eval-coding-autopilot",
            name="Coding Autopilot Safety",
            pack_id="coding-autopilot",
            description="Checks planning, branch isolation, trace quality, and review gates.",
            checks=["branch isolation", "policy approvals", "trace completeness"],
        ),
        EvalSuite(
            id="eval-research-newsroom",
            name="Research Desk Citations",
            pack_id="research-newsroom",
            description="Checks citation coverage, breadth, and synthesis quality.",
            checks=["citation count", "source diversity", "hallucination guardrail"],
        ),
    ]


def record_trace(trace: TraceRecord | dict[str, Any]) -> None:
    record = trace.to_dict() if isinstance(trace, TraceRecord) else dict(trace)
    TRACES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TRACES_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    records: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
        if len(records) >= limit:
            break
    return records


def list_traces(limit: int = 40) -> list[dict[str, Any]]:
    records = _read_jsonl(TRACES_JSONL, limit)
    if records:
        return records

    traces: list[dict[str, Any]] = []
    for record in _read_jsonl(OTEL_JSONL, limit):
        traces.append(
            TraceRecord(
                id=record.get("task_id") or record.get("timestamp") or task_id(),
                title=record.get("tool_name") or record.get("model") or "Runtime span",
                category=record.get("span_type") or "runtime",
                status="completed",
                provider=record.get("provider", ""),
                tools=[record.get("tool_name")] if record.get("tool_name") else [],
                metadata={
                    "workspace_id": record.get("workspace_id", ""),
                    "latency_ms": record.get("latency_ms", 0),
                    "total_tokens": int(record.get("input_tokens", 0)) + int(record.get("output_tokens", 0)),
                },
                started_at=record.get("timestamp", now_iso()),
                finished_at=record.get("timestamp", now_iso()),
            ).to_dict()
        )
    return traces


def _openclaw_dir(path_hint: str = "") -> Path:
    if path_hint:
        return Path(path_hint).expanduser()
    try:
        from openclaw_integration.config_gen import OPENCLAW_DIR

        return OPENCLAW_DIR
    except (ImportError, ModuleNotFoundError):
        return Path.home() / ".openclaw"


def detect_openclaw_install(path_hint: str = "") -> OpenClawImportManifest:
    base = _openclaw_dir(path_hint)
    config_path = base / "openclaw.json"
    manifest = OpenClawImportManifest(
        source_path=str(base),
        config_path=str(config_path) if config_path.exists() else "",
    )

    if shutil.which("openclaw"):
        try:
            result = subprocess.run(
                ["openclaw", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            manifest.detected_version = result.stdout.strip() or result.stderr.strip()
        except (subprocess.SubprocessError, OSError):
            manifest.detected_version = "installed"
    else:
        manifest.warnings.append("OpenClaw binary was not found on PATH.")

    env_summary = {
        "openrouter_key": bool(os.environ.get("OPENROUTER_API_KEY")),
        "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai_key": bool(os.environ.get("OPENAI_API_KEY")),
    }
    manifest.env_summary = env_summary
    if env_summary["anthropic_key"]:
        manifest.warnings.append("Anthropic API usage is configured; provider independence is recommended.")
    if env_summary["openrouter_key"]:
        manifest.migration_actions.append("Preserve OpenRouter as an optional fallback provider profile.")

    if config_path.exists():
        config = _read_json(config_path)
        manifest.channels = sorted((config.get("channels") or {}).keys())
        providers = (((config.get("models") or {}).get("providers")) or {})
        manifest.providers = sorted(providers.keys())
        manifest.skills = sorted((config.get("skills") or {}).keys())

        if "whatsapp" in manifest.channels:
            manifest.suggested_primary_pack = "chat-app-command-center"
            manifest.migration_actions.append("Map WhatsApp messaging into the Chat-App Personal Command Center pack.")
        if "web-browser" in manifest.skills and not manifest.suggested_primary_pack:
            manifest.suggested_primary_pack = "research-newsroom"
        if "ollama" in manifest.providers:
            manifest.migration_actions.append("Keep local Ollama as the primary provider profile.")
        if any(provider != "ollama" for provider in manifest.providers):
            manifest.migration_actions.append("Create provider profiles for cloud providers and keep local fallback enabled.")
        manifest.migration_actions.append("Import safe OpenClaw config and preserve supported workflows.")
    else:
        manifest.blockers.append("openclaw.json was not found in the expected location.")

    skills_dir = base / "skills"
    if skills_dir.exists():
        manifest.skills = sorted({*manifest.skills, *[entry.name for entry in skills_dir.iterdir() if entry.is_dir()]})

    if not manifest.suggested_primary_pack:
        manifest.suggested_primary_pack = "daily-briefing-os"

    return manifest


def test_provider_profile(profile_id: str) -> dict[str, Any]:
    profile = get_provider_profile(profile_id)
    if not profile:
        return {"ok": False, "status": "unknown", "detail": "Provider profile not found."}

    if profile.local_only or profile.kind == "ollama":
        try:
            from services.modeld.ollama_client import is_running

            running = bool(is_running())
        except (ImportError, ConnectionError, OSError, RuntimeError):
            running = False
        return {
            "ok": running,
            "status": "online" if running else "offline",
            "detail": "Local Ollama runtime detected." if running else "Ollama is not responding on the local endpoint.",
            "profile": profile.to_dict(),
        }

    if profile.auth_env and not os.environ.get(profile.auth_env):
        return {
            "ok": False,
            "status": "needs_credentials",
            "detail": f"Set {profile.auth_env} to activate this provider profile.",
            "profile": profile.to_dict(),
        }

    return {
        "ok": True,
        "status": "configured",
        "detail": "Provider profile is configured and ready to be selected.",
        "profile": profile.to_dict(),
    }


def make_trace(
    *,
    title: str,
    category: str,
    status: str,
    provider: str = "",
    pack_id: str = "",
    tools: list[str] | None = None,
    approvals: int = 0,
    citations: int = 0,
    metadata: dict[str, Any] | None = None,
) -> TraceRecord:
    return TraceRecord(
        id=task_id(),
        title=title,
        category=category,
        status=status,
        provider=provider,
        pack_id=pack_id,
        tools=tools or [],
        approvals=approvals,
        citations=citations,
        metadata=metadata or {},
        started_at=now_iso(),
        finished_at=now_iso(),
    )


def as_payload(items: list[Any]) -> list[dict[str, Any]]:
    return [item.to_dict() if hasattr(item, "to_dict") else asdict(item) for item in items]
