"""
voice_agent.py — narration audio generation.

Uses Piper TTS — local, CPU-only.
Reads script.txt produced by writer_agent.
Produces: voice.wav

Resume logic: if voice.wav already exists, skip entirely.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from core.agent_base import AgentBase

# ── config — all overridable via .env ──────────────────────────────────────────
PIPER_BIN       = os.environ.get("PIPER_BIN",       "piper")
PIPER_MODEL     = os.environ.get("PIPER_VOICE",     "en_US-lessac-medium.onnx")

# Default model dir — checks ~/.local/share/piper first (pip install piper-tts)
_DEFAULT_MODEL_DIR = str(Path.home() / ".local" / "share" / "piper")
PIPER_MODEL_DIR = os.environ.get("PIPER_MODEL_DIR", _DEFAULT_MODEL_DIR)


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

        script = self.read_artifact(job_id, "script.txt")
        if not script:
            raise RuntimeError("script.txt not found — writer must run first")

        # Clean markdown before sending to TTS
        script = self._clean_script(script)

        pipeline_cfg = job.get("pipeline_config") or {}
        voice_cfg    = pipeline_cfg.get("voice", {})
        voice_model  = voice_cfg.get("piper_voice", PIPER_MODEL)

        self.logger.info(f"[voice] generating narration ({len(script)} chars, model={voice_model})")
        wav_bytes = self._synthesize(script, model=voice_model)
        self.write_artifact(job_id, "voice.wav", wav_bytes)
        self.logger.info(f"[voice] narration written ({len(wav_bytes):,} bytes)")

    def _synthesize(self, text: str, model: str = PIPER_MODEL) -> bytes:
        """Pipe text through Piper and return WAV bytes."""
        # Resolve model path
        model_path = Path(PIPER_MODEL_DIR) / model
        if not model_path.exists():
            # Try without .onnx extension check — maybe it's a full path
            if Path(model).exists():
                model_path = Path(model)
            else:
                raise RuntimeError(
                    f"Piper voice model not found: {model_path}\n"
                    f"Run: piper --download-voices or check PIPER_MODEL_DIR"
                )

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [PIPER_BIN, "--model", str(model_path), "--output_file", str(tmp_path)],
                input=text,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Piper error: {result.stderr.strip()}")
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    def _clean_script(self, text: str) -> str:
        """Strip markdown formatting before sending to TTS."""
        text = re.sub(r"#+\s", "", text)
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


if __name__ == "__main__":
    VoiceAgent("voice_agent").run()
