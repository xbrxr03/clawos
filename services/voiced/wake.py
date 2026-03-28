"""
openWakeWord integration — hey_jarvis.onnx as "Hey Nexus" trigger.
Ships with the pre-trained hey_jarvis model (phonetically close enough).
Custom hey_nexus.onnx can be trained post-launch via Docker pipeline.
"""
import logging
import threading
from pathlib import Path

log = logging.getLogger("voiced.wake")
MODEL_PATH = Path(__file__).parent / "models" / "hey_jarvis.onnx"


class WakeWordDetector:
    def __init__(self, on_wake, sensitivity: float = 0.5):
        self.on_wake    = on_wake
        self.sensitivity = sensitivity
        self._thread    = None
        self._running   = False

    def start(self) -> bool:
        if not MODEL_PATH.exists():
            log.warning(f"Wake word model not found at {MODEL_PATH} — wake word disabled")
            return False
        try:
            import openwakeword
            self._model = openwakeword.Model(
                wakeword_models=[str(MODEL_PATH)],
                inference_framework="onnx",
            )
            self._running = True
            self._thread  = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            log.info("Wake word detector started — say 'Hey Nexus'")
            return True
        except ImportError:
            log.warning("openwakeword not installed — wake word disabled")
            return False
        except Exception as e:
            log.warning(f"Wake word init failed: {e}")
            return False

    def _listen_loop(self):
        """Listen in 1280-sample chunks (80ms at 16kHz). Required by openWakeWord."""
        try:
            import pyaudio
            import numpy as np
            pa     = pyaudio.PyAudio()
            stream = pa.open(rate=16000, channels=1, format=pyaudio.paInt16,
                             input=True, frames_per_buffer=1280)
            while self._running:
                raw   = stream.read(1280, exception_on_overflow=False)
                audio = np.frombuffer(raw, dtype=np.int16)
                pred  = self._model.predict(audio)
                for model_name, score in pred.items():
                    if score >= self.sensitivity:
                        log.info(f"Wake word detected (score={score:.2f})")
                        self.on_wake()
                        break
            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception as e:
            log.error(f"Wake word listen loop error: {e}")

    def stop(self):
        self._running = False
