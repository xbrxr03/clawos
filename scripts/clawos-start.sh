#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ordered startup - called by clawos.service ExecStart
# Launches all services as background processes in dependency order.
# clawos.service is the supervisor - all child processes live under it.

set -uo pipefail

CLAWOS_HOME="${CLAWOS_HOME:-$HOME/.clawos-runtime}"
LOG_DIR="$CLAWOS_HOME/logs"
PIDS_DIR="$CLAWOS_HOME/run"
mkdir -p "$LOG_DIR" "$PIDS_DIR"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}OK${NC} $*"; }
fail() { echo -e "  ${RED}XX${NC} $*"; }
info() { echo -e "  ${YELLOW}->${NC} $*"; }

start_svc() {
    local name="$1"
    local script="$2"
    local wait_secs="${3:-2}"
    local pidfile="$PIDS_DIR/$name.pid"

    info "Starting $name..."

    if [ -f "$pidfile" ]; then
        kill "$(cat "$pidfile")" 2>/dev/null || true
        rm -f "$pidfile"
    fi

    PYTHONPATH="$CLAWOS_HOME" \
    CLAWOS_HOME="$CLAWOS_HOME" \
    CLAWOS_SERVICE="$name" \
    OLLAMA_HOST="http://localhost:11434" \
    "$CLAWOS_HOME/venv/bin/python3" "$CLAWOS_HOME/$script" \
        >> "$LOG_DIR/$name.log" 2>&1 &

    local pid=$!
    echo "$pid" > "$pidfile"

    sleep "$wait_secs"
    if kill -0 "$pid" 2>/dev/null; then
        ok "$name (pid $pid)"
    else
        fail "$name exited - check $LOG_DIR/$name.log"
        if [[ "$name" =~ ^(policyd|memd|modeld|agentd|clawd)$ ]]; then
            echo "  Critical service failed. Aborting."
            exit 1
        fi
    fi
}

start_gatewayd() {
    local name="gatewayd"
    local pidfile="$PIDS_DIR/$name.pid"
    info "Starting $name..."
    [ -f "$pidfile" ] && kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f "$pidfile"

    openclaw gateway --allow-unconfigured \
        >> "$LOG_DIR/$name.log" 2>&1 &

    local pid=$!
    echo "$pid" > "$pidfile"
    sleep 2
    kill -0 "$pid" 2>/dev/null && ok "$name (pid $pid)" || fail "$name exited - check $LOG_DIR/$name.log"
}

echo ""
echo -e "${BOLD}Starting ClawOS...${NC}"
echo ""

start_svc  "policyd"    "services/policyd/service.py"    2
start_svc  "memd"       "services/memd/service.py"       2
start_svc  "modeld"     "services/modeld/service.py"     2
start_svc  "toolbridge" "services/toolbridge/service.py" 2
start_svc  "agentd"     "services/agentd/service.py"     2
start_svc  "voiced"     "services/voiced/service.py"     1
start_svc  "clawd"      "services/clawd/service.py"      2
start_svc  "dashd"      "services/dashd/main.py"         2
start_gatewayd

echo ""
echo -e "${GREEN}${BOLD}ClawOS is running.${NC}"
echo ""
echo "  Dashboard: http://localhost:7070"
echo "  Chat:      clawos"
echo "  Status:    clawos status"
echo ""

# Hold process open so clawos.service (Type=simple) stays active
# All child PIDs are tracked in ~/clawos/run/*.pid
wait
