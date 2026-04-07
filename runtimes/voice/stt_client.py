# SPDX-License-Identifier: AGPL-3.0-or-later
"""Whisper-backed speech-to-text helpers for the local voice pipeline."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=2)
def _load_whisper(model_name: str):
    import whisper

    return whisper.load_model(model_name)


def transcribe(audio_path: str | Path, model_name: str = "base") -> str:
    model = _load_whisper(model_name)
    result = model.transcribe(str(audio_path), fp16=False, language="en")
    return str(result.get("text", "")).strip()
