# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ElevenLabs TTS adapter for ClawOS voiced service.
Premium-only — falls back to Piper if key is missing or on error.

Usage:
    from adapters.audio.elevenlabs_adapter import speak, backend
    audio_bytes = speak("Hello, I am Claw.")
    print(backend())  # "elevenlabs" | "unavailable"

Voice default: Daniel (onwK4e9ZLuTAKqWW03F9)
"""
import logging
import os

log = logging.getLogger("elevenlabs_adapter")

_backend = None  # "elevenlabs" | "unavailable"

# Default voice: ElevenLabs Daniel — warm, professional, natural
DEFAULT_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"
_XI_API_BASE = "https://api.elevenlabs.io"


def _load():
    global _backend
    if _backend is not None:
        return

    api_key = _get_api_key()
    if not api_key:
        log.info("ElevenLabs API key not set — adapter unavailable (Piper will be used)")
        _backend = "unavailable"
        return

    try:
        import httpx  # noqa: F401 — just check it's installed
        _backend = "elevenlabs"
        log.info("ElevenLabs adapter ready (streaming, Daniel voice)")
    except ImportError:
        log.warning("httpx not installed — ElevenLabs adapter unavailable. pip install httpx")
        _backend = "unavailable"


def _get_api_key() -> str:
    """Read ElevenLabs API key from env or secretd."""
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if key:
        return key
    try:
        from services.secretd.service import get_secret
        key = get_secret("elevenlabs_api_key") or ""
    except Exception:
        pass
    return key


def _get_voice_id() -> str:
    """Read voice ID from config, fall back to Daniel."""
    try:
        from clawos_core.config import get
        return get("voice.elevenlabs_voice_id", DEFAULT_VOICE_ID)
    except Exception:
        return DEFAULT_VOICE_ID


def get_api_key() -> str:
    return _get_api_key()


def get_voice_id() -> str:
    return _get_voice_id()


def speak(text: str, voice_id: str = "") -> bytes:
    """
    Convert text to speech using ElevenLabs streaming API.
    Returns raw MP3 bytes, or empty bytes on failure.
    Falls back gracefully — caller should detect empty bytes and use Piper.
    """
    _load()
    if _backend != "elevenlabs":
        return b""

    api_key = _get_api_key()
    if not api_key:
        return b""

    voice_id = voice_id or _get_voice_id()
    url = f"{_XI_API_BASE}/v1/text-to-speech/{voice_id}"

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.82,
            "style": 0.15,
            "use_speaker_boost": True,
        },
        "output_format": "mp3_44100_128",
    }

    try:
        import httpx
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                url,
                json=payload,
                headers={
                    "xi-api-key": api_key,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                },
            )
            if response.status_code == 200:
                audio = response.content
                log.debug(f"ElevenLabs spoke {len(text)} chars → {len(audio)} bytes MP3")
                return audio
            elif response.status_code == 401:
                log.warning("ElevenLabs: invalid API key — falling back to Piper")
                return b""
            elif response.status_code == 422:
                log.warning(f"ElevenLabs: text rejected (422): {text[:60]}")
                return b""
            else:
                log.warning(f"ElevenLabs HTTP {response.status_code}: {response.text[:100]}")
                return b""
    except Exception as e:
        log.warning(f"ElevenLabs speak failed: {e} — falling back to Piper")
        return b""


def backend() -> str:
    """Return which backend is active: 'elevenlabs' | 'unavailable'."""
    _load()
    return _backend or "unavailable"


def reset():
    """Force reload (used in tests to inject env var after module load)."""
    global _backend
    _backend = None
