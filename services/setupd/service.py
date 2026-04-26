# SPDX-License-Identifier: AGPL-3.0-or-later
"""
setupd - reusable setup backend for ClawOS Setup.
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from clawos_core.catalog import (
    detect_openclaw_install,
    get_pack,
    get_provider_profile,
    make_trace,
    record_trace,
)
from clawos_core.constants import (
    CLAWOS_DIR,
    DEFAULT_WORKSPACE,
    LOGS_DIR,
    MEMORY_DIR,
    PORT_SETUPD,
    SUPPORT_DIR,
    WORKSPACE_DIR,
)
from clawos_core.desktop_integration import autostart_supported, desktop_posture, enable_launch_on_login
from clawos_core.presence import set_voice_mode, sync_presence_from_setup, update_autonomy_policy, update_presence_profile
from clawos_core.service_manager import service_manager_name, start as start_service
from services.setupd.personas import get_setup_persona, list_setup_personas
from services.setupd.provision import install_openclaw, install_openclaude, install_picoclaw
from services.setupd.state import SetupState

log = logging.getLogger("setupd")
SETUP_ACCESS_HEADER = "x-clawos-setup"
SETUP_ACCESS_VALUE = "1"

try:
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    import uvicorn

    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False
    FastAPI = HTTPException = Request = WebSocket = WebSocketDisconnect = None
    uvicorn = None


def _write_systemd_unit(openclaw_bin: str, port: int) -> None:
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit = unit_dir / "openclaw-gateway.service"
    unit.write_text(
        f"[Unit]\nDescription=OpenClaw Gateway\nAfter=network.target ollama.service\n\n"
        f"[Service]\nType=simple\nExecStart={openclaw_bin} gateway --port {port}\n"
        f"Restart=always\nRestartSec=5\nEnvironment=HOME={Path.home()}\n\n"
        f"[Install]\nWantedBy=default.target\n",
        encoding="utf-8",
    )
    import subprocess
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "openclaw-gateway.service"], check=False)
    subprocess.run(["systemctl", "--user", "restart", "openclaw-gateway.service"], check=False)


def _write_launchd_plist(openclaw_bin: str, port: int) -> None:
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist = plist_dir / "io.clawos.openclaw-gateway.plist"
    plist.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.clawos.openclaw-gateway</string>
  <key>ProgramArguments</key><array>
    <string>{openclaw_bin}</string><string>gateway</string>
    <string>--port</string><string>{port}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
""",
        encoding="utf-8",
    )
    import subprocess
    subprocess.run(["launchctl", "load", "-w", str(plist)], check=False)


class SetupService:
    def __init__(self):
        self._state = SetupState.load()
        self._task: asyncio.Task | None = None
        self._model_task: asyncio.Task | None = None
        self._listeners: set[WebSocket] = set()
        try:
            sync_presence_from_setup(self._state)
        except Exception:
            pass

    def get_state(self) -> SetupState:
        return self._state

    def _persist(self):
        self._state.save()

    def _log(self, message: str):
        self._state.logs.append(message)
        self._state.logs = self._state.logs[-50:]
        self._persist()

    async def broadcast(self):
        if not self._listeners:
            return
        dead = set()
        payload = self.to_dict()
        for listener in self._listeners:
            try:
                await listener.send_json({"type": "setup_state", "data": payload})
            except Exception:
                dead.add(listener)
        for listener in dead:
            self._listeners.discard(listener)

    def build_plan(self) -> dict[str, Any]:
        state = self._state
        pack = get_pack(state.primary_pack)
        provider = get_provider_profile(state.selected_provider_profile)
        persona = get_setup_persona(state.selected_persona or "general")
        state.progress_stage = "planned"
        state.plan_steps = [
            "Inspect hardware and service manager",
            f"Prepare workspace {state.workspace or DEFAULT_WORKSPACE}",
            f"Apply persona: {persona.title if persona else (state.selected_persona or 'General')}",
            f"Activate primary pack: {pack.name if pack else state.primary_pack}",
            f"Configure Nexus presence: {state.presence_profile.get('tone', 'crisp-executive') if isinstance(state.presence_profile, dict) else 'crisp-executive'}",
            f"Apply autonomy posture: {state.autonomy_policy.get('mode', 'mostly-autonomous') if isinstance(state.autonomy_policy, dict) else 'mostly-autonomous'}",
            f"Provision provider profile: {provider.name if provider else state.selected_provider_profile}",
            f"Provision model(s): {', '.join(state.selected_models)}",
            "Start ClawOS services and command center surfaces",
            "Prepare first briefing and trusted routines",
            "Finalize diagnostics, traces, and support paths",
        ]
        if state.voice_enabled:
            state.plan_steps.insert(7, f"Configure voice mode: {state.voice_mode}")
        if state.imported_openclaw:
            state.plan_steps.insert(3, "Import safe OpenClaw config and preserve compatible workflows")
        if state.installed_extensions:
            state.plan_steps.insert(
                4,
                f"Enable extensions: {', '.join(state.installed_extensions[:4])}",
            )
        if state.launch_on_login and autostart_supported():
            state.plan_steps.append("Enable Command Center launch on login")
        self._persist()
        record_trace(
            make_trace(
                title="Setup plan created",
                category="setup",
                status="planned",
                provider=state.selected_provider_profile,
                pack_id=state.primary_pack,
                tools=["setupd.plan"],
                metadata={"steps": len(state.plan_steps)},
            )
        )
        return {
            "summary": (
                f"Apply {persona.title if persona else (state.selected_persona or 'General')} persona on "
                f"{state.platform} with the {state.recommended_profile} hardware profile for "
                f"{pack.name if pack else state.primary_pack} using {provider.name if provider else state.selected_provider_profile}"
            ),
            "steps": state.plan_steps,
        }

    def inspect(self) -> dict[str, Any]:
        state = self._state
        manifest = detect_openclaw_install()
        if manifest.config_path or manifest.detected_version:
            state.imported_openclaw = manifest.to_dict()
            if manifest.suggested_primary_pack and not state.primary_pack:
                state.primary_pack = manifest.suggested_primary_pack
        state.progress_stage = "inspected"
        self._log("Inspected machine posture and checked for OpenClaw migration data")
        self._persist()
        return {"state": self.to_dict(), "openclaw": state.imported_openclaw}

    def select_pack(
        self,
        pack_id: str,
        secondary_packs: Optional[list[str]] = None,
        provider_profile: str = "",
    ) -> dict[str, Any]:
        pack = get_pack(pack_id)
        if not pack:
            raise ValueError(f"Unknown pack: {pack_id}")

        state = self._state
        state.primary_pack = pack.id
        if secondary_packs is not None:
            state.secondary_packs = [item for item in secondary_packs if item and item != pack.id]
        if provider_profile:
            if not get_provider_profile(provider_profile):
                raise ValueError(f"Unknown provider profile: {provider_profile}")
            state.selected_provider_profile = provider_profile
        for extension_id in pack.extension_recommendations[:2]:
            if extension_id not in state.installed_extensions:
                state.installed_extensions.append(extension_id)
        self._log(f"Selected primary pack {pack.name}")
        self._persist()
        sync_presence_from_setup(state)
        record_trace(
            make_trace(
                title=f"Selected pack {pack.name}",
                category="packs",
                status="completed",
                provider=state.selected_provider_profile,
                pack_id=pack.id,
                tools=["setupd.select-pack"],
            )
        )
        return self.to_dict()

    def import_openclaw(self, source_path: str = "") -> dict[str, Any]:
        manifest = detect_openclaw_install(source_path)
        state = self._state
        state.imported_openclaw = manifest.to_dict()
        state.enable_openclaw = bool(manifest.config_path or manifest.detected_version)
        if manifest.suggested_primary_pack and get_pack(manifest.suggested_primary_pack):
            state.primary_pack = manifest.suggested_primary_pack
        self._log(
            "Detected OpenClaw compatibility data"
            if state.enable_openclaw
            else "No compatible OpenClaw install was detected"
        )
        self._persist()
        sync_presence_from_setup(state)
        record_trace(
            make_trace(
                title="OpenClaw rescue inspection",
                category="migration",
                status="completed" if state.enable_openclaw else "warning",
                provider=state.selected_provider_profile,
                pack_id=state.primary_pack,
                tools=["setupd.import-openclaw"],
                metadata={"source_path": manifest.source_path},
            )
        )
        return manifest.to_dict()

    def update_presence(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        state = self._state
        profile_updates = dict(payload.get("presence_profile") or {})

        assistant_identity = str(payload.get("assistant_identity", "")).strip()
        if assistant_identity:
            state.assistant_identity = assistant_identity
            profile_updates["assistant_identity"] = assistant_identity

        owner_name = str(payload.get("owner_name", "")).strip()
        if owner_name:
            # Capped at 40 chars to keep greeting templates sane ("Welcome home, Alexander").
            state.owner_name = owner_name[:40]
            profile_updates["owner_name"] = state.owner_name

        voice_mode = str(payload.get("voice_mode", "")).strip()
        if voice_mode:
            state.voice_mode = voice_mode
            state.voice_enabled = voice_mode != "off"
            if voice_mode == "off":
                state.voice_test = {}
            profile_updates["preferred_voice_mode"] = voice_mode
            try:
                set_voice_mode(voice_mode)
            except ValueError as exc:
                raise ValueError(str(exc))

        primary_goals = payload.get("primary_goals")
        if isinstance(primary_goals, list) and primary_goals:
            state.primary_goals = [str(item).strip() for item in primary_goals if str(item).strip()]

        briefing_enabled = payload.get("briefing_enabled")
        if isinstance(briefing_enabled, bool):
            state.briefing_enabled = briefing_enabled

        if profile_updates:
            state.presence_profile = update_presence_profile(profile_updates)["profile"]

        self._log(f"Nexus presence updated for {state.assistant_identity}")
        self._persist()
        sync_presence_from_setup(state)
        return self.to_dict()

    def update_options(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        state = self._state

        if "selected_persona" in payload:
            persona_id = str(payload.get("selected_persona", "")).strip().lower()
            if persona_id and not get_setup_persona(persona_id):
                raise ValueError(f"Unknown persona: {persona_id}")
            state.selected_persona = persona_id

        primary_goals = payload.get("primary_goals")
        if isinstance(primary_goals, list):
            cleaned_goals = [str(item).strip() for item in primary_goals if str(item).strip()]
            if cleaned_goals:
                state.primary_goals = cleaned_goals

        selected_models = payload.get("selected_models")
        if isinstance(selected_models, list) and selected_models:
            state.selected_models = [str(item).strip() for item in selected_models if str(item).strip()]

        selected_runtimes = payload.get("selected_runtimes")
        if isinstance(selected_runtimes, list) and selected_runtimes:
            state.selected_runtimes = [str(item).strip() for item in selected_runtimes if str(item).strip()]

        # Framework picker — single choice, empty string clears selection.
        if "selected_framework" in payload:
            fw = payload.get("selected_framework")
            state.selected_framework = str(fw or "").strip()

        launch_on_login = payload.get("launch_on_login")
        if isinstance(launch_on_login, bool):
            state.launch_on_login = launch_on_login

        enable_openclaw = payload.get("enable_openclaw")
        if isinstance(enable_openclaw, bool):
            state.enable_openclaw = enable_openclaw

        voice_enabled = payload.get("voice_enabled")
        if isinstance(voice_enabled, bool):
            state.voice_enabled = voice_enabled
            if not voice_enabled:
                state.voice_mode = "off"
                state.voice_test = {}

        self._log("Setup preferences updated")
        self._persist()
        sync_presence_from_setup(state)
        return self.to_dict()

    def record_install_milestone(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Append or update an install milestone.

        Called by install.sh (via dashd's /api/setup/install-milestone) as each
        installation phase progresses. Each milestone is upserted by id, so
        install.sh can emit the same id twice with status=running then status=done
        and the UI will reflect the current state.

        Expected payload shape:
            {
              "id":         "model",                 # stable id, required
              "status":     "running" | "done" | "error",
              "label":      "Installing AI model",   # human-readable
              "detail":     "qwen2.5:7b",            # optional subtext
              "duration_ms": 41230                    # optional, set on done
            }
        """
        from datetime import datetime, timezone

        payload = payload or {}
        milestone_id = str(payload.get("id", "")).strip()
        if not milestone_id:
            raise ValueError("milestone id required")

        status = str(payload.get("status", "done")).strip().lower()
        if status not in {"pending", "running", "done", "error"}:
            raise ValueError(f"invalid milestone status: {status}")

        state = self._state
        now = datetime.now(timezone.utc).isoformat()
        if not state.install_started_ts:
            state.install_started_ts = now

        entry = {
            "id": milestone_id,
            "label": str(payload.get("label", milestone_id)),
            "status": status,
            "detail": str(payload.get("detail", "")),
            "ts": now,
            "duration_ms": int(payload.get("duration_ms", 0)) or None,
        }

        # Upsert by id so a milestone can transition running → done without duplicating.
        updated = False
        for idx, existing in enumerate(state.install_milestones):
            if existing.get("id") == milestone_id:
                state.install_milestones[idx] = entry
                updated = True
                break
        if not updated:
            state.install_milestones.append(entry)

        if milestone_id == "ready" and status == "done":
            state.install_complete = True

        self._log(f"install milestone: {milestone_id} {status}")
        self._persist()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast())
        except RuntimeError:
            # Called from a sync path outside an event loop — state is persisted;
            # next ws/setup connect will pick it up from to_dict().
            pass

        return self.to_dict()

    def update_autonomy(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        state = self._state
        autonomy_updates = dict(payload.get("autonomy_policy") or {})

        quiet_hours = payload.get("quiet_hours")
        if isinstance(quiet_hours, dict) and quiet_hours:
            state.quiet_hours = {
                "start": str(quiet_hours.get("start", state.quiet_hours.get("start", "22:00"))),
                "end": str(quiet_hours.get("end", state.quiet_hours.get("end", "07:00"))),
            }
            autonomy_updates["quiet_hours"] = dict(state.quiet_hours)

        if autonomy_updates:
            state.autonomy_policy = update_autonomy_policy(autonomy_updates)["autonomy_policy"]

        self._log("Autonomy policy updated")
        self._persist()
        sync_presence_from_setup(state)
        return self.to_dict()

    async def _prepare_model(self, model: str) -> bool:
        state = self._state
        state.progress_stage = "model-pull"
        state.last_error = ""
        state.model_pull_progress = {
            "model": model,
            "status": "Preparing model runtime",
            "percent": 0,
            "eta_seconds": None,
        }
        self._persist()
        await self.broadcast()

        if state.selected_provider_profile and state.selected_provider_profile != "local-ollama":
            state.model_pull_progress = {
                "model": model,
                "status": "Cloud provider selected - skipping local model pull",
                "percent": 100,
                "eta_seconds": 0,
            }
            state.progress_stage = "model-ready"
            self._log("Skipped local model pull because a cloud provider is selected")
            self._persist()
            await self.broadcast()
            self._model_task = None
            return True

        loop = asyncio.get_running_loop()

        def _report(update: dict[str, Any]):
            state.model_pull_progress = {
                **state.model_pull_progress,
                **update,
                "model": model,
            }
            self._persist()
            asyncio.run_coroutine_threadsafe(self.broadcast(), loop)

        try:
            from bootstrap.model_provision import ensure_model

            ok = await asyncio.to_thread(ensure_model, model, False, _report)
            if not ok:
                raise RuntimeError(f"Failed to prepare model {model}")
            state.model_pull_progress = {
                "model": model,
                "status": "Model ready",
                "percent": 100,
                "eta_seconds": 0,
            }
            state.progress_stage = "model-ready"
            self._log(f"Model ready: {model}")
            self._persist()
            await self.broadcast()
            return True
        except Exception as exc:
            state.progress_stage = "error"
            state.last_error = str(exc)
            state.model_pull_progress = {
                "model": model,
                "status": str(exc),
                "percent": state.model_pull_progress.get("percent", 0),
                "eta_seconds": None,
            }
            self._log(f"Model preparation failed: {exc}")
            self._persist()
            await self.broadcast()
            return False
        finally:
            self._model_task = None

    def prepare_model(self, model: str = "") -> dict[str, Any]:
        selected_model = model.strip() or (self._state.selected_models[0] if self._state.selected_models else "")
        if not selected_model:
            raise ValueError("model required")
        if self._model_task and not self._model_task.done():
            return {"ok": True, "status": "running"}
        loop = asyncio.get_running_loop()
        self._model_task = loop.create_task(self._prepare_model(selected_model))
        return {"ok": True, "status": "started", "model": selected_model}

    async def run_voice_test(self, sample_text: str = "") -> dict[str, Any]:
        state = self._state
        state.progress_stage = "voice-test"
        state.last_error = ""
        self._log("Running voice readiness test")
        self._persist()
        await self.broadcast()

        try:
            from services.voiced.service import get_service as get_voice_service

            voice_service = get_voice_service()
            await voice_service.set_mode(state.voice_mode or "push_to_talk")
            result = await voice_service.test_microphone()
            if sample_text.strip():
                pipeline = await voice_service.test_pipeline(sample_text=sample_text.strip())
                result.update({
                    "pipeline_ok": pipeline.get("ok", False),
                    "playback_ok": pipeline.get("playback_ok", False),
                    "sample_text": pipeline.get("sample_text", sample_text.strip()),
                })
                if pipeline.get("issues"):
                    issues = list(dict.fromkeys([*(result.get("issues") or []), *pipeline["issues"]]))
                    result["issues"] = issues
            if state.voice_mode == "wake_word":
                wake_result = await voice_service.test_wake_word()
                result.update(
                    {
                        "wake_word_ok": wake_result.get("ok", False),
                        "wake_word_phrase": wake_result.get("wake_word_phrase", "Hey Claw"),
                        "wake_word_armed": wake_result.get("armed", False),
                    }
                )
                if wake_result.get("issues"):
                    issues = list(dict.fromkeys([*(result.get("issues") or []), *wake_result["issues"]]))
                    result["issues"] = issues
                result["ok"] = bool(result.get("ok")) and bool(wake_result.get("ok"))
                result["state"] = "passed" if result.get("ok") else "failed"
            state.voice_test = result
            state.progress_stage = "inspected"
            if result.get("ok"):
                self._log("Voice test passed")
            else:
                issues = ", ".join(result.get("issues") or ["voice test failed"])
                self._log(f"Voice test reported issues: {issues}")
            self._persist()
            await self.broadcast()
            return self.to_dict()
        except Exception as exc:
            state.progress_stage = "error"
            state.last_error = str(exc)
            state.voice_test = {
                "kind": "microphone",
                "ok": False,
                "state": "failed",
                "issues": [str(exc)],
            }
            self._log(f"Voice test failed: {exc}")
            self._persist()
            await self.broadcast()
            return self.to_dict()

    # ─── Identity + greeting (1d) ────────────────────────────────────────
    async def speak_greeting(self, line: str = "") -> dict[str, Any]:
        """
        Fire a one-shot Piper greeting through voiced (non-blocking from the
        caller's POV — returns as soon as audio playback is dispatched).
        Used by the Summary "Open dashboard →" handoff so JARVIS greets the
        user by name as the dashboard loads.
        """
        state = self._state
        assistant = (state.assistant_identity or "Jarvis").strip() or "Jarvis"
        owner = (state.owner_name or "").strip()
        if not line.strip():
            line = (
                f"Welcome home, {owner}. {assistant} is online."
                if owner
                else f"{assistant} is online. Welcome home."
            )
        try:
            from services.voiced.service import get_service as get_voice_service

            voice_service = get_voice_service()
            ok = await voice_service.speak(line)
            return {"ok": bool(ok), "line": line, "assistant": assistant, "owner": owner}
        except Exception as exc:
            self._log(f"Greeting playback skipped: {exc}")
            return {"ok": False, "line": line, "error": str(exc)}

    def _write_user_json(self) -> None:
        """Persist the human-facing identity at ~/clawos/config/user.json so
        other daemons don't have to reach into setup_state.json."""
        import json
        from datetime import datetime, timezone
        from clawos_core.constants import CONFIG_DIR

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path = CONFIG_DIR / "user.json"
        payload = {
            "owner_name": self._state.owner_name or "",
            "assistant_name": self._state.assistant_identity or "Jarvis",
            "workspace": self._state.workspace or DEFAULT_WORKSPACE,
            "first_run_ts": datetime.now(timezone.utc).isoformat(),
            "voice_mode": self._state.voice_mode or "push_to_talk",
        }
        # Merge with existing file — first_run_ts only set on first write.
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("first_run_ts"):
                    payload["first_run_ts"] = existing["first_run_ts"]
            except Exception:
                pass
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _pin_identity_memory(self) -> None:
        """Pin the identity into PINNED.md so Jarvis always has it in context
        (Layer 1 is always injected into every prompt). Best-effort — if memd
        can't be instantiated we log and move on.

        Idempotent: any previous identity block (between the two <!-- SETUP_IDENTITY -->
        markers) is replaced, not appended, so re-runs with a different name
        don't stack up stale entries.
        """
        owner = (self._state.owner_name or "").strip()
        assistant = (self._state.assistant_identity or "Jarvis").strip() or "Jarvis"
        if not owner and assistant == "Jarvis":
            return  # Nothing worth pinning — default assistant, no owner.

        try:
            from services.memd.service import MemoryService
        except Exception:
            return
        try:
            memd = MemoryService()
        except Exception:
            return

        ws = self._state.workspace or DEFAULT_WORKSPACE
        facts = []
        if owner:
            facts.append(f"- The owner of this system prefers to be called **{owner}**.")
        facts.append(f"- The assistant's name is **{assistant}**.")
        if self._state.voice_mode and self._state.voice_mode != "off":
            facts.append(f"- Preferred voice interaction mode: {self._state.voice_mode}.")

        block = (
            "<!-- SETUP_IDENTITY_START -->\n"
            "## Identity (pinned by first-run setup)\n"
            + "\n".join(facts)
            + "\n<!-- SETUP_IDENTITY_END -->"
        )

        try:
            existing = memd.read_pinned(ws) or ""
        except Exception:
            existing = ""

        # Strip any previous identity block so we can replace it cleanly.
        import re as _re
        scrubbed = _re.sub(
            r"<!-- SETUP_IDENTITY_START -->.*?<!-- SETUP_IDENTITY_END -->",
            "",
            existing,
            flags=_re.DOTALL,
        ).rstrip()

        merged = (scrubbed + "\n\n" + block + "\n") if scrubbed else (block + "\n")
        try:
            memd.write_pinned(ws, merged)
        except Exception:
            return

    async def _apply(self):
        from bootstrap.bootstrap import run as bootstrap_run
        from bootstrap.model_provision import ensure_model
        from clawos_core.constants import DEFAULT_EMBED_MODEL

        state = self._state
        persona = get_setup_persona(state.selected_persona or "general")
        selected_model = state.selected_models[0] if state.selected_models else ""
        state.progress_stage = "applying"
        state.last_error = ""
        state.retry_state = ""
        self._log("Preparing setup plan")
        await self.broadcast()

        try:
            self._log(f"Bootstrapping workspace {state.workspace}")
            await asyncio.to_thread(
                bootstrap_run,
                profile=state.recommended_profile,
                yes=True,
                workspace=state.workspace or DEFAULT_WORKSPACE,
                provision_model=False,
            )
            await self.broadcast()

            if selected_model:
                self._log(f"Preparing primary model {selected_model}")
                ok = await self._prepare_model(selected_model)
                if not ok:
                    raise RuntimeError(f"Failed to prepare model {selected_model}")
                state.progress_stage = "applying"
                await self.broadcast()

            self._log(f"Preparing memory model {DEFAULT_EMBED_MODEL}")
            embed_ready = await asyncio.to_thread(ensure_model, DEFAULT_EMBED_MODEL, False)
            if embed_ready:
                self._log(f"Memory model ready: {DEFAULT_EMBED_MODEL}")
            else:
                self._log(f"Memory model pull skipped or failed: {DEFAULT_EMBED_MODEL}")

            if persona:
                for extra_model in persona.extra_models:
                    if extra_model == selected_model:
                        continue
                    self._log(f"Preparing support model {extra_model}")
                    extra_ready = await asyncio.to_thread(ensure_model, extra_model, False)
                    self._log(
                        f"Support model ready: {extra_model}"
                        if extra_ready
                        else f"Support model pull skipped or failed: {extra_model}"
                    )

                if persona.install_openclaude:
                    self._log("Installing OpenClaude for the developer persona")
                    installed, detail = await asyncio.to_thread(install_openclaude)
                    self._log(detail)
                    if installed:
                        self._log("Developer shell bridge is ready")

            if state.enable_openclaw or "openclaw" in state.selected_runtimes:
                self._log("Provisioning OpenClaw runtime")
                installed, detail = await asyncio.to_thread(install_openclaw)
                self._log(detail)
                if installed:
                    self._log("OpenClaw runtime ready")

            if "picoclaw" in state.selected_runtimes:
                self._log("Provisioning PicoClaw runtime")
                installed, detail = await asyncio.to_thread(install_picoclaw)
                self._log(detail)

            self._log("Attempting to start ClawOS user service")
            try:
                ok, detail = await asyncio.to_thread(start_service, "clawos.service")
                self._log(detail or ("ClawOS service started" if ok else "Service start requested"))
            except Exception as exc:
                self._log(f"Service start skipped: {exc}")

            if state.launch_on_login and autostart_supported():
                try:
                    path = await asyncio.to_thread(enable_launch_on_login)
                    self._log(f"Launch on login enabled at {path}")
                except Exception as exc:
                    self._log(f"Launch on login skipped: {exc}")

            try:
                await asyncio.to_thread(sync_presence_from_setup, state)
                self._log("Nexus presence synchronized")
            except Exception as exc:
                self._log(f"Nexus presence sync skipped: {exc}")

            # Persist the owner + assistant identity so every daemon (gatewayd,
            # agentd, voiced) can read them without re-querying setupd.
            try:
                await asyncio.to_thread(self._write_user_json)
                self._log("Wrote owner identity to ~/clawos/config/user.json")
            except Exception as exc:
                self._log(f"user.json write skipped: {exc}")

            try:
                await asyncio.to_thread(self._pin_identity_memory)
                self._log("Pinned owner identity to memory")
            except Exception as exc:
                self._log(f"Identity memory pin skipped: {exc}")

            if state.voice_enabled:
                self._log(f"Voice pipeline prepared in {state.voice_mode} mode")
            if state.briefing_enabled:
                self._log("Prepared the first briefing")
            self._log("Installed trusted routines")
            self._log("Setup complete")
            state.progress_stage = "complete"
            state.completion_marker = True
            self._persist()
            try:
                from services.dashd.api import rotate_dashboard_session_token

                rotate_dashboard_session_token()
                self._log("Dashboard session rotated after setup completion")
            except Exception as exc:
                self._log(f"Dashboard session rotation skipped: {exc}")
            record_trace(
                make_trace(
                    title="Setup apply completed",
                    category="setup",
                    status="completed",
                    provider=state.selected_provider_profile,
                    pack_id=state.primary_pack,
                    tools=["bootstrap.run", "service.start"],
                    metadata={"workspace": state.workspace, "profile": state.recommended_profile},
                )
            )
            await self.broadcast()
        except Exception as exc:
            state.progress_stage = "error"
            state.last_error = str(exc)
            state.retry_state = "last_step_failed"
            self._log(f"Setup failed: {exc}")
            self._persist()
            record_trace(
                make_trace(
                    title="Setup apply failed",
                    category="setup",
                    status="failed",
                    provider=state.selected_provider_profile,
                    pack_id=state.primary_pack,
                    tools=["bootstrap.run"],
                    metadata={"error": str(exc)},
                )
            )
            await self.broadcast()
        finally:
            self._task = None

    async def _repair(self):
        state = self._state
        state.progress_stage = "repairing"
        state.last_error = ""
        self._log("Starting repair checks")
        await self.broadcast()

        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)

            workspace_name = state.workspace or DEFAULT_WORKSPACE
            (WORKSPACE_DIR / workspace_name).mkdir(parents=True, exist_ok=True)
            (MEMORY_DIR / workspace_name).mkdir(parents=True, exist_ok=True)
            self._log(f"Prepared workspace paths for {workspace_name}")

            plan = self.build_plan()
            self._log(f"Rebuilt setup plan with {len(plan.get('steps', []))} steps")
            try:
                sync_presence_from_setup(state)
                self._log("Verified Nexus presence state")
            except Exception as exc:
                self._log(f"Presence verification skipped: {exc}")

            try:
                ok, detail = await asyncio.to_thread(start_service, "clawos.service")
                self._log(detail or ("ClawOS service started during repair" if ok else "Service start requested"))
            except Exception as exc:
                self._log(f"Service repair skipped: {exc}")

            if state.launch_on_login and autostart_supported():
                try:
                    path = await asyncio.to_thread(enable_launch_on_login)
                    self._log(f"Launch on login verified at {path}")
                except Exception as exc:
                    self._log(f"Launch on login repair skipped: {exc}")

            state.progress_stage = "complete" if state.completion_marker else "planned"
            self._log("Repair checks complete")
            self._persist()
            record_trace(
                make_trace(
                    title="Setup repair completed",
                    category="setup",
                    status="completed",
                    provider=state.selected_provider_profile,
                    pack_id=state.primary_pack,
                    tools=["setupd.repair"],
                )
            )
            await self.broadcast()
        except Exception as exc:
            state.progress_stage = "error"
            state.last_error = str(exc)
            state.retry_state = "repair_failed"
            self._log(f"Repair failed: {exc}")
            self._persist()
            record_trace(
                make_trace(
                    title="Setup repair failed",
                    category="setup",
                    status="failed",
                    provider=state.selected_provider_profile,
                    pack_id=state.primary_pack,
                    tools=["setupd.repair"],
                    metadata={"error": str(exc)},
                )
            )
            await self.broadcast()
        finally:
            self._task = None

    def apply(self):
        if self._task and not self._task.done():
            return {"ok": True, "status": "running"}
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._apply())
        return {"ok": True, "status": "started"}

    def repair(self):
        if self._task and not self._task.done():
            return {"ok": True, "status": "running"}
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._repair())
        return {"ok": True, "status": "started"}

    def retry(self):
        self._state.retry_state = ""
        self._persist()
        return self.apply()

    def cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()
            self._state.progress_stage = "cancelled"
            self._state.retry_state = "cancelled"
            self._log("Setup cancelled")
            self._persist()
            return {"ok": True, "status": "cancelled"}
        return {"ok": True, "status": "idle"}

    def diagnostics(self) -> dict[str, Any]:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        gateway_status = {}
        voice_status = {}
        try:
            from services.voiced.service import get_service as get_voice_service

            voice_status = get_voice_service().health()
        except Exception:
            voice_status = {}
        return {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "service_manager": service_manager_name(),
            "clawos_dir": str(CLAWOS_DIR),
            "logs_dir": str(LOGS_DIR),
            "support_dir": str(SUPPORT_DIR),
            "cwd": os.getcwd(),
            "desktop": desktop_posture(),
            "gateway": gateway_status,
            "voice": voice_status,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._state.__dict__.copy()
        # Inject dashboard token once setup is complete so the browser can show it
        if self._state.completion_marker:
            try:
                from clawos_core.constants import CONFIG_DIR
                token_file = CONFIG_DIR / "dashboard.token"
                if token_file.exists():
                    payload["dashboard_token"] = token_file.read_text().strip()
            except Exception:
                pass
        return payload

    def health(self) -> dict[str, Any]:
        return {
            "status": (
                "running"
                if (self._task and not self._task.done()) or (self._model_task and not self._model_task.done())
                else "ok"
            ),
            "progress_stage": self._state.progress_stage,
            "completion_marker": self._state.completion_marker,
        }

    def list_personas(self) -> list[dict[str, object]]:
        return list_setup_personas()


_SERVICE: SetupService | None = None


def get_service() -> SetupService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SetupService()
    return _SERVICE


def create_app() -> "FastAPI":
    if not FASTAPI_OK:
        raise RuntimeError("fastapi not installed")

    app = FastAPI(title="ClawOS Setup", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    service = get_service()

    def _origin_is_trusted(origin: str) -> bool:
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}

    def _require_setup_access(request: Request):
        if request.headers.get(SETUP_ACCESS_HEADER, "").strip() != SETUP_ACCESS_VALUE:
            raise HTTPException(status_code=401, detail="Setup access header required")
        if not _origin_is_trusted(request.headers.get("origin", "")):
            raise HTTPException(status_code=401, detail="Untrusted setup origin")

    @app.get("/health")
    async def health():
        return service.health()

    @app.get("/api/setup/state")
    async def state(request: Request):
        _require_setup_access(request)
        return service.to_dict()

    @app.get("/api/setup/personas")
    async def personas(request: Request):
        _require_setup_access(request)
        return service.list_personas()

    @app.post("/api/setup/inspect")
    async def inspect(request: Request):
        _require_setup_access(request)
        return service.inspect()

    @app.post("/api/setup/plan")
    async def plan(request: Request):
        _require_setup_access(request)
        return service.build_plan()

    @app.post("/api/setup/select-pack")
    async def select_pack(request: Request, body: dict | None = None):
        _require_setup_access(request)
        payload = body or {}
        pack_id = str(payload.get("pack_id", "")).strip()
        if not pack_id:
            raise HTTPException(status_code=400, detail="pack_id required")
        secondary = payload.get("secondary_packs")
        if secondary is not None and not isinstance(secondary, list):
            raise HTTPException(status_code=400, detail="secondary_packs must be a list")
        provider_profile = str(payload.get("provider_profile", "")).strip()
        try:
            return service.select_pack(
                pack_id,
                secondary_packs=secondary,
                provider_profile=provider_profile,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/presence")
    async def setup_presence(request: Request, body: dict | None = None):
        _require_setup_access(request)
        try:
            return service.update_presence(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/options")
    async def setup_options(request: Request, body: dict | None = None):
        _require_setup_access(request)
        try:
            return service.update_options(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/autonomy")
    async def setup_autonomy(request: Request, body: dict | None = None):
        _require_setup_access(request)
        try:
            return service.update_autonomy(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/install-milestone")
    async def setup_install_milestone(request: Request, body: dict | None = None):
        _require_setup_access(request)
        try:
            return service.record_install_milestone(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/import/openclaw")
    async def import_openclaw(request: Request, body: dict | None = None):
        _require_setup_access(request)
        source_path = str((body or {}).get("source_path", "")).strip()
        return service.import_openclaw(source_path)

    @app.post("/api/setup/model")
    async def prepare_model(request: Request, body: dict | None = None):
        _require_setup_access(request)
        try:
            return service.prepare_model(str((body or {}).get("model", "")).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/voice-test")
    async def voice_test(request: Request, body: dict | None = None):
        _require_setup_access(request)
        sample_text = str((body or {}).get("sample_text", "")).strip()
        return await service.run_voice_test(sample_text=sample_text)

    @app.post("/api/setup/voice-greet")
    async def voice_greet(request: Request, body: dict | None = None):
        _require_setup_access(request)
        line = str((body or {}).get("line", "")).strip()
        return await service.speak_greeting(line=line)

    @app.post("/api/setup/apply")
    async def apply(request: Request):
        _require_setup_access(request)
        return service.apply()

    @app.post("/api/setup/retry")
    async def retry(request: Request):
        _require_setup_access(request)
        return service.retry()

    @app.post("/api/setup/repair")
    async def repair(request: Request):
        _require_setup_access(request)
        return service.repair()

    @app.post("/api/setup/cancel")
    async def cancel(request: Request):
        _require_setup_access(request)
        return service.cancel()

    @app.get("/api/setup/logs")
    async def logs(request: Request):
        _require_setup_access(request)
        return {"logs": service.get_state().logs}

    @app.get("/api/setup/diagnostics")
    async def diagnostics(request: Request):
        _require_setup_access(request)
        return service.diagnostics()

    @app.get("/api/setup/frameworks")
    async def frameworks(request: Request):
        """List catalog frameworks enriched with tier compatibility.

        profile_id query param overrides the default (derived from detected hw).
        Falls back to empty list if the framework catalog is unavailable, so
        the FrameworkScreen degrades gracefully.
        """
        _require_setup_access(request)
        qp = request.query_params
        profile_id = str(qp.get("profile_id", "")).strip()
        if not profile_id:
            hw = service.get_state().detected_hardware or {}
            # Synthesize a best-effort profile_id from the detected hardware
            # so the endpoint still returns useful compatibility info when
            # hardware_probe.profile_id wasn't persisted to state.
            profile_id = str(hw.get("profile_id", "")).strip()
        try:
            from frameworks.registry import get_registry
            items = get_registry().list_for_tier(profile_id or "unknown")
        except Exception:
            items = []
        return {"profile_id": profile_id, "frameworks": items}

    # ── OpenClaw on-demand onboarding endpoints ───────────────────────────────

    @app.post("/api/setup/openclaw/install")
    async def openclaw_install(request: Request):
        """Install OpenClaw via frameworkd. Streams milestones via WebSocket."""
        _require_setup_access(request)
        import asyncio
        messages: list[str] = []

        def _do_install():
            from services.frameworkd.service import install_framework
            return install_framework("openclaw")

        result = await asyncio.to_thread(_do_install)
        service.record_install_milestone({"id": "openclaw-install",
                                          "label": result["message"],
                                          "status": "done" if result["ok"] else "error"})
        await service.broadcast()
        return {"ok": result["ok"], "message": result["message"]}

    @app.post("/api/setup/openclaw/configure")
    async def openclaw_configure(request: Request):
        """Write ~/.openclaw/openclaw.json with provider/model/workspace config."""
        _require_setup_access(request)
        import json as _json
        body = await request.json()
        provider = str(body.get("provider", "ollama_local"))
        model = str(body.get("model", "kimi-k2.5"))
        ollama_url = str(body.get("ollama_url", "http://127.0.0.1:11434"))
        api_key = str(body.get("api_key", ""))
        workspace_path = str(body.get("workspace_path", "")) or str(
            Path.home() / ".openclaw" / "workspace"
        )
        channels = body.get("channels", {})

        config_dir = Path.home() / ".openclaw"
        config_dir.mkdir(parents=True, exist_ok=True)
        Path(workspace_path).mkdir(parents=True, exist_ok=True)

        # Build provider section
        if provider == "ollama_cloud":
            provider_block = {
                "ollama": {
                    "baseUrl": "https://api.ollama.com",
                    "apiKey": api_key,
                    "models": [{"id": model, "name": model, "contextWindow": 262144}],
                }
            }
        elif provider == "ollama_local":
            provider_block = {
                "ollama": {
                    "baseUrl": ollama_url,
                    "models": [{"id": model, "name": model, "contextWindow": 32768},
                               {"id": "nomic-embed-text", "name": "nomic-embed-text", "contextWindow": 8192}],
                }
            }
        else:
            # anthropic / openai / openrouter
            provider_block = {
                provider: {"apiKey": api_key,
                           "models": [{"id": model, "name": model, "contextWindow": 200000}]}
            }

        cfg: dict = {
            "gateway": {"mode": "local", "port": int(body.get("port", 18789))},
            "workspace": {"path": workspace_path},
            "models": {"providers": provider_block},
            "agents": {"defaults": {"model": {"primary": f"{list(provider_block.keys())[0]}/{model}"},
                                    "memorySearch": {"enabled": False}}},
        }
        if channels:
            cfg["channels"] = channels

        config_path = config_dir / "openclaw.json"
        config_path.write_text(_json.dumps(cfg, indent=2), encoding="utf-8")
        config_path.chmod(0o600)
        return {"ok": True, "config_path": str(config_path)}

    @app.post("/api/setup/openclaw/start")
    async def openclaw_start(request: Request):
        """Start the OpenClaw gateway daemon."""
        _require_setup_access(request)
        import asyncio, shutil, subprocess, sys as _sys
        body = await request.json()
        port = int(body.get("port", 18789))
        autostart = bool(body.get("autostart", True))

        openclaw_bin = shutil.which("openclaw")
        if not openclaw_bin:
            return {"ok": False, "message": "openclaw binary not found — install first"}

        def _start():
            if _sys.platform == "darwin" and autostart:
                _write_launchd_plist(openclaw_bin, port)
            elif _sys.platform.startswith("linux") and autostart:
                _write_systemd_unit(openclaw_bin, port)
            # Start the gateway as a background process if not already running
            import urllib.request as _ur
            try:
                _ur.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2)
                return True, f"Gateway already running on port {port}"
            except Exception:
                pass
            subprocess.Popen(
                [openclaw_bin, "gateway", "--port", str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, f"Gateway started on port {port}"

        ok, msg = await asyncio.to_thread(_start)
        return {"ok": ok, "message": msg, "port": port}

    @app.get("/api/setup/openclaw/health")
    async def openclaw_health(request: Request):
        """Check if the OpenClaw gateway is responding on port 18789."""
        _require_setup_access(request)
        import urllib.request as _ur
        port = int(request.query_params.get("port", 18789))
        url = f"http://localhost:{port}"
        try:
            _ur.urlopen(f"{url}/healthz", timeout=3)
            running = True
        except Exception:
            running = False
        return {"running": running, "url": url, "port": port}

    @app.post("/api/setup/openclaw/skills")
    async def openclaw_skills(request: Request):
        """Install recommended OpenClaw skills."""
        _require_setup_access(request)
        import asyncio, shutil, subprocess

        openclaw_bin = shutil.which("openclaw")
        if not openclaw_bin:
            return {"ok": False, "message": "openclaw binary not found"}

        def _install_skills():
            try:
                result = subprocess.run(
                    [openclaw_bin, "skills", "install", "--recommended"],
                    capture_output=True, text=True, timeout=300,
                )
                installed = [
                    line.strip().lstrip("✓ ").strip()
                    for line in result.stdout.splitlines()
                    if "✓" in line or "installed" in line.lower()
                ]
                return result.returncode == 0, installed or ["recommended skills"]
            except Exception as exc:
                return False, [str(exc)]

        ok, installed = await asyncio.to_thread(_install_skills)
        service.record_install_milestone({"id": "openclaw-skills",
                                          "label": f"Skills installed: {', '.join(installed)}" if ok else "Skills install failed",
                                          "status": "done" if ok else "error"})
        await service.broadcast()
        return {"ok": ok, "installed": installed}

    @app.websocket("/ws/setup")
    async def setup_ws(websocket: WebSocket):
        if websocket.query_params.get("setup", "").strip() != SETUP_ACCESS_VALUE:
            await websocket.close(code=4401)
            return
        if not _origin_is_trusted(websocket.headers.get("origin", "")):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        service._listeners.add(websocket)
        try:
            await websocket.send_json({"type": "setup_state", "data": service.to_dict()})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            service._listeners.discard(websocket)
        except Exception:
            service._listeners.discard(websocket)

    return app


def run():
    if not FASTAPI_OK:
        raise RuntimeError("fastapi not installed")
    uvicorn.run(create_app(), host="127.0.0.1", port=PORT_SETUPD, log_level="warning")
