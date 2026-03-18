"""
ClawOS voiced — Voice Pipeline Supervisor
==========================================
Whisper STT (44100Hz via pipewire) + Piper TTS (lessac-medium).
Push-to-talk and always-on modes.
Full implementation in Session 3 alongside gatewayd.
"""
import asyncio
import logging
from clawos_core.constants import VOICE_DIR
from clawos_core.config.loader import get

log = logging.getLogger("voiced")


class VoiceService:
    def __init__(self):
        self.enabled  = get("voice.enabled",  False)
        self.mode     = get("voice.mode",      "push_to_talk")
        self.stt_ok   = self._check_stt()
        self.tts_ok   = self._check_tts()
        self._running = False

    def _check_stt(self) -> bool:
        try:
            import whisper
            return True
        except ImportError:
            return False

    def _check_tts(self) -> bool:
        import shutil
        return shutil.which("piper") is not None

    def health(self) -> dict:
        return {
            "enabled":  self.enabled,
            "mode":     self.mode,
            "stt_ok":   self.stt_ok,
            "tts_ok":   self.tts_ok,
            "running":  self._running,
        }

    async def start(self):
        if not self.enabled:
            log.info("voiced disabled by config")
            return
        if not self.stt_ok:
            log.warning("Whisper not installed — voiced disabled")
            return
        if not self.tts_ok:
            log.warning("Piper not found — TTS disabled")
        self._running = True
        log.info(f"voiced started — mode={self.mode}")

    async def stop(self):
        self._running = False

    async def speak(self, text: str) -> bool:
        """Synthesise speech via Piper. Returns True on success."""
        if not self.tts_ok or not text:
            return False
        try:
            import subprocess
            model = VOICE_DIR / "en_US-lessac-medium.onnx"
            if not model.exists():
                log.warning(f"Piper model not found: {model}")
                return False
            proc = subprocess.Popen(
                ["piper", "--model", str(model), "--output-raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            audio, _ = proc.communicate(input=text.encode(), timeout=15)
            # Play raw audio via aplay
            play = subprocess.run(
                ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
                input=audio, capture_output=True
            )
            return play.returncode == 0
        except Exception as e:
            log.error(f"TTS error: {e}")
            return False

    async def listen(self) -> str:
        """Record one utterance and transcribe. Returns text."""
        if not self.stt_ok:
            return ""
        try:
            from runtimes.voice.microphone import record_utterance
            from runtimes.voice.stt_client import transcribe
            audio_path = await record_utterance()
            return await transcribe(audio_path)
        except Exception as e:
            log.error(f"STT error: {e}")
            return ""


_svc = None

def get_service() -> VoiceService:
    global _svc
    if _svc is None:
        _svc = VoiceService()
    return _svc
