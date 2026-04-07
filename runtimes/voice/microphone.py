# SPDX-License-Identifier: AGPL-3.0-or-later
"""Best-effort local microphone capture helpers for the voice pipeline."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from clawos_core.constants import VOICE_DIR


SAMPLE_RATE_HZ = 44100


def available_recorder() -> str:
    for candidate in ("pw-record", "ffmpeg", "parecord", "arecord"):
        if shutil.which(candidate):
            return candidate
    return ""


def default_device_label() -> str:
    recorder = available_recorder()
    if recorder == "pw-record":
        return "PipeWire default input"
    if recorder == "arecord":
        return "ALSA default input"
    if recorder == "ffmpeg":
        return "PipeWire/PulseAudio default input"
    if recorder == "parecord":
        return "PulseAudio default input"
    return "No input backend"


def record_utterance(duration_s: float = 3.0, sample_rate: int = SAMPLE_RATE_HZ, output_path: str | Path | None = None) -> Path:
    recorder = available_recorder()
    if not recorder:
        raise RuntimeError("No supported local recorder is available")

    captures_dir = VOICE_DIR / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    output = Path(output_path) if output_path else captures_dir / f"utterance-{int(time.time() * 1000)}.wav"

    if recorder == "arecord":
        subprocess.run(
            [
                "arecord",
                "-q",
                "-f",
                "S16_LE",
                "-r",
                str(sample_rate),
                "-c",
                "1",
                "-d",
                str(max(1, int(round(duration_s)))),
                str(output),
            ],
            check=True,
            timeout=max(5, int(duration_s) + 5),
            capture_output=True,
        )
    elif recorder == "ffmpeg":
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "pulse",
                "-i",
                "default",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-t",
                f"{duration_s:.1f}",
                str(output),
            ],
            check=True,
            timeout=max(6, int(duration_s) + 6),
            capture_output=True,
        )
    else:
        if recorder == "parecord":
            command = [
                "parecord",
                "--rate",
                str(sample_rate),
                "--channels",
                "1",
                "--format",
                "s16le",
                "--file-format",
                "wav",
                str(output),
            ]
        else:
            command = [
                "pw-record",
                "--rate",
                str(sample_rate),
                "--channels",
                "1",
                str(output),
            ]
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(max(1.0, duration_s))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)

    if not output.exists() or output.stat().st_size <= 44:
        raise RuntimeError("Microphone capture did not produce usable audio")
    return output
