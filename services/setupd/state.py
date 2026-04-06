# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Persistent SetupState for ClawOS setup flows.
"""
from __future__ import annotations

import json
import platform as py_platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bootstrap.hardware_probe import probe
from bootstrap.profile_selector import recommended_model, select_with_bundle
from clawos_core.constants import DEFAULT_WORKSPACE, SETUP_STATE_JSON
from clawos_core.platform import platform_key
from clawos_core.presence import default_autonomy_policy, default_presence_profile
from clawos_core.service_manager import service_manager_name


@dataclass
class SetupState:
    install_channel: str = "desktop"
    platform: str = field(default_factory=platform_key)
    architecture: str = field(default_factory=py_platform.machine)
    service_manager: str = field(default_factory=service_manager_name)
    detected_hardware: dict[str, Any] = field(default_factory=dict)
    recommended_profile: str = "balanced"
    selected_runtimes: list[str] = field(default_factory=lambda: ["nexus", "picoclaw"])
    selected_models: list[str] = field(default_factory=lambda: ["qwen2.5:7b"])
    selected_provider_profile: str = "local-ollama"
    primary_pack: str = "daily-briefing-os"
    secondary_packs: list[str] = field(default_factory=lambda: ["coding-autopilot"])
    installed_extensions: list[str] = field(default_factory=lambda: ["mcp-manager"])
    workspace: str = DEFAULT_WORKSPACE
    assistant_identity: str = "Nexus"
    presence_profile: dict[str, Any] = field(default_factory=lambda: default_presence_profile().to_dict())
    autonomy_policy: dict[str, Any] = field(default_factory=lambda: default_autonomy_policy().to_dict())
    quiet_hours: dict[str, str] = field(default_factory=lambda: {"start": "22:00", "end": "07:00"})
    primary_goals: list[str] = field(default_factory=lambda: ["daily briefing", "meeting prep", "inbox triage"])
    voice_mode: str = "push_to_talk"
    briefing_enabled: bool = True
    voice_enabled: bool = True
    enable_openclaw: bool = False
    launch_on_login: bool = True
    policy_mode: str = "recommended"
    progress_stage: str = "idle"
    logs: list[str] = field(default_factory=list)
    retry_state: str = ""
    completion_marker: bool = False
    last_error: str = ""
    plan_steps: list[str] = field(default_factory=list)
    imported_openclaw: dict[str, Any] = field(default_factory=dict)

    def save(self, path: Path | None = None):
        path = path or SETUP_STATE_JSON
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass

    @classmethod
    def load(cls, path: Path | None = None) -> "SetupState":
        path = path or SETUP_STATE_JSON
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        return cls.from_machine()

    @classmethod
    def from_machine(cls) -> "SetupState":
        hw = probe()
        bundle = select_with_bundle(hw)
        return cls(
            detected_hardware={
                "summary": f"Tier {hw.tier} - {hw.ram_gb} GB RAM - {hw.gpu_name}",
                "ram_gb": hw.ram_gb,
                "gpu_name": hw.gpu_name,
                "gpu_vram_gb": hw.gpu_vram_gb,
                "tier": hw.tier,
                "cpu_cores": hw.cpu_cores,
                "has_mic": hw.has_mic,
                "ollama_ok": hw.ollama_ok,
                "node_ok": hw.node_ok,
            },
            recommended_profile=bundle["profile"],
            selected_runtimes=bundle["runtimes"],
            selected_models=[recommended_model(hw)],
            selected_provider_profile="local-ollama",
            primary_pack="daily-briefing-os",
            secondary_packs=["coding-autopilot"] if hw.ram_gb >= 16 else [],
            installed_extensions=["mcp-manager"] if hw.ram_gb >= 16 else [],
            assistant_identity="Nexus",
            presence_profile=default_presence_profile().to_dict(),
            autonomy_policy=default_autonomy_policy().to_dict(),
            quiet_hours={"start": "22:00", "end": "07:00"},
            primary_goals=["daily briefing", "meeting prep", "inbox triage"],
            voice_mode="push_to_talk" if hw.has_mic and hw.ram_gb >= 8 else "off",
            briefing_enabled=True,
            voice_enabled=hw.has_mic and hw.ram_gb >= 8,
            enable_openclaw="openclaw" in bundle["runtimes"],
        )

    @classmethod
    def migrate(cls) -> "SetupState":
        try:
            from setup.first_run.state import WizardState

            legacy = WizardState.load()
            state = cls.from_machine()
            state.recommended_profile = legacy.profile or state.recommended_profile
            state.selected_runtimes = list(legacy.runtimes or state.selected_runtimes)
            state.selected_models = [legacy.model] if legacy.model else state.selected_models
            state.workspace = legacy.workspace_id or state.workspace
            state.assistant_identity = "Nexus"
            state.presence_profile = default_presence_profile().to_dict()
            state.autonomy_policy = default_autonomy_policy().to_dict()
            state.quiet_hours = {"start": "22:00", "end": "07:00"}
            state.primary_goals = ["daily briefing", "meeting prep", "inbox triage"]
            state.voice_mode = "push_to_talk" if legacy.voice_enabled else "off"
            state.briefing_enabled = True
            state.voice_enabled = legacy.voice_enabled
            state.enable_openclaw = legacy.runtime in {"openclaw", "both"} or legacy.whatsapp_enabled
            state.selected_provider_profile = "local-ollama"
            state.primary_pack = "chat-app-command-center" if legacy.whatsapp_enabled else state.primary_pack
            if legacy.runtime in {"openclaw", "both"} and "coding-autopilot" not in state.secondary_packs:
                state.secondary_packs.append("coding-autopilot")
            state.launch_on_login = True
            state.policy_mode = legacy.policy_mode or state.policy_mode
            state.completion_marker = legacy.completed
            return state
        except Exception:
            return cls.from_machine()
