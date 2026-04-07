# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Shared Nexus presence, autonomy, briefing, mission, and voice-session state.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from clawos_core.constants import PRESENCE_STATE_JSON
from clawos_core.models import AttentionEvent, AutonomyPolicy, Briefing, Mission, PresenceProfile, VoiceSession
from clawos_core.util.time import now_iso


def default_presence_profile() -> PresenceProfile:
    return PresenceProfile()


def default_autonomy_policy() -> AutonomyPolicy:
    return AutonomyPolicy()


def default_voice_session(mode: str = "push_to_talk") -> VoiceSession:
    return VoiceSession(mode=mode)


def _seed_missions(primary_pack: str = "daily-briefing-os") -> list[Mission]:
    if primary_pack == "coding-autopilot":
        return [
            Mission(
                title="Overnight coding lane",
                summary="Queue repo planning, isolated execution, and review-ready output.",
                checkpoint="waiting-for-instructions",
                status="idle",
                trust_lane="trusted-automatic",
                next_action="Start a coding mission when you are ready.",
            ),
            Mission(
                title="Repository watch",
                summary="Monitor traces, approvals, and failures across active coding runs.",
                checkpoint="monitoring",
                status="active",
                trust_lane="automatic",
                next_action="Surface blockers that need a review decision.",
            ),
        ]

    return [
        Mission(
            title="Morning briefing",
            summary="Prepare your daily priorities, meetings, travel, and reminders before you ask.",
            checkpoint="monitoring-calendar",
            status="active",
            trust_lane="automatic",
            next_action="Refresh the briefing when your schedule changes.",
        ),
        Mission(
            title="Inbox triage",
            summary="Stage replies, follow-ups, and reminders without sending sensitive content automatically.",
            checkpoint="drafting",
            status="active",
            trust_lane="trusted-automatic",
            next_action="Escalate only when a draft needs approval.",
        ),
        Mission(
            title="Meeting prep",
            summary="Build packets, talking points, and travel/admin readiness before important events.",
            checkpoint="waiting-for-event",
            status="idle",
            trust_lane="trusted-automatic",
            next_action="Open automatically when the next meeting approaches.",
        ),
    ]


def _load_setup_defaults() -> dict[str, Any]:
    try:
        from services.setupd.state import SetupState

        state = SetupState.load()
        return {
            "assistant_identity": state.assistant_identity,
            "primary_pack": state.primary_pack,
            "voice_mode": state.voice_mode,
            "quiet_hours": dict(state.quiet_hours or {}),
            "primary_goals": list(state.primary_goals or []),
            "briefing_enabled": bool(state.briefing_enabled),
            "provider_profile": state.selected_provider_profile,
            "workspace": state.workspace,
        }
    except Exception:
        return {
            "assistant_identity": "Nexus",
            "primary_pack": "daily-briefing-os",
            "voice_mode": "push_to_talk",
            "quiet_hours": {"start": "22:00", "end": "07:00"},
            "primary_goals": ["daily briefing", "meeting prep", "inbox triage"],
            "briefing_enabled": True,
            "provider_profile": "local-ollama",
            "workspace": "nexus_default",
        }


def _setup_value(setup: Any, key: str, default: Any) -> Any:
    if isinstance(setup, dict):
        return setup.get(key, default)
    return getattr(setup, key, default)


def _default_state() -> dict[str, Any]:
    setup = _load_setup_defaults()
    profile = default_presence_profile()
    profile.assistant_identity = setup.get("assistant_identity", "Nexus")
    profile.preferred_voice_mode = setup.get("voice_mode", "push_to_talk")

    autonomy = default_autonomy_policy()
    autonomy.quiet_hours = dict(setup.get("quiet_hours") or autonomy.quiet_hours)

    return {
        "presence_profile": profile.to_dict(),
        "autonomy_policy": autonomy.to_dict(),
        "voice_session": default_voice_session(setup.get("voice_mode", "push_to_talk")).to_dict(),
        "missions": [mission.to_dict() for mission in _seed_missions(setup.get("primary_pack", "daily-briefing-os"))],
    }


def load_presence_state(path: Path | None = None) -> dict[str, Any]:
    path = path or PRESENCE_STATE_JSON
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
    else:
        raw = {}

    state = _default_state()
    for key, value in raw.items():
        if key in state and _has_value(value):
            state[key] = value
    return state


def save_presence_state(state: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    path = path or PRESENCE_STATE_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass
    return state


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def get_presence_payload(path: Path | None = None) -> dict[str, Any]:
    state = load_presence_state(path)
    return {
        "profile": state["presence_profile"],
        "autonomy_policy": state["autonomy_policy"],
        "voice_session": state["voice_session"],
    }


def update_presence_profile(updates: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    state = load_presence_state(path)
    profile = dict(state["presence_profile"])
    for key, value in (updates or {}).items():
        if key in profile and _has_value(value):
            profile[key] = value
    if profile.get("preferred_voice_mode"):
        session = dict(state["voice_session"])
        session["mode"] = profile["preferred_voice_mode"]
        session["updated_at"] = now_iso()
        state["voice_session"] = session
    state["presence_profile"] = profile
    save_presence_state(state, path)
    return get_presence_payload(path)


def update_autonomy_policy(updates: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    state = load_presence_state(path)
    policy = dict(state["autonomy_policy"])
    for key, value in (updates or {}).items():
        if key in policy and _has_value(value):
            policy[key] = value
    state["autonomy_policy"] = policy
    save_presence_state(state, path)
    return get_presence_payload(path)


def get_voice_session(path: Path | None = None) -> dict[str, Any]:
    state = load_presence_state(path)
    return dict(state["voice_session"])


def update_voice_session(updates: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    state = load_presence_state(path)
    session = dict(state["voice_session"])
    for key, value in (updates or {}).items():
        if key in session and value is not None:
            session[key] = value
    session["updated_at"] = now_iso()
    state["voice_session"] = session
    if session.get("mode"):
        profile = dict(state["presence_profile"])
        profile["preferred_voice_mode"] = session["mode"]
        state["presence_profile"] = profile
    save_presence_state(state, path)
    return dict(session)


def set_voice_mode(mode: str, path: Path | None = None) -> dict[str, Any]:
    allowed = {"off", "push_to_talk", "wake_word", "continuous"}
    if mode not in allowed:
        raise ValueError(f"Unsupported voice mode: {mode}")
    return update_voice_session(
        {
            "mode": mode,
            "state": "idle",
            "follow_up_open": False,
        },
        path,
    )


def list_missions(path: Path | None = None) -> list[dict[str, Any]]:
    state = load_presence_state(path)
    missions = state.get("missions") or []
    if missions:
        return missions
    setup = _load_setup_defaults()
    missions = [mission.to_dict() for mission in _seed_missions(setup.get("primary_pack", "daily-briefing-os"))]
    state["missions"] = missions
    save_presence_state(state, path)
    return missions


def start_mission(title: str, summary: str = "", trust_lane: str = "trusted-automatic", path: Path | None = None) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("Mission title is required")
    state = load_presence_state(path)
    mission = Mission(
        title=title.strip(),
        summary=summary.strip() or "Nexus is tracking this objective and will surface blockers when needed.",
        checkpoint="queued",
        status="active",
        trust_lane=trust_lane,
        next_action="Monitor the mission from the command center.",
    )
    missions = list(state.get("missions") or [])
    missions.insert(0, mission.to_dict())
    state["missions"] = missions[:10]
    save_presence_state(state, path)
    return mission.to_dict()


def build_today_briefing(
    *,
    setup_state: Any | None = None,
    services: dict[str, Any] | None = None,
    approvals: list[dict[str, Any]] | None = None,
    missions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    setup = setup_state or _load_setup_defaults()
    approvals = approvals or []
    services = services or {}
    missions = missions or list_missions()

    service_entries = list((services or {}).values())
    healthy = len([item for item in service_entries if (item or {}).get("status") in {"up", "running"}])
    total_services = len(service_entries)
    primary_pack = _setup_value(setup, "primary_pack", "daily-briefing-os")
    provider_profile = _setup_value(setup, "selected_provider_profile", _setup_value(setup, "provider_profile", "local-ollama"))
    workspace = _setup_value(setup, "workspace", "nexus_default")

    briefing = Briefing(
        title="Today's briefing",
        headline=f"Nexus is tracking your {primary_pack.replace('-', ' ')} lane.",
        summary="High-signal updates only. Routines can run automatically inside trusted lanes.",
        items=[
            {
                "title": "Now",
                "body": "The command center is ready. Ask Nexus to queue a mission or open a conversation from here.",
                "priority": "high",
            },
            {
                "title": "Decisions",
                "body": f"{len(approvals)} approval{'s' if len(approvals) != 1 else ''} waiting. Sensitive actions still pause for your review.",
                "priority": "medium" if approvals else "low",
            },
            {
                "title": "Routines",
                "body": f"{len(missions)} mission{'s' if len(missions) != 1 else ''} in view across workspace {workspace}.",
                "priority": "medium",
            },
            {
                "title": "System posture",
                "body": f"{healthy}/{total_services or 0} services healthy. Provider posture is {provider_profile}.",
                "priority": "low",
            },
        ],
    )
    return briefing.to_dict()


def build_attention_events(
    *,
    services: dict[str, Any] | None = None,
    approvals: list[dict[str, Any]] | None = None,
    missions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    services = services or {}
    approvals = approvals or []
    missions = missions or list_missions()
    events: list[AttentionEvent] = []

    blocked = [mission for mission in missions if mission.get("blocked")]
    if blocked:
        mission = blocked[0]
        events.append(
            AttentionEvent(
                title="A mission needs you",
                summary=f"{mission.get('title', 'An active mission')} is blocked and waiting on a decision.",
                urgency="high",
                surface="spoken-visual",
                category="mission",
            )
        )

    if approvals:
        approval = approvals[0]
        target = approval.get("target") or approval.get("tool") or "A sensitive action"
        urgency = "high" if approval.get("risk") == "high" else "medium"
        surface = "spoken-visual" if urgency == "high" else "visual"
        events.append(
            AttentionEvent(
                title="Approval waiting",
                summary=f"{target} is waiting for your review.",
                urgency=urgency,
                surface=surface,
                category="approval",
            )
        )

    degraded = [name for name, item in (services or {}).items() if (item or {}).get("status") not in {"up", "running"}]
    if degraded:
        events.append(
            AttentionEvent(
                title="Service posture changed",
                summary=f"Nexus noticed degraded services: {', '.join(degraded[:3])}.",
                urgency="medium",
                surface="visual",
                category="system",
            )
        )

    if not events:
        events.append(
            AttentionEvent(
                title="Quietly on watch",
                summary="Nexus is monitoring your routines and will only interrupt when something meaningful changes.",
                urgency="low",
                surface="log",
                category="presence",
            )
        )

    return [event.to_dict() for event in events[:4]]


def sync_presence_from_setup(state_like: Any, path: Path | None = None) -> dict[str, Any]:
    state = load_presence_state(path)
    profile = dict(state["presence_profile"])
    profile["assistant_identity"] = getattr(state_like, "assistant_identity", profile.get("assistant_identity", "Nexus"))
    profile["preferred_voice_mode"] = getattr(state_like, "voice_mode", profile.get("preferred_voice_mode", "push_to_talk"))
    state["presence_profile"] = profile

    policy = dict(state["autonomy_policy"])
    policy["quiet_hours"] = dict(getattr(state_like, "quiet_hours", policy.get("quiet_hours", {})) or policy.get("quiet_hours", {}))
    if getattr(state_like, "autonomy_policy", None):
        incoming_policy = getattr(state_like, "autonomy_policy")
        if isinstance(incoming_policy, dict):
            for key, value in incoming_policy.items():
                if key in policy and _has_value(value):
                    policy[key] = value
    state["autonomy_policy"] = policy

    session = dict(state["voice_session"])
    session["mode"] = getattr(state_like, "voice_mode", session.get("mode", "push_to_talk"))
    session["updated_at"] = now_iso()
    state["voice_session"] = session

    if not state.get("missions"):
        primary_pack = getattr(state_like, "primary_pack", "daily-briefing-os")
        state["missions"] = [mission.to_dict() for mission in _seed_missions(primary_pack)]

    save_presence_state(state, path)
    return get_presence_payload(path)
