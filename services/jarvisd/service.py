# SPDX-License-Identifier: AGPL-3.0-or-later
"""JARVIS OpenClaw-backed chat and voice service."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from adapters.audio.elevenlabs_adapter import get_api_key
from adapters.audio.tts_router import active_provider, speak as tts_speak
from clawos_core.config.loader import get as cfg_get
from clawos_core.constants import CLAWOS_CONFIG, CONFIG_DIR, PIPER_MODEL, VOICE_DIR
from clawos_core.util.ids import entry_id
from clawos_core.util.time import now_iso
from openclaw_integration.responses_api import ensure_gateway_ready, gateway_health, request_response
from runtimes.voice.microphone import SAMPLE_RATE_HZ, available_recorder, default_device_label, record_utterance
from runtimes.voice.stt_client import transcribe

log = logging.getLogger("jarvisd")

JARVIS_STATE_JSON = CONFIG_DIR / "jarvis_state.json"
JARVIS_UI_THREAD = "jarvis-ui"
JARVIS_WORKSPACE = "jarvis_openclaw"
DEFAULT_JARVIS_VOICE_ID = "nPczCjzI2devNBz1zQrb"
TURN_LIMIT = 24

_BRIEFING_TRIGGERS = [
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\bwhat(?:'s| is)?\s*up\b",
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\b(?:good\s+)?morning\b",
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\bbrief(?:ing|\ me)?\b",
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\bwhat(?:'s|\ is)?\s+(?:my\s+)?day\b",
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\bcatch\s+me\s+up\b",
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\bwhat\s+do\s+i\s+have\b",
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\bwhat(?:'s|\ is)\s+going\s+on\b",
    r"(?:^|\b)(?:hey\s+jarvis|jarvis)\b.*\bgive\s+me\s+(?:my\s+)?(?:day|update|briefing)\b",
]

_AFFIRMATIVES = frozenset({
    "yes", "yeah", "yep", "sure", "go ahead", "let's do it", "lets do it",
    "ok", "okay", "do it", "yes please", "absolutely", "definitely", "yup",
})

WEATHER_CODES = {
    0: "clear and bright",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "misty",
    51: "light drizzle",
    53: "steady drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "passing showers",
    81: "showery",
    82: "intense showers",
    95: "stormy",
}


def _load_state() -> dict[str, Any]:
    if JARVIS_STATE_JSON.exists():
        try:
            return json.loads(JARVIS_STATE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"threads": {}, "shared_memory": {}}


def _save_state(state: dict[str, Any]) -> None:
    JARVIS_STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    JARVIS_STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _thread_state(thread_key: str, state: dict[str, Any]) -> dict[str, Any]:
    threads = state.setdefault("threads", {})
    thread = threads.setdefault(
        thread_key,
        {
            "thread_key": thread_key,
            "response_id": "",
            "mode": "push_to_talk",
            "state": "idle",
            "voice_enabled": True,
            "tts_provider": "elevenlabs",
            "openclaw_status": "unavailable",
            "last_utterance": "",
            "last_response": "",
            "live_caption": "",
            "recent_turns": [],
            "follow_up_open": False,
            "updated_at": now_iso(),
        },
    )
    thread.setdefault("recent_turns", [])
    return thread


def _write_nested(config: dict[str, Any], dotted_key: str, value: Any) -> None:
    current = config
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _load_user_config() -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - yaml is available in supported envs
        raise RuntimeError("PyYAML is required to update JARVIS config") from exc

    if not CLAWOS_CONFIG.exists():
        return {}
    with open(CLAWOS_CONFIG, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _save_user_config(config: dict[str, Any]) -> None:
    import yaml

    CLAWOS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(CLAWOS_CONFIG, "w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, default_flow_style=False, sort_keys=False)


def _current_config() -> dict[str, Any]:
    legacy_mode = str(cfg_get("voice.mode", "push_to_talk"))
    voice_enabled = bool(cfg_get("jarvis.voice.voice_enabled", legacy_mode != "off"))
    input_mode = str(cfg_get("jarvis.voice.input_mode", legacy_mode if legacy_mode in {"push_to_talk", "wake_word"} else "push_to_talk"))
    if input_mode not in {"push_to_talk", "wake_word"}:
        input_mode = "push_to_talk"
    provider_pref = str(cfg_get("jarvis.voice.tts_provider_preference", cfg_get("voice.tts_provider", "elevenlabs"))).strip().lower()
    if provider_pref not in {"elevenlabs", "piper"}:
        provider_pref = "elevenlabs"
    voice_id = str(cfg_get("jarvis.voice.elevenlabs_voice_id", cfg_get("voice.elevenlabs_voice_id", DEFAULT_JARVIS_VOICE_ID))).strip()
    wake_phrase = str(cfg_get("jarvis.voice.wake_phrase", "Hey Jarvis")).strip() or "Hey Jarvis"
    calendar_ics_url = str(cfg_get("jarvis.briefing.calendar_ics_url", "")).strip()
    return {
        "voice_enabled": voice_enabled,
        "input_mode": input_mode,
        "wake_phrase": wake_phrase,
        "tts_provider_preference": provider_pref,
        "elevenlabs_voice_id": voice_id or DEFAULT_JARVIS_VOICE_ID,
        "elevenlabs_key_set": bool(get_api_key()),
        "calendar_ics_url": calendar_ics_url,
    }


class JarvisService:
    def __init__(self):
        self.stt_model = str(cfg_get("voice.stt_model", "base"))
        self.sample_rate_hz = int(cfg_get("voice.record_rate", SAMPLE_RATE_HZ))
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session_listeners: list[Callable[[dict[str, Any]], Awaitable[None] | None]] = []

    def add_session_listener(self, listener: Callable[[dict[str, Any]], Awaitable[None] | None]) -> None:
        if listener not in self._session_listeners:
            self._session_listeners.append(listener)

    def remove_session_listener(self, listener: Callable[[dict[str, Any]], Awaitable[None] | None]) -> None:
        if listener in self._session_listeners:
            self._session_listeners.remove(listener)

    def _notify_session(self, session: dict[str, Any]) -> None:
        if not self._session_listeners:
            return
        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        for listener in list(self._session_listeners):
            try:
                result = listener(dict(session))
                if asyncio.iscoroutine(result):
                    loop.create_task(result)
            except Exception:
                continue

    def _ensure_loop(self) -> None:
        if self._loop is not None:
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def _stt_available(self) -> bool:
        try:
            import whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def _playback_backend(self) -> str:
        for candidate in ("aplay", "ffplay"):
            if shutil.which(candidate):
                return candidate
        return ""

    def _wake_word_available(self) -> bool:
        wake_model = Path(__file__).parent.parent / "voiced" / "models" / "hey_jarvis.onnx"
        if not wake_model.exists():
            return False
        try:
            import openwakeword  # noqa: F401

            return True
        except ImportError:
            return False

    def _briefing_sources(self, state: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
        state = state or _load_state()
        shared = state.setdefault("shared_memory", {})
        source_status: dict[str, str] = {}
        payload: dict[str, Any] = {}

        weather = self._weather_snapshot()
        source_status["weather"] = weather["status"]
        payload["weather"] = weather["text"]

        headlines = self._headline_snapshot()
        source_status["headlines"] = headlines["status"]
        payload["headlines"] = headlines["items"]

        calendar = self._calendar_snapshot()
        source_status["calendar"] = calendar["status"]
        payload["calendar"] = calendar["items"]

        tasks = self._task_snapshot()
        source_status["tasks"] = tasks["status"]
        payload["tasks"] = tasks["items"]

        project = self._project_snapshot(shared)
        source_status["last_project"] = project["status"]
        payload["last_project"] = project["text"]

        return payload, source_status

    def health(self) -> dict[str, Any]:
        config = _current_config()
        openclaw = gateway_health()
        provider = active_provider(config["tts_provider_preference"])
        provider_status = {
            "preferred": config["tts_provider_preference"],
            "active": provider,
            "fallback": config["tts_provider_preference"] == "elevenlabs" and provider != "elevenlabs",
            "elevenlabs_key_set": config["elevenlabs_key_set"],
        }
        _, briefing_sources = self._briefing_sources()
        return {
            "openclaw_installed": bool(openclaw["installed"]),
            "openclaw_running": bool(openclaw["running"]),
            "gateway_port": int(openclaw["gateway_port"]),
            "gateway_url": openclaw["gateway_url"],
            "stt_ok": self._stt_available(),
            "tts_ok": bool(self._playback_backend()) and (provider == "elevenlabs" or shutil.which("piper") is not None or PIPER_MODEL.exists()),
            "wake_word_ok": self._wake_word_available(),
            "microphone_ok": bool(available_recorder()),
            "microphone_backend": available_recorder(),
            "playback_backend": self._playback_backend(),
            "device_label": default_device_label(),
            "sample_rate_hz": self.sample_rate_hz,
            "provider_status": provider_status,
            "briefing_sources": briefing_sources,
            "config_path": openclaw["config_path"],
        }

    def config(self) -> dict[str, Any]:
        return dict(_current_config())

    def set_config(self, updates: dict[str, Any] | None = None) -> dict[str, Any]:
        updates = updates or {}
        config = _load_user_config()

        voice_enabled = updates.get("voice_enabled")
        if isinstance(voice_enabled, bool):
            _write_nested(config, "jarvis.voice.voice_enabled", voice_enabled)

        input_mode = str(updates.get("input_mode", "")).strip()
        if input_mode in {"push_to_talk", "wake_word"}:
            _write_nested(config, "jarvis.voice.input_mode", input_mode)

        wake_phrase = str(updates.get("wake_phrase", "")).strip()
        if wake_phrase:
            _write_nested(config, "jarvis.voice.wake_phrase", wake_phrase)

        provider_pref = str(updates.get("tts_provider_preference", "")).strip().lower()
        if provider_pref in {"elevenlabs", "piper"}:
            _write_nested(config, "jarvis.voice.tts_provider_preference", provider_pref)

        voice_id = str(updates.get("elevenlabs_voice_id", "")).strip()
        if voice_id:
            _write_nested(config, "jarvis.voice.elevenlabs_voice_id", voice_id)

        api_key = str(updates.get("elevenlabs_api_key", "")).strip()
        if api_key:
            try:
                from services.secretd.service import get_store

                get_store().set("elevenlabs_api_key", api_key)
            except Exception:
                pass
            os.environ["ELEVENLABS_API_KEY"] = api_key

        calendar_ics_url = str(updates.get("calendar_ics_url", "")).strip()
        if calendar_ics_url is not None and "calendar_ics_url" in updates:
            _write_nested(config, "jarvis.briefing.calendar_ics_url", calendar_ics_url)

        _save_user_config(config)
        session = self.session()
        self._notify_session(session)
        return self.config()

    def _openclaw_status(self) -> str:
        health = self.health()
        if health["openclaw_running"]:
            return "running"
        if health["openclaw_installed"]:
            return "available"
        return "unavailable"

    def session(self, thread_key: str = JARVIS_UI_THREAD) -> dict[str, Any]:
        config = self.config()
        state = _load_state()
        thread = _thread_state(thread_key, state)
        thread["mode"] = config["input_mode"] if config["voice_enabled"] else "off"
        thread["voice_enabled"] = config["voice_enabled"]
        thread["tts_provider"] = active_provider(config["tts_provider_preference"])
        thread["openclaw_status"] = self._openclaw_status()
        thread["updated_at"] = thread.get("updated_at") or now_iso()
        return dict(thread)

    def _update_thread(self, thread_key: str, **updates: Any) -> dict[str, Any]:
        state = _load_state()
        thread = _thread_state(thread_key, state)
        for key, value in updates.items():
            if value is not None:
                thread[key] = value
        thread["updated_at"] = now_iso()
        _save_state(state)
        session = self.session(thread_key)
        self._notify_session(session)
        return session

    def _append_turn(self, thread_key: str, *, role: str, text: str, source: str, spoken: bool) -> None:
        state = _load_state()
        thread = _thread_state(thread_key, state)
        turn = {
            "id": entry_id(),
            "role": role,
            "text": text,
            "source": source,
            "spoken": spoken,
            "created_at": now_iso(),
        }
        thread["recent_turns"] = (thread.get("recent_turns") or []) + [turn]
        thread["recent_turns"] = thread["recent_turns"][-TURN_LIMIT:]
        thread["updated_at"] = now_iso()
        _save_state(state)
        self._notify_session(self.session(thread_key))

    def _remember_context(self, thread_key: str, user_text: str, assistant_text: str) -> None:
        state = _load_state()
        shared = state.setdefault("shared_memory", {})
        shared["last_thread_key"] = thread_key
        shared["last_topic"] = user_text[:200]
        shared["last_response"] = assistant_text[:240]
        project_match = re.search(r"(?:project|working on)\s+([A-Za-z0-9][A-Za-z0-9 _-]{2,60})", user_text, flags=re.IGNORECASE)
        if project_match:
            project_name = project_match.group(1).strip(" .")
            project_name = re.sub(r"^project\s+", "", project_name, flags=re.IGNORECASE)
            shared["last_project"] = project_name
        shared["updated_at"] = now_iso()
        _save_state(state)

    def _weather_snapshot(self) -> dict[str, Any]:
        latitude = cfg_get("jarvis.briefing.latitude")
        longitude = cfg_get("jarvis.briefing.longitude")
        timezone = str(cfg_get("jarvis.briefing.timezone", "auto"))
        location = str(cfg_get("jarvis.briefing.location_label", "your area"))
        if latitude is None or longitude is None:
            return {"status": "demo", "text": "It's bright and sunny at 22°C with a light breeze."}
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast?"
                + urllib.parse.urlencode(
                    {
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,weather_code",
                        "timezone": timezone,
                    }
                )
            )
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            current = payload.get("current") or {}
            temp = current.get("temperature_2m")
            code = int(current.get("weather_code", 0))
            condition = WEATHER_CODES.get(code, "settled")
            return {"status": "live", "text": f"In {location}, it's {condition} at {temp}°C."}
        except Exception:
            return {"status": "demo", "text": "It's bright and sunny at 22°C with a light breeze."}

    def _headline_snapshot(self) -> dict[str, Any]:
        brave_key = os.environ.get("BRAVE_API_KEY", "").strip()
        if not brave_key:
            try:
                from services.secretd.service import get_store

                brave_key = get_store().get("brave_api_key") or ""
            except Exception:
                brave_key = ""
        if not brave_key:
            return {
                "status": "demo",
                "items": [
                    "AI tooling is dominating the product and developer headlines.",
                    "Local-first assistants are drawing heavy interest from teams shipping on-device UX.",
                    "Secure agent workflows and human approvals remain a big theme across enterprise launches.",
                ],
            }
        try:
            req = urllib.request.Request(
                "https://api.search.brave.com/res/v1/news/search?q=top%20technology%20headlines&count=3",
                headers={"X-Subscription-Token": brave_key, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            results = payload.get("results") or payload.get("news", {}).get("results") or []
            titles = [str(item.get("title", "")).strip() for item in results if str(item.get("title", "")).strip()]
            if titles:
                return {"status": "live", "items": titles[:3]}
        except Exception:
            pass
        return {
            "status": "demo",
            "items": [
                "AI tooling is dominating the product and developer headlines.",
                "Local-first assistants are drawing heavy interest from teams shipping on-device UX.",
                "Secure agent workflows and human approvals remain a big theme across enterprise launches.",
            ],
        }

    def _calendar_snapshot(self) -> dict[str, Any]:
        ics_url = str(cfg_get("jarvis.briefing.calendar_ics_url", "")).strip()
        if not ics_url:
            return {"status": "demo", "items": ["a product meeting at 3 PM", "a webinar at 7 PM"]}
        try:
            import icalendar  # type: ignore[import]
            from datetime import date, datetime, timezone

            with urllib.request.urlopen(ics_url, timeout=10) as resp:  # noqa: S310
                cal = icalendar.Calendar.from_ical(resp.read())
            today = date.today()
            events: list[tuple[int, str]] = []
            for component in cal.walk():
                if component.name != "VEVENT":
                    continue
                dtstart = component.get("dtstart")
                if not dtstart:
                    continue
                dt = dtstart.dt
                # Handle all-day events (date) and timed events (datetime)
                event_date = dt if isinstance(dt, date) and not isinstance(dt, datetime) else getattr(dt, "date", lambda: today)()
                if event_date != today:
                    continue
                summary = str(component.get("summary", "")).strip()
                if not summary:
                    continue
                if isinstance(dt, datetime):
                    local_dt = dt.astimezone() if dt.tzinfo else dt
                    h = local_dt.hour % 12 or 12
                    period = "AM" if local_dt.hour < 12 else "PM"
                    time_str = f"{h}:{local_dt.minute:02d} {period}"
                    events.append((local_dt.hour * 60 + local_dt.minute, f"{summary} at {time_str}"))
                else:
                    events.append((0, summary))
            events.sort(key=lambda x: x[0])
            items = [label for _, label in events[:5]]
            if items:
                return {"status": "live", "items": items}
        except Exception as exc:
            log.debug("Calendar ICS fetch failed: %s", exc)
        return {"status": "demo", "items": ["a product meeting at 3 PM", "a webinar at 7 PM"]}

    def _task_snapshot(self) -> dict[str, Any]:
        try:
            from clawos_core.presence import list_missions

            missions = [item for item in list_missions() if str(item.get("status", "")).strip() in {"active", "idle"}]
            if missions:
                items = [str(item.get("title", "")).strip() for item in missions[:3] if str(item.get("title", "")).strip()]
                if items:
                    return {"status": "live", "items": items}
        except Exception:
            pass
        return {"status": "demo", "items": ["keep the JARVIS room moving", "finish the OpenClaw bridge", "tighten the demo script"]}

    def _project_snapshot(self, shared_memory: dict[str, Any]) -> dict[str, Any]:
        project = str(shared_memory.get("last_project", "")).strip()
        if project:
            return {"status": "live", "text": project}
        return {"status": "demo", "text": "the JARVIS voice room and OpenClaw bridge"}

    def _looks_like_briefing_request(self, message: str) -> bool:
        normalized = " ".join(message.lower().split())
        return any(re.search(pattern, normalized) for pattern in _BRIEFING_TRIGGERS)

    def _looks_like_standalone_greeting(self, message: str) -> bool:
        normalized = " ".join(message.lower().split())
        return bool(re.match(r"^(?:hey\s+jarvis|jarvis|hi\s+jarvis|hello\s+jarvis)\s*[.!?]?$", normalized))

    def _is_affirmative(self, message: str) -> bool:
        return message.lower().strip(".!? ") in _AFFIRMATIVES

    def _format_briefing_text(self, context: dict[str, Any]) -> str:
        headlines = context["headlines"]
        headline_line = ", ".join(headlines[:2]) if headlines else "the usual industry churn"
        calendar_line = ", and ".join(context["calendar"]) if context["calendar"] else "a light schedule"
        task_line = ", ".join(context["tasks"][:2]) if context["tasks"] else "a focused day"
        project_line = context["last_project"]
        return (
            f"Hello Sir. {context['weather']} The headlines are covering {headline_line}. "
            f"On your schedule today, you have {calendar_line}. I'm also tracking {task_line}. "
            f"Last time we were working on {project_line}. Want to pick it back up?"
        )

    async def _briefing_reply(self, thread_key: str, source: str) -> tuple[str, dict[str, str]]:
        context, source_status = self._briefing_sources()
        health = self.health()
        if health["openclaw_running"]:
            prompt = (
                "You are JARVIS. Deliver a spoken daily briefing in a warm, cinematic tone. "
                "Use the provided context directly, do not invent any missing data, and close by offering to resume the last project.\n\n"
                f"Weather: {context['weather']}\n"
                f"Headlines: {json.dumps(context['headlines'])}\n"
                f"Calendar: {json.dumps(context['calendar'])}\n"
                f"Tasks: {json.dumps(context['tasks'])}\n"
                f"Last project: {context['last_project']}\n"
            )
            try:
                result = await asyncio.to_thread(
                    request_response,
                    prompt,
                    session_key=thread_key,
                    channel=source,
                )
                text = str(result.get("text", "")).strip()
                if text:
                    return text, source_status
            except Exception as exc:
                log.warning("OpenClaw briefing generation failed, using local formatter: %s", exc)
        return self._format_briefing_text(context), source_status

    async def listen(self, thread_key: str, duration_s: float = 4.0) -> str:
        self._ensure_loop()
        if not self._stt_available():
            self._update_thread(thread_key, state="idle", follow_up_open=False)
            return ""
        self._update_thread(thread_key, state="listening", live_caption="Listening...", follow_up_open=True)
        try:
            audio_path = await asyncio.to_thread(record_utterance, duration_s, self.sample_rate_hz)
            self._update_thread(thread_key, state="thinking", live_caption="Transcribing...")
            transcript = await asyncio.to_thread(transcribe, audio_path, self.stt_model)
            self._update_thread(
                thread_key,
                state="idle",
                follow_up_open=False,
                last_utterance=transcript or "",
                live_caption=transcript or "",
            )
            return transcript
        except Exception as exc:
            log.error("JARVIS STT error: %s", exc)
            self._update_thread(thread_key, state="idle", follow_up_open=False, live_caption="")
            return ""

    async def speak(self, text: str) -> bool:
        config = self.config()
        if not text or not config["voice_enabled"]:
            return False
        playback_backend = self._playback_backend()
        if not playback_backend:
            return False
        try:
            audio = await asyncio.to_thread(
                tts_speak,
                text,
                provider_preference=config["tts_provider_preference"],
                voice_id=config["elevenlabs_voice_id"],
            )
            if not audio:
                return False
            provider = active_provider(config["tts_provider_preference"])
            is_mp3 = provider == "elevenlabs" or audio[:3] == b"ID3" or audio[:2] == b"\xff\xfb"
            if is_mp3:
                play = await asyncio.to_thread(
                    subprocess.run,
                    ["ffplay", "-autoexit", "-nodisp", "-loglevel", "quiet", "-"],
                    input=audio,
                    capture_output=True,
                )
            elif playback_backend == "aplay":
                play = await asyncio.to_thread(
                    subprocess.run,
                    ["aplay", "-q", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
                    input=audio,
                    capture_output=True,
                )
            else:
                play = await asyncio.to_thread(
                    subprocess.run,
                    ["ffplay", "-autoexit", "-nodisp", "-loglevel", "quiet", "-f", "s16le", "-ar", "22050", "-ac", "1", "-"],
                    input=audio,
                    capture_output=True,
                )
            return play.returncode == 0
        except Exception as exc:
            log.error("JARVIS TTS error: %s", exc)
            return False

    async def chat(
        self,
        message: str,
        *,
        thread_key: str = JARVIS_UI_THREAD,
        source: str = "jarvis-ui",
        speak_reply: bool | None = None,
    ) -> dict[str, Any]:
        self._ensure_loop()
        text = str(message or "").strip()
        if not text:
            raise ValueError("message required")

        self._append_turn(thread_key, role="user", text=text, source=source, spoken=False)
        self._update_thread(thread_key, state="thinking", last_utterance=text, live_caption=text, follow_up_open=False)

        # Standalone greeting — no OpenClaw needed, just confirm presence
        if self._looks_like_standalone_greeting(text):
            reply = "Good morning, Sir. I'm online and ready. Say 'what's up' for your full briefing, or ask me anything."
            source_status: dict[str, str] = {}
        else:
            health = self.health()
            if not health["openclaw_installed"] or not health["openclaw_running"]:
                raise RuntimeError("OpenClaw is unavailable for JARVIS right now")

            # Check if user is responding to the project continuation prompt
            state = _load_state()
            shared = state.setdefault("shared_memory", {})
            if self._is_affirmative(text) and shared.get("awaiting_project_continue"):
                project = str(shared.get("last_project", "")).strip()
                shared["awaiting_project_continue"] = False
                _save_state(state)
                if project:
                    text = f"Resume the project: {project}. Pick up where we left off. Acknowledge briefly and ask where to start."

            if self._looks_like_briefing_request(text):
                reply, source_status = await self._briefing_reply(thread_key, source)
                # Mark that we offered project continuation — next "yes" will resume it
                state2 = _load_state()
                state2.setdefault("shared_memory", {})["awaiting_project_continue"] = True
                _save_state(state2)
            else:
                state = _load_state()
                thread = _thread_state(thread_key, state)
                result = await asyncio.to_thread(
                    request_response,
                    text,
                    session_key=thread_key,
                    channel=source,
                    previous_response_id=str(thread.get("response_id", "")),
                )
                reply = str(result.get("text", "")).strip() or "I'm online, but that reply came back empty."
                source_status = self.health()["briefing_sources"]
                self._update_thread(thread_key, response_id=str(result.get("response_id", "")).strip() or thread.get("response_id", ""))

        should_speak = self.config()["voice_enabled"] if speak_reply is None else bool(speak_reply)
        self._update_thread(thread_key, state="speaking" if should_speak else "idle", last_response=reply, live_caption=reply)
        spoken = await self.speak(reply) if should_speak else False
        self._append_turn(thread_key, role="assistant", text=reply, source=source, spoken=spoken)
        self._remember_context(thread_key, text, reply)
        session = self._update_thread(thread_key, state="idle", follow_up_open=False, last_response=reply, live_caption=reply)
        return {"reply": reply, "spoken": spoken, "session": session, "briefing_sources": source_status}

    async def push_to_talk(self, thread_key: str = JARVIS_UI_THREAD) -> dict[str, Any]:
        config = self.config()
        if not config["voice_enabled"]:
            return {
                "ok": False,
                "trigger": "push_to_talk",
                "transcript": "",
                "reply": "",
                "spoken": False,
                "error": "JARVIS voice output is off",
                "session": self.session(thread_key),
            }
        transcript = await self.listen(thread_key, duration_s=4.0)
        if not transcript.strip():
            return {
                "ok": False,
                "trigger": "push_to_talk",
                "transcript": "",
                "reply": "",
                "spoken": False,
                "issues": ["No speech detected"],
                "session": self.session(thread_key),
            }
        result = await self.chat(transcript, thread_key=thread_key, source="jarvis-ui:voice")
        return {
            "ok": True,
            "trigger": "push_to_talk",
            "transcript": transcript,
            "reply": result["reply"],
            "spoken": result["spoken"],
            "session": result["session"],
        }

    async def speak_morning_briefing(self, workspace_id: str | None = None) -> dict[str, Any]:
        """
        AIPass pattern: speak a 2-sentence morning briefing on session start.
        Reads last session state + pending queue from memd.
        Only fires if voice is enabled and there's meaningful content.
        """
        try:
            from services.memd.service import MemoryService
            from clawos_core.constants import DEFAULT_WORKSPACE
            ws = workspace_id or DEFAULT_WORKSPACE
            mem = MemoryService()
            state = mem.load_session_state(ws)
            pending = mem.get_pending_queue(ws)
        except Exception:
            return {"ok": False, "spoken": False, "reason": "memd unavailable"}

        if not state and not pending:
            return {"ok": False, "spoken": False, "reason": "no session state"}

        # Build 2-sentence briefing
        last_work = state.get("last_work", "")
        ended_at = state.get("ended_at", "")
        parts: list[str] = []
        if last_work:
            parts.append(f"Welcome back. Last session you were working on: {last_work}.")
        if pending:
            pending_str = ", ".join(pending[:2])
            parts.append(f"You have {len(pending)} pending task{'s' if len(pending) > 1 else ''}: {pending_str}.")
        elif not parts:
            return {"ok": False, "spoken": False, "reason": "nothing to brief"}

        briefing_text = " ".join(parts[:2])
        config = self.config()
        spoken = False
        if config.get("voice_enabled"):
            try:
                spoken = await self.speak(briefing_text)
            except Exception:
                pass
        self._update_thread(JARVIS_UI_THREAD, last_response=briefing_text, live_caption=briefing_text)
        return {"ok": True, "spoken": spoken, "briefing": briefing_text}

    async def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in {"off", "push_to_talk", "wake_word"}:
            raise ValueError(f"Unsupported JARVIS mode: {mode}")
        updates = {
            "voice_enabled": mode != "off",
            "input_mode": "push_to_talk" if mode == "off" else mode,
        }
        self.set_config(updates)
        return self._update_thread(
            JARVIS_UI_THREAD,
            mode=mode,
            voice_enabled=mode != "off",
            state="idle",
            follow_up_open=False,
        )


_svc: JarvisService | None = None


def get_service() -> JarvisService:
    global _svc
    if _svc is None:
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        _svc = JarvisService()
    return _svc
