# SPDX-License-Identifier: AGPL-3.0-or-later
"""Helpers for transcribing inbound WhatsApp voice notes and audio media."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from clawos_core.constants import VOICE_DIR
from runtimes.voice.microphone import SAMPLE_RATE_HZ
from runtimes.voice.stt_client import transcribe


AUDIO_SUFFIXES = {".aac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm"}


def is_audio_media(media_path: str | Path) -> bool:
    return Path(media_path).suffix.lower() in AUDIO_SUFFIXES


def process_inbound_media(media_path: str | Path) -> dict[str, Any]:
    path = Path(media_path)
    result: dict[str, Any] = {
        "path": str(path),
        "kind": "file",
        "ok": False,
        "transcript": "",
        "issues": [],
    }
    if not path.exists():
        result["issues"] = [f"Media path does not exist: {path}"]
        return result
    if not is_audio_media(path):
        result["kind"] = "file"
        return result

    audio_path = _normalize_audio(path)
    transcript = transcribe(audio_path)
    result.update(
        {
            "kind": "voice_note",
            "ok": bool(transcript.strip()),
            "transcript": transcript.strip(),
            "sample_rate_hz": SAMPLE_RATE_HZ,
        }
    )
    if not result["ok"]:
        result["issues"] = ["Voice note could not be transcribed"]
    return result


def _normalize_audio(path: Path) -> Path:
    if path.suffix.lower() == ".wav":
        return path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return path

    output_dir = VOICE_DIR / "whatsapp"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{path.stem}-{int(time.time() * 1000)}.wav"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE_HZ),
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output
