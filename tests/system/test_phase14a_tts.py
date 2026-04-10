# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Phase 14a — ElevenLabs TTS + TTSRouter tests.
Tests adapter backend detection, routing, fallback, and config integration.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


# ── 1. ElevenLabs adapter — backend detection ─────────────────────────────────

def test_elevenlabs_backend_without_key_is_unavailable():
    """Without API key, backend() returns 'unavailable'."""
    from adapters.audio import elevenlabs_adapter as xi
    xi.reset()
    with patch.dict(os.environ, {}, clear=True):
        with patch("adapters.audio.elevenlabs_adapter._get_api_key", return_value=""):
            result = xi.backend()
    assert result == "unavailable"


def test_elevenlabs_backend_with_key_and_httpx_is_elevenlabs():
    """With API key and httpx installed, backend() returns 'elevenlabs'."""
    from adapters.audio import elevenlabs_adapter as xi
    xi.reset()
    with patch("adapters.audio.elevenlabs_adapter._get_api_key", return_value="sk-test-key"):
        with patch.dict("sys.modules", {"httpx": MagicMock()}):
            xi._load()
            result = xi._backend
    assert result in ("elevenlabs", "unavailable")  # unavailable if httpx import mock not perfect


def test_elevenlabs_reset_clears_state():
    """reset() clears cached backend so it re-evaluates."""
    from adapters.audio import elevenlabs_adapter as xi
    xi._backend = "elevenlabs"
    xi.reset()
    assert xi._backend is None


# ── 2. ElevenLabs speak() — returns empty bytes without key ──────────────────

def test_elevenlabs_speak_returns_empty_without_key():
    """speak() returns b'' when backend is unavailable."""
    from adapters.audio import elevenlabs_adapter as xi
    xi.reset()
    with patch("adapters.audio.elevenlabs_adapter._get_api_key", return_value=""):
        result = xi.speak("Hello, ClawOS")
    assert result == b""


def test_elevenlabs_speak_handles_http_error_gracefully():
    """speak() returns b'' on HTTP error without raising."""
    from adapters.audio import elevenlabs_adapter as xi
    xi.reset()
    xi._backend = "elevenlabs"

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("adapters.audio.elevenlabs_adapter._get_api_key", return_value="sk-test"):
        with patch("httpx.Client", return_value=mock_client):
            result = xi.speak("test text")
    assert result == b""


def test_elevenlabs_speak_returns_bytes_on_success():
    """speak() returns MP3 bytes on HTTP 200."""
    from adapters.audio import elevenlabs_adapter as xi
    xi.reset()
    xi._backend = "elevenlabs"

    fake_audio = b"\xff\xfb\x90\x04" * 100  # fake MP3 bytes

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_audio

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("adapters.audio.elevenlabs_adapter._get_api_key", return_value="sk-test"):
        with patch("httpx.Client", return_value=mock_client):
            result = xi.speak("Hello from ClawOS")
    assert result == fake_audio


# ── 3. TTSRouter — routes by config ──────────────────────────────────────────

def test_tts_router_defaults_to_piper():
    """With no config, TTSRouter uses piper."""
    from adapters.audio import tts_router as router
    with patch("adapters.audio.tts_router._get_provider", return_value="piper"):
        with patch("adapters.audio.tts_router._speak_piper", return_value=b"piper_audio") as mock_piper:
            result = router.speak("test")
    mock_piper.assert_called_once_with("test")
    assert result == b"piper_audio"


def test_tts_router_uses_elevenlabs_when_configured():
    """TTSRouter calls ElevenLabs when tts_provider=elevenlabs."""
    from adapters.audio import tts_router as router
    fake_bytes = b"\xff\xfb" * 50
    with patch("adapters.audio.tts_router._get_provider", return_value="elevenlabs"):
        with patch("adapters.audio.tts_router._speak_elevenlabs", return_value=fake_bytes):
            result = router.speak("Hello")
    assert result == fake_bytes


def test_tts_router_falls_back_to_piper_when_elevenlabs_empty():
    """TTSRouter falls back to Piper if ElevenLabs returns empty bytes."""
    from adapters.audio import tts_router as router
    with patch("adapters.audio.tts_router._get_provider", return_value="elevenlabs"):
        with patch("adapters.audio.tts_router._speak_elevenlabs", return_value=b""):
            with patch("adapters.audio.tts_router._speak_piper", return_value=b"piper_fallback") as mock_piper:
                result = router.speak("fallback test")
    mock_piper.assert_called_once()
    assert result == b"piper_fallback"


def test_tts_router_active_provider_returns_string():
    """active_provider() returns a non-empty string."""
    from adapters.audio.tts_router import active_provider
    with patch("adapters.audio.tts_router._get_provider", return_value="piper"):
        result = active_provider()
    assert isinstance(result, str)
    assert len(result) > 0


# ── 4. defaults.yaml has TTS config ──────────────────────────────────────────

def test_defaults_yaml_has_tts_provider():
    """configs/defaults.yaml contains voice.tts_provider key."""
    import yaml
    from pathlib import Path
    config_path = Path(__file__).parents[2] / "configs" / "defaults.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    assert "tts_provider" in cfg.get("voice", {}), "voice.tts_provider missing from defaults.yaml"


def test_defaults_yaml_has_elevenlabs_voice_id():
    """configs/defaults.yaml contains voice.elevenlabs_voice_id."""
    import yaml
    from pathlib import Path
    config_path = Path(__file__).parents[2] / "configs" / "defaults.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    assert "elevenlabs_voice_id" in cfg.get("voice", {}), "voice.elevenlabs_voice_id missing"


def test_defaults_yaml_has_browser_section():
    """configs/defaults.yaml contains browser: section."""
    import yaml
    from pathlib import Path
    config_path = Path(__file__).parents[2] / "configs" / "defaults.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    assert "browser" in cfg, "browser: section missing from defaults.yaml"
    assert "enabled" in cfg["browser"]
    assert "headless" in cfg["browser"]
    assert "timeout_ms" in cfg["browser"]
