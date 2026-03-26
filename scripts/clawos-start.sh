#!/usr/bin/env bash
# ClawOS ordered startup — called by clawos.service ExecStart
# Starts all 9 services in dependency order, waiting for each to be healthy
# before proceeding to the next.

set -uo pipefail

CLAWOS_HOME="${CLAWOS_HOME:-$HOME/clawos}"
LOG_DIR="$CLAWOS_HOME/logs"
mkdir -p "$LOG_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }
info() { echo -e "  ${YELLOW}→${NC} $*"; }

# Wait for an HTTP health endpoint to respond, or just a process to be running
# Usage: wait_healthy <unit> <port|-> [timeout_secs]
wait_healthy() {
    local unit="$1"
    local port="$2"
    local timeout="${3:-15}"

    if [ "$port" = "-" ]; then
        # No HTTP check — just wait for process to be active
        for i in $(seq 1 $timeout); do
            systemctl --user is-active --quiet "$unit" && return 0
            sleep 1
        done
    else
        for i in $(seq 1 $timeout); do
            if curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
                return 0
            fi
            sleep 1
        done
    fi

    return 1
}

start_service() {
    local unit="$1"
    local port="${2:--}"
    local label="${3:-$unit}"
    local timeout="${4:-15}"

    info "Starting $label..."

    # Don't fail if already running
    systemctl --user start "$unit" 2>/dev/null || true

    if wait_healthy "$unit" "$port" "$timeout"; then
        ok "$label"
    else
        fail "$label failed to become healthy (port $port)"
        echo "  Check logs: journalctl --user -u $unit -n 30"
        # Non-optional services abort the boot
        if [[ "$unit" =~ ^clawos-(policyd|memd|modeld|toolbridge|agentd|clawd) ]]; then
            echo ""
            echo "  Critical service failed. Stopping ClawOS."
            bash "$CLAWOS_HOME/scripts/clawos-stop.sh" 2>/dev/null || true
            exit 1
        fi
    fi
}

echo ""
echo -e "${BOLD}Starting ClawOS...${NC}"
echo ""

# Boot order (matches architecture spec):
# 1. policyd  — permission gate must be first
# 2. memd     — memory layer
# 3. modeld   — model routing
# 4. toolbridge — tool execution boundary (no HTTP health, check process)
# 5. agentd   — task queue
# 6. voiced   — voice pipeline (optional, soft failure)
# 7. clawd    — orchestration
# 8. dashd    — dashboard UI
# 9. gatewayd — WhatsApp bridge (optional, soft failure)

start_service "clawos-policyd"   "7074" "policyd   (permission gate)"    15
start_service "clawos-memd"      "7073" "memd      (memory manager)"     15
start_service "clawos-modeld"    "7075" "modeld    (model routing)"      20
start_service "clawos-toolbridge" "-"   "toolbridge (tool execution)"    10
start_service "clawos-agentd"    "7072" "agentd    (task queue)"         15
start_service "clawos-voiced"    "-"    "voiced    (voice pipeline)"     10   # soft fail
start_service "clawos-clawd"     "7071" "clawd     (orchestration)"      15
start_service "clawos-dashd"     "7070" "dashd     (dashboard)"          15
start_service "clawos-gatewayd"  "-"    "gatewayd  (WhatsApp bridge)"    15   # soft fail

echo ""
echo -e "${GREEN}${BOLD}ClawOS is running.${NC}"
echo ""
echo "  Dashboard: http://localhost:7070"
echo "  Chat:      clawos"
echo "  Status:    clawos status"
echo ""
