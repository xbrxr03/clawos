"""
voice_agent.py — narration audio generation.

Uses Piper TTS (https://github.com/rhasspy/piper) — local, CPU-only.
Reads script.txt produced by the writer agent.
Produces: voice.wav

Resume logic: if voice.wav already exists, skip generation entirely.
"""

import subprocess
import tempfile
from pathlib import Path

from core.agent_base import AgentBase


import os

PIPER_BIN       = os.environ.get("PIPER_BIN",       "piper")
PIPER_MODEL     = os.environ.get("PIPER_VOICE",     "en_US-lessac-medium.onnx")
PIPER_MODEL_DIR = os.environ.get("PIPER_MODEL_DIR", "/usr/share/piper/voices")
SAMPLE_RATE     = 22050


class VoiceAgent(AgentBase):

    @property
    def phase_name(self) -> str:
        return "voice"

    @property
    def resource_class(self) -> str:
        return "light"

    def process_job(self, job: dict):
        job_id = job["job_id"]

        if self.artifact_exists(job_id, "voice.wav"):
            self.logger.info("[voice] voice.wav exists — skipping")
            return

        # Load the script
        script = self.read_artifact(job_id, "script.txt")
        if not script:
            raise RuntimeError("script.txt not found — writer must run first")

        # Read voice model from template pipeline_config if available
        pipeline_cfg  = job.get("pipeline_config") or {}
        voice_cfg     = pipeline_cfg.get("voice", {})
        voice_model   = voice_cfg.get("piper_voice", PIPER_MODEL)
        speech_speed  = voice_cfg.get("speed", 1.0)

        self.logger.info(f"[voice] generating narration ({len(script)} chars, model={voice_model})")
        wav_bytes = self._synthesize(script, model=voice_model)
        self.write_artifact(job_id, "voice.wav", wav_bytes)
        self.logger.info(f"[voice] narration written ({len(wav_bytes):,} bytes)")

    # ── Piper helpers ─────────────────────────────────────────────────────────

    def _synthesize(self, text: str, model: str = PIPER_MODEL) -> bytes:
        """
        Pipe text through Piper and return WAV bytes.

        Piper usage: echo "text" | piper --model <model> --output_file <out.wav>
        We use a temp file for the output then read it back.
        """
        model_path = Path(PIPER_MODEL_DIR) / model

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [
                    PIPER_BIN,
                    "--model",       str(model_path),
                    "--output_file", str(tmp_path),
                ],
                input=text,
                capture_output=True,
                text=True,
                timeout=600,   # long scripts can take time on CPU
            )
            if result.returncode != 0:
                raise RuntimeError(f"Piper error: {result.stderr.strip()}")
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    def _clean_script(self, text: str) -> str:
        """
        Strip any markdown formatting from the script before sending to TTS.
        """
        import re
        text = re.sub(r"#+\s", "", text)       # headings
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)  # bold/italic
        text = re.sub(r"`[^`]+`", "", text)    # code
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links
        return text.strip()


if __name__ == "__main__":
    VoiceAgent("voice_agent").run()
