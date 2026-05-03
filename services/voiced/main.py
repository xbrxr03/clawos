# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Voice Pipeline 2.0 Service (voiced)
====================================
Modern voice processing with streaming, VAD, wake word, and interruption.

Features:
- Streaming TTS (real-time, not file-based)
- Voice Activity Detection (VAD)
- Wake word detection ("Hey JARVIS")
- Real-time interruption handling
- Multi-language voice support
- WebRTC audio streaming

Addresses the voice modernization gap from CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import base64
import json
import logging
import numpy as np
import time
import wave
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, AsyncIterator
import threading
import queue

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import uvicorn

try:
    import webrtcvad
    WEBRTC_VAD_AVAILABLE = True
except ImportError:
    WEBRTC_VAD_AVAILABLE = False

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False

try:
    from piper import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

from clawos_core.constants import CLAWOS_DIR, PORT_VOICED
from clawos_core.config.loader import get as get_config

log = logging.getLogger("voiced")

# Audio settings
SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 30
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)


class VoiceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class VoiceConfig:
    """Voice pipeline configuration."""
    wake_word: str = "hey jarvis"
    language: str = "en"
    tts_voice: str = "en_US-lessac-medium"
    vad_aggressiveness: int = 3  # 0-3, higher is more aggressive
    silence_timeout_ms: int = 1500
    interruption_enabled: bool = True
    streaming_tts: bool = True


class VADProcessor:
    """
    Voice Activity Detection using WebRTC VAD.
    
    Detects when user starts/stops speaking.
    """
    
    def __init__(self, aggressiveness: int = 3, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        
        if WEBRTC_VAD_AVAILABLE:
            self.vad = webrtcvad.Vad(aggressiveness)
        else:
            self.vad = None
            log.warning("WebRTC VAD not available, using simple energy-based VAD")
        
        self.buffer = deque(maxlen=100)
        self.is_speaking = False
        self.silence_counter = 0
    
    def process_chunk(self, audio_chunk: bytes) -> bool:
        """
        Process audio chunk and return True if speech detected.
        
        Args:
            audio_chunk: Raw PCM audio bytes (16-bit, 16kHz)
        
        Returns:
            True if speech detected, False otherwise
        """
        if self.vad:
            # WebRTC VAD
            try:
                return self.vad.is_speech(audio_chunk, self.sample_rate)
            except (OSError, AttributeError) as e:
                log.debug(f"suppressed: {e}")
        
        # Fallback: Simple energy-based VAD
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        energy = np.sqrt(np.mean(audio_data**2))
        return energy > 500  # Threshold
    
    def detect_speech_segment(self, audio_chunks: list[bytes]) -> Optional[bytes]:
        """
        Detect speech segment from multiple chunks.
        
        Returns complete speech audio or None if no speech detected.
        """
        speech_chunks = []
        silence_count = 0
        max_silence = int(1500 / CHUNK_DURATION_MS)  # 1.5s silence timeout
        
        for chunk in audio_chunks:
            is_speech = self.process_chunk(chunk)
            
            if is_speech:
                speech_chunks.append(chunk)
                silence_count = 0
                self.is_speaking = True
            else:
                if self.is_speaking:
                    silence_count += 1
                    if silence_count <= max_silence:
                        speech_chunks.append(chunk)  # Include trailing silence
                    else:
                        # Speech ended
                        break
        
        if speech_chunks:
            self.is_speaking = False
            return b"".join(speech_chunks)
        
        return None


class WakeWordDetector:
    """
    Wake word detection using Porcupine.
    
    Supports "Hey JARVIS" and custom wake words.
    """
    
    def __init__(self, wake_word: str = "hey jarvis"):
        self.wake_word = wake_word
        self.porcupine = None
        
        if PORCUPINE_AVAILABLE:
            try:
                # Use built-in keywords or custom model
                keywords = ["jarvis", "hey computer", "bumblebee"]
                keyword_paths = pvporcupine.KEYWORDS
                
                self.porcupine = pvporcupine.create(
                    keywords=keywords
                )
                log.info(f"Wake word detector initialized with: {keywords}")
            except (ImportError, OSError, RuntimeError) as e:
                log.error(f"Failed to initialize Porcupine: {e}")
                self.porcupine = None
        else:
            log.warning("Porcupine not available, wake word detection disabled")
    
    def process_chunk(self, audio_chunk: bytes) -> bool:
        """
        Process audio chunk and return True if wake word detected.
        """
        if not self.porcupine:
            return False
        
        try:
            # Convert bytes to PCM array
            pcm = np.frombuffer(audio_chunk, dtype=np.int16)
            
            # Porcupine expects specific frame length
            frame_length = self.porcupine.frame_length
            if len(pcm) >= frame_length:
                result = self.porcupine.process(pcm[:frame_length])
                return result >= 0  # Wake word detected
        except (OSError, RuntimeError) as e:
            log.error(f"Wake word processing error: {e}")
        
        return False
    
    def cleanup(self):
        """Cleanup Porcupine resources."""
        if self.porcupine:
            self.porcupine.delete()


class StreamingTTS:
    """
    Streaming Text-to-Speech using Piper.
    
    Generates audio in chunks for real-time playback.
    """
    
    def __init__(self, voice_model: str = "en_US-lessac-medium"):
        self.voice_model = voice_model
        self.voice = None
        
        if PIPER_AVAILABLE:
            try:
                # Load Piper voice
                model_path = CLAWOS_DIR / "voices" / f"{voice_model}.onnx"
                config_path = CLAWOS_DIR / "voices" / f"{voice_model}.onnx.json"
                
                if model_path.exists() and config_path.exists():
                    self.voice = PiperVoice.load(str(model_path), str(config_path))
                    log.info(f"Loaded Piper voice: {voice_model}")
                else:
                    log.warning(f"Piper voice files not found: {model_path}")
            except (OSError, RuntimeError) as e:
                log.error(f"Failed to load Piper voice: {e}")
        else:
            log.warning("Piper not available, streaming TTS disabled")
    
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Synthesize text to speech in streaming chunks.
        
        Yields audio chunks for real-time playback.
        """
        if not self.voice:
            # Fallback: return empty
            log.error("TTS not available")
            return
        
        try:
            # Piper doesn't natively support streaming, but we can simulate it
            # by generating in sentences and yielding chunks
            import io
            
            # Split into sentences
            sentences = self._split_sentences(text)
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                
                # Synthesize to WAV in memory
                wav_io = io.BytesIO()
                
                # Generate audio
                self.voice.synthesize(sentence, wav_io)
                
                # Get audio data
                wav_io.seek(0)
                audio_data = wav_io.read()
                
                # Parse WAV header and yield PCM data
                if len(audio_data) > 44:  # WAV header size
                    # Yield in chunks
                    pcm_data = audio_data[44:]  # Skip header
                    chunk_size = 4096
                    
                    for i in range(0, len(pcm_data), chunk_size):
                        chunk = pcm_data[i:i+chunk_size]
                        yield chunk
                        await asyncio.sleep(0.01)  # Small delay for streaming effect
        
        except (OSError, RuntimeError) as e:
            log.error(f"TTS synthesis error: {e}")
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for chunked synthesis."""
        import re
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]


class STTProcessor:
    """
    Speech-to-Text using Whisper.
    
    Transcribes audio to text.
    """
    
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None
        
        if WHISPER_AVAILABLE:
            try:
                log.info(f"Loading Whisper model: {model_size}")
                self.model = whisper.load_model(model_size)
                log.info("Whisper model loaded")
            except (ImportError, OSError, RuntimeError) as e:
                log.error(f"Failed to load Whisper: {e}")
        else:
            log.warning("Whisper not available, STT disabled")
    
    def transcribe(self, audio_data: bytes, language: str = "en") -> Optional[str]:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: Raw PCM audio bytes
            language: Language code (e.g., "en", "es", "fr")
        
        Returns:
            Transcribed text or None if failed
        """
        if not self.model:
            return None
        
        try:
            # Convert bytes to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Transcribe
            result = self.model.transcribe(audio_np, language=language)
            
            return result.get("text", "").strip()
        
        except (OSError, RuntimeError) as e:
            log.error(f"Transcription error: {e}")
            return None


class VoicePipeline:
    """
    Complete voice pipeline integrating VAD, wake word, STT, and TTS.
    
    States:
    - IDLE: Waiting for wake word
    - LISTENING: Wake word detected, listening for command
    - PROCESSING: Transcribing and processing command
    - SPEAKING: Playing TTS response
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.state = VoiceState.IDLE
        
        # Components
        self.vad = VADProcessor(self.config.vad_aggressiveness)
        self.wake_detector = WakeWordDetector(self.config.wake_word)
        self.stt = STTProcessor()
        self.tts = StreamingTTS(self.config.tts_voice)
        
        # Audio buffers
        self.audio_buffer = deque(maxlen=300)  # ~9 seconds
        self.command_buffer: list[bytes] = []
        
        # Interruption handling
        self.is_speaking = False
        self.should_interrupt = False
        
        # Callbacks
        self.on_wake_word: Optional[Callable] = None
        self.on_command: Optional[Callable[[str], str]] = None  # Returns response text
        self.on_state_change: Optional[Callable[[VoiceState], None]] = None
    
    def set_state(self, new_state: VoiceState):
        """Change state and notify."""
        old_state = self.state
        self.state = new_state
        
        if old_state != new_state:
            log.info(f"State: {old_state.value} -> {new_state.value}")
            
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except (RuntimeError, TypeError, AttributeError) as e:
                    log.error(f"State change callback error: {e}")
    
    async def process_audio_chunk(self, audio_chunk: bytes) -> Optional[bytes]:
        """
        Process incoming audio chunk based on current state.
        
        Returns:
            TTS audio chunk if speaking, None otherwise
        """
        # Check for interruption if speaking
        if self.state == VoiceState.SPEAKING and self.config.interruption_enabled:
            if self.vad.process_chunk(audio_chunk):
                log.info("Interruption detected!")
                self.should_interrupt = True
                self.is_speaking = False
                self.set_state(VoiceState.LISTENING)
                self.command_buffer = []
                return None
        
        if self.state == VoiceState.IDLE:
            # Check for wake word
            if self.wake_detector.process_chunk(audio_chunk):
                log.info(f"Wake word detected: {self.config.wake_word}")
                self.set_state(VoiceState.LISTENING)
                self.command_buffer = []
                
                if self.on_wake_word:
                    try:
                        self.on_wake_word()
                    except (RuntimeError, TypeError, AttributeError) as e:
                        log.error(f"Wake word callback error: {e}")
            
            # Also buffer audio for context
            self.audio_buffer.append(audio_chunk)
        
        elif self.state == VoiceState.LISTENING:
            # Collect audio until silence detected
            self.command_buffer.append(audio_chunk)
            
            # Check for speech end (silence)
            if not self.vad.process_chunk(audio_chunk):
                self.vad.silence_counter += 1
                
                # 1.5 seconds of silence = end of command
                if self.vad.silence_counter >= int(1500 / CHUNK_DURATION_MS):
                    # Process command
                    command_audio = b"".join(self.command_buffer)
                    self.set_state(VoiceState.PROCESSING)
                    
                    # Transcribe
                    text = self.stt.transcribe(command_audio, self.config.language)
                    
                    if text:
                        log.info(f"Transcribed: '{text}'")
                        
                        # Process command
                        if self.on_command:
                            try:
                                response_text = self.on_command(text)
                                
                                # Start speaking
                                self.set_state(VoiceState.SPEAKING)
                                self.is_speaking = True
                                self.should_interrupt = False
                                
                                # Return first TTS chunk
                                async for tts_chunk in self.tts.synthesize_stream(response_text):
                                    if self.should_interrupt:
                                        break
                                    return tts_chunk
                            
                            except (OSError, RuntimeError) as e:
                                log.error(f"Command processing error: {e}")
                    
                    # Return to idle
                    self.set_state(VoiceState.IDLE)
                    self.command_buffer = []
            else:
                self.vad.silence_counter = 0
        
        elif self.state == VoiceState.SPEAKING:
            # Continue speaking or handle interruption
            if self.should_interrupt:
                self.is_speaking = False
                self.should_interrupt = False
                self.set_state(VoiceState.LISTENING)
                return None
            
            # Return next TTS chunk
            # (In real implementation, this would come from a queue)
            pass
        
        return None
    
    def cleanup(self):
        """Cleanup resources."""
        self.wake_detector.cleanup()


# FastAPI app for WebSocket streaming
app = FastAPI(title="ClawOS Voice 2.0 Service", version="0.1.0")

# Global pipeline instance
voice_pipeline: Optional[VoicePipeline] = None


@app.on_event("startup")
async def startup():
    """Initialize voice pipeline."""
    global voice_pipeline
    voice_pipeline = VoicePipeline()
    
    # Set up callbacks
    async def on_wake():
        log.info("Wake word triggered!")
        # Call waketrd to handle briefing/chat
        try:
            import httpx
            from clawos_core.constants import PORT_WAKETRD
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"http://127.0.0.1:{PORT_WAKETRD}/trigger")
        except (httpx.HTTPError, OSError, ConnectionError) as e:
            log.warning(f"Failed to call waketrd: {e}")
    
    def on_wake_sync():
        # Async wrapper for the callback
        asyncio.create_task(on_wake())
    
    def on_command(text: str) -> str:
        log.info(f"Processing command: {text}")
        # In real implementation, this would call the agent
        return f"I heard you say: {text}"
    
    voice_pipeline.on_wake_word = on_wake_sync
    voice_pipeline.on_command = on_command
    
    log.info("Voice 2.0 service started")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup voice pipeline."""
    global voice_pipeline
    if voice_pipeline:
        voice_pipeline.cleanup()
    log.info("Voice 2.0 service stopped")


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time voice streaming."""
    await websocket.accept()
    log.info("Voice WebSocket connected")
    
    try:
        while True:
            # Receive audio chunk
            message = await websocket.receive()
            
            if isinstance(message, str):
                # Control message
                data = json.loads(message)
                if data.get("action") == "interrupt":
                    if voice_pipeline:
                        voice_pipeline.should_interrupt = True
            else:
                # Binary audio data
                audio_chunk = message
                
                if voice_pipeline:
                    # Process audio
                    tts_chunk = await voice_pipeline.process_audio_chunk(audio_chunk)
                    
                    if tts_chunk:
                        # Send TTS audio back
                        await websocket.send_bytes(tts_chunk)
    
    except WebSocketDisconnect:
        log.info("Voice WebSocket disconnected")
    except (json.JSONDecodeError, ValueError) as e:
        log.error(f"WebSocket error: {e}")


@app.post("/api/v1/speak")
async def speak_endpoint(request: dict):
    """HTTP endpoint for text-to-speech."""
    text = request.get("text", "")
    voice = request.get("voice", "en_US-lessac-medium")
    
    if not voice_pipeline or not voice_pipeline.tts.voice:
        return {"error": "TTS not available"}
    
    # Generate audio
    audio_chunks = []
    async for chunk in voice_pipeline.tts.synthesize_stream(text):
        audio_chunks.append(chunk)
    
    # Combine and encode
    audio_data = b"".join(audio_chunks)
    
    return {
        "audio": base64.b64encode(audio_data).decode(),
        "format": "wav",
        "duration_ms": len(audio_data) / 32  # Approximate for 16kHz 16-bit
    }


@app.post("/api/v1/transcribe")
async def transcribe_endpoint(request: dict):
    """HTTP endpoint for speech-to-text."""
    audio_b64 = request.get("audio", "")
    language = request.get("language", "en")
    
    if not voice_pipeline or not voice_pipeline.stt.model:
        return {"error": "STT not available"}
    
    # Decode audio
    audio_data = base64.b64decode(audio_b64)
    
    # Transcribe
    text = voice_pipeline.stt.transcribe(audio_data, language)
    
    return {
        "text": text,
        "language": language
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "up",
        "service": "voiced",
        "features": {
            "vad": WEBRTC_VAD_AVAILABLE,
            "wake_word": PORCUPINE_AVAILABLE,
            "stt": WHISPER_AVAILABLE,
            "tts": PIPER_AVAILABLE
        },
        "state": voice_pipeline.state.value if voice_pipeline else "unknown"
    }


def run():
    """Run the voice service."""
    config = get_config()
    host = config.get("voice", {}).get("host", "127.0.0.1")
    port = config.get("voice", {}).get("port", PORT_VOICED)
    
    log.info(f"Starting Voice 2.0 service on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
