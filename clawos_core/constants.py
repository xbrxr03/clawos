"""
ClawOS Core Constants
=====================
Single source of truth for version, paths, service names, ports.
Import from here — never hardcode these elsewhere.

Environment overrides:
  OLLAMA_HOST   — point at a remote Ollama server (e.g. http://192.168.1.50:11434)
  CLAWOS_MODEL  — override the default chat model
"""
import os
from pathlib import Path

# ── Version ───────────────────────────────────────────────────────────────────
VERSION      = "0.1.0"
CODENAME     = "Prototype"
VERSION_FULL = f"{VERSION} {CODENAME}"

# ── Paths ─────────────────────────────────────────────────────────────────────
CLAWOS_DIR       = Path.home() / "clawos"
CONFIG_DIR       = CLAWOS_DIR / "config"
LOGS_DIR         = CLAWOS_DIR / "logs"
MEMORY_DIR       = CLAWOS_DIR / "memory"
WORKSPACE_DIR    = CLAWOS_DIR / "workspace"
VOICE_DIR        = CLAWOS_DIR / "voice"
SERVICES_DIR     = Path(__file__).parent.parent

# Runtime data (systemd standard locations for a real install)
VAR_LIB_DIR      = Path("/var/lib/clawos")
VAR_LOG_DIR      = Path("/var/log/clawos")
ETC_DIR          = Path("/etc/clawos")

# Audit
AUDIT_JSONL      = LOGS_DIR / "audit.jsonl"
POLICYD_DB       = CONFIG_DIR / "policyd.db"
MEMORY_FTS_DB    = MEMORY_DIR / "fts.db"
HARDWARE_JSON    = CONFIG_DIR / "hardware.json"
CLAWOS_CONFIG    = CONFIG_DIR / "clawos.yaml"

# Voice models
PIPER_MODEL      = VOICE_DIR / "en_US-lessac-medium.onnx"
PIPER_CONFIG     = VOICE_DIR / "en_US-lessac-medium.onnx.json"

# ── Service names ─────────────────────────────────────────────────────────────
SERVICES = [
    "policyd",
    "memd",
    "modeld",
    "toolbridge",
    "agentd",
    "voiced",
    "clawd",
    "dashd",
    "gatewayd",
]

# ── Ports ─────────────────────────────────────────────────────────────────────
PORT_DASHD    = 7070
PORT_CLAWD    = 7071
PORT_AGENTD   = 7072
PORT_MEMD     = 7073
PORT_POLICYD  = 7074
PORT_MODELD   = 7075
PORT_GATEWAYD = 7076
PORT_OLLAMA   = 11434

# Read from environment — allows pointing at a remote Ollama server
# Example: export OLLAMA_HOST=http://192.168.1.50:11434
OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

# ── Models ────────────────────────────────────────────────────────────────────
# Four models. Nothing else.
#   basic:    qwen2.5:1.5b  — simple Q&A, greetings, acks (ARM/CPU-only friendly)
#   standard: qwen2.5:3b    — writing, summarization, general tasks
#   full:     qwen2.5:7b    — tools, code, RAG, complex reasoning (GPU recommended)
#   openclaw: kimi-k2.5:cloud — OpenClaw agent sessions (cloud, 256k ctx)
DEFAULT_MODEL       = os.environ.get("CLAWOS_MODEL", "qwen2.5:7b")
DEFAULT_EMBED_MODEL = "nomic-embed-text"

MODEL_PROFILES = {
    # Tier A: ARM / CPU-only / low RAM (RPi 5, 8GB mini PCs)
    # qwen2.5:1.5b runs at ~3-5 tok/s on RPi 5 — responsive
    "lowram":      {"chat": "qwen2.5:1.5b", "ctx": 2048, "voice": False},
    # Tier B: x86 8-16GB (laptops, mini PCs with iGPU)
    "balanced":    {"chat": "qwen2.5:3b",   "ctx": 4096, "voice": True},
    # Tier C: x86 16GB+ with discrete GPU
    "performance": {"chat": "qwen2.5:7b",   "ctx": 8192, "voice": True},
}

# ── Agent loop ────────────────────────────────────────────────────────────────
MAX_ITERATIONS    = 8
MAX_HISTORY       = 12
DEFAULT_WORKSPACE = "nexus_default"   # renamed from jarvis_default

# ── Audio ─────────────────────────────────────────────────────────────────────
RECORD_RATE      = 44100
WHISPER_RATE     = 16000
AUDIO_CHANNELS   = 1
AUDIO_CHUNK      = 2048
SILENCE_RMS      = 300
SILENCE_SECS     = 1.8
MAX_RECORD_SECS  = 30
WHISPER_MODEL    = "base"

# ── Policy ────────────────────────────────────────────────────────────────────
APPROVAL_TIMEOUT_S  = 120
TOOL_SCORE_QUEUE    = 50

# ── Ensure critical dirs exist ────────────────────────────────────────────────
def ensure_dirs():
    for d in [CONFIG_DIR, LOGS_DIR, MEMORY_DIR, WORKSPACE_DIR, VOICE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
