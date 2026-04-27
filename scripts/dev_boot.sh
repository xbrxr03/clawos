#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS dev_boot.sh — start all services for development
# Usage: bash scripts/dev_boot.sh [--no-dashboard] [--no-voice] [--health-check]

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
FAILED_SERVICES=()

# Colors for output
BOLD="\033[1m"
RESET="\033[0m"
G="\033[38;5;84m"
Y="\033[38;5;220m"
R="\033[38;5;203m"

cleanup() {
  echo ""
  echo "  Stopping ClawOS services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup SIGINT SIGTERM

log() { echo -e "  ${BOLD}[boot]${RESET} $*"; }
ok() { echo -e "  ${G}✓${RESET} $*"; }
warn() { echo -e "  ${Y}⚠${RESET} $*"; }
fail() { echo -e "  ${R}✗${RESET} $*"; }

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

# Check if a service is healthy by checking its log output
wait_for_service() {
  local service=$1
  local max_wait=${2:-10}
  local pid=$3
  
  for i in $(seq 1 $max_wait); do
    # Check if process is still running
    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi
    sleep 0.5
  done
  return 0
}

# Start a service with error handling
start_service() {
  local service=$1
  local module=$2
  
  log "Starting ${service}..."
  
  # Check if module exists
  if ! python3 -c "import ${module}" 2>/dev/null; then
    warn "Module ${module} not found, skipping ${service}"
    FAILED_SERVICES+=("$service")
    return 1
  fi
  
  python3 -m ${module}.main &
  local pid=$!
  PIDS+=($pid)
  
  if wait_for_service "$service" 5 "$pid"; then
    if kill -0 "$pid" 2>/dev/null; then
      ok "${service} started (pid: $pid)"
      return 0
    else
      fail "${service} failed to start"
      FAILED_SERVICES+=("$service")
      return 1
    fi
  else
    fail "${service} timed out or crashed"
    FAILED_SERVICES+=("$service")
    return 1
  fi
}

log "ClawOS dev boot — profile: $CLAWOS_PROFILE"

# 1. Check Ollama
if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  warn "Ollama not running. Start it: ollama serve"
else
  ok "Ollama is running"
fi

# 2. Start core services
start_service "policyd" "services.policyd"
sleep 0.3

start_service "memd" "services.memd"
sleep 0.3

start_service "modeld" "services.modeld"
sleep 0.3

start_service "agentd" "services.agentd"
sleep 0.3

# 3. Optional services
if [[ " $* " =~ " --no-dashboard " ]]; then
  log "Skipping dashd (--no-dashboard)"
elif port_in_use 7070; then
  ok "Dashboard already running on :7070"
else
  start_service "dashd" "services.dashd"
fi

# 4. Optional: clawd (command execution)
if ! [[ " $* " =~ " --no-clawd " ]]; then
  start_service "clawd" "services.clawd" || true
fi

# 5. Health check summary
echo ""
log "╔══════════════════════════════════════╗"
log "║   ClawOS is running (dev mode)       ║"
log "║   Dashboard: http://localhost:7070   ║"
log "║   Chat:      clawos                  ║"
log "║   Ctrl+C to stop all services        ║"
log "╚══════════════════════════════════════╝"

if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
  echo ""
  warn "Some services failed to start:"
  for svc in "${FAILED_SERVICES[@]}"; do
    echo "    - $svc"
  done
  echo ""
  log "Check logs for details: tail -f ~/.clawos-runtime/logs/*.log"
fi

log ""

wait
