# SPDX-License-Identifier: AGPL-3.0-or-later
"""
TTS Router — routes text-to-speech to Piper or ElevenLabs.
Reads voiced.tts_provider from config.

Usage:
    from adapters.audio.tts_router import speak, active_provider
    audio_bytes = speak("Hello from ClawOS")
    # Returns: bytes (MP3 or WAV depending on provider)
"""
import logging

log = logging.getLogger("tts_router")


def _get_provider() -> str:
    """Read tts_provider from config. Default: piper."""
    try:
        from clawos_core.config import get
        return get("voice.tts_provider", "piper").lower().strip()
    except Exception:
        return "piper"


def speak(text: str, provider_preference: str = "", voice_id: str = "") -> bytes:
    """
    Route TTS request to the configured provider.

    Returns audio bytes:
    - piper: returns WAV bytes (16-bit PCM, 22050Hz)
    - elevenlabs: returns MP3 bytes (44100Hz, 128kbps)
    - On any failure: falls back to Piper silently.
    """
    provider = (provider_preference or _get_provider()).lower().strip()

    if provider == "elevenlabs":
        audio = _speak_elevenlabs(text, voice_id=voice_id)
        if audio:
            return audio
        log.info("ElevenLabs unavailable — falling back to Piper")
        return _speak_piper(text)

    return _speak_piper(text)


def _speak_elevenlabs(text: str, voice_id: str = "") -> bytes:
    try:
        from adapters.audio.elevenlabs_adapter import speak as xi_speak, backend
        if backend() == "unavailable":
            return b""
        return xi_speak(text, voice_id=voice_id)
    except Exception as e:
        log.warning(f"ElevenLabs TTS error: {e}")
        return b""


def _speak_piper(text: str) -> bytes:
    """Invoke Piper TTS — returns WAV bytes or empty on failure."""
    try:
        import subprocess
        import shutil
        piper_bin = shutil.which("piper") or shutil.which("piper-tts")
        if not piper_bin:
            log.warning("Piper not found in PATH — TTS unavailable")
            return b""

        from clawos_core.config import get
        model_path = get("voice.piper_model", "")

        cmd = [piper_bin, "--output-raw"]
        if model_path:
            cmd += ["--model", model_path]

        result = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        log.warning(f"Piper exited {result.returncode}: {result.stderr[:100]}")
        return b""
    except subprocess.TimeoutExpired:
        log.warning("Piper TTS timed out")
        return b""
    except Exception as e:
        log.warning(f"Piper TTS error: {e}")
        return b""


def active_provider(provider_preference: str = "") -> str:
    """Return the active TTS provider name."""
    provider = (provider_preference or _get_provider()).lower().strip()
    if provider == "elevenlabs":
        try:
            from adapters.audio.elevenlabs_adapter import backend
            if backend() == "elevenlabs":
                return "elevenlabs"
        except Exception:
            pass
        return "piper (elevenlabs unavailable)"
    return "piper"
