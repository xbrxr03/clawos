"""
ClawOS Core Constants
=====================
Single source of truth for version, paths, service names, ports.
Import from here — never hardcode these elsewhere.
"""
from pathlib import Path

# ── Version ───────────────────────────────────────────────────────────────────
VERSION   = "0.1.0"
CODENAME  = "Prototype"
VERSION_FULL = f"{VERSION} {CODENAME}"

# ── Paths ─────────────────────────────────────────────────────────────────────
CLAWOS_DIR       = Path.home() / "clawos"
CONFIG_DIR       = CLAWOS_DIR / "config"
LOGS_DIR         = CLAWOS_DIR / "logs"
MEMORY_DIR       = CLAWOS_DIR / "memory"
WORKSPACE_DIR    = CLAWOS_DIR / "workspace"
VOICE_DIR        = CLAWOS_DIR / "voice"
SERVICES_DIR     = Path(__file__).parent.parent  # clawos_v3/

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

OLLAMA_HOST   = "http://localhost:11434"

# ── Models ────────────────────────────────────────────────────────────────────
DEFAULT_MODEL        = "gemma3:4b"
DEFAULT_EMBED_MODEL  = "nomic-embed-text"

MODEL_PROFILES = {
    "lowram":      {"chat": "gemma3:4b",   "ctx": 2048, "voice": False},
    "balanced":    {"chat": "gemma3:4b",   "ctx": 4096, "voice": True},
    "performance": {"chat": "gemma3:12b",  "ctx": 8192, "voice": True},
}

# ── Agent loop ────────────────────────────────────────────────────────────────
MAX_ITERATIONS   = 8
MAX_HISTORY      = 12
DEFAULT_WORKSPACE = "jarvis_default"

# ── Audio ─────────────────────────────────────────────────────────────────────
RECORD_RATE      = 44100   # Hz — ALC294 native rate via pipewire
WHISPER_RATE     = 16000   # Hz — Whisper expected rate (resamples from WAV)
AUDIO_CHANNELS   = 1
AUDIO_CHUNK      = 2048
SILENCE_RMS      = 300
SILENCE_SECS     = 1.8
MAX_RECORD_SECS  = 30
WHISPER_MODEL    = "base"

# ── Policy ────────────────────────────────────────────────────────────────────
APPROVAL_TIMEOUT_S  = 120
TOOL_SCORE_QUEUE    = 50   # risk score >= this → queue for human approval

# ── Ensure critical dirs exist ────────────────────────────────────────────────
def ensure_dirs():
    for d in [CONFIG_DIR, LOGS_DIR, MEMORY_DIR, WORKSPACE_DIR, VOICE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
