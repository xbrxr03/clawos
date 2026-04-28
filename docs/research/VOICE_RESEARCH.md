# Voice Projects Research for ClawOS

## Top Voice Stack Projects for OpenClaw/Local AI

### 1. **VoiceClaw** (Muin Company)
- **Repo**: github.com/muin-company/voiceclaw
- **Features**: Wake word + STT + TTS integration for OpenClaw
- **Status**: Active OpenClaw plugin

### 2. **Purple-Horizons/openclaw-voice**
- **Stars**: 96 | **Forks**: 18
- **Features**: Browser-based voice chat for AI assistants
- **Stack**: Whisper STT + ElevenLabs TTS
- **Works with**: OpenAI, Claude, custom agents
- **Note**: Open source, self-hosted, private, free

### 3. **joetomasone/clawd-voice**
- **Features**: Local voice assistant for OpenClaw
- **Stack**: Wake word + Whisper STT + ElevenLabs TTS
- **Language**: Python

### 4. **ShayneP/local-voice-ai**
- **Stars**: 479 | **Forks**: 148
- **Stack**: Ollama + Kokoro + Nemotron STT + LiveKit
- **Language**: TypeScript (71.8%), Python (15.2%)
- **Status**: Popular, actively maintained

### 5. **MnAkash/aalap**
- **Features**: Speech-to-speech dialogue management
- **Stack**: faster-whisper ASR + Piper TTS + wake-word support
- **License**: Apache 2.0

### 6. **openwakeword-trainer** (lgpearson1771)
- **Features**: Train custom wake word models
- **Stack**: openWakeWord + Piper TTS + speechbrain
- **Output**: Tiny ONNX models (~200 KB)
- **Requirements**: WSL2/Linux + CUDA

### 7. **Piper TTS** (rhasspy)
- **Stars**: Very popular
- **Features**: Fast, local neural text-to-speech
- **Status**: Industry standard for offline TTS
- **Integrates with**: Home Assistant, OpenClaw, etc.

### 8. **Wyoming Protocol** (Home Assistant)
- **Features**: Local voice control protocol
- **Stack**: Piper TTS + faster-whisper + openWakeWord
- **Status**: Widely adopted in smart home ecosystem

### 9. **easy-oww** (pjdoland)
- **Features**: Complete CLI for custom wake word creation
- **Stack**: openWakeWord with guided pipeline

### 10. **OpenOcto**
- **Website**: openocto.dev
- **Features**: Open-source AI assistant constructor
- **Stack**: Voice control + persona system + local execution

### 11. **piper-sample-generator**
- **PyPI**: piper-sample-generator
- **Purpose**: Generate TTS samples for wake word training
- **License**: MIT

### 12. **whisper-stt-local-server** (fakehec)
- **Features**: High-performance Whisper STT API
- **Architecture**: Hot/Cold worker architecture
- **Stack**: FastAPI + faster-whisper

## Key Technologies Summary

| Component | Best Option | Alternatives |
|-----------|-------------|--------------|
| **Wake Word** | openWakeWord | Porcupine (Picovoice), Snowboy |
| **STT** | faster-whisper | Whisper.cpp, Whisper JAX |
| **TTS** | Piper TTS | Kokoro TTS, Coqui TTS, MeloTTS |
| **Voice Activity** | WebRTC VAD | Silero VAD |
| **Audio Streaming** | LiveKit | WebRTC native |

## ClawOS Current Stack

✅ **openWakeWord** - Wake word detection
✅ **Whisper** (OpenAI) - Speech-to-text
✅ **Piper TTS** - Text-to-speech (offline)
✅ **WebRTC VAD** - Voice activity detection

## Recommendations for ClawOS

1. **Benchmark against ShayneP/local-voice-ai** - 479 stars, very popular
2. **Study Purple-Horizons implementation** - Browser-based, well-received
3. **Consider faster-whisper** over base Whisper for speed
4. **Look at Wyoming Protocol** for Home Assistant ecosystem compatibility
5. **Evaluate LiveKit** for production audio streaming
6. **Custom wake word training** via easy-oww or openwakeword-trainer

## Competitive Position

ClawOS already uses industry-standard components (Piper, Whisper, openWakeWord). 
Differentiators could be:
- Hardware-aware voice model selection
- Voice-specific memory/personality layers
- Multi-language voice personas
- Integration with 29 built-in workflows via voice
