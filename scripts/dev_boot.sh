#!/bin/bash
# ClawOS dev_boot.sh — start all services for development
# Usage: bash scripts/dev_boot.sh [--no-dashboard] [--no-voice]

set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
export PYTHONPATH="$ROOT"
export CLAWOS_PROFILE="${CLAWOS_PROFILE:-balanced}"

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

# 6. dashd (unless --no-dashboard)
if [[ ! " $* " =~ " --no-dashboard " ]]; then
  log "Starting dashd at http://localhost:7070 ..."
  python3 -m services.dashd.main &
  PIDS+=($!)
  sleep 0.5
fi

log ""
log "╔══════════════════════════════════════╗"
log "║   ClawOS is running (dev mode)       ║"
log "║   Dashboard: http://localhost:7070   ║"
log "║   Chat:      python3 -m clients.cli.repl ║"
log "║   Ctrl+C to stop all services        ║"
log "╚══════════════════════════════════════╝"
log ""

wait
