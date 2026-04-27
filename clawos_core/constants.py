# SPDX-License-Identifier: AGPL-3.0-or-later
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
from clawos_core.platform import launch_agents_dir, platform_key

# ── Version ───────────────────────────────────────────────────────────────────
VERSION      = "0.1.0"
CODENAME     = "Nexus"
VERSION_FULL = f"{VERSION} {CODENAME}"

# ── Paths ─────────────────────────────────────────────────────────────────────
CLAWOS_DIR       = Path(os.environ.get("CLAWOS_DIR", str(Path.home() / "clawos"))).expanduser()
CONFIG_DIR       = CLAWOS_DIR / "config"
LOGS_DIR         = CLAWOS_DIR / "logs"
MEMORY_DIR       = CLAWOS_DIR / "memory"
WORKSPACE_DIR    = CLAWOS_DIR / "workspace"
VOICE_DIR        = CLAWOS_DIR / "voice"
SERVICES_DIR     = Path(__file__).parent.parent
RUNTIME_PLATFORM = platform_key()
LAUNCH_AGENTS_DIR = launch_agents_dir()
SYSTEMD_USER_DIR  = Path.home() / ".config" / "systemd" / "user"

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
OTEL_JSONL       = LOGS_DIR / "otel.jsonl"
TRACES_JSONL     = LOGS_DIR / "traces.jsonl"
SETUP_STATE_JSON = CONFIG_DIR / "setup_state.json"
PRESENCE_STATE_JSON = CONFIG_DIR / "presence_state.json"
SUPPORT_DIR      = CLAWOS_DIR / "support"

# Voice models
PIPER_MODEL      = VOICE_DIR / "en_US-lessac-medium.onnx"
PIPER_CONFIG     = VOICE_DIR / "en_US-lessac-medium.onnx.json"

# ── Service names ─────────────────────────────────────────────────────────────
SERVICES = [
    "policyd",
    "metricd",
    "memd",
    "modeld",
    "toolbridge",
    "agentd",
    "voiced",
    "clawd",
    "dashd",
    "a2ad",
    "setupd",
    "picoclawd",
]

# ── Ports ─────────────────────────────────────────────────────────────────────
PORT_DASHD      = 7070
PORT_CLAWD      = 7071
PORT_AGENTD     = 7072
PORT_MEMD       = 7073
PORT_POLICYD    = 7074
PORT_MODELD     = 7075
PORT_METRICD    = 7076
PORT_MCPD       = 7077
PORT_OBSERVD    = 7078
PORT_VOICED     = 7079
PORT_DESKTOPD   = 7080
PORT_AGENTD_V2  = 7081
PORT_A2AD       = 7083
PORT_SETUPD     = 7084
PORT_PICOCLAWD  = 18800
PORT_OLLAMA     = 11434

# Legacy aliases used by older code
A2A_PORT_NEXUS  = PORT_A2AD
A2A_PORT_RAGD   = 7082

# Read from environment
OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

# ── Models ────────────────────────────────────────────────────────────────────
# Four canonical models. Nothing else.
DEFAULT_MODEL       = os.environ.get("CLAWOS_MODEL", "gemma3:4b")
DEFAULT_EMBED_MODEL = "nomic-embed-text"

MODEL_PROFILES = {
    # Tier A: CPU-only / ≤8GB RAM — gemma3:4b is the best CPU model at this tier
    "lowram":      {"chat": "gemma3:4b",    "ctx": 2048,  "voice": False, "tier": "A"},
    # Tier B: x86 8-16GB — gemma3:4b still best for CPU, qwen2.5:7b with GPU
    "balanced":    {"chat": "gemma3:4b",    "ctx": 4096,  "voice": True,  "tier": "B"},
    # Tier C: x86 16-32GB with GPU
    "performance": {"chat": "qwen2.5:7b",   "ctx": 8192,  "voice": True,  "tier": "C"},
    # Tier D: 32GB+ RAM + GPU ≥10GB VRAM
    "gaming":      {"chat": "qwen2.5:7b",   "ctx": 16384, "voice": True,  "tier": "D",
                    "max_parallel": 3, "vram_per_agent_gb": 5.5},
}

# ── Agent loop ────────────────────────────────────────────────────────────────
MAX_ITERATIONS    = 8
MAX_HISTORY       = 12
DEFAULT_WORKSPACE = "nexus_default"

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

# ── Tier D multi-agent ────────────────────────────────────────────────────────
TIER_D_MAX_PARALLEL    = 3
TIER_D_VRAM_PER_AGENT  = 5.5   # GB reserved per agent session
TIER_D_VRAM_RESERVE    = 1.0   # GB always kept free for system

# ── PicoClaw (Tier A) ────────────────────────────────────────────────────────
PICOCLAW_GITHUB     = "sipeed/picoclaw"
PICOCLAW_VERSION    = "v0.2.4"
PICOCLAW_HTTP_TIMEOUT = 300

# ── A2A Protocol ─────────────────────────────────────────────────────────────
A2A_MDNS_SERVICE    = "_clawos._tcp.local"
A2A_DISCOVERY_SECS  = 60
A2A_BEARER_TOKEN_ENV = "CLAWOS_A2A_TOKEN"

# ── metricd ───────────────────────────────────────────────────────────────────
DEFAULT_DAILY_TOKEN_BUDGET = 100_000   # per workspace; 0 = unlimited

# ── Ensure critical dirs exist ────────────────────────────────────────────────
def ensure_dirs():
    for d in [CONFIG_DIR, LOGS_DIR, MEMORY_DIR, WORKSPACE_DIR, VOICE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
