# SPDX-License-Identifier: AGPL-3.0-or-later
"""voice_agent.py — Piper TTS narration. Reads script.txt, produces voice.wav."""
import os
import re
import subprocess
import tempfile
from pathlib import Path
from core.agent_base import AgentBase

PIPER_BIN       = os.environ.get("PIPER_BIN", "piper")
PIPER_MODEL     = os.environ.get("PIPER_VOICE", "en_US-lessac-medium.onnx")
PIPER_MODEL_DIR = os.environ.get("PIPER_MODEL_DIR",
                                  str(Path.home() / ".local" / "share" / "piper"))

class VoiceAgent(AgentBase):
    @property
    def phase_name(self): return "voice"
    @property
    def resource_class(self): return "light"

    def process_job(self, job: dict):
        job_id = job["job_id"]
        if self.artifact_exists(job_id, "voice.wav"):
            self.logger.info("[voice] voice.wav exists — skipping"); return
        script = self.read_artifact(job_id, "script.txt")
        if not script:
            raise RuntimeError("script.txt not found — writer must run first")
        script = self._clean(script)
        self.logger.info(f"[voice] generating narration ({len(script)} chars)")
        wav = self._synthesize(script)
        self.write_artifact(job_id, "voice.wav", wav)
        self.logger.info(f"[voice] done ({len(wav):,} bytes)")

    def _synthesize(self, text: str) -> bytes:
        model_path = Path(PIPER_MODEL_DIR) / PIPER_MODEL
        if not model_path.exists():
            raise RuntimeError(
                f"Piper voice model not found: {model_path}\n"
                f"Run: bash ~/clawos/content_factory_skill/install.sh")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            r = subprocess.run(
                [PIPER_BIN, "--model", str(model_path), "--output_file", str(tmp_path)],
                input=text, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"Piper error: {r.stderr.strip()}")
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    def _clean(self, text: str) -> str:
        text = re.sub(r"#+\s", "", text)
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

if __name__ == "__main__":
    VoiceAgent("voice_agent").run()
