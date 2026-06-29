# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Unit tests for voiced — VoiceService initialization and health checks.
All audio/backends mocked — no hardware or external services needed.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── VoiceService initialization ───────────────────────────────────────────────

class TestVoiceServiceInit:
    def test_service_creates(self):
        """VoiceService can be instantiated."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        assert svc._running is False
        assert svc._session_listeners == []

    def test_default_mode(self):
        """VoiceService has a default mode setting."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        assert svc.default_mode in ("push_to_talk", "wake_word", "off")


# ── VoiceService health ───────────────────────────────────────────────────────

class TestVoiceServiceHealth:
    def test_health_returns_dict(self):
        """health() returns a structured dict."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        with patch("services.voiced.service.get_voice_session", return_value={"mode": "off"}):
            h = svc.health()
        assert isinstance(h, dict)
        assert "status" in h
        assert "enabled" in h
        assert "mode" in h
        assert "stt_ok" in h
        assert "tts_ok" in h

    def test_health_mode_off_means_disabled(self):
        """When mode is 'off', health reports enabled=False."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        with patch("services.voiced.service.get_voice_session", return_value={"mode": "off"}):
            h = svc.health()
        assert h["enabled"] is False

    def test_health_stt_without_whisper(self):
        """STT reports unavailable when whisper is not installed."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        svc._stt_available = lambda: False
        with patch("services.voiced.service.get_voice_session", return_value={"mode": "push_to_talk"}), \
             patch("services.voiced.service.available_recorder", return_value=""), \
             patch("services.voiced.service.default_device_label", return_value="none"):
            h = svc.health()
        assert h["stt_ok"] is False

    def test_health_microphone_backend(self):
        """health() reports which microphone backend is available."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        svc._microphone_backend = lambda: "sounddevice"
        with patch("services.voiced.service.get_voice_session", return_value={"mode": "push_to_talk"}):
            h = svc.health()
        assert h["microphone_backend"] == "sounddevice"


# ── VoiceService session listeners ───────────────────────────────────────────

class TestVoiceSessionListeners:
    def test_add_listener(self):
        """add_session_listener registers a callable."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        listener = MagicMock()
        svc.add_session_listener(listener)
        assert listener in svc._session_listeners

    def test_remove_listener(self):
        """remove_session_listener unregisters a callable."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        listener = MagicMock()
        svc.add_session_listener(listener)
        svc.remove_session_listener(listener)
        assert listener not in svc._session_listeners

    def test_no_duplicate_listeners(self):
        """Same listener cannot be added twice."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        listener = MagicMock()
        svc.add_session_listener(listener)
        svc.add_session_listener(listener)
        assert svc._session_listeners.count(listener) == 1


# ── VoiceService start/stop ───────────────────────────────────────────────────

class TestVoiceServiceLifecycle:
    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """start() sets _running to True when mode is not 'off'."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        with patch("services.voiced.service.get_voice_session", return_value={"mode": "push_to_talk"}), \
             patch.object(svc, "_ensure_runtime"), \
             patch.object(svc, "_sync_session"), \
             patch.object(svc, "_set_tray_state"):
            await svc.start()
        assert svc._running is True

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        """stop() sets _running to False."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        svc._running = True
        with patch.object(svc, "_stop_wake_detector"), \
             patch.object(svc, "_sync_session"), \
             patch.object(svc, "_set_tray_state"):
            await svc.stop()
        assert svc._running is False


# ── VoiceService speak (mocked audio) ─────────────────────────────────────────

class TestVoiceServiceSpeak:
    @pytest.mark.asyncio
    async def test_speak_empty_text_returns_false(self):
        """speak() returns False for empty text."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        result = await svc.speak("")
        assert result is False

    @pytest.mark.asyncio
    async def test_speak_no_playback_returns_false(self):
        """speak() returns False when no playback backend is available."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        with patch.object(svc, "_ensure_runtime"), \
             patch.object(svc, "_playback_backend", return_value=""), \
             patch.object(svc, "_sync_session"), \
             patch.object(svc, "_set_tray_state"):
            result = await svc.speak("Hello")
        assert result is False


# ── VoiceService set_mode ─────────────────────────────────────────────────────

class TestVoiceServiceSetMode:
    @pytest.mark.asyncio
    async def test_set_mode_off(self):
        """set_mode('off') stops the service."""
        from services.voiced.service import VoiceService
        svc = VoiceService()
        svc._running = True
        with patch("services.voiced.service.set_voice_mode", return_value={"mode": "off"}), \
             patch.object(svc, "_notify_session"), \
             patch.object(svc, "stop", new_callable=AsyncMock) as mock_stop:
            await svc.set_mode("off")
            mock_stop.assert_called_once()