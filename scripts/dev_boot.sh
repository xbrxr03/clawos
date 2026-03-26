#!/bin/bash
# ClawOS dev_boot.sh — start all services for development
# Usage: bash scripts/dev_boot.sh [--no-dashboard] [--no-voice]

set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
export PYTHONPATH="$ROOT"

# ── Detect profile from clawos.yaml, fall back to env, fall back to balanced ──
if [ -z "${CLAWOS_PROFILE:-}" ]; then
  YAML="$HOME/clawos/config/clawos.yaml"
  if [ -f "$YAML" ]; then
    DETECTED=$(grep '_profile:' "$YAML" 2>/dev/null | head -1 | awk '{print $2}' | tr -d '"'"'" )
    CLAWOS_PROFILE="${DETECTED:-balanced}"
  else
    CLAWOS_PROFILE="balanced"
  fi
fi
export CLAWOS_PROFILE

PIDS=()

cleanup() {
  echo ""
  echo "  Stopping ClawOS services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup SIGINT SIGTERM

log() { echo "  [boot] $*"; }

port_in_use() {
  local port=$1
  # Try ss first (faster), fall back to netstat, fall back to /dev/tcp
  if command -v ss &>/dev/null; then
    ss -tnlp 2>/dev/null | grep -q ":${port} " && return 0
  elif command -v netstat &>/dev/null; then
    netstat -tnlp 2>/dev/null | grep -q ":${port} " && return 0
  else
    (echo > /dev/tcp/127.0.0.1/$port) 2>/dev/null && return 0
  fi
  return 1
}

log "ClawOS dev boot — profile: $CLAWOS_PROFILE"

# 1. Check Ollama
if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  log "WARNING: Ollama not running. Start it: ollama serve"
fi

# 2. policyd
log "Starting policyd..."
python3 -m services.policyd.main &
PIDS+=($!)
sleep 0.5

# 3. memd
log "Starting memd..."
python3 -m services.memd.main &
PIDS+=($!)
sleep 0.5

# 4. modeld
log "Starting modeld..."
python3 -m services.modeld.main &
PIDS+=($!)
sleep 0.5

# 5. agentd
log "Starting agentd..."
python3 -m services.agentd.main &
PIDS+=($!)
sleep 0.5

# 6. dashd — only if port 7070 is free and --no-dashboard not passed
if [[ " $* " =~ " --no-dashboard " ]]; then
  log "Skipping dashd (--no-dashboard)"
elif port_in_use 7070; then
  log "Dashboard already running on :7070 — skipping dashd"
else
  log "Starting dashd at http://localhost:7070 ..."
  python3 -m services.dashd.main &
  PIDS+=($!)
  sleep 0.5
fi

log ""
log "╔══════════════════════════════════════╗"
log "║   ClawOS is running (dev mode)       ║"
log "║   Dashboard: http://localhost:7070   ║"
log "║   Chat:      clawos                  ║"
log "║   Ctrl+C to stop all services        ║"
log "╚══════════════════════════════════════╝"
log ""

wait
