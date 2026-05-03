# SPDX-License-Identifier: AGPL-3.0-or-later
"""ClawOS voiced: local voice pipeline supervision and testing."""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from clawos_core.config.loader import get
from clawos_core.constants import PIPER_MODEL, VOICE_DIR
from clawos_core.presence import get_voice_session, set_voice_mode, update_voice_session
from runtimes.voice.microphone import SAMPLE_RATE_HZ, available_recorder, default_device_label, record_utterance
from runtimes.voice.stt_client import transcribe

log = logging.getLogger("voiced")


class VoiceService:
    def __init__(self):
        self.stt_model = str(get("voice.stt_model", "base"))
        self.sample_rate_hz = int(get("voice.record_rate", SAMPLE_RATE_HZ))
        self.default_mode = str(get("voice.mode", "push_to_talk"))
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake_detector = None
        self._tray = None
        self._session_listeners: list[Callable[[dict[str, Any]], Awaitable[None] | None]] = []

    def _session(self) -> dict[str, Any]:
        session = get_voice_session()
        if not session.get("mode"):
            return set_voice_mode(self.default_mode)
        return session

    def _microphone_backend(self) -> str:
        return available_recorder()

    def _playback_backend(self) -> str:
        for candidate in ("aplay", "ffplay"):
            if shutil.which(candidate):
                return candidate
        return ""

    def _stt_available(self) -> bool:
        try:
            import whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def _wake_word_available(self) -> bool:
        wake_model = Path(__file__).parent / "models" / "hey_jarvis.onnx"
        if not wake_model.exists():
            return False
        try:
            import openwakeword  # noqa: F401

            return True
        except ImportError:
            return False

    def _device_label(self) -> str:
        session = self._session()
        return str(session.get("device_label") or default_device_label())

    def _sync_session(self, **updates: Any) -> dict[str, Any]:
        session = update_voice_session(
            {
                "device_label": self._device_label(),
                **updates,
            }
        )
        self._notify_session(session)
        return session

    def add_session_listener(self, listener: Callable[[dict[str, Any]], Awaitable[None] | None]):
        if listener not in self._session_listeners:
            self._session_listeners.append(listener)

    def remove_session_listener(self, listener: Callable[[dict[str, Any]], Awaitable[None] | None]):
        if listener in self._session_listeners:
            self._session_listeners.remove(listener)

    def _notify_session(self, session: dict[str, Any]):
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
            except (RuntimeError, TypeError, AttributeError):
                continue

    def _ensure_runtime(self):
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = None
        self._ensure_tray()

    def session(self) -> dict[str, Any]:
        return self._session()

    def health(self) -> dict[str, Any]:
        session = self._session()
        microphone_backend = self._microphone_backend()
        playback_backend = self._playback_backend()
        mode = str(session.get("mode", self.default_mode))
        enabled = mode != "off"
        stt_ok = self._stt_available()
        tts_ok = shutil.which("piper") is not None and PIPER_MODEL.exists() and bool(playback_backend)
        wake_word_ok = self._wake_word_available()
        degraded = enabled and (not microphone_backend or not stt_ok or (mode == "wake_word" and not wake_word_ok))
        return {
            "status": "degraded" if degraded else ("running" if self._running else "ok"),
            "enabled": enabled,
            "mode": mode,
            "state": session.get("state", "idle"),
            "running": self._running,
            "stt_ok": stt_ok,
            "tts_ok": tts_ok,
            "wake_word_ok": wake_word_ok,
            "microphone_ok": bool(microphone_backend),
            "microphone_backend": microphone_backend,
            "playback_backend": playback_backend,
            "device_label": self._device_label(),
            "sample_rate_hz": self.sample_rate_hz,
            "follow_up_open": bool(session.get("follow_up_open", False)),
        }

    def _stop_wake_detector(self):
        if self._wake_detector:
            try:
                self._wake_detector.stop()
            except (OSError, RuntimeError, AttributeError) as e:
                log.debug(f"suppressed: {e}")
            self._wake_detector = None

    def _ensure_tray(self):
        if self._tray is not None:
            return
        try:
            from services.voiced.tray import VoiceTray

            self._tray = VoiceTray()
            self._tray.start()
        except (ImportError, OSError):
            self._tray = None

    def _set_tray_state(self, state: str):
        if not self._tray:
            return
        try:
            from services.voiced.tray import VoiceState

            mapping = {
                "idle": VoiceState.SLEEPING,
                "sleeping": VoiceState.SLEEPING,
                "listening": VoiceState.LISTENING,
                "thinking": VoiceState.THINKING,
                "speaking": VoiceState.SPEAKING,
            }
            self._tray.set_state(mapping.get(state, VoiceState.SLEEPING))
        except (ImportError, AttributeError, KeyError):
            return

    async def start(self):
        session = self._session()
        self._loop = asyncio.get_running_loop()
        self._ensure_runtime()
        self._running = session.get("mode", self.default_mode) != "off"
        self._sync_session(state="idle", device_label=self._device_label())
        self._set_tray_state("idle")
        if session.get("mode") == "wake_word":
            self._start_wake_detector()
        log.info("voiced started mode=%s", session.get("mode", self.default_mode))

    async def stop(self):
        self._stop_wake_detector()
        self._running = False
        self._sync_session(state="idle", follow_up_open=False)
        self._set_tray_state("idle")

    def _start_wake_detector(self):
        self._stop_wake_detector()
        if not self._wake_word_available():
            return False
        try:
            from services.voiced.wake import WakeWordDetector

            self._wake_detector = WakeWordDetector(self._on_wake_word)
            return bool(self._wake_detector.start())
        except (ImportError, OSError, RuntimeError) as exc:
            log.warning("Wake detector unavailable: %s", exc)
            self._wake_detector = None
            return False

    def _on_wake_word(self):
        if not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self._handle_voice_roundtrip(trigger="wake_word"), self._loop)

    async def set_mode(self, mode: str) -> dict[str, Any]:
        self._ensure_runtime()
        session = set_voice_mode(mode)
        self._notify_session(session)
        if mode == "off":
            await self.stop()
            return session
        self._running = True
        self._sync_session(mode=mode, state="idle", follow_up_open=False)
        if mode == "wake_word":
            self._start_wake_detector()
        else:
            self._stop_wake_detector()
        return self.session()

    async def speak(self, text: str) -> bool:
        if not text:
            return False
        self._ensure_runtime()
        playback_backend = self._playback_backend()
        if not playback_backend:
            return False
        try:
            self._sync_session(state="speaking", last_response=text)
            self._set_tray_state("speaking")

            # Route through TTSRouter (handles ElevenLabs → Piper fallback)
            try:
                from adapters.audio.tts_router import speak as tts_speak, active_provider
                provider = active_provider()
                audio = await asyncio.to_thread(tts_speak, text)
            except (OSError, RuntimeError, ImportError) as tts_exc:
                log.warning("TTSRouter unavailable, falling back to Piper directly: %s", tts_exc)
                audio = b""
                provider = "piper"

            # Direct Piper fallback if TTSRouter returned nothing
            if not audio:
                if shutil.which("piper") is None or not PIPER_MODEL.exists():
                    return False
                proc = subprocess.Popen(
                    ["piper", "--model", str(PIPER_MODEL), "--output-raw"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                audio, _ = await asyncio.to_thread(proc.communicate, text.encode("utf-8"), 20)
                provider = "piper"

            if not audio:
                return False

            # Playback — ElevenLabs returns MP3, Piper returns raw PCM
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
        except (OSError, subprocess.SubprocessError) as exc:
            log.error("TTS error: %s", exc)
            return False
        finally:
            self._sync_session(state="idle", follow_up_open=False)
            self._set_tray_state("idle")

    async def listen(self, duration_s: float = 3.0) -> str:
        if not self._stt_available():
            return ""
        self._ensure_runtime()
        self._sync_session(state="listening", follow_up_open=True)
        self._set_tray_state("listening")
        try:
            audio_path = await asyncio.to_thread(record_utterance, duration_s, self.sample_rate_hz)
            self._sync_session(state="thinking")
            self._set_tray_state("thinking")
            transcript = await asyncio.to_thread(transcribe, audio_path, self.stt_model)
            self._sync_session(last_utterance=transcript or "", state="idle", follow_up_open=False)
            return transcript
        except (OSError, RuntimeError, TimeoutError) as exc:
            log.error("STT error: %s", exc)
            self._sync_session(state="idle", follow_up_open=False)
            return ""
        finally:
            self._set_tray_state("idle")

    async def test_microphone(self, duration_s: float = 3.0) -> dict[str, Any]:
        self._ensure_runtime()
        health = self.health()
        issues: list[str] = []
        if not health["microphone_ok"]:
            issues.append("No supported local microphone recorder was found")
        if not health["stt_ok"]:
            issues.append("Whisper is not installed")
        transcript = ""
        if not issues:
            transcript = await self.listen(duration_s=duration_s)
            if not transcript:
                issues.append("No speech was detected in the microphone test")
        return {
            "kind": "microphone",
            "ok": not issues and bool(transcript),
            "mode": self.session().get("mode", self.default_mode),
            "state": "passed" if not issues and transcript else "failed",
            "device_label": health["device_label"],
            "sample_rate_hz": self.sample_rate_hz,
            "microphone_backend": health["microphone_backend"],
            "transcript": transcript,
            "issues": issues,
        }

    async def test_pipeline(self, sample_text: str = "Voice pipeline ready.", duration_s: float = 3.0) -> dict[str, Any]:
        self._ensure_runtime()
        microphone = await self.test_microphone(duration_s=duration_s)
        playback_ok = False
        issues = list(microphone.get("issues") or [])
        if not issues:
            playback_ok = await self.speak(sample_text)
            if not playback_ok:
                issues.append("Piper playback is unavailable")
        return {
            **microphone,
            "kind": "pipeline",
            "ok": microphone.get("ok", False) and playback_ok,
            "state": "passed" if microphone.get("ok", False) and playback_ok else "failed",
            "playback_ok": playback_ok,
            "sample_text": sample_text,
            "issues": issues,
        }

    async def test_wake_word(self) -> dict[str, Any]:
        self._ensure_runtime()
        issues: list[str] = []
        keep_running = self.session().get("mode") == "wake_word"
        armed = self._wake_detector is not None
        if not self._wake_word_available():
            issues.append('Wake word runtime is unavailable for "Hey Claw"')
        elif not armed:
            armed = self._start_wake_detector()
            if not armed:
                issues.append("Wake word detector could not be armed")
        if armed and not keep_running:
            self._stop_wake_detector()
        return {
            "kind": "wake_word",
            "ok": not issues and armed,
            "state": "passed" if not issues and armed else "failed",
            "mode": self.session().get("mode", self.default_mode),
            "wake_word_ok": self._wake_word_available(),
            "armed": armed,
            "wake_word_phrase": "Hey Claw",
            "issues": issues,
        }

    async def push_to_talk(self) -> dict[str, Any]:
        self._ensure_runtime()
        if self.session().get("mode") == "off":
            return {
                "ok": False,
                "trigger": "push_to_talk",
                "transcript": "",
                "response": "",
                "playback_ok": False,
                "error": "Voice mode is off",
                "session": self.session(),
            }
        return await self._handle_voice_roundtrip(trigger="push_to_talk")

    async def _handle_voice_roundtrip(self, trigger: str) -> dict[str, Any]:
        self._ensure_runtime()
        transcript = await self.listen(duration_s=4.0)
        if transcript and transcript.strip():
            try:
                from services.agentd.service import get_manager
                self._sync_session(state="thinking")
                response = await get_manager().chat_direct(transcript.strip(), channel="voice")
            except (OSError, RuntimeError) as exc:
                log.warning("Voice agent call failed: %s", exc)
                response = "Sorry, I couldn't process that request."
        else:
            response = ""
        playback_ok = await self.speak(response) if response else False
        return {
            "ok": bool(transcript),
            "trigger": trigger,
            "transcript": transcript,
            "response": response,
            "playback_ok": playback_ok,
            "session": self.session(),
        }


_svc = None


def get_service() -> VoiceService:
    global _svc
    if _svc is None:
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        _svc = VoiceService()
    return _svc


TALK_MODE_TIMEOUT = 10


async def run_voice_session(agent, stt_fn, tts_fn, tray=None):
    """Handle a wake-word-triggered voice conversation session."""
    from services.voiced.tray import VoiceState

    async def _think(text):
        if tray:
            tray.set_state(VoiceState.THINKING)
        try:
            reply = await agent.chat(text)
        except (OSError, RuntimeError, ConnectionError) as exc:
            reply = f"Sorry, I encountered an error: {exc}"
        if tray:
            tray.set_state(VoiceState.SPEAKING)
        tts_fn(reply)
        return reply

    if tray:
        tray.set_state(VoiceState.LISTENING)

    deadline = asyncio.get_event_loop().time() + TALK_MODE_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        if tray:
            tray.set_state(VoiceState.LISTENING)
        remaining = deadline - asyncio.get_event_loop().time()
        follow_up = await asyncio.get_event_loop().run_in_executor(None, stt_fn, min(remaining, TALK_MODE_TIMEOUT))
        if follow_up and follow_up.strip():
            await _think(follow_up.strip())
            deadline = asyncio.get_event_loop().time() + TALK_MODE_TIMEOUT
        else:
            break

    if tray:
        tray.set_state(VoiceState.SLEEPING)
