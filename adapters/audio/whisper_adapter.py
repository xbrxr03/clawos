# SPDX-License-Identifier: AGPL-3.0-or-later
"""
faster-whisper drop-in adapter for voiced service.
4x faster than openai-whisper on CPU, same accuracy.

Usage:
    from adapters.audio.whisper_adapter import transcribe
    text = transcribe(audio_bytes, rate=44100)

Falls back to openai-whisper if faster-whisper not installed.
"""
import io
import logging
import wave
from pathlib import Path
from clawos_core.constants import WHISPER_MODEL, WHISPER_RATE
import subprocess

log = logging.getLogger("whisper_adapter")

_model = None
_backend = None   # "faster" | "openai" | None


def _load():
    global _model, _backend
    if _backend is not None:
        return

    # Try faster-whisper first
    try:
        from faster_whisper import WhisperModel
        _model   = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        _backend = "faster"
        log.info(f"faster-whisper loaded (model={WHISPER_MODEL}, int8 CPU)")
        return
    except ImportError:
        log.debug("faster-whisper not installed — falling back to openai-whisper")
    except (OSError, subprocess.SubprocessError, RuntimeError) as e:
        log.warning(f"faster-whisper load failed: {e}")

    # Fallback: openai-whisper
    try:
        import whisper
        _model   = whisper.load_model(WHISPER_MODEL)
        _backend = "openai"
        log.info(f"openai-whisper loaded (model={WHISPER_MODEL})")
        return
    except ImportError:
        log.warning("Neither faster-whisper nor openai-whisper installed. "
                    "pip install faster-whisper")
    except (OSError, RuntimeError, AttributeError) as e:
        log.error(f"Whisper load failed: {e}")

    _backend = None


def transcribe(audio_bytes: bytes, rate: int = 44100) -> str:
    """
    Transcribe raw PCM audio bytes to text.
    audio_bytes: raw 16-bit mono PCM at `rate` Hz.
    """
    _load()
    if _backend is None:
        return ""

    # Write to temp WAV for whisper
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)   # 16-bit
            wf.setframerate(rate)
            wf.writeframes(audio_bytes)

    try:
        if _backend == "faster":
            segments, _ = _model.transcribe(tmp_path, language="en", beam_size=5)
            text = " ".join(seg.text for seg in segments).strip()
        else:
            import numpy as np
            import soundfile as sf
            data, sr = sf.read(tmp_path, dtype="float32")
            result = _model.transcribe(data, language="en")
            text = result.get("text", "").strip()
        log.debug(f"Transcribed ({_backend}): {text[:80]}")
        return text
    except (OSError, RuntimeError, AttributeError) as e:
        log.warning(f"Transcription failed: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except (OSError, PermissionError) as e:
            log.debug(f"unexpected: {e}")
            pass


def backend() -> str:
    """Return which backend is active: 'faster' | 'openai' | 'none'."""
    _load()
    return _backend or "none"
