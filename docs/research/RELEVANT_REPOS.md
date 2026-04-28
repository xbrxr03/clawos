# Relevant Repositories for ClawOS Implementation
## Research Summary: What to Steal, What to Avoid, What to Build

---

## 🏆 TIER 1: Direct Implementation References

### 1. **OpenPawz** (github.com/OpenPawz/openpawz)
**Stars:** Growing fast | **Stack:** Tauri v2 + Rust + React

**What Makes It Special:**
- **~5MB native binary** (vs 200MB Electron apps)
- **"Librarian Method"** — semantic tool discovery via embedding model
- **"Foreman Protocol"** — cheap worker models execute expensive tool calls
- **"Conductor Protocol"** — workflow compilation (10-node flow in 4-8s vs 24s+)
- **Hybrid memory system** with knowledge graph (Engram)
- **400+ integrations** via MCP bridge to n8n
- **10-layer security** with command risk classifier

**What You Should Steal:**
1. **The Conductor workflow optimizer** — ClawOS has 29 workflows, this would make them compile/run faster
2. **Semantic tool discovery** — Instead of loading all skills into context, embed and search
3. **MCP Bridge pattern** — Auto-deploy workflows for new integrations
4. **5-phase execution pipeline** — Action DAG planning → Constrained decoding → Embedding-indexed registry → Binary IPC → Speculative execution
5. **Security layers** — Their command risk classifier (30+ danger patterns, 5 risk levels) is exactly what ClawOS policyd needs

**Implementation Path:**
```rust
// Add to ClawOS policyd
pub struct CommandRiskClassifier {
    patterns: Vec<DangerPattern>,
    risk_levels: [RiskLevel; 5], // critical, high, medium, low, safe
}

impl CommandRiskClassifier {
    pub fn classify(&self, command: &str) -> RiskAssessment {
        // 30+ regex patterns like sudo, rm -rf, curl | bash
        // Color-coded approval modals in UI
    }
}
```

---

### 2. **jincocodev/openclaw-jarvis-ui** (11⭐)
**Stack:** Three.js + Express + WebSocket

**What Makes It Special:**
- **Already built for OpenClaw** — drop-in skill
- **Three.js orb** with IDLE/THINKING/RESPONDING states
- **Audio visualization** (spectrum, ring, waveform)
- **Real-time system monitoring** via SSE
- **6-color theme system** (red, orange, green, cyan, blue, purple)
- **Edge TTS integration** (300+ voices)

**What You Should Steal:**
1. **The orb visualization states** — Direct port to ClawOS dashboard
2. **Audio reactivity** — Spectrum + ring + waveform layers
3. **Theme system** — HSL hue rotation, persisted in localStorage
4. **Power save mode** — Throttle from 60fps to 15fps, disable particles
5. **TTS switching** — Edge vs macOS say engines

**Implementation Path:**
```typescript
// Add to ClawOS dashboard
interface OrbState {
  state: 'idle' | 'listening' | 'thinking' | 'responding';
  color: HSLColor;
  audioLevel: number; // 0-1 for reactivity
}

// Three.js scene with:
// - Core sphere with fresnel glow
// - Orbiting particles
// - State-based color transitions
// - Audio-reactive displacement
```

---

### 3. **ChiFungHillmanChan/jarvis-ai-assistant** (Tauri v2 + React + Rust)
**Stars:** Growing | **Stack:** Tauri v2 + Canvas2D (no Three.js!)

**What Makes It Special:**
- **Canvas2D 3D sphere** — Custom math, no WebGL dependency
- **18 native tools** (open apps, shell commands, system control)
- **Voice pipeline** — Push-to-talk (Cmd+Shift+J), Whisper STT, macOS TTS
- **Morning briefing** — Aggregated context on launch
- **Cron scheduler** — 7 built-in jobs + custom natural language creation
- **SQLite local-first** — 11 tables, offline capable

**What You Should Steal:**
1. **Canvas2D approach** — Lighter than Three.js for basic 3D visualization
2. **Global shortcut system** — Cmd+Shift+J for voice activation
3. **Morning briefing pattern** — Context aggregation (tasks + calendar + email + weather)
4. **Tool execution loop** — Claude primary + OpenAI fallback, multi-step iterations
5. **Action parser** — Intercept AI responses and execute embedded commands

**Implementation Path:**
```rust
// Add to ClawOS agentd
#[tauri::command]
async fn execute_tool_chain(
    tools: Vec<ToolCall>,
    max_iterations: u32,
) -> Result<ToolResult, Error> {
    // Multi-step tool execution with Claude tool calling
    // Fallback to OpenAI if Claude errors
}

// Global shortcut handler
cmd + shift + j => activate_voice_mode()
```

---

### 4. **aguscruiz/voiceorb** (7⭐)
**Stack:** Three.js + Web Audio API + Custom GLSL shaders

**What Makes It Special:**
- **Pure proof-of-concept** — perfect reference code
- **4 visual states** — Idle, Listening, Thinking, Speaking
- **Real-time audio reactivity** — FFT analysis, 256 samples
- **Custom GLSL shaders** — Fresnel effects, Perlin noise displacement
- **Frequency-based color mixing** — Audio drives both color and displacement

**What You Should Steal:**
1. **GLSL shader structure** — Vertex + fragment shaders for organic orb
2. **State transition animations** — Smooth color/intensity interpolation
3. **Audio analysis approach** — Focus on mid-range frequencies (10-40 bins) for voice
4. **Perlin noise displacement** — For natural, breathing-like movement

**Implementation Path:**
```glsl
// Vertex shader for organic displacement
uniform float uAudioLevel;
uniform float uTime;

void main() {
    vec3 pos = position;
    float noise = snoise(pos * 2.0 + uTime * 0.5);
    pos += normal * noise * uAudioLevel * 0.3;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
```

---

## 🥈 TIER 2: Architecture Inspiration

### 5. **vierisid/jarvis** (248⭐)
**Stack:** Bun + TypeScript + SQLite + Go sidecar

**What Makes It Special:**
- **Always-on daemon** — Not request/response, runs 24/7
- **Sidecar pattern** — One daemon, unlimited sidecars on any machine
- **Desktop awareness** — Screen capture every 5-10s, struggle detection
- **Multi-agent hierarchy** — 9 specialist roles with delegation
- **Goal pursuit (OKRs)** — Drill sergeant accountability
- **Voice with wake word** — openwakeword (ONNX), runs in-browser
- **Visual workflow builder** — 50+ nodes, n8n-style

**What You Should Steal:**
1. **Sidecar architecture** — Separate heavy daemon from lightweight agents
2. **Continuous awareness** — Screen capture + OCR + activity inference
3. **Multi-agent delegation** — AgentTaskManager with 9 specialist roles
4. **Goal pursuit system** — OKR hierarchy with morning planning/evening review
5. **Wake word implementation** — openwakeword ONNX model in browser

**Implementation Path:**
```rust
// ClawOS sidecar architecture
pub struct Sidecar {
    machine_name: String,
    capabilities: Vec<Capability>, // desktop, browser, terminal, filesystem
    websocket: WebSocket,
}

// Wake word detection
pub struct WakeWordDetector {
    model: OrtModel, // ONNX runtime
    sensitivity: f32,
}
```

---

### 6. **oxide-lab/Oxide-Lab** (Tauri v2 + Candle)
**Stack:** Tauri v2 + Rust + Svelte 5 + Candle (HuggingFace)

**What Makes It Special:**
- **100% local inference** — Candle ML framework (Rust), no cloud
- **Multi-architecture** — Llama, Qwen, Mistral, DeepSeek, Yi
- **Hardware acceleration** — CPU, CUDA, Metal, Intel MKL, Apple Accelerate
- **Streaming text generation**
- **~10MB binary** — No Electron bloat

**What You Should Steal:**
1. **Candle integration** — Rust-native ML inference (alternative to Ollama)
2. **Hardware detection** — CPU vs CUDA vs Metal fallback
3. **GGUF/SafeTensors loading** — Direct model loading without Python

**Implementation Path:**
```rust
// Alternative to Ollama for model inference
use candle_core::{Device, Tensor};
use candle_transformers::models::qwen::Model;

pub struct LocalInference {
    model: Model,
    device: Device, // CUDA if available, else Metal, else CPU
}
```

---

## 🥉 TIER 3: Competitors to Differentiate From

### 7. **Ollama Desktop App** (pierreportal/ollama-desktop)
**Stars:** Growing | **Stack:** Tauri + React + TypeScript

**What It Does:**
- Lightweight ChatGPT clone for Ollama
- Basic chat interface

**Why ClawOS Is Better:**
- Ollama Desktop is just a chat UI
- ClawOS has workflows, memory, voice, policy, A2A federation
- Position: "Ollama runs models. ClawOS runs agents."

---

### 8. **ChatShell Desktop** (chatshellapp/chatshell-desktop)
**Stars:** 11⭐ | **Stack:** Rust + Tauri

**What It Does:**
- Terminal-integrated AI
- 73% Rust backend

**Why ClawOS Is Better:**
- ChatShell is terminal-centric
- ClawOS is GUI-first with visual workflows
- Position: "ChatShell augments your terminal. ClawOS augments your life."

---

## 📋 Implementation Priority List

### IMMEDIATE (Week 1-2)

1. **Orb Visualization** (`voiceorb` + `openclaw-jarvis-ui`)
   - Port Three.js orb to ClawOS dashboard
   - 4 states: idle/listening/thinking/responding
   - Audio reactivity with Web Audio API

2. **Theme System** (`openclaw-jarvis-ui`)
   - 6-color HSL palette
   - Persist in localStorage
   - Apply to dashboard + orb

3. **Global Shortcut** (`jarvis-ai-assistant`)
   - Cmd/Ctrl+Shift+J for voice
   - System tray integration
   - Tauri globalShortcut API

### SHORT-TERM (Month 1)

4. **Voice Pipeline** (`openclaw-jarvis-ui` + `jarvis-ai-assistant`)
   - Edge TTS integration (300+ voices)
   - Piper TTS local fallback
   - Whisper STT

5. **Personality Presets** (`jarvis-ai-assistant` + `vierisid/jarvis`)
   - JARVIS, FRIDAY, EDITH, KAREN templates
   - SOUL.md generation
   - Voice selection per personality

6. **Morning Briefing** (`jarvis-ai-assistant`)
   - Context aggregation
   - Scheduled workflow
   - Voice delivery option

### MEDIUM-TERM (Month 2-3)

7. **Semantic Tool Discovery** (`OpenPawz`)
   - Embed skills/workflows
   - Cosine similarity search
   - Dynamic tool loading

8. **Command Risk Classifier** (`OpenPawz`)
   - 30+ danger patterns
   - 5 risk levels
   - Color-coded approval UI

9. **Sidecar Architecture** (`vierisid/jarvis`)
   - Separate daemon from agents
   - Multi-machine support
   - Desktop awareness via sidecar

### LONG-TERM (Month 4+)

10. **Wake Word Detection** (`vierisid/jarvis`)
    - openwakeword ONNX
    - Browser/WebView runtime
    - "Hey JARVIS" activation

11. **Goal Pursuit System** (`vierisid/jarvis`)
    - OKR hierarchy
    - Daily planning/review
    - Accountability automation

12. **Visual Workflow Builder** (`vierisid/jarvis` + `OpenPawz`)
    - React Flow / @xyflow/react
    - 50+ node types
    - Natural language workflow creation

---

## 🎯 Key Architectural Decisions

### Orb Visualization
**Recommended approach:** Three.js + React Three Fiber
- `voiceorb` for GLSL shaders
- `openclaw-jarvis-ui` for state management
- Custom fresnel glow + Perlin noise

### Desktop App
**Recommended:** Tauri v2 (already decided, this confirms)
- `OpenPawz`, `jarvis-ai-assistant`, `Oxide-Lab` all use it
- Smaller bundle than Electron
- Rust backend matches ClawOS services

### Voice
**Hybrid approach:**
- **Cloud:** Edge TTS (free, 300+ voices) via `openclaw-jarvis-ui`
- **Local:** Piper TTS via existing ClawOS integration
- **STT:** Whisper (local) via existing ClawOS integration
- **Wake word:** openwakeword (ONNX) via `vierisid/jarvis`

### Memory
**Already strong in ClawOS**, but could add:
- Knowledge graph visualization from `vierisid/jarvis` (Engram-style)
- Morning briefing context aggregation from `jarvis-ai-assistant`

### Security
**Command risk classifier** from `OpenPawz`:
- Already have policyd in ClawOS
- Add pattern-based risk scoring
- UI for approval modals

---

## 🚀 Quick Win Implementations

### 1. JARVIS Orb (2-3 days)
```bash
# Based on openclaw-jarvis-ui + voiceorb
cd clawos/dashboard
npm install three @react-three/fiber
# Port orb component
# Add to main dashboard view
```

### 2. Theme System (1 day)
```typescript
// From openclaw-jarvis-ui
const themes = {
  jarvis: { hue: 200, accent: '#00b4ff' }, // cyan
  friday: { hue: 280, accent: '#a855f7' }, // purple
  edith: { hue: 160, accent: '#10b981' }, // emerald
};
```

### 3. Global Shortcut (1 day)
```rust
// Tauri v2 global shortcut
use tauri::GlobalShortcutManager;

fn setup_shortcut(app: &mut App) {
    app.global_shortcut_manager()
        .register("Cmd+Shift+J", || activate_voice());
}
```

### 4. Personality Presets (2-3 days)
```yaml
# SOUL.md templates
# jarvis.yaml
name: JARVIS
voice: en-GB-RyanNeural
greeting: "Good {time_of_day}, sir. JARVIS online."
traits: [efficient, witty, loyal, british]

# friday.yaml  
name: FRIDAY
voice: en-US-AriaNeural
greeting: "Systems online. How can I assist?"
traits: [direct, efficient, task-focused]
```

---

## 🎓 Lessons from the Research

### What's Working in the Market:
1. **Tauri v2** is the dominant choice for AI desktop apps
2. **Three.js orbs** are the visual signature of "JARVIS-like" experiences
3. **Edge TTS** is the free alternative to ElevenLabs
4. **openWakeWord** is the standard for local wake word detection
5. **Canvas2D** can do impressive 3D without WebGL overhead

### What's Missing (Your Opportunity):
1. **Hardware-aware provisioning** — Nobody else does this!
2. **14-layer memory** — ClawOS is ahead here
3. **Policy engine** — OpenPawz has something similar, but ClawOS Merkle chaining is unique
4. **Workflow compilation** — Conductor Protocol from OpenPawz could be adapted
5. **Bootable ISO** — Ultimate "turn any PC into JARVIS" experience

### Competitive Positioning:
- **vs OpenPawz:** They have MCP bridge and n8n integration — ClawOS has hardware detection and 14-layer memory
- **vs vierisid/jarvis:** They have sidecars and desktop awareness — ClawOS has policy governance and framework ecosystem
- **vs jarvis-ai-assistant:** They have Canvas2D sphere — ClawOS can use Three.js for better visuals
- **vs OpenWebUI/Dify:** Not even comparable — they're chat interfaces, ClawOS is an OS

---

**Bottom Line:** You have the best foundation. These repos show you exactly how to build the "JARVIS experience" on top. The orb visualization, personality system, and voice activation are all well-trodden paths now — the innovation is combining them with your hardware-aware, policy-governed, memory-rich architecture.
